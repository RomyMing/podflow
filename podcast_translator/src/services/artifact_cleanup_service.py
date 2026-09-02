import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.speaker import Speaker
from src.models.task import Task
from src.pipeline.voice_providers import ElevenLabsProviderError, ElevenLabsVoiceProvider
from src.services.storage_service import StorageService
from src.services.user_api_key_service import UserApiKeyService

logger = logging.getLogger(__name__)


class ArtifactCleanupService:
    def __init__(self, db: AsyncSession, storage_service: StorageService | None = None):
        self.db = db
        self.storage_service = storage_service or StorageService()

    async def cleanup_completed_tasks(self, *, older_than_days: int | None = None, limit: int = 100) -> int:
        retention_days = older_than_days if older_than_days is not None else settings.PCT_INTERMEDIATE_ARTIFACT_RETENTION_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, retention_days))
        result = await self.db.execute(
            select(Task)
            .where(
                Task.status == "completed",
                Task.finished_at.is_not(None),
                Task.finished_at <= cutoff,
            )
            .order_by(Task.finished_at)
            .limit(max(1, limit))
        )
        tasks = list(result.scalars().all())
        deleted = 0
        for task in tasks:
            deleted += await self.cleanup_task_intermediates(task.id)
        return deleted

    async def cleanup_task_intermediates(self, task_id: uuid.UUID) -> int:
        task_prefix = f"{task_id}/"
        keep_keys = {
            f"{task_id}/output/final_podcast.mp3",
            f"{task_id}/manifest.json",
        }
        return await self.storage_service.delete_prefix(task_prefix, keep_keys=keep_keys)

    async def cleanup_expired_voices(self, *, older_than_days: int | None = None, limit: int = 500) -> int:
        """Delete cloned ElevenLabs voices for completed tasks past the retention window.

        Only ``elevenlabs`` voices are removed — VoxCPM/CosyVoice keep no cloud-side
        resource. Credentials are resolved per task owner (user key, else system key).
        On success the speaker's ``voice_id`` is cleared and ``enrollment_status`` set to
        ``"deleted"`` so the same voice is never deleted twice (idempotent reruns). A 404
        from ElevenLabs (voice already gone) counts as success.
        """
        retention_days = older_than_days if older_than_days is not None else settings.PCT_VOICE_CLONE_RETENTION_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, retention_days))
        result = await self.db.execute(
            select(Speaker, Task.user_id)
            .join(Task, Speaker.task_id == Task.id)
            .where(
                Task.status == "completed",
                Task.finished_at.is_not(None),
                Task.finished_at <= cutoff,
                Speaker.voice_provider == "elevenlabs",
                Speaker.voice_id.is_not(None),
            )
            .order_by(Task.finished_at)
            .limit(max(1, limit))
        )
        rows = result.all()
        if not rows:
            return 0

        speakers_by_user: dict[uuid.UUID, list[Speaker]] = defaultdict(list)
        for speaker, user_id in rows:
            speakers_by_user[user_id].append(speaker)

        key_service = UserApiKeyService(self.db)
        deleted = 0
        for user_id, speakers in speakers_by_user.items():
            credentials = await key_service.resolve_credentials(user_id, "elevenlabs")
            if credentials is None:
                logger.warning(
                    "No ElevenLabs credentials for user %s; skipping %d expired voice(s).",
                    user_id,
                    len(speakers),
                )
                continue
            provider = ElevenLabsVoiceProvider(credentials)
            for speaker in speakers:
                voice_id = speaker.voice_id
                try:
                    await asyncio.to_thread(provider.delete_voice, voice_id)
                except ElevenLabsProviderError as exc:
                    if exc.status_code != 404:
                        logger.warning("Failed to delete ElevenLabs voice %s: %s", voice_id, exc)
                        continue
                    logger.info("ElevenLabs voice %s already absent; marking deleted.", voice_id)
                speaker.voice_id = None
                speaker.enrollment_status = "deleted"
                deleted += 1

        if deleted:
            await self.db.commit()
        return deleted
