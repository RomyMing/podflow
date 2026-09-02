import logging
import os
import subprocess
import sys
import threading
import time
import uuid

from src.config import settings
from src.core.database import AsyncSessionLocal
from src.core.exceptions import StaleWorkerGenerationError
from src.core.provider_errors import TaskPausedError
from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.pause import raise_if_user_paused
from src.pipeline.progress import (
    OPAQUE_PROGRESS_STAGES,
    estimate_stage_progress,
)
from src.pipeline.utils import run_sync
from src.services.provider_preflight_service import ProviderPreflightService
from src.services.storage_service import StorageService
from src.services.task_runtime_service import TaskRuntimeService
from src.workers.celery_app import celery_app
from src.workers.task_liveness import (
    acquire_task_ownership,
    build_owner_token,
    owns_task,
    release_task_ownership,
    task_dispatch_guard_key,
)
from src.core.redis import get_redis_sync

logger = logging.getLogger(__name__)

RESUMABLE_FAILURE_MARKERS = (
    "SoftTimeLimitExceeded",
    "WorkerLostError",
)


def _is_resumable_failure(error_message: str | None) -> bool:
    return bool(error_message and any(marker in error_message for marker in RESUMABLE_FAILURE_MARKERS))


def _resolve_resume_stage(current_stage: str | None) -> TaskStage:
    """Resume an interrupted task from where it stopped, not from scratch.

    Early stages (uploaded/preparing) fall back to separation, since there is no
    meaningful partial work to reuse before separation.
    """
    if not current_stage:
        return TaskStage.SEPARATING
    try:
        stage = TaskStage(current_stage)
    except ValueError:
        return TaskStage.SEPARATING
    if stage in (TaskStage.UPLOADED, TaskStage.PREPARING):
        return TaskStage.SEPARATING
    return stage


class WorkerTaskLifecycleHooks:
    def __init__(self, task_id: str, run_generation: int = 0, owner: str | None = None):
        self.task_id = task_id
        self.task_uuid = uuid.UUID(task_id)
        self.run_generation = run_generation
        self.owner = owner
        self.current_stage: TaskStage | None = None
        self.audio_duration: float | None = None
        # Used by the heartbeat to estimate elapsed-based progress for opaque stages.
        self._stage_started_monotonic: float | None = None
        self._items_reported_stage: str | None = None
        self._last_reported_progress: int = 0

    def _run(self, callback):
        self.ensure_ownership()

        async def runner():
            async with AsyncSessionLocal() as session:
                service = TaskRuntimeService(session)
                return await callback(service)

        return run_sync(runner())

    def ensure_ownership(self) -> None:
        if not self.owner:
            return
        owned = owns_task(self.task_id, self.owner)
        if owned is False:
            raise StaleWorkerGenerationError(
                f"Task {self.task_id} worker generation {self.run_generation} lost ownership."
            )

    def stage_elapsed_seconds(self) -> float | None:
        if self._stage_started_monotonic is None:
            return None
        return max(0.0, time.monotonic() - self._stage_started_monotonic)

    def on_stage_started(self, stage: TaskStage):
        self.current_stage = stage
        self._stage_started_monotonic = time.monotonic()
        self._last_reported_progress = 0
        self._run(
            lambda service: service.mark_stage_started(
                self.task_uuid,
                stage,
                expected_generation=self.run_generation,
            )
        )

    def on_stage_progress(self, stage: TaskStage, stage_progress: int):
        self._last_reported_progress = max(self._last_reported_progress, int(stage_progress))
        self._run(
            lambda service: service.mark_stage_progress(
                self.task_uuid,
                stage,
                stage_progress,
                expected_generation=self.run_generation,
            )
        )

    def on_stage_items_progress(
        self,
        stage: TaskStage,
        items_total: int | None = None,
        items_done: int | None = None,
        cost_estimate: float | None = None,
        processed_seconds: float | None = None,
        total_seconds: float | None = None,
        chunk_index: int | None = None,
        chunk_count: int | None = None,
        metrics: dict | None = None,
    ):
        # This stage emits real per-item progress, so the heartbeat must not overwrite it
        # with an elapsed-based estimate.
        self._items_reported_stage = stage.value
        self._run(
            lambda service: service.mark_stage_items_progress(
                self.task_uuid,
                stage,
                items_total=items_total,
                items_done=items_done,
                cost_estimate=cost_estimate,
                processed_seconds=processed_seconds,
                total_seconds=total_seconds,
                chunk_index=chunk_index,
                chunk_count=chunk_count,
                metrics=metrics,
                expected_generation=self.run_generation,
            )
        )

    def on_stage_completed(self, stage: TaskStage, ctx: PipelineContext):
        if stage in {
            TaskStage.DIARIZING,
            TaskStage.TRANSCRIBING,
            TaskStage.TRANSLATING,
            TaskStage.SYNTHESIZING,
            TaskStage.ALIGNING,
            TaskStage.MIXING,
        }:
            self._run(
                lambda service: service.persist_pipeline_state(
                    self.task_uuid,
                    ctx,
                    expected_generation=self.run_generation,
                )
            )
        self._run(
            lambda service: service.mark_stage_completed(
                self.task_uuid,
                stage,
                expected_generation=self.run_generation,
            )
        )

    def on_pipeline_state_checkpoint(self, ctx: PipelineContext):
        self._run(
            lambda service: service.persist_pipeline_state(
                self.task_uuid,
                ctx,
                expected_generation=self.run_generation,
            )
        )

    def on_stage_failed(self, stage: TaskStage, error_message: str):
        logger.warning("Stage %s failed for task %s: %s", stage.value, self.task_uuid, error_message)

    def on_audio_prepared(self, audio_duration: float, config_updates: dict | None = None):
        self.audio_duration = audio_duration
        self._run(
            lambda service: service.mark_audio_prepared(
                self.task_uuid,
                audio_duration=audio_duration,
                config_updates=config_updates,
                expected_generation=self.run_generation,
            )
        )


def _with_runtime_service(callback):
    async def runner():
        async with AsyncSessionLocal() as session:
            service = TaskRuntimeService(session)
            return await callback(service)

    return run_sync(runner())


def _final_output_object_name(task_id: str) -> str:
    return f"{task_id}/output/final_podcast.mp3"


def _preflight_stage_for_run(stage: TaskStage, has_explicit_start_stage: bool) -> TaskStage:
    if has_explicit_start_stage:
        return stage
    if stage in {TaskStage.UPLOADED, TaskStage.PREPARING, TaskStage.SEPARATING}:
        return TaskStage.PREPARING
    return stage


def _complete_if_final_output_exists(
    task_id: str,
    source_audio_url: str,
    run_generation: int,
) -> dict | None:
    final_object_name = _final_output_object_name(task_id)
    storage_service = StorageService()
    try:
        final_exists = run_sync(storage_service.object_exists(final_object_name))
    except Exception:
        logger.warning(
            "[Celery] Failed to check existing final output for task %s",
            task_id,
            exc_info=True,
        )
        return None

    if not final_exists:
        return None

    task_uuid = uuid.UUID(task_id)
    ctx = PipelineContext(
        task_id=task_id,
        source_audio_url=source_audio_url,
        output_audio_url=final_object_name,
    )
    task = _with_runtime_service(
        lambda service: service.mark_completed(
            task_uuid,
            ctx,
            expected_generation=run_generation,
        )
    )
    logger.warning(
        "[Celery] Task %s already has final output %s; marked completed and skipped pipeline.",
        task_id,
        final_object_name,
    )
    return {
        "task_id": task_id,
        "status": task.status.upper(),
        "output_audio_url": task.output_audio_url,
    }


def _start_heartbeat_helper(
    task_id: str,
    owner: str,
    interval: int,
    lock_ttl: int,
    heartbeat_ttl: int,
) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "src.workers.heartbeat_helper",
            "--task-id",
            task_id,
            "--owner",
            owner,
            "--parent-pid",
            str(os.getpid()),
            "--interval",
            str(interval),
            "--lock-ttl",
            str(lock_ttl),
            "--heartbeat-ttl",
            str(heartbeat_ttl),
        ],
        close_fds=True,
    )


def _run_progress_estimator(
    stop_event: "threading.Event",
    task_id: str,
    hooks: "WorkerTaskLifecycleHooks",
) -> None:
    """Best-effort UI progress; liveness is maintained by the independent helper process."""
    interval = max(5, int(settings.PCT_WORKER_HEARTBEAT_INTERVAL_SECONDS))
    multiplier = float(settings.PCT_ETA_DURATION_MULTIPLIER or 1.0)

    while not stop_event.is_set():
        stage = hooks.current_stage
        if (
            stage is not None
            and stage in OPAQUE_PROGRESS_STAGES
            and hooks._items_reported_stage != stage.value
        ):
            elapsed = hooks.stage_elapsed_seconds()
            if elapsed is not None:
                est = estimate_stage_progress(stage, elapsed, hooks.audio_duration, multiplier=multiplier)
                if est > hooks._last_reported_progress:
                    try:
                        hooks.on_stage_progress(stage, est)
                    except Exception:
                        logger.warning("Progress estimator update failed for task %s", task_id, exc_info=True)

        stop_event.wait(interval)


def _mock_speakers_and_segments(task_id: str, speaker_count: int) -> tuple[list[dict], list[dict]]:
    """Fabricate mock speakers + transcribed segments for the requested speaker count.

    ``speaker_count`` 0 (auto) or 1 reproduces the canonical single-speaker demo flow
    byte-for-byte; 2-4 fans the conversation across that many speakers (one line each)
    so multi-speaker behaviour can be exercised without the real diarization stage.
    """
    n = speaker_count if 2 <= speaker_count <= 4 else 1

    def _speaker(index: int) -> dict:
        label = f'SPEAKER_{index:02d}'
        return {
            'id': label,
            'label': label,
            'ref_audio_url': f'{task_id}/speakers/{label}_ref.wav',
            'voice_provider': 'mock',
            'voice_model': 'mock',
            'enrollment_status': 'enrolled',
        }

    speakers = [_speaker(i) for i in range(n)]

    if n == 1:
        segments = [
            {'speaker_id': 'SPEAKER_00', 'start': 0.0, 'end': 3.2, 'text': 'Hello and welcome.'},
            {'speaker_id': 'SPEAKER_00', 'start': 3.2, 'end': 7.5, 'text': 'This is a mock translation run.'},
        ]
    else:
        segments = [
            {
                'speaker_id': f'SPEAKER_{i:02d}',
                'start': i * 4.0,
                'end': i * 4.0 + 4.0,
                'text': f'Mock line {i + 1}.',
            }
            for i in range(n)
        ]
    return speakers, segments


def _execute_mock_pipeline(
    task_id: str,
    source_audio_url: str,
    hooks: WorkerTaskLifecycleHooks,
    speaker_count: int = 0,
) -> PipelineContext:
    storage_service = StorageService()
    ctx = PipelineContext(
        task_id=task_id,
        source_audio_url=source_audio_url,
        lifecycle_hooks=hooks,
    )

    speakers, transcribed_segments = _mock_speakers_and_segments(task_id, speaker_count)
    translations = {
        'Hello and welcome.': '你好，欢迎收听。',
        'This is a mock translation run.': '这是一条模拟翻译链路。',
    }

    stages = [
        TaskStage.SEPARATING,
        TaskStage.DIARIZING,
        TaskStage.TRANSCRIBING,
        TaskStage.TRANSLATING,
        TaskStage.SYNTHESIZING,
        TaskStage.ALIGNING,
        TaskStage.MIXING,
    ]

    for stage in stages:
        raise_if_user_paused(task_id, stage)
        hooks.on_stage_started(stage)
        time.sleep(settings.PCT_MOCK_PIPELINE_STAGE_DELAY_SECONDS)

        if stage == TaskStage.DIARIZING:
            ctx.speakers = speakers
            ctx.segments = [
                {k: v for k, v in segment.items() if k != 'text'}
                for segment in transcribed_segments
            ]
        elif stage == TaskStage.TRANSCRIBING:
            ctx.segments = [dict(segment) for segment in transcribed_segments]
        elif stage == TaskStage.TRANSLATING:
            for segment in ctx.segments or []:
                segment['translation'] = translations.get(segment.get('text', ''), '模拟翻译内容。')
        elif stage == TaskStage.SYNTHESIZING:
            ctx.synth_segments = [
                {
                    'segment_id': index,
                    'audio_url': source_audio_url,
                    'duration': round(segment['end'] - segment['start'], 4),
                }
                for index, segment in enumerate(ctx.segments or [])
            ]
        elif stage == TaskStage.ALIGNING:
            running = 0.0
            for synth in ctx.synth_segments or []:
                synth['aligned_start'] = running
                synth['aligned_end'] = running + synth['duration']
                running = synth['aligned_end']
        elif stage == TaskStage.MIXING:
            final_object_name = f'{task_id}/output/final_podcast.mp3'
            run_sync(storage_service.copy_object(source_audio_url, final_object_name))
            ctx.output_audio_url = final_object_name

        hooks.on_stage_completed(stage, ctx)
        hooks.on_stage_progress(stage, 100)

    return ctx


@celery_app.task(
    bind=True,
    name='tasks.run_pipeline',
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=settings.PCT_PIPELINE_TASK_TIME_LIMIT_SECONDS,
    soft_time_limit=settings.PCT_PIPELINE_TASK_SOFT_TIME_LIMIT_SECONDS,
)
def run_pipeline_task(
    self,
    task_id: str,
    source_audio_url: str,
    start_stage: str | None = None,
    force_resume: bool = False,
    run_generation: int | None = None,
):
    logger.info('[Celery] Received pipeline task: %s', task_id)
    task_uuid = uuid.UUID(task_id)
    snapshot = _with_runtime_service(lambda service: service.get_task_snapshot(task_uuid))
    if run_generation is None:
        if snapshot.run_generation != 0:
            logger.warning(
                "[Celery] Skip legacy task message for %s because generation is now %s",
                task_id,
                snapshot.run_generation,
            )
            return {"task_id": task_id, "status": "STALE_WORKER"}
        run_generation = 0
    if snapshot.run_generation != run_generation:
        logger.warning(
            "[Celery] Skip stale generation %s for task %s; current generation is %s",
            run_generation,
            task_id,
            snapshot.run_generation,
        )
        return {"task_id": task_id, "status": "STALE_WORKER"}

    celery_task_id = getattr(self.request, "id", None) or str(uuid.uuid4())
    lock_owner = build_owner_token(run_generation, celery_task_id)
    hooks = WorkerTaskLifecycleHooks(task_id, run_generation, lock_owner)
    # Short, heartbeat-renewed TTL: if this worker dies (OOM/SIGKILL) the lock expires
    # quickly instead of wedging retries for the multi-day task time limit.
    lock_ttl_seconds = max(int(settings.PCT_WORKER_LOCK_TTL_SECONDS), 60)

    if not acquire_task_ownership(task_id, lock_owner, lock_ttl_seconds):
        logger.warning('[Celery] Skip duplicate pipeline execution for task %s', task_id)
        return {
            'task_id': task_id,
            'status': 'SKIPPED_DUPLICATE',
        }

    heartbeat_interval = max(5, int(settings.PCT_WORKER_HEARTBEAT_INTERVAL_SECONDS))
    heartbeat_ttl = max(heartbeat_interval * 2, int(settings.PCT_TASK_STALL_TIMEOUT_SECONDS))
    try:
        heartbeat_process = _start_heartbeat_helper(
            task_id,
            lock_owner,
            heartbeat_interval,
            lock_ttl_seconds,
            heartbeat_ttl,
        )
    except Exception:
        release_task_ownership(task_id, lock_owner)
        logger.exception("[Celery] Failed to start heartbeat helper for task %s", task_id)
        raise
    progress_stop = threading.Event()
    progress_thread = threading.Thread(
        target=_run_progress_estimator,
        args=(progress_stop, task_id, hooks),
        name=f"progress-{task_id[:8]}",
        daemon=True,
    )
    progress_thread.start()
    redis_client = get_redis_sync()
    if redis_client is not None:
        try:
            redis_client.delete(task_dispatch_guard_key(task_id))
        except Exception:
            logger.warning(
                "[Celery] Failed to clear dispatch guard for task %s",
                task_id,
                exc_info=True,
            )

    try:
        snapshot = _with_runtime_service(lambda service: service.get_task_snapshot(task_uuid))
        if snapshot.run_generation != run_generation:
            raise StaleWorkerGenerationError(
                f"Task {task_id} generation changed before execution started."
            )
        resume_failed_task = snapshot.status == "failed" and _is_resumable_failure(snapshot.error_message)
        if snapshot.status == "completed" and not start_stage:
            logger.warning('[Celery] Skip task %s because it is already terminal: %s', task_id, snapshot.status)
            return {
                'task_id': task_id,
                'status': snapshot.status.upper(),
                'output_audio_url': snapshot.output_audio_url,
            }
        if snapshot.status == "failed" and not start_stage and not resume_failed_task and not force_resume:
            logger.warning('[Celery] Skip task %s because it is already terminal: %s', task_id, snapshot.status)
            return {
                'task_id': task_id,
                'status': snapshot.status.upper(),
                'output_audio_url': snapshot.output_audio_url,
            }
        if snapshot.status == "paused" and not start_stage and not force_resume:
            logger.warning('[Celery] Skip paused task %s until the user resumes it.', task_id)
            return {
                'task_id': task_id,
                'status': 'PAUSED',
                'output_audio_url': snapshot.output_audio_url,
            }
        if not start_stage:
            completed_result = _complete_if_final_output_exists(
                task_id,
                source_audio_url,
                run_generation,
            )
            if completed_result:
                return completed_result

        if (resume_failed_task or force_resume) and not start_stage:
            logger.warning(
                '[Celery] Resuming task %s after failure: %s',
                task_id,
                snapshot.error_message,
            )

        _with_runtime_service(
            lambda service: service.mark_task_processing(
                task_uuid,
                force=bool(start_stage) or resume_failed_task or force_resume,
                expected_generation=run_generation,
            )
        )

        ctx = _with_runtime_service(
            lambda service: service.build_pipeline_context(task_uuid, source_audio_url)
        )
        ctx.lifecycle_hooks = hooks

        if start_stage:
            try:
                stage_enum = TaskStage(start_stage)
            except ValueError:
                logger.error("[Celery] Invalid start_stage '%s' for task %s. Using default.", start_stage, task_id)
                stage_enum = TaskStage.SEPARATING
            ctx.invalidated_stages.add(stage_enum.value)
        elif resume_failed_task or force_resume:
            # Auto-resume after a resumable failure (e.g. OOM/WorkerLost): continue from the
            # stage that was interrupted instead of redoing the whole pipeline.
            stage_enum = _resolve_resume_stage(snapshot.current_stage)
            ctx.invalidated_stages.add(stage_enum.value)
            logger.warning("[Celery] Auto-resuming task %s from stage %s", task_id, stage_enum.value)
        else:
            stage_enum = TaskStage.SEPARATING

        if settings.PCT_PIPELINE_MODE == 'mock':
            mock_speaker_count = int((ctx.config or {}).get('speaker_count') or 0)
            result_ctx = _execute_mock_pipeline(task_id, source_audio_url, hooks, mock_speaker_count)
        else:
            preflight_stage = _preflight_stage_for_run(stage_enum, bool(start_stage))
            if preflight_stage == TaskStage.PREPARING:
                hooks.on_stage_started(TaskStage.PREPARING)
            ProviderPreflightService().preflight_task_sync(
                user_id=ctx.user_id,
                config=ctx.config,
                stage=preflight_stage,
            )
            if preflight_stage == TaskStage.PREPARING and not settings.PCT_ENABLE_LONG_AUDIO_PIPELINE:
                hooks.on_stage_progress(TaskStage.PREPARING, 100)
                hooks.on_stage_completed(TaskStage.PREPARING, ctx)

            if settings.PCT_ENABLE_LONG_AUDIO_PIPELINE:
                from src.pipeline.long_audio import LongAudioPipeline

                pipeline = LongAudioPipeline(start_stage=stage_enum)
            else:
                from src.pipeline.orchestrator import PodcastTranslatorPipeline

                pipeline = PodcastTranslatorPipeline(start_stage=stage_enum)
            result_ctx = pipeline.execute_task(ctx)

        logger.info('[Celery] Pipeline completed for task %s. Output: %s', task_id, result_ctx.output_audio_url)
        if not result_ctx.output_audio_url:
            raise RuntimeError("Pipeline completed without output audio URL.")
        _with_runtime_service(
            lambda service: service.mark_completed(
                task_uuid,
                result_ctx,
                expected_generation=run_generation,
            )
        )

        return {
            'task_id': task_id,
            'status': 'COMPLETED',
            'output_audio_url': result_ctx.output_audio_url,
        }
    except TaskPausedError as exc:
        pause_exc = exc
        logger.warning(
            '[Celery] Task %s paused due to provider issue (%s/%s): %s',
            task_id,
            pause_exc.provider,
            pause_exc.provider_error_code or pause_exc.reason_code,
            pause_exc,
        )
        try:
            paused_task = _with_runtime_service(
                lambda service: service.mark_paused(
                    task_uuid,
                    pause_exc.stage,
                    str(pause_exc),
                    pause_reason_code=pause_exc.reason_code,
                    provider_error_code=pause_exc.provider_error_code,
                    expected_generation=run_generation,
                )
            )
        except StaleWorkerGenerationError:
            logger.warning("[Celery] Ignore pause from stale worker for task %s", task_id)
            return {"task_id": task_id, "status": "STALE_WORKER"}
        return {
            'task_id': task_id,
            'status': 'PAUSED',
            'pause_reason_code': paused_task.pause_reason_code,
            'provider_error_code': paused_task.provider_error_code,
        }
    except StaleWorkerGenerationError as exc:
        logger.warning("[Celery] Stopping stale worker for task %s: %s", task_id, exc)
        return {"task_id": task_id, "status": "STALE_WORKER"}
    except Exception as exc:
        logger.exception('[Celery] Unexpected error for task %s: %s', task_id, exc)
        failure_message = str(exc)
        try:
            _with_runtime_service(
                lambda service: service.mark_failed(
                    task_uuid,
                    hooks.current_stage,
                    failure_message,
                    expected_generation=run_generation,
                )
            )
        except StaleWorkerGenerationError:
            logger.warning("[Celery] Ignore failure from stale worker for task %s", task_id)
        raise
    finally:
        progress_stop.set()
        progress_thread.join(timeout=5)
        heartbeat_process.terminate()
        try:
            heartbeat_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            heartbeat_process.kill()
            heartbeat_process.wait(timeout=5)
        release_task_ownership(task_id, lock_owner)


@celery_app.task(name='tasks.cleanup_expired_voices')
def cleanup_expired_voices_task() -> int:
    """Periodic sweep that deletes ElevenLabs voices past the retention window."""
    async def runner():
        async with AsyncSessionLocal() as session:
            from src.services.artifact_cleanup_service import ArtifactCleanupService

            return await ArtifactCleanupService(session).cleanup_expired_voices()

    deleted = run_sync(runner())
    logger.info('[Celery] Voice retention sweep deleted %s expired voice(s).', deleted)
    return deleted


@celery_app.task(name="tasks.reconcile_stalled_tasks")
def reconcile_stalled_tasks_task() -> int:
    """Periodic, side-effecting stall scan; API reads remain strictly read-only."""
    async def runner():
        async with AsyncSessionLocal() as session:
            return await TaskRuntimeService(session).reconcile_stalled_tasks()

    reconciled = run_sync(runner())
    logger.info("[Celery] Stall reconciliation changed %s task(s).", reconciled)
    return reconciled
