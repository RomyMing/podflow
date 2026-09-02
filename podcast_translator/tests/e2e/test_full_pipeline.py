import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.conftest import TEST_DATABASE_URL


def test_mock_worker_runs_current_full_pipeline_flow(monkeypatch):
    from src.models import Base
    from src.models.segment import Segment
    from src.models.speaker import Speaker
    from src.models.task import Task
    from src.models.task_stage_run import TaskStageRun
    from src.models.user import User
    from src.pipeline.context import TaskStage
    from src.workers import tasks as worker_tasks

    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    task_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async def setup_database():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            user = User(
                id=user_id,
                phone="13800138001",
                nickname="E2E User",
                is_active=True,
                monthly_quota=5,
                monthly_used=1,
            )
            task = Task(
                id=task_id,
                user_id=user_id,
                status="pending",
                current_stage=TaskStage.UPLOADED.value,
                progress_percent=0,
                source_file_name="source.mp3",
                source_audio_url="uploads/source.mp3",
                config={"target_language": "zh"},
                error_message=None,
            )
            session.add_all([user, task])
            await session.commit()

    async def read_final_state():
        async with session_factory() as session:
            task = await session.get(Task, task_id)
            user = await session.get(User, user_id)
            stage_runs = (
                await session.execute(
                    select(TaskStageRun)
                    .where(TaskStageRun.task_id == task_id)
                    .order_by(TaskStageRun.started_at, TaskStageRun.stage)
                )
            ).scalars().all()
            speakers = (
                await session.execute(select(Speaker).where(Speaker.task_id == task_id))
            ).scalars().all()
            segments = (
                await session.execute(
                    select(Segment)
                    .where(Segment.task_id == task_id)
                    .order_by(Segment.start_time)
                )
            ).scalars().all()
            return task, user, stage_runs, speakers, segments

    async def teardown_database():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    copied_objects = []

    class FakeStorageService:
        async def copy_object(self, source_object_name: str, target_object_name: str) -> str:
            copied_objects.append((source_object_name, target_object_name))
            return target_object_name

    asyncio.run(setup_database())
    monkeypatch.setattr(worker_tasks, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(worker_tasks.settings, "PCT_PIPELINE_MODE", "mock")
    monkeypatch.setattr(worker_tasks.settings, "PCT_MOCK_PIPELINE_STAGE_DELAY_SECONDS", 0)
    monkeypatch.setattr(worker_tasks.settings, "PCT_CLEANUP_INTERMEDIATES_ON_COMPLETION", False)
    class FakeHeartbeatProcess:
        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(worker_tasks, "acquire_task_ownership", lambda *args, **kwargs: True)
    monkeypatch.setattr(worker_tasks, "release_task_ownership", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker_tasks, "owns_task", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        worker_tasks,
        "_start_heartbeat_helper",
        lambda *args, **kwargs: FakeHeartbeatProcess(),
    )
    monkeypatch.setattr(worker_tasks, "_run_progress_estimator", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker_tasks, "_complete_if_final_output_exists", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker_tasks, "StorageService", FakeStorageService)
    monkeypatch.setattr(
        "src.services.task_runtime_service.publish_task_progress_message",
        lambda **kwargs: None,
    )

    try:
        result = worker_tasks.run_pipeline_task(str(task_id), "uploads/source.mp3")
        task, user, stage_runs, speakers, segments = asyncio.run(read_final_state())
    finally:
        asyncio.run(teardown_database())

    assert result == {
        "task_id": str(task_id),
        "status": "COMPLETED",
        "output_audio_url": f"{task_id}/output/final_podcast.mp3",
    }
    assert copied_objects == [("uploads/source.mp3", f"{task_id}/output/final_podcast.mp3")]

    assert task.status == "completed"
    assert task.current_stage == TaskStage.MIXING.value
    assert task.progress_percent == 100
    assert task.output_audio_url == f"{task_id}/output/final_podcast.mp3"
    assert task.error_message is None
    assert task.finished_at is not None
    assert user.monthly_used == 1

    expected_stages = [
        TaskStage.SEPARATING.value,
        TaskStage.DIARIZING.value,
        TaskStage.TRANSCRIBING.value,
        TaskStage.TRANSLATING.value,
        TaskStage.SYNTHESIZING.value,
        TaskStage.ALIGNING.value,
        TaskStage.MIXING.value,
    ]
    assert [run.stage for run in stage_runs] == expected_stages
    assert all(run.status == "completed" for run in stage_runs)
    assert all(run.attempt == 1 for run in stage_runs)
    assert all(run.finished_at is not None for run in stage_runs)

    assert [speaker.label for speaker in speakers] == ["SPEAKER_00"]
    assert len(segments) == 2
    assert [segment.original_text for segment in segments] == [
        "Hello and welcome.",
        "This is a mock translation run.",
    ]
    assert all(segment.translated_text for segment in segments)
    assert [segment.synth_audio_url for segment in segments] == [
        "uploads/source.mp3",
        "uploads/source.mp3",
    ]
