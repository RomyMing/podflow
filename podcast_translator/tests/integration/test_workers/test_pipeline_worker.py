"""Integration tests for the Celery pipeline worker (`run_pipeline_task`).

These exercise the worker end-to-end against the real Postgres test database with the
heavy edges stubbed (object storage, redis lock, websocket publish): multi-speaker mock
runs, the provider-credentials -> paused transition (no quota refund), and the
already-completed resume guard.
"""
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.conftest import TEST_DATABASE_URL


def _make_session_factory():
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _reset_schema(engine):
    from src.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed(
    session_factory,
    *,
    task_id,
    user_id,
    config,
    monthly_used=1,
    status="pending",
    run_generation=0,
):
    from src.models.task import Task
    from src.models.user import User
    from src.pipeline.context import TaskStage

    async with session_factory() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    phone=f"138{uuid.uuid4().int % 100000000:08d}",
                    nickname="Integration User",
                    is_active=True,
                    monthly_quota=5,
                    monthly_used=monthly_used,
                ),
                Task(
                    id=task_id,
                    user_id=user_id,
                    status=status,
                    current_stage=TaskStage.UPLOADED.value,
                    progress_percent=0,
                    source_file_name="source.mp3",
                    source_audio_url="uploads/source.mp3",
                    config=config,
                    error_message=None,
                    run_generation=run_generation,
                ),
            ]
        )
        await session.commit()


def _patch_common(monkeypatch, worker_tasks, session_factory, copied_objects):
    class FakeStorageService:
        async def copy_object(self, source_object_name: str, target_object_name: str) -> str:
            copied_objects.append((source_object_name, target_object_name))
            return target_object_name

    monkeypatch.setattr(worker_tasks, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(worker_tasks.settings, "PCT_MOCK_PIPELINE_STAGE_DELAY_SECONDS", 0)
    monkeypatch.setattr(worker_tasks.settings, "PCT_CLEANUP_INTERMEDIATES_ON_COMPLETION", False)
    class FakeHeartbeatProcess:
        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(worker_tasks, "acquire_task_ownership", lambda *a, **k: True)
    monkeypatch.setattr(worker_tasks, "release_task_ownership", lambda *a, **k: None)
    monkeypatch.setattr(worker_tasks, "owns_task", lambda *a, **k: True)
    monkeypatch.setattr(worker_tasks, "_start_heartbeat_helper", lambda *a, **k: FakeHeartbeatProcess())
    monkeypatch.setattr(worker_tasks, "_run_progress_estimator", lambda *a, **k: None)
    monkeypatch.setattr(worker_tasks, "_complete_if_final_output_exists", lambda *a, **k: None)
    monkeypatch.setattr(worker_tasks, "StorageService", FakeStorageService)
    monkeypatch.setattr(
        "src.services.task_runtime_service.publish_task_progress_message",
        lambda **kwargs: None,
    )


def test_mock_pipeline_runs_multi_speaker(monkeypatch):
    from src.models.segment import Segment
    from src.models.speaker import Speaker
    from src.models.task import Task
    from src.workers import tasks as worker_tasks

    engine, session_factory = _make_session_factory()
    task_id, user_id = uuid.uuid4(), uuid.uuid4()
    copied_objects = []

    asyncio.run(_reset_schema(engine))
    asyncio.run(_seed(session_factory, task_id=task_id, user_id=user_id, config={"target_language": "zh", "speaker_count": 3}))
    _patch_common(monkeypatch, worker_tasks, session_factory, copied_objects)
    monkeypatch.setattr(worker_tasks.settings, "PCT_PIPELINE_MODE", "mock")

    async def read_state():
        async with session_factory() as session:
            task = await session.get(Task, task_id)
            speakers = (await session.execute(select(Speaker).where(Speaker.task_id == task_id))).scalars().all()
            segments = (await session.execute(select(Segment).where(Segment.task_id == task_id))).scalars().all()
            return task, speakers, segments

    try:
        result = worker_tasks.run_pipeline_task(str(task_id), "uploads/source.mp3")
        task, speakers, segments = asyncio.run(read_state())
    finally:
        asyncio.run(engine.dispose())

    assert result["status"] == "COMPLETED"
    assert task.status == "completed"
    assert sorted(s.label for s in speakers) == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    # One line per speaker, each assigned to a distinct speaker.
    assert len(segments) == 3
    assert len({seg.speaker_id for seg in segments}) == 3
    assert all(seg.translated_text for seg in segments)


def test_missing_credentials_pauses_without_refund(monkeypatch):
    from src.core.provider_errors import TaskPausedError
    from src.models.task import Task
    from src.models.user import User
    from src.pipeline.context import TaskStage
    from src.workers import tasks as worker_tasks

    engine, session_factory = _make_session_factory()
    task_id, user_id = uuid.uuid4(), uuid.uuid4()
    copied_objects = []

    asyncio.run(_reset_schema(engine))
    asyncio.run(
        _seed(
            session_factory,
            task_id=task_id,
            user_id=user_id,
            config={"target_language": "zh", "translation_provider": "deepseek"},
            monthly_used=1,
        )
    )
    _patch_common(monkeypatch, worker_tasks, session_factory, copied_objects)
    monkeypatch.setattr(worker_tasks.settings, "PCT_PIPELINE_MODE", "real")

    class FakePreflight:
        def preflight_task_sync(self, *, user_id, config, stage):
            raise TaskPausedError(
                "deepseek API key is not configured.",
                provider="deepseek",
                reason_code="provider_credentials_missing",
                stage=TaskStage.PREPARING,
            )

    monkeypatch.setattr(worker_tasks, "ProviderPreflightService", FakePreflight)

    async def read_state():
        async with session_factory() as session:
            return await session.get(Task, task_id), await session.get(User, user_id)

    try:
        result = worker_tasks.run_pipeline_task(str(task_id), "uploads/source.mp3")
        task, user = asyncio.run(read_state())
    finally:
        asyncio.run(engine.dispose())

    assert result["status"] == "PAUSED"
    assert result["pause_reason_code"] == "provider_credentials_missing"
    assert task.status == "paused"
    assert task.pause_reason_code == "provider_credentials_missing"
    assert task.finished_at is None
    # Paused != failed: quota is NOT refunded.
    assert user.monthly_used == 1
    assert copied_objects == []


def test_completed_task_is_not_rerun(monkeypatch):
    from src.models.task import Task
    from src.workers import tasks as worker_tasks

    engine, session_factory = _make_session_factory()
    task_id, user_id = uuid.uuid4(), uuid.uuid4()
    copied_objects = []

    asyncio.run(_reset_schema(engine))
    asyncio.run(_seed(session_factory, task_id=task_id, user_id=user_id, config={"target_language": "zh"}))
    _patch_common(monkeypatch, worker_tasks, session_factory, copied_objects)
    monkeypatch.setattr(worker_tasks.settings, "PCT_PIPELINE_MODE", "mock")

    async def read_status():
        async with session_factory() as session:
            return (await session.get(Task, task_id)).status

    try:
        first = worker_tasks.run_pipeline_task(str(task_id), "uploads/source.mp3")
        second = worker_tasks.run_pipeline_task(str(task_id), "uploads/source.mp3")
        status = asyncio.run(read_status())
    finally:
        asyncio.run(engine.dispose())

    assert first["status"] == "COMPLETED"
    assert second["status"] == "COMPLETED"
    assert status == "completed"
    # The mixing copy only ran on the first invocation; the second short-circuits.
    assert copied_objects == [("uploads/source.mp3", f"{task_id}/output/final_podcast.mp3")]


def test_legacy_message_cannot_run_after_generation_advance(monkeypatch):
    from src.models.task import Task
    from src.workers import tasks as worker_tasks

    engine, session_factory = _make_session_factory()
    task_id, user_id = uuid.uuid4(), uuid.uuid4()
    copied_objects = []

    asyncio.run(_reset_schema(engine))
    asyncio.run(
        _seed(
            session_factory,
            task_id=task_id,
            user_id=user_id,
            config={"target_language": "zh"},
            run_generation=2,
        )
    )
    _patch_common(monkeypatch, worker_tasks, session_factory, copied_objects)

    async def read_state():
        async with session_factory() as session:
            return await session.get(Task, task_id)

    try:
        legacy_result = worker_tasks.run_pipeline_task(str(task_id), "uploads/source.mp3")
        stale_result = worker_tasks.run_pipeline_task(
            str(task_id),
            "uploads/source.mp3",
            run_generation=1,
        )
        task = asyncio.run(read_state())
    finally:
        asyncio.run(engine.dispose())

    assert legacy_result["status"] == "STALE_WORKER"
    assert stale_result["status"] == "STALE_WORKER"
    assert task.status == "pending"
    assert task.run_generation == 2
    assert copied_objects == []
