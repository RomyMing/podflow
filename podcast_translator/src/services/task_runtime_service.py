import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from redis.exceptions import RedisError

from src.core.exceptions import ResourceNotFoundError, StaleWorkerGenerationError
from src.core.redis import build_task_progress_payload, get_redis_async, publish_task_progress_message
from src.models.segment import Segment
from src.models.speaker import Speaker
from src.models.task import Task
from src.models.task_stage_run import TaskStageRun
from src.models.user import User
from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.progress import get_overall_progress, get_stage_progress, get_stage_progress_from_overall
from src.pipeline.speaker_gender import ensure_mixed_fallback_genders
from src.repositories.task_repo import TaskRepository
from src.repositories.user_repo import UserRepository
from src.config import settings
from src.services.artifact_cleanup_service import ArtifactCleanupService
from src.services.eta_service import estimate_task_eta_seconds
from src.services.storage_service import StorageService

TERMINAL_STATUSES = {"completed", "failed"}
BLOCKED_STATUSES = {"completed", "failed", "paused"}
MAX_TASK_ERROR_MESSAGE_LENGTH = 1000
logger = logging.getLogger(__name__)


def truncate_task_error_message(error_message: str | None) -> str | None:
    if error_message is None:
        return None

    if len(error_message) <= MAX_TASK_ERROR_MESSAGE_LENGTH:
        return error_message

    suffix = "\n...[truncated]"
    keep_length = MAX_TASK_ERROR_MESSAGE_LENGTH - len(suffix)
    return f"{error_message[:keep_length]}{suffix}"


class TaskRuntimeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_repo = TaskRepository(Task, db)
        self.user_repo = UserRepository(User, db)

    async def _get_task_or_raise(self, task_id: uuid.UUID) -> Task:
        task = await self.task_repo.get(task_id)
        if task is None:
            raise ResourceNotFoundError("Task not found")
        return task

    async def _get_task_with_stage_runs_or_raise(self, task_id: uuid.UUID) -> Task:
        result = await self.db.execute(
            select(Task)
            .options(selectinload(Task.stage_runs))
            .where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise ResourceNotFoundError("Task not found")
        return task

    async def _get_task_for_update_or_raise(self, task_id: uuid.UUID) -> Task:
        result = await self.db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise ResourceNotFoundError("Task not found")
        return task

    @staticmethod
    def _assert_generation(task: Task, expected_generation: int | None) -> None:
        if expected_generation is None:
            return
        if task.run_generation != expected_generation:
            raise StaleWorkerGenerationError(
                f"Task {task.id} worker generation {expected_generation} was superseded by "
                f"generation {task.run_generation}."
            )

    def build_progress_payload(
        self,
        task: Task,
        *,
        event: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stage_progress_percent = None
        if task.current_stage:
            try:
                stage_progress_percent = get_stage_progress_from_overall(
                    TaskStage(task.current_stage),
                    task.progress_percent,
                )
            except ValueError:
                stage_progress_percent = None

        try:
            stage_runs = list(task.stage_runs or [])
        except Exception:
            stage_runs = []

        eta_seconds = estimate_task_eta_seconds(
            status=task.status,
            current_stage=task.current_stage,
            progress_percent=task.progress_percent,
            audio_duration=task.audio_duration,
            stage_runs=stage_runs,
        )

        payload = build_task_progress_payload(
            task_id=str(task.id),
            stage=task.current_stage,
            progress_percent=task.progress_percent,
            status=task.status,
            error_message=task.error_message,
            pause_reason_code=task.pause_reason_code,
            provider_error_code=task.provider_error_code,
            output_audio_url=task.output_audio_url,
            audio_duration=task.audio_duration,
            stage_progress_percent=stage_progress_percent,
            eta_seconds=eta_seconds,
            finished_at=task.finished_at,
            event=event,
        )
        if extra:
            payload.update({key: value for key, value in extra.items() if value is not None})
        return payload

    async def get_task_progress_payload_for_user(self, task_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        task = await self._get_task_with_stage_runs_or_raise(task_id)
        if task.user_id != user_id:
            raise ResourceNotFoundError("Task not found")
        return self.build_progress_payload(task, event="snapshot")

    async def get_task_snapshot(self, task_id: uuid.UUID) -> Task:
        return await self._get_task_or_raise(task_id)

    async def build_pipeline_context(self, task_id: uuid.UUID, source_audio_url: str) -> PipelineContext:
        task = await self._get_task_or_raise(task_id)
        config = task.config or {}
        ctx = PipelineContext(
            task_id=str(task_id),
            user_id=task.user_id,
            source_audio_url=source_audio_url or task.source_audio_url or "",
            source_language=config.get("source_language"),
            target_language=config.get("target_language") or "zh",
            config=config,
            output_audio_url=task.output_audio_url,
        )

        speakers = (
            await self.db.execute(
                select(Speaker)
                .where(Speaker.task_id == task_id)
                .order_by(Speaker.label)
            )
        ).scalars().all()
        speaker_by_uuid = {speaker.id: speaker for speaker in speakers}
        if speakers:
            ctx.speakers = [
                {
                    "id": speaker.label,
                    "label": speaker.label,
                    "ref_audio_url": speaker.reference_audio_url,
                    "voice_embedding_url": speaker.voice_embedding_url,
                    "gender": speaker.gender,
                    "pitch_hz": speaker.pitch_hz,
                    "voice_provider": speaker.voice_provider,
                    "voice_id": speaker.voice_id,
                    "voice_model": speaker.voice_model,
                    "enrollment_status": speaker.enrollment_status,
                    "fallback_reason": speaker.fallback_reason,
                }
                for speaker in speakers
            ]
            if ensure_mixed_fallback_genders(ctx.speakers):
                logger.info(
                    "Task %s: normalized restored two-speaker fallback genders.",
                    task_id,
                )

        segments = (
            await self.db.execute(
                select(Segment)
                .where(Segment.task_id == task_id)
                .order_by(Segment.start_time, Segment.end_time)
            )
        ).scalars().all()
        if segments:
            ctx.segments = []
            for segment in segments:
                speaker = speaker_by_uuid.get(segment.speaker_id) if segment.speaker_id else None
                segment_data = {
                    "speaker_id": speaker.label if speaker else "UNKNOWN",
                    "start": float(segment.start_time),
                    "end": float(segment.end_time),
                }
                if segment.original_text:
                    segment_data["text"] = segment.original_text
                if segment.translated_text:
                    segment_data["translation"] = segment.translated_text
                if segment.original_audio_url:
                    segment_data["original_audio_url"] = segment.original_audio_url
                if segment.synth_audio_url:
                    segment_data["synth_audio_url"] = segment.synth_audio_url
                ctx.segments.append(segment_data)

        return ctx

    async def mark_task_processing(
        self,
        task_id: uuid.UUID,
        *,
        force: bool = False,
        expected_generation: int | None = None,
    ) -> Task:
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if task.status in TERMINAL_STATUSES and not force:
            return task
        updates = {
            "status": "processing",
            "current_stage": task.current_stage or TaskStage.UPLOADED.value,
            "progress_percent": max(task.progress_percent, 0),
            "error_message": None,
            "paused_at": None,
            "pause_reason_code": None,
            "provider_error_code": None,
            "last_activity_at": datetime.now(timezone.utc),
        }
        if force:
            updates.update(
                {
                    "output_audio_url": None,
                    "finished_at": None,
                }
            )
        return await self._update_task(task, updates, event="task_started")

    async def mark_stage_started(
        self,
        task_id: uuid.UUID,
        stage: TaskStage,
        *,
        expected_generation: int | None = None,
    ) -> Task:
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if task.status in BLOCKED_STATUSES:
            return task
        await self._mark_stage_run_started(task_id, stage)
        return await self._update_task(
            task,
            {
                "status": "processing",
                "current_stage": stage.value,
                # Progress is task-wide and must stay monotonic across a resume.
                # Re-entering the interrupted stage should not make a 91% task
                # appear to restart at that stage's 73% lower bound.
                "progress_percent": max(task.progress_percent, get_stage_progress(stage)),
                "error_message": None,
                "last_activity_at": datetime.now(timezone.utc),
            },
            event="stage_started",
        )

    async def mark_stage_progress(
        self,
        task_id: uuid.UUID,
        stage: TaskStage,
        stage_progress: int,
        *,
        expected_generation: int | None = None,
    ) -> Task:
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if task.status in BLOCKED_STATUSES:
            return task
        progress = get_overall_progress(stage, stage_progress)
        return await self._update_task(
            task,
            {
                "status": "processing",
                "current_stage": stage.value,
                "progress_percent": max(task.progress_percent, progress),
                "last_activity_at": datetime.now(timezone.utc),
            },
            event="stage_progress",
        )

    async def mark_stage_completed(
        self,
        task_id: uuid.UUID,
        stage: TaskStage,
        *,
        expected_generation: int | None = None,
    ) -> None:
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if task.status in BLOCKED_STATUSES:
            return
        await self._mark_stage_run_finished(task_id, stage, status="completed")
        task.last_activity_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def mark_stage_items_progress(
        self,
        task_id: uuid.UUID,
        stage: TaskStage,
        *,
        items_total: int | None = None,
        items_done: int | None = None,
        cost_estimate: float | None = None,
        processed_seconds: float | None = None,
        total_seconds: float | None = None,
        chunk_index: int | None = None,
        chunk_count: int | None = None,
        metrics: dict[str, Any] | None = None,
        expected_generation: int | None = None,
    ) -> None:
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if task.status in BLOCKED_STATUSES:
            return
        await self._update_stage_run_progress(
            task_id,
            stage,
            items_total=items_total,
            items_done=items_done,
            cost_estimate=cost_estimate,
            metrics=metrics,
        )
        task.last_activity_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self._publish_task_progress(
            task_id,
            event="stage_items_progress",
            extra={
                "processed_seconds": processed_seconds,
                "total_seconds": total_seconds,
                "chunk_index": chunk_index,
                "chunk_count": chunk_count,
            },
        )

    async def mark_audio_prepared(
        self,
        task_id: uuid.UUID,
        *,
        audio_duration: float,
        config_updates: dict[str, Any] | None = None,
        expected_generation: int | None = None,
    ) -> Task:
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if expected_generation is not None and task.status in BLOCKED_STATUSES:
            return task
        config = dict(task.config or {})
        if config_updates:
            config.update(config_updates)
        return await self._update_task(
            task,
            {
                "audio_duration": audio_duration,
                "config": config,
                "last_activity_at": datetime.now(timezone.utc),
            },
            event="task_metadata",
        )

    async def persist_pipeline_state(
        self,
        task_id: uuid.UUID,
        ctx: PipelineContext,
        *,
        expected_generation: int | None = None,
    ) -> None:
        if not ctx.segments and not ctx.speakers:
            return

        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        config = dict(task.config or {})
        if ctx.source_language:
            config["source_language"] = ctx.source_language
        if ctx.target_language:
            config["target_language"] = ctx.target_language
        await self.task_repo.update(
            task,
            {"config": config, "last_activity_at": datetime.now(timezone.utc)},
        )

        await self.db.execute(delete(Segment).where(Segment.task_id == task_id))
        await self.db.execute(delete(Speaker).where(Speaker.task_id == task_id))
        await self.db.flush()

        if ensure_mixed_fallback_genders(ctx.speakers):
            logger.info(
                "Task %s: normalized persisted two-speaker fallback genders.",
                task_id,
            )

        speaker_map: dict[str, Speaker] = {}
        for speaker_data in ctx.speakers or []:
            speaker_label = str(speaker_data.get("label") or speaker_data.get("id") or "UNKNOWN")
            speaker = Speaker(
                task_id=task_id,
                label=speaker_label,
                voice_embedding_url=speaker_data.get("voice_embedding_url"),
                reference_audio_url=speaker_data.get("ref_audio_url"),
                gender=speaker_data.get("gender"),
                pitch_hz=speaker_data.get("pitch_hz"),
                voice_provider=speaker_data.get("voice_provider"),
                voice_id=speaker_data.get("voice_id"),
                voice_model=speaker_data.get("voice_model"),
                enrollment_status=speaker_data.get("enrollment_status"),
                fallback_reason=speaker_data.get("fallback_reason"),
            )
            self.db.add(speaker)
            await self.db.flush()
            speaker_map[str(speaker_data.get("id") or speaker_label)] = speaker

        synth_map = {item.get("segment_id"): item for item in (ctx.synth_segments or [])}
        for index, segment_data in enumerate(ctx.segments or []):
            speaker_ref = segment_data.get("speaker_id")
            speaker = speaker_map.get(str(speaker_ref)) if speaker_ref is not None else None
            synth_data = synth_map.get(index)
            segment = Segment(
                task_id=task_id,
                speaker_id=speaker.id if speaker else None,
                start_time=float(segment_data.get("start", 0.0)),
                end_time=float(segment_data.get("end", 0.0)),
                original_text=segment_data.get("text") or segment_data.get("original_text"),
                translated_text=segment_data.get("translation") or segment_data.get("translated_text"),
                original_audio_url=segment_data.get("original_audio_url"),
                synth_audio_url=(synth_data or {}).get("audio_url") or segment_data.get("synth_audio_url"),
            )
            self.db.add(segment)

        await self.db.commit()

    async def mark_completed(
        self,
        task_id: uuid.UUID,
        ctx: PipelineContext,
        *,
        expected_generation: int | None = None,
    ) -> Task:
        await self.persist_pipeline_state(
            task_id,
            ctx,
            expected_generation=expected_generation,
        )
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if task.status == "completed":
            return task
        completed_task = await self._update_task(
            task,
            {
                "status": "completed",
                "current_stage": TaskStage.MIXING.value,
                "progress_percent": 100,
                "output_audio_url": ctx.output_audio_url,
                "error_message": None,
                "paused_at": None,
                "pause_reason_code": None,
                "provider_error_code": None,
                "finished_at": datetime.now(timezone.utc),
                "last_activity_at": datetime.now(timezone.utc),
            },
            event="task_completed",
        )
        await self._clear_task_runtime_keys(task_id)
        await self._cleanup_completed_task_artifacts(task_id)
        return completed_task

    @staticmethod
    def _runtime_key(task_id: uuid.UUID, suffix: str) -> str:
        return f"task:{task_id}:{suffix}"

    async def _clear_task_runtime_keys(self, task_id: uuid.UUID) -> None:
        redis = get_redis_async()
        if redis is None:
            return
        try:
            await redis.delete(
                *[
                    self._runtime_key(task_id, suffix)
                    for suffix in (
                        "worker-lock",
                        "heartbeat",
                        "stall-suspected-at",
                        "dispatch-guard",
                        "reap-lock",
                        "auto-resume-count",
                    )
                ]
            )
        except Exception:
            logger.warning("Failed to clear runtime keys for task %s", task_id, exc_info=True)

    async def reconcile_stalled_tasks(self) -> int:
        if not settings.PCT_ENABLE_STALL_RECONCILER:
            return 0
        timeout = max(60, int(settings.PCT_TASK_STALL_TIMEOUT_SECONDS))
        before = datetime.now(timezone.utc) - timedelta(seconds=timeout)
        candidates = await self.task_repo.get_stall_candidates(
            before,
            max(1, int(settings.PCT_TASK_STALL_SCAN_BATCH_SIZE)),
        )
        reconciled = 0
        for task in candidates:
            generation_before = task.run_generation
            status_before = task.status
            updated = await self.reconcile_if_stalled(task)
            if updated.run_generation != generation_before or updated.status != status_before:
                reconciled += 1
        return reconciled

    async def reconcile_if_stalled(self, task: Task) -> Task:
        """Confirm a stall using heartbeat, lock, activity, and a second observation window."""
        if task.status != "processing":
            return task

        redis = get_redis_async()
        if redis is None:
            return task

        try:
            return await self._reconcile_processing_task(task, redis)
        except (RedisError, ConnectionError, TimeoutError):
            logger.warning(
                "Skipped stall reconciliation for task %s because liveness state was unavailable.",
                task.id,
                exc_info=True,
            )
            return task

    async def _reconcile_processing_task(self, task: Task, redis: Any) -> Task:
        """Reconcile one processing task after a usable Redis client was obtained."""

        heartbeat_key = self._runtime_key(task.id, "heartbeat")
        lock_key = self._runtime_key(task.id, "worker-lock")
        suspect_key = self._runtime_key(task.id, "stall-suspected-at")
        dispatch_key = self._runtime_key(task.id, "dispatch-guard")
        reap_key = self._runtime_key(task.id, "reap-lock")
        resume_count_key = self._runtime_key(task.id, "auto-resume-count")

        if await redis.get(heartbeat_key) is not None:
            await redis.delete(suspect_key)
            return task

        stall_timeout = max(60, int(settings.PCT_TASK_STALL_TIMEOUT_SECONDS))
        now = datetime.now(timezone.utc)
        reference = task.last_activity_at or task.created_at
        ref_aware = reference if reference.tzinfo else reference.replace(tzinfo=timezone.utc)
        if (now - ref_aware).total_seconds() < stall_timeout:
            await redis.delete(suspect_key)
            return task

        if await redis.get(lock_key) is not None or await redis.get(dispatch_key) is not None:
            return task

        confirmation = max(60, int(settings.PCT_TASK_STALL_CONFIRMATION_SECONDS))
        suspected_at = await redis.get(suspect_key)
        if suspected_at is None:
            await redis.set(
                suspect_key,
                str(now.timestamp()),
                ex=stall_timeout + confirmation * 2,
                nx=True,
            )
            logger.warning("Task %s is suspected stalled; awaiting confirmation.", task.id)
            return task
        try:
            suspected_seconds = now.timestamp() - float(suspected_at)
        except (TypeError, ValueError):
            await redis.delete(suspect_key)
            return task
        if suspected_seconds < confirmation:
            return task

        reap_token = str(uuid.uuid4())
        if not await redis.set(
            reap_key,
            reap_token,
            ex=max(30, int(settings.PCT_TASK_STALL_SCAN_INTERVAL_SECONDS) * 2),
            nx=True,
        ):
            return task

        # Recheck every signal after taking the single-flight guard.
        if (
            await redis.get(heartbeat_key) is not None
            or await redis.get(lock_key) is not None
            or await redis.get(dispatch_key) is not None
        ):
            await redis.delete(suspect_key)
            return task

        locked = await self._get_task_for_update_or_raise(task.id)
        if locked.status != "processing":
            return locked
        locked_reference = locked.last_activity_at or locked.created_at
        locked_reference = (
            locked_reference
            if locked_reference.tzinfo
            else locked_reference.replace(tzinfo=timezone.utc)
        )
        if (datetime.now(timezone.utc) - locked_reference).total_seconds() < stall_timeout:
            await redis.delete(suspect_key)
            return locked

        stage: TaskStage | None = None
        if locked.current_stage:
            try:
                stage = TaskStage(locked.current_stage)
            except ValueError:
                stage = None

        cap = max(0, int(settings.PCT_MAX_AUTO_RESUMES))
        resume_count = int(await redis.get(resume_count_key) or 0)
        if resume_count >= cap or not locked.source_audio_url:
            logger.warning(
                "Marking confirmed stalled task %s as failed after %s auto-resume(s).",
                locked.id,
                resume_count,
            )
            locked.run_generation += 1
            failed_generation = locked.run_generation
            await self.db.commit()
            return await self.mark_failed(
                locked.id,
                stage,
                "Task stalled: worker heartbeat, ownership, and progress all stopped. "
                "Auto-resume limit reached — please retry, use a shorter clip, or a larger/GPU worker.",
                expected_generation=failed_generation,
            )

        locked.run_generation += 1
        new_generation = locked.run_generation
        await self.db.commit()
        await self.db.refresh(locked)
        try:
            await redis.set(
                dispatch_key,
                str(new_generation),
                ex=max(
                    60,
                    int(settings.PCT_WORKER_LOCK_TTL_SECONDS),
                    stall_timeout + confirmation,
                ),
            )
            from src.workers.tasks import run_pipeline_task

            run_pipeline_task.delay(
                str(locked.id),
                locked.source_audio_url,
                locked.current_stage,
                True,
                new_generation,
            )
        except Exception:
            await redis.delete(dispatch_key)
            logger.warning("Failed to re-dispatch stalled task %s", locked.id, exc_info=True)
            return locked

        try:
            await redis.incr(resume_count_key)
            await redis.expire(resume_count_key, 7 * 24 * 3600)
            await redis.delete(suspect_key)
        except Exception:
            logger.warning(
                "Task %s was dispatched as generation %s, but resume metadata could not be updated.",
                locked.id,
                new_generation,
                exc_info=True,
            )
        logger.warning(
            "Auto-resumed confirmed stalled task %s as generation %s.",
            locked.id,
            new_generation,
        )
        await self._publish_task_progress(locked.id, event="task_auto_resume")
        return locked

    async def mark_failed(
        self,
        task_id: uuid.UUID,
        stage: TaskStage | None,
        error_message: str,
        *,
        expected_generation: int | None = None,
    ) -> Task:
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if task.status in TERMINAL_STATUSES:
            return task

        user = await self.user_repo.get(task.user_id)
        if user is not None:
            new_used = max(0, user.monthly_used - 1)
            await self.user_repo.update(user, {"monthly_used": new_used})

        if stage:
            await self._mark_stage_run_finished(task_id, stage, status="failed")

        failed_task = await self._update_task(
            task,
            {
                "status": "failed",
                "current_stage": stage.value if stage else task.current_stage,
                "progress_percent": (
                    max(task.progress_percent, get_stage_progress(stage))
                    if stage
                    else task.progress_percent
                ),
                "error_message": truncate_task_error_message(error_message),
                "paused_at": None,
                "pause_reason_code": None,
                "provider_error_code": None,
                "finished_at": datetime.now(timezone.utc),
                "last_activity_at": datetime.now(timezone.utc),
            },
            event="task_failed",
        )
        await self._clear_task_runtime_keys(task_id)
        return failed_task

    async def mark_paused(
        self,
        task_id: uuid.UUID,
        stage: TaskStage | None,
        error_message: str,
        *,
        pause_reason_code: str,
        provider_error_code: str | None = None,
        expected_generation: int | None = None,
    ) -> Task:
        task = await self._get_task_for_update_or_raise(task_id)
        self._assert_generation(task, expected_generation)
        if task.status in TERMINAL_STATUSES:
            return task
        if stage:
            await self._mark_stage_run_finished(
                task_id,
                stage,
                status="paused",
                error_code=provider_error_code or pause_reason_code,
            )
        paused_task = await self._update_task(
            task,
            {
                "status": "paused",
                "current_stage": stage.value if stage else task.current_stage,
                "progress_percent": (
                    max(task.progress_percent, get_stage_progress(stage))
                    if stage
                    else task.progress_percent
                ),
                "error_message": truncate_task_error_message(error_message),
                "paused_at": datetime.now(timezone.utc),
                "pause_reason_code": pause_reason_code,
                "provider_error_code": provider_error_code,
                "finished_at": None,
                "last_activity_at": datetime.now(timezone.utc),
            },
            event="task_paused",
        )
        await self._clear_task_runtime_keys(task_id)
        return paused_task

    async def _mark_stage_run_started(self, task_id: uuid.UUID, stage: TaskStage) -> TaskStageRun:
        active = await self._get_active_stage_run(task_id, stage)
        if active is not None:
            return active

        max_attempt = await self.db.scalar(
            select(func.max(TaskStageRun.attempt)).where(
                TaskStageRun.task_id == task_id,
                TaskStageRun.stage == stage.value,
            )
        )
        run = TaskStageRun(
            task_id=task_id,
            stage=stage.value,
            attempt=int(max_attempt or 0) + 1,
            status="processing",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def _update_stage_run_progress(
        self,
        task_id: uuid.UUID,
        stage: TaskStage,
        *,
        items_total: int | None = None,
        items_done: int | None = None,
        cost_estimate: float | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> TaskStageRun:
        run = await self._get_active_stage_run(task_id, stage)
        if run is None:
            run = await self._mark_stage_run_started(task_id, stage)
        if items_total is not None:
            run.items_total = items_total
        if items_done is not None:
            run.items_done = items_done
        if cost_estimate is not None:
            run.cost_estimate = cost_estimate
        if metrics:
            next_metrics = dict(run.metrics or {})
            next_metrics.update(metrics)
            run.metrics = next_metrics
        await self.db.flush()
        return run

    async def _mark_stage_run_finished(
        self,
        task_id: uuid.UUID,
        stage: TaskStage,
        *,
        status: str,
        error_code: str | None = None,
    ) -> None:
        run = await self._get_active_stage_run(task_id, stage)
        if run is None:
            run = await self._mark_stage_run_started(task_id, stage)
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.error_code = error_code
        await self.db.flush()

    async def _get_active_stage_run(self, task_id: uuid.UUID, stage: TaskStage) -> TaskStageRun | None:
        result = await self.db.execute(
            select(TaskStageRun)
            .where(
                TaskStageRun.task_id == task_id,
                TaskStageRun.stage == stage.value,
                TaskStageRun.finished_at.is_(None),
            )
            .order_by(TaskStageRun.attempt.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _update_task(self, task: Task, updates: dict[str, Any], *, event: str | None = None) -> Task:
        await self.task_repo.update(task, updates)
        await self.db.commit()
        await self.db.refresh(task)
        await self._publish_task_progress(task.id, event=event)
        return task

    async def _publish_task_progress(
        self,
        task_id: uuid.UUID,
        *,
        event: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        task = await self._get_task_with_stage_runs_or_raise(task_id)
        publish_task_progress_message(**self.build_progress_payload(task, event=event, extra=extra))

    async def _cleanup_completed_task_artifacts(self, task_id: uuid.UUID) -> None:
        if not settings.PCT_CLEANUP_INTERMEDIATES_ON_COMPLETION:
            return

        try:
            task = await self._get_task_for_update_or_raise(task_id)
            source_audio_url = task.source_audio_url

            await ArtifactCleanupService(self.db).cleanup_task_intermediates(task_id)
            if source_audio_url and not source_audio_url.startswith("http"):
                await StorageService().delete_object(source_audio_url)

            task.source_audio_url = None
            await self.db.flush()
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.warning("Failed to cleanup completed task artifacts for %s", task_id, exc_info=True)
