import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import aiofiles
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.exceptions import (
    FeatureDisabledError,
    ResourceNotFoundError,
    TaskDispatchError,
    TooManyActiveTasksError,
    ValidationError,
)
from src.core.redis import get_redis_async, get_task_pause_request_key, publish_task_progress_message
from src.models.task import Task
from src.pipeline.context import TaskStage
from src.repositories.task_repo import TaskRepository
from src.schemas.task import TaskSegmentResponse
from src.services.eta_service import estimate_task_eta_seconds
from src.services.quota_service import QuotaService
from src.services.storage_service import StorageService
from src.services.task_runtime_service import truncate_task_error_message

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {
    "aac",
    "flac",
    "m4a",
    "mp3",
    "mp4",
    "mpeg",
    "mpga",
    "ogg",
    "opus",
    "wav",
    "webm",
}
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/aac",
    "audio/flac",
    "audio/m4a",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/opus",
    "audio/wav",
    "audio/webm",
    "audio/x-m4a",
    "audio/x-wav",
    "video/mp4",
    "video/webm",
}
GENERIC_UPLOAD_MIME_TYPES = {"application/octet-stream", "binary/octet-stream"}
ALLOWED_TRANSLATION_PROVIDERS = {"deepseek", "openai"}
ALLOWED_VOICE_CLONE_MODES = {"off", "best_effort", "required"}
ALLOWED_VOICE_CLONE_PROVIDERS = {"elevenlabs", "cosyvoice", "voxcpm"}


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_repo = TaskRepository(Task, db)
        self.quota_service = QuotaService(db)
        self.storage_service = StorageService()

    async def create_task(
        self, user_id: uuid.UUID, file: UploadFile, config: Dict[str, Any] = None
    ) -> Task:
        if not settings.PCT_ALLOW_USER_UPLOAD:
            raise FeatureDisabledError("Audio uploads are disabled in this environment.")

        source_file_name = Path(file.filename).name if file.filename else None
        file_ext = self._validate_upload_file_type(file, source_file_name)

        await self._enforce_active_task_limit(user_id)
        await self.quota_service.consume_quota(user_id)

        task_id = uuid.uuid4()
        object_name = f"uploads/{user_id}/{task_id}.{file_ext}"
        tmp_local_path: str | None = None
        uploaded_path: str | None = None
        created_task: Task | None = None
        task_persisted = False

        try:
            tmp_dir = os.path.join(tempfile.gettempdir(), "podcast_translator")
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_local_path = os.path.join(tmp_dir, f"{task_id}_raw.{file_ext}")

            chunk_size = 5 * 1024 * 1024
            total_bytes = 0
            async with aiofiles.open(tmp_local_path, "wb") as out_file:
                while content := await file.read(chunk_size):
                    total_bytes += len(content)
                    if total_bytes > settings.PCT_MAX_UPLOAD_BYTES:
                        max_gb = settings.PCT_MAX_UPLOAD_BYTES / 1024 / 1024 / 1024
                        raise ValidationError(f"Audio file exceeds the {max_gb:.1f}GB upload limit.")
                    await out_file.write(content)

            uploaded_path = await self.storage_service.upload_file(
                local_path=tmp_local_path,
                object_name=object_name,
                content_type=file.content_type or "application/octet-stream",
            )

            created_task = await self.task_repo.create(
                Task(
                    id=task_id,
                    user_id=user_id,
                    status="pending",
                    current_stage=TaskStage.UPLOADED.value,
                    progress_percent=0,
                    source_file_name=source_file_name,
                    source_audio_url=uploaded_path,
                    config=self._with_default_config(config),
                    error_message=None,
                )
            )
            await self.db.commit()
            await self.db.refresh(created_task)
            task_persisted = True

            try:
                from src.workers.tasks import run_pipeline_task

                run_pipeline_task.delay(
                    str(task_id),
                    uploaded_path,
                    None,
                    False,
                    created_task.run_generation,
                )
            except Exception as exc:
                raise TaskDispatchError(
                    "Upload succeeded, but the processing queue is temporarily unavailable. Please try again later."
                ) from exc

            return created_task
        except Exception:
            await self.db.rollback()
            if task_persisted and created_task is not None:
                await self._cleanup_persisted_task(created_task)
            if uploaded_path:
                await self._cleanup_uploaded_object(uploaded_path)
            await self.quota_service.refund_quota(user_id)
            raise
        finally:
            self._cleanup_temp_file(tmp_local_path)

    async def _enforce_active_task_limit(self, user_id: uuid.UUID) -> None:
        limit = settings.PCT_MAX_ACTIVE_TASKS_PER_USER
        if limit <= 0:
            return
        active = await self.task_repo.count_active_tasks(user_id)
        if active >= limit:
            raise TooManyActiveTasksError(
                f"You already have {active} task(s) in progress. "
                f"Please wait for them to finish (limit: {limit})."
            )

    async def get_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task = await self.task_repo.get(task_id)
        if not task or task.user_id != user_id:
            raise ResourceNotFoundError("Task not found")

        if task.source_audio_url and not task.source_audio_url.startswith("http"):
            task.source_audio_url = await self.storage_service.get_presigned_url(task.source_audio_url)
        if task.output_audio_url and not task.output_audio_url.startswith("http"):
            task.output_audio_url = await self.storage_service.get_presigned_url(task.output_audio_url)
        self._attach_eta(task)
        return task

    async def get_task_segments(
        self, task_id: uuid.UUID, user_id: uuid.UUID, skip: int = 0, limit: int = 200
    ) -> List[TaskSegmentResponse]:
        task = await self.task_repo.get(task_id)
        if not task or task.user_id != user_id:
            raise ResourceNotFoundError("Task not found")

        segments = await self.task_repo.get_task_segments(task_id, skip, limit)
        return [
            TaskSegmentResponse(
                index=skip + offset,
                speaker_label=segment.speaker.label if segment.speaker else None,
                start_time=segment.start_time,
                end_time=segment.end_time,
                original_text=segment.original_text,
                translated_text=segment.translated_text,
            )
            for offset, segment in enumerate(segments)
        ]

    async def request_pause(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        """User-initiated cooperative pause. Sets a Redis flag the running pipeline checks at
        stage/chunk boundaries; the task transitions to ``paused`` once it reaches the next
        boundary (so progress already done is checkpointed and resumable)."""
        task = await self.task_repo.get(task_id)
        if not task or task.user_id != user_id:
            raise ResourceNotFoundError("Task not found")
        if task.status not in ("pending", "processing"):
            raise ValidationError("只有正在执行或排队中的任务可以暂停。")

        redis = get_redis_async()
        if redis is not None:
            await redis.set(get_task_pause_request_key(task_id), "1", ex=24 * 3600)
        publish_task_progress_message(
            task_id=str(task_id),
            stage=task.current_stage,
            progress_percent=task.progress_percent,
            status=task.status,
            event="pause_requested",
        )
        return task

    async def delete_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a task and its stored artifacts. Not allowed while actively running — the
        client should pause first (the running task would otherwise keep writing objects)."""
        task = await self.task_repo.get(task_id)
        if not task or task.user_id != user_id:
            raise ResourceNotFoundError("Task not found")
        if task.status in ("pending", "processing"):
            raise ValidationError("请先暂停任务，再删除。")

        redis = get_redis_async()
        if redis is not None:
            for suffix in (
                "worker-lock",
                "heartbeat",
                "stall-suspected-at",
                "dispatch-guard",
                "reap-lock",
                "auto-resume-count",
                "pause-requested",
            ):
                try:
                    await redis.delete(f"task:{task_id}:{suffix}")
                except Exception:
                    logger.warning("Failed to clear redis key %s for task %s", suffix, task_id, exc_info=True)

        from src.services.artifact_cleanup_service import ArtifactCleanupService

        try:
            await ArtifactCleanupService(self.db).cleanup_task_intermediates(task_id)
        except Exception:
            logger.warning("Failed to clean intermediates while deleting task %s", task_id, exc_info=True)
        for object_name in (task.source_audio_url, task.output_audio_url):
            if object_name and not object_name.startswith("http"):
                try:
                    await self.storage_service.delete_object(object_name)
                except Exception:
                    logger.warning("Failed to delete object %s for task %s", object_name, task_id, exc_info=True)

        await self.task_repo.delete(task)
        await self.db.commit()

    async def resume_task(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        config_updates: Dict[str, Any] | None = None,
    ) -> Task:
        task = await self.task_repo.get(task_id)
        if not task or task.user_id != user_id:
            raise ResourceNotFoundError("Task not found")
        if task.status != "paused":
            raise ValidationError("Only paused tasks can be resumed.")
        if not task.source_audio_url:
            raise ValidationError("Task source audio is missing.")

        # Clear all ownership/reconciliation state before assigning a new generation.
        redis = get_redis_async()
        if redis is not None:
            try:
                await redis.delete(
                    *[
                        f"task:{task_id}:{suffix}"
                        for suffix in (
                            "pause-requested",
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
                logger.warning(
                    "Failed to clear runtime keys before resuming task %s",
                    task_id,
                    exc_info=True,
                )

        next_config = self._with_resume_config_updates(task.config, config_updates)
        if next_config is not None:
            await self.task_repo.update(task, {"config": next_config})
            await self.db.commit()
            await self.db.refresh(task)

        start_stage = task.current_stage or TaskStage.SEPARATING.value
        next_generation = task.run_generation + 1
        await self.task_repo.update(
            task,
            {
                "status": "pending",
                "run_generation": next_generation,
                "error_message": None,
                "paused_at": None,
                "pause_reason_code": None,
                "provider_error_code": None,
                "finished_at": None,
                "last_activity_at": datetime.now(timezone.utc),
            },
        )
        await self.db.commit()
        await self.db.refresh(task)
        try:
            from src.workers.tasks import run_pipeline_task

            run_pipeline_task.delay(
                str(task_id),
                task.source_audio_url,
                start_stage,
                True,
                next_generation,
            )
        except Exception as exc:
            await self.task_repo.update(
                task,
                {
                    "status": "paused",
                    "paused_at": datetime.now(timezone.utc),
                    "error_message": "The processing queue is temporarily unavailable.",
                },
            )
            await self.db.commit()
            raise TaskDispatchError(
                "The processing queue is temporarily unavailable. Please try again later."
            ) from exc
        publish_task_progress_message(
            task_id=str(task.id),
            stage=task.current_stage,
            progress_percent=task.progress_percent,
            status=task.status,
            event="task_resume_queued",
        )
        return task

    async def list_tasks(self, user_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Task]:
        tasks = await self.task_repo.get_user_tasks(user_id, skip, limit)
        for index, task in enumerate(tasks):
            if task.source_audio_url and not task.source_audio_url.startswith("http"):
                task.source_audio_url = await self.storage_service.get_presigned_url(task.source_audio_url)
            if task.output_audio_url and not task.output_audio_url.startswith("http"):
                task.output_audio_url = await self.storage_service.get_presigned_url(task.output_audio_url)
            self._attach_eta(task)
        return tasks

    async def update_task_progress(
        self,
        task_id: uuid.UUID,
        stage: str,
        progress: int,
        status: str = "processing",
        error_message: str | None = None,
    ) -> None:
        task = await self.task_repo.get(task_id)
        if not task:
            raise ResourceNotFoundError("Task not found")

        await self.task_repo.update(
            task,
            {
                "current_stage": stage,
                "progress_percent": progress,
                "status": status,
                "error_message": truncate_task_error_message(error_message),
            },
        )
        await self.db.commit()
        await self.db.refresh(task)

        publish_task_progress_message(
            task_id=str(task_id),
            stage=stage,
            progress_percent=progress,
            status=status,
            error_message=error_message,
            event="task_update",
        )

    async def _cleanup_persisted_task(self, task: Task) -> None:
        try:
            await self.task_repo.delete(task)
            await self.db.commit()
        except Exception:
            logger.warning("Failed to delete task %s during upload rollback", task.id, exc_info=True)
            await self.db.rollback()

    async def _cleanup_uploaded_object(self, object_name: str) -> None:
        try:
            await self.storage_service.delete_object(object_name)
        except Exception:
            logger.warning(
                "Failed to delete uploaded object %s during upload rollback",
                object_name,
                exc_info=True,
            )

    def _cleanup_temp_file(self, tmp_local_path: str | None) -> None:
        if not tmp_local_path:
            return
        try:
            if os.path.exists(tmp_local_path):
                os.remove(tmp_local_path)
        except OSError:
            logger.warning("Failed to remove temp upload file %s", tmp_local_path, exc_info=True)

    def _with_default_config(self, config: Dict[str, Any] | None) -> Dict[str, Any]:
        next_config = dict(config or {})
        self._normalize_translation_provider(next_config)
        self._normalize_speaker_count(next_config)
        self._normalize_voice_clone_mode(next_config)
        self._normalize_voice_clone_provider(next_config)
        next_config.setdefault("tts_model_tier", "quality")
        next_config.setdefault("voice_clone_mode", "best_effort")
        next_config.setdefault("voice_clone_provider", settings.PCT_VOICE_CLONE_PROVIDER)
        if (
            settings.PCT_REQUIRE_VOICE_CLONE_CONSENT
            and next_config.get("voice_clone_mode") != "off"
            and not next_config.get("voice_clone_consent_confirmed")
        ):
            raise ValidationError("Voice clone consent is required before processing this audio.")
        return next_config

    def _with_resume_config_updates(
        self,
        current_config: Dict[str, Any] | None,
        config_updates: Dict[str, Any] | None,
    ) -> Dict[str, Any] | None:
        if not config_updates:
            return None

        next_config = dict(current_config or {})
        if "translation_provider" in config_updates:
            next_config["translation_provider"] = config_updates["translation_provider"]
            self._normalize_translation_provider(next_config)
        if "voice_clone_mode" in config_updates:
            next_config["voice_clone_mode"] = config_updates["voice_clone_mode"]
            self._normalize_voice_clone_mode(next_config)
        if "voice_clone_consent_confirmed" in config_updates:
            next_config["voice_clone_consent_confirmed"] = config_updates["voice_clone_consent_confirmed"]
            self._normalize_voice_clone_mode(next_config)
        if "voice_clone_provider" in config_updates:
            next_config["voice_clone_provider"] = config_updates["voice_clone_provider"]
            self._normalize_voice_clone_provider(next_config)
        return next_config

    def _normalize_translation_provider(self, config: Dict[str, Any]) -> None:
        if "translation_provider" not in config:
            return

        provider = str(config.get("translation_provider") or "").strip().lower()
        if provider not in ALLOWED_TRANSLATION_PROVIDERS:
            allowed = ", ".join(sorted(ALLOWED_TRANSLATION_PROVIDERS))
            raise ValidationError(f"Unsupported translation provider. Allowed values: {allowed}.")
        config["translation_provider"] = provider

    def _normalize_voice_clone_mode(self, config: Dict[str, Any]) -> None:
        mode = str(config.get("voice_clone_mode") or "best_effort").strip().lower()
        if mode not in ALLOWED_VOICE_CLONE_MODES:
            allowed = ", ".join(sorted(ALLOWED_VOICE_CLONE_MODES))
            raise ValidationError(f"Unsupported voice clone mode. Allowed values: {allowed}.")
        config["voice_clone_mode"] = mode
        if "voice_clone_consent_confirmed" in config:
            config["voice_clone_consent_confirmed"] = bool(config.get("voice_clone_consent_confirmed"))

    def _normalize_speaker_count(self, config: Dict[str, Any]) -> None:
        if "speaker_count" not in config:
            return
        try:
            speaker_count = int(config.get("speaker_count") or 0)
        except (TypeError, ValueError) as exc:
            raise ValidationError("speaker_count must be an integer from 0 to 4.") from exc
        if speaker_count < 0 or speaker_count > 4:
            raise ValidationError("当前内测版仅支持自动检测或 1-4 位说话人。")
        config["speaker_count"] = speaker_count

    def _normalize_voice_clone_provider(self, config: Dict[str, Any]) -> None:
        provider = str(config.get("voice_clone_provider") or settings.PCT_VOICE_CLONE_PROVIDER).strip().lower()
        if provider not in ALLOWED_VOICE_CLONE_PROVIDERS:
            allowed = ", ".join(sorted(ALLOWED_VOICE_CLONE_PROVIDERS))
            raise ValidationError(f"Unsupported voice clone provider. Allowed values: {allowed}.")
        config["voice_clone_provider"] = provider

    def _validate_upload_file_type(self, file: UploadFile, source_file_name: str | None) -> str:
        suffix = Path(source_file_name or "").suffix.lower().lstrip(".")
        if suffix not in ALLOWED_AUDIO_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
            raise ValidationError(f"Unsupported audio file type. Allowed extensions: {allowed}.")

        content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
        if (
            content_type
            and content_type not in ALLOWED_AUDIO_MIME_TYPES
            and content_type not in GENERIC_UPLOAD_MIME_TYPES
        ):
            allowed = ", ".join(sorted(ALLOWED_AUDIO_MIME_TYPES))
            raise ValidationError(f"Unsupported audio MIME type '{content_type}'. Allowed MIME types: {allowed}.")

        return suffix

    def _attach_eta(self, task: Task) -> None:
        try:
            stage_runs = list(task.stage_runs or [])
        except Exception:
            stage_runs = []
        task.eta_seconds = estimate_task_eta_seconds(
            status=task.status,
            current_stage=task.current_stage,
            progress_percent=task.progress_percent,
            audio_duration=task.audio_duration,
            stage_runs=stage_runs,
        )
