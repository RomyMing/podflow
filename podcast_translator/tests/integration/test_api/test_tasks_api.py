import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from src.models.task import Task
from src.pipeline.context import TaskStage


class TestCreateTask:
    @patch("src.services.storage_service.StorageService._instance", None)
    @patch("src.services.task_service.StorageService")
    async def test_create_task_unauthenticated(self, MockStorage, client):
        resp = await client.post("/api/v1/tasks", files={"file": ("test.mp3", b"data", "audio/mpeg")})
        assert resp.status_code == 401

    @patch("src.workers.tasks.run_pipeline_task")
    @patch("src.services.storage_service.StorageService._instance", None)
    async def test_create_task_success(self, mock_celery, authenticated_client, mock_user):
        user_id = mock_user.id
        mock_celery.delay = MagicMock()

        with patch("src.services.task_service.StorageService") as MockStorage:
            mock_inst = MockStorage.return_value
            mock_inst.upload_file = AsyncMock(return_value="uploads/test.mp3")
            mock_inst.ensure_bucket_exists = AsyncMock()

            resp = await authenticated_client.post(
                "/api/v1/tasks",
                files={"file": ("test.mp3", b"fake-audio", "audio/mpeg")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["user_id"] == str(user_id)

    @patch("src.workers.tasks.run_pipeline_task")
    @patch("src.services.storage_service.StorageService._instance", None)
    async def test_create_task_queue_unavailable_returns_503(
        self,
        mock_celery,
        authenticated_client,
        db_session,
        mock_user,
    ):
        mock_celery.delay = MagicMock(side_effect=RuntimeError("broker down"))

        with patch("src.services.task_service.StorageService") as MockStorage:
            mock_inst = MockStorage.return_value
            mock_inst.upload_file = AsyncMock(return_value="uploads/test.mp3")
            mock_inst.ensure_bucket_exists = AsyncMock()
            mock_inst.delete_object = AsyncMock()

            resp = await authenticated_client.post(
                "/api/v1/tasks",
                files={"file": ("test.mp3", b"fake-audio", "audio/mpeg")},
            )

        assert resp.status_code == 503
        assert "processing queue" in resp.json()["detail"]
        mock_inst.delete_object.assert_awaited_once_with("uploads/test.mp3")

        result = await db_session.execute(select(Task).where(Task.user_id == mock_user.id))
        assert result.scalars().all() == []

    async def test_create_task_invalid_config_returns_400(self, authenticated_client):
        resp = await authenticated_client.post(
            "/api/v1/tasks",
            data={"config": "{"},
            files={"file": ("test.mp3", b"fake-audio", "audio/mpeg")},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid upload config payload"


class TestListTasks:
    async def test_list_tasks_authenticated(self, authenticated_client):
        resp = await authenticated_client.get("/api/v1/tasks")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_tasks_unauthenticated(self, client):
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 401


class TestGetTask:
    async def test_get_task_not_found(self, authenticated_client):
        fake_id = str(uuid.uuid4())
        resp = await authenticated_client.get(f"/api/v1/tasks/{fake_id}")
        assert resp.status_code == 404


class TestResumeTask:
    @patch("src.workers.tasks.run_pipeline_task")
    async def test_resume_paused_task_dispatches_from_current_stage(
        self,
        mock_celery,
        authenticated_client,
        db_session,
        mock_user,
    ):
        task = Task(
            id=uuid.uuid4(),
            user_id=mock_user.id,
            status="paused",
            current_stage=TaskStage.SYNTHESIZING.value,
            progress_percent=80,
            source_audio_url="uploads/source.mp3",
            config={},
            error_message="Arrearage",
            pause_reason_code="provider_billing_required",
            provider_error_code="Arrearage",
        )
        db_session.add(task)
        await db_session.commit()
        mock_celery.delay = MagicMock()

        resp = await authenticated_client.post(f"/api/v1/tasks/{task.id}/resume")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["pause_reason_code"] is None
        mock_celery.delay.assert_called_once_with(
            str(task.id),
            "uploads/source.mp3",
            TaskStage.SYNTHESIZING.value,
            True,
            1,
        )

    async def test_resume_non_paused_task_returns_400(self, authenticated_client, db_session, mock_user):
        task = Task(
            id=uuid.uuid4(),
            user_id=mock_user.id,
            status="processing",
            current_stage=TaskStage.SYNTHESIZING.value,
            progress_percent=80,
            source_audio_url="uploads/source.mp3",
            config={},
            error_message=None,
        )
        db_session.add(task)
        await db_session.commit()

        resp = await authenticated_client.post(f"/api/v1/tasks/{task.id}/resume")

        assert resp.status_code == 400
