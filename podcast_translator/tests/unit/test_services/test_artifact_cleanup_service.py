import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import SecretStr

from src.models.speaker import Speaker
from src.models.task import Task
from src.pipeline.voice_providers import ElevenLabsProviderError
from src.services.artifact_cleanup_service import ArtifactCleanupService


class FakeElevenLabsProvider:
    """Records delete_voice calls so the cleanup logic can be tested without HTTP."""

    deleted: list[str] = []
    raise_404_for: set[str] = set()

    def __init__(self, credentials):
        self.credentials = credentials

    def delete_voice(self, voice_id: str) -> None:
        FakeElevenLabsProvider.deleted.append(voice_id)
        if voice_id in FakeElevenLabsProvider.raise_404_for:
            raise ElevenLabsProviderError("not found", status_code=404)


@pytest.fixture(autouse=True)
def _patch_provider_and_system_key(monkeypatch):
    FakeElevenLabsProvider.deleted = []
    FakeElevenLabsProvider.raise_404_for = set()
    monkeypatch.setattr(
        "src.services.artifact_cleanup_service.ElevenLabsVoiceProvider",
        FakeElevenLabsProvider,
    )
    # System-level ElevenLabs key so resolve_credentials returns something for any user.
    from src.config import settings

    monkeypatch.setattr(settings, "PCT_ELEVENLABS_API_KEY", SecretStr("xi-test"))


async def _make_task(db_session, user, *, status="completed", finished_days_ago=30):
    finished_at = (
        datetime.now(timezone.utc) - timedelta(days=finished_days_ago)
        if finished_days_ago is not None
        else None
    )
    task = Task(
        id=uuid.uuid4(),
        user_id=user.id,
        status=status,
        finished_at=finished_at,
    )
    db_session.add(task)
    await db_session.flush()
    return task


async def _add_speaker(db_session, task, *, provider, voice_id):
    speaker = Speaker(
        id=uuid.uuid4(),
        task_id=task.id,
        label="SPEAKER_00",
        voice_provider=provider,
        voice_id=voice_id,
        enrollment_status="enrolled",
    )
    db_session.add(speaker)
    await db_session.flush()
    return speaker


async def test_cleanup_deletes_expired_elevenlabs_voice(db_session, mock_user):
    task = await _make_task(db_session, mock_user)
    speaker = await _add_speaker(db_session, task, provider="elevenlabs", voice_id="voice-abc")

    deleted = await ArtifactCleanupService(db_session).cleanup_expired_voices()

    assert deleted == 1
    assert FakeElevenLabsProvider.deleted == ["voice-abc"]
    await db_session.refresh(speaker)
    assert speaker.voice_id is None
    assert speaker.enrollment_status == "deleted"


async def test_cleanup_skips_non_elevenlabs_and_recent_voices(db_session, mock_user):
    # VoxCPM keeps no cloud resource -> never touched.
    voxcpm_task = await _make_task(db_session, mock_user)
    await _add_speaker(db_session, voxcpm_task, provider="voxcpm", voice_id="local-1")
    # Recent ElevenLabs task is still inside the retention window.
    recent_task = await _make_task(db_session, mock_user, finished_days_ago=0)
    await _add_speaker(db_session, recent_task, provider="elevenlabs", voice_id="voice-recent")

    deleted = await ArtifactCleanupService(db_session).cleanup_expired_voices()

    assert deleted == 0
    assert FakeElevenLabsProvider.deleted == []


async def test_cleanup_skips_non_completed_tasks(db_session, mock_user):
    paused_task = await _make_task(db_session, mock_user, status="paused")
    await _add_speaker(db_session, paused_task, provider="elevenlabs", voice_id="voice-paused")

    deleted = await ArtifactCleanupService(db_session).cleanup_expired_voices()

    assert deleted == 0
    assert FakeElevenLabsProvider.deleted == []


async def test_cleanup_is_idempotent_on_rerun(db_session, mock_user):
    task = await _make_task(db_session, mock_user)
    await _add_speaker(db_session, task, provider="elevenlabs", voice_id="voice-xyz")
    service = ArtifactCleanupService(db_session)

    first = await service.cleanup_expired_voices()
    second = await service.cleanup_expired_voices()

    assert first == 1
    assert second == 0
    assert FakeElevenLabsProvider.deleted == ["voice-xyz"]


async def test_cleanup_treats_404_as_success(db_session, mock_user):
    FakeElevenLabsProvider.raise_404_for = {"voice-gone"}
    task = await _make_task(db_session, mock_user)
    speaker = await _add_speaker(db_session, task, provider="elevenlabs", voice_id="voice-gone")

    deleted = await ArtifactCleanupService(db_session).cleanup_expired_voices()

    assert deleted == 1
    await db_session.refresh(speaker)
    assert speaker.voice_id is None
    assert speaker.enrollment_status == "deleted"
