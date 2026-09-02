import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import settings
from src.core.exceptions import (
    QuotaExceededError,
    ResourceNotFoundError,
    TaskDispatchError,
    TooManyActiveTasksError,
    ValidationError,
)
from src.models.task import Task
from src.pipeline.context import TaskStage
from src.services.task_service import TaskService


def make_upload_file(
    filename: str = 'test.mp3',
    content: bytes = b'fake-audio-data',
    content_type: str = 'audio/mpeg',
):
    from fastapi import UploadFile
    from starlette.datastructures import Headers

    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({'content-type': content_type}),
    )


class TestCreateTask:
    @patch('src.services.task_service.StorageService')
    async def test_create_task_success(self, MockStorage, db_session, mock_user):
        user_id = mock_user.id
        storage = MockStorage.return_value
        storage.upload_file = AsyncMock(return_value='uploads/test/file.mp3')

        service = TaskService(db_session)
        service.storage_service = storage

        with patch('src.workers.tasks.run_pipeline_task') as mock_celery:
            mock_celery.delay = MagicMock()
            task = await service.create_task(user_id, make_upload_file(), {'target_language': 'zh'})

        await db_session.refresh(mock_user)

        assert task.status == 'pending'
        assert task.user_id == user_id
        assert task.current_stage == TaskStage.UPLOADED.value
        assert task.progress_percent == 0
        assert task.source_audio_url == 'uploads/test/file.mp3'
        assert task.config == {
            'target_language': 'zh',
            'tts_model_tier': 'quality',
            'voice_clone_mode': 'best_effort',
            'voice_clone_provider': 'elevenlabs',
        }
        assert task.error_message is None
        assert mock_user.monthly_used == 1
        mock_celery.delay.assert_called_once()

    async def _seed_active_tasks(self, db_session, user_id, count, status="processing"):
        for _ in range(count):
            db_session.add(
                Task(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    status=status,
                    current_stage=TaskStage.SEPARATING.value,
                    progress_percent=0,
                    source_audio_url="uploads/x.mp3",
                )
            )
        await db_session.flush()

    async def test_create_task_blocked_when_active_limit_reached(self, db_session, mock_user, monkeypatch):
        monkeypatch.setattr(settings, "PCT_MAX_ACTIVE_TASKS_PER_USER", 2)
        await self._seed_active_tasks(db_session, mock_user.id, 2)

        service = TaskService(db_session)
        with pytest.raises(TooManyActiveTasksError, match="in progress"):
            await service.create_task(mock_user.id, make_upload_file())

        # Blocked before quota is consumed.
        await db_session.refresh(mock_user)
        assert mock_user.monthly_used == 0

    async def test_create_task_active_limit_ignores_terminal_tasks(self, db_session, mock_user, monkeypatch):
        monkeypatch.setattr(settings, "PCT_MAX_ACTIVE_TASKS_PER_USER", 1)
        # Completed/failed tasks do not count toward the active limit.
        await self._seed_active_tasks(db_session, mock_user.id, 3, status="completed")

        service = TaskService(db_session)
        # Should not raise the active-task error (count is 0).
        await service._enforce_active_task_limit(mock_user.id)

    async def test_create_task_quota_exceeded(self, db_session, mock_user_exhausted):
        service = TaskService(db_session)

        with pytest.raises(QuotaExceededError):
            await service.create_task(mock_user_exhausted.id, make_upload_file())

    async def test_create_task_rejects_unsupported_extension_before_quota(self, db_session, mock_user):
        service = TaskService(db_session)

        with pytest.raises(ValidationError, match="Unsupported audio file type"):
            await service.create_task(mock_user.id, make_upload_file("notes.txt", content_type="audio/mpeg"))

        await db_session.refresh(mock_user)
        assert mock_user.monthly_used == 0

    async def test_create_task_rejects_unsupported_mime_before_quota(self, db_session, mock_user):
        service = TaskService(db_session)

        with pytest.raises(ValidationError, match="Unsupported audio MIME type"):
            await service.create_task(mock_user.id, make_upload_file("clip.mp3", content_type="text/plain"))

        await db_session.refresh(mock_user)
        assert mock_user.monthly_used == 0

    @patch('src.services.task_service.StorageService')
    async def test_create_task_upload_fail_refunds_quota(self, MockStorage, db_session, mock_user):
        storage = MockStorage.return_value
        storage.upload_file = AsyncMock(side_effect=Exception('S3 down'))

        service = TaskService(db_session)
        service.storage_service = storage

        with pytest.raises(Exception, match='S3 down'):
            await service.create_task(mock_user.id, make_upload_file())

        await db_session.refresh(mock_user)
        assert mock_user.monthly_used == 0

    @patch('src.services.task_service.StorageService')
    async def test_create_task_dispatch_fail_rolls_back_everything(self, MockStorage, db_session, mock_user):
        storage = MockStorage.return_value
        storage.upload_file = AsyncMock(return_value='uploads/test/file.mp3')
        storage.delete_object = AsyncMock()

        service = TaskService(db_session)
        service.storage_service = storage

        with patch('src.workers.tasks.run_pipeline_task') as mock_celery:
            mock_celery.delay = MagicMock(side_effect=RuntimeError('broker down'))
            with pytest.raises(TaskDispatchError):
                await service.create_task(mock_user.id, make_upload_file())

        await db_session.refresh(mock_user)
        tasks = await service.list_tasks(mock_user.id)

        assert mock_user.monthly_used == 0
        assert tasks == []
        storage.delete_object.assert_awaited_once_with('uploads/test/file.mp3')


class TestGetTask:
    @patch('src.services.task_service.StorageService')
    async def test_get_task_success(self, MockStorage, db_session, mock_user):
        storage = MockStorage.return_value
        storage.upload_file = AsyncMock(return_value='uploads/test/file.mp3')
        storage.get_presigned_url = AsyncMock(return_value='http://signed-url')

        service = TaskService(db_session)
        service.storage_service = storage

        with patch('src.workers.tasks.run_pipeline_task') as mock_celery:
            mock_celery.delay = MagicMock()
            created = await service.create_task(mock_user.id, make_upload_file())

        task = await service.get_task(created.id, mock_user.id)

        assert task.id == created.id
        assert task.source_audio_url == 'http://signed-url'

    async def test_get_task_not_found(self, db_session, mock_user):
        service = TaskService(db_session)

        with pytest.raises(ResourceNotFoundError):
            await service.get_task(uuid.uuid4(), mock_user.id)

    @patch('src.services.task_service.StorageService')
    async def test_get_task_wrong_user(self, MockStorage, db_session, mock_user, mock_user_exhausted):
        storage = MockStorage.return_value
        storage.upload_file = AsyncMock(return_value='uploads/test/file.mp3')

        service = TaskService(db_session)
        service.storage_service = storage

        with patch('src.workers.tasks.run_pipeline_task') as mock_celery:
            mock_celery.delay = MagicMock()
            created = await service.create_task(mock_user.id, make_upload_file())

        with pytest.raises(ResourceNotFoundError):
            await service.get_task(created.id, mock_user_exhausted.id)


class TestGetTaskSegments:
    async def _seed_task_with_segments(self, db_session, user_id):
        from src.models.segment import Segment
        from src.models.speaker import Speaker

        task = Task(
            id=uuid.uuid4(),
            user_id=user_id,
            status="completed",
            current_stage=TaskStage.MIXING.value,
            progress_percent=100,
        )
        db_session.add(task)
        speaker = Speaker(id=uuid.uuid4(), task_id=task.id, label="SPEAKER_00")
        db_session.add(speaker)
        # Insert out of chronological order to verify sorting by start_time.
        db_session.add(
            Segment(
                id=uuid.uuid4(),
                task_id=task.id,
                speaker_id=speaker.id,
                start_time=5.0,
                end_time=8.0,
                original_text="hello",
                translated_text="你好",
            )
        )
        db_session.add(
            Segment(
                id=uuid.uuid4(),
                task_id=task.id,
                speaker_id=speaker.id,
                start_time=0.0,
                end_time=4.0,
                original_text="world",
                translated_text="世界",
            )
        )
        await db_session.flush()
        return task

    async def test_returns_segments_sorted_with_speaker_label(self, db_session, mock_user):
        task = await self._seed_task_with_segments(db_session, mock_user.id)
        service = TaskService(db_session)

        segments = await service.get_task_segments(task.id, mock_user.id)

        assert [s.start_time for s in segments] == [0.0, 5.0]
        assert [s.index for s in segments] == [0, 1]
        assert segments[0].original_text == "world"
        assert segments[0].translated_text == "世界"
        assert segments[0].speaker_label == "SPEAKER_00"

    async def test_pagination_index_offset(self, db_session, mock_user):
        task = await self._seed_task_with_segments(db_session, mock_user.id)
        service = TaskService(db_session)

        segments = await service.get_task_segments(task.id, mock_user.id, skip=1, limit=10)

        assert len(segments) == 1
        assert segments[0].index == 1
        assert segments[0].start_time == 5.0

    async def test_not_found(self, db_session, mock_user):
        service = TaskService(db_session)
        with pytest.raises(ResourceNotFoundError):
            await service.get_task_segments(uuid.uuid4(), mock_user.id)

    async def test_wrong_user(self, db_session, mock_user, mock_user_exhausted):
        task = await self._seed_task_with_segments(db_session, mock_user.id)
        service = TaskService(db_session)
        with pytest.raises(ResourceNotFoundError):
            await service.get_task_segments(task.id, mock_user_exhausted.id)


class TestListTasks:
    @patch('src.services.task_service.StorageService')
    async def test_list_tasks_only_own(self, MockStorage, db_session, mock_user, mock_user_exhausted):
        storage = MockStorage.return_value
        storage.upload_file = AsyncMock(return_value='uploads/test/file.mp3')
        storage.get_presigned_url = AsyncMock(return_value='http://signed-url')

        service = TaskService(db_session)
        service.storage_service = storage

        with patch('src.workers.tasks.run_pipeline_task') as mock_celery:
            mock_celery.delay = MagicMock()
            await service.create_task(mock_user.id, make_upload_file('a.mp3'))
            await service.create_task(mock_user.id, make_upload_file('b.mp3'))

        tasks = await service.list_tasks(mock_user.id)
        tasks_other = await service.list_tasks(mock_user_exhausted.id)

        assert len(tasks) == 2
        assert len(tasks_other) == 0
        assert all(task.user_id == mock_user.id for task in tasks)


class TestPauseAndDelete:
    async def _seed(self, db_session, user_id, status):
        task = Task(
            id=uuid.uuid4(), user_id=user_id, status=status,
            current_stage=TaskStage.SEPARATING.value, progress_percent=10,
            source_audio_url=None,
        )
        db_session.add(task)
        await db_session.flush()
        return task

    async def test_manual_resume_increments_generation(self, db_session, mock_user):
        task = await self._seed(db_session, mock_user.id, "paused")
        task.source_audio_url = "uploads/test/source.mp3"
        await db_session.flush()
        service = TaskService(db_session)

        with patch("src.services.task_service.get_redis_async", return_value=None):
            with patch("src.workers.tasks.run_pipeline_task.delay") as delay:
                updated = await service.resume_task(task.id, mock_user.id)

        assert updated.status == "pending"
        assert updated.run_generation == 1
        delay.assert_called_once_with(
            str(task.id),
            "uploads/test/source.mp3",
            TaskStage.SEPARATING.value,
            True,
            1,
        )

    async def test_request_pause_on_running_task(self, db_session, mock_user, monkeypatch):
        monkeypatch.setattr("src.services.task_service.get_redis_async", lambda: None)
        task = await self._seed(db_session, mock_user.id, "processing")
        service = TaskService(db_session)
        out = await service.request_pause(task.id, mock_user.id)
        assert out.id == task.id  # returns the task; transition happens in worker

    async def test_request_pause_rejects_non_running(self, db_session, mock_user, monkeypatch):
        monkeypatch.setattr("src.services.task_service.get_redis_async", lambda: None)
        task = await self._seed(db_session, mock_user.id, "completed")
        service = TaskService(db_session)
        with pytest.raises(ValidationError):
            await service.request_pause(task.id, mock_user.id)

    @patch("src.services.artifact_cleanup_service.ArtifactCleanupService.cleanup_task_intermediates")
    async def test_delete_paused_task(self, mock_cleanup, db_session, mock_user, monkeypatch):
        mock_cleanup.return_value = 0
        monkeypatch.setattr("src.services.task_service.get_redis_async", lambda: None)
        task = await self._seed(db_session, mock_user.id, "paused")
        tid = task.id
        service = TaskService(db_session)
        service.storage_service = MagicMock()
        await service.delete_task(tid, mock_user.id)
        assert await service.task_repo.get(tid) is None

    async def test_delete_rejects_running_task(self, db_session, mock_user, monkeypatch):
        monkeypatch.setattr("src.services.task_service.get_redis_async", lambda: None)
        task = await self._seed(db_session, mock_user.id, "processing")
        service = TaskService(db_session)
        with pytest.raises(ValidationError):
            await service.delete_task(task.id, mock_user.id)

    async def test_request_pause_wrong_user(self, db_session, mock_user, mock_user_exhausted, monkeypatch):
        monkeypatch.setattr("src.services.task_service.get_redis_async", lambda: None)
        task = await self._seed(db_session, mock_user.id, "processing")
        service = TaskService(db_session)
        with pytest.raises(ResourceNotFoundError):
            await service.request_pause(task.id, mock_user_exhausted.id)
