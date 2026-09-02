import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from src.core.exceptions import StaleWorkerGenerationError
from src.models.segment import Segment
from src.models.speaker import Speaker
from src.models.task import Task
from src.models.task_stage_run import TaskStageRun
from src.pipeline.context import PipelineContext, TaskStage
from src.services.task_runtime_service import TaskRuntimeService, truncate_task_error_message


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            deleted += int(self.values.pop(key, None) is not None)
        return deleted

    async def incr(self, key):
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    async def expire(self, key, seconds):
        return key in self.values


class UnavailableRedis:
    async def get(self, key):
        raise ConnectionError("redis unavailable")


async def create_task(db_session, user_id) -> Task:
    task = Task(
        id=uuid.uuid4(),
        user_id=user_id,
        status='pending',
        current_stage=TaskStage.UPLOADED.value,
        progress_percent=0,
        source_audio_url='uploads/test/source.mp3',
        config={'target_language': 'zh'},
        error_message=None,
    )
    db_session.add(task)
    await db_session.flush()
    return task


class TestTaskRuntimeService:
    async def test_stale_generation_cannot_update_progress(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.run_generation = 2
        task.status = "processing"
        await db_session.flush()

        with pytest.raises(StaleWorkerGenerationError):
            await TaskRuntimeService(db_session).mark_stage_progress(
                task.id,
                TaskStage.TRANSCRIBING,
                50,
                expected_generation=1,
            )

    async def test_stale_completion_and_failure_do_not_mutate_or_refund(
        self,
        db_session,
        mock_user,
    ):
        mock_user.monthly_used = 1
        task = await create_task(db_session, mock_user.id)
        task.run_generation = 2
        task.status = "processing"
        await db_session.flush()
        service = TaskRuntimeService(db_session)
        ctx = PipelineContext(
            task_id=str(task.id),
            source_audio_url=task.source_audio_url,
            output_audio_url=f"{task.id}/output/final.mp3",
        )

        with pytest.raises(StaleWorkerGenerationError):
            await service.mark_completed(task.id, ctx, expected_generation=1)
        with pytest.raises(StaleWorkerGenerationError):
            await service.mark_failed(
                task.id,
                TaskStage.TRANSLATING,
                "old worker failed",
                expected_generation=1,
            )

        await db_session.refresh(task)
        await db_session.refresh(mock_user)
        assert task.status == "processing"
        assert mock_user.monthly_used == 1

    async def test_real_progress_updates_last_activity(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.status = "processing"
        task.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=1)
        before = task.last_activity_at

        with patch("src.services.task_runtime_service.publish_task_progress_message"):
            await TaskRuntimeService(db_session).mark_stage_progress(
                task.id,
                TaskStage.TRANSCRIBING,
                20,
                expected_generation=0,
            )

        assert task.last_activity_at > before

    async def test_stall_first_observation_only_marks_suspected(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.status = "processing"
        task.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=1)
        redis = FakeRedis()

        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            with patch("src.workers.tasks.run_pipeline_task.delay") as delay:
                updated = await TaskRuntimeService(db_session).reconcile_if_stalled(task)

        assert updated.status == "processing"
        assert f"task:{task.id}:stall-suspected-at" in redis.values
        delay.assert_not_called()

    async def test_non_processing_and_unavailable_redis_do_not_reconcile(
        self,
        db_session,
        mock_user,
    ):
        task = await create_task(db_session, mock_user.id)
        service = TaskRuntimeService(db_session)

        with patch("src.services.task_runtime_service.get_redis_async", return_value=UnavailableRedis()):
            unchanged = await service.reconcile_if_stalled(task)
        assert unchanged.status == "pending"

        task.status = "processing"
        task.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.flush()
        with patch("src.services.task_runtime_service.get_redis_async", return_value=UnavailableRedis()):
            unchanged = await service.reconcile_if_stalled(task)

        assert unchanged.status == "processing"
        assert unchanged.run_generation == 0

    async def test_fresh_activity_clears_suspect(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.status = "processing"
        task.last_activity_at = datetime.now(timezone.utc)
        redis = FakeRedis()
        suspect_key = f"task:{task.id}:stall-suspected-at"
        redis.values[suspect_key] = "1"

        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            await TaskRuntimeService(db_session).reconcile_if_stalled(task)

        assert suspect_key not in redis.values

    async def test_confirmation_window_and_dispatch_guard_prevent_resume(
        self,
        db_session,
        mock_user,
    ):
        task = await create_task(db_session, mock_user.id)
        task.status = "processing"
        task.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=1)
        redis = FakeRedis()
        suspect_key = f"task:{task.id}:stall-suspected-at"
        redis.values[suspect_key] = str(datetime.now(timezone.utc).timestamp())
        service = TaskRuntimeService(db_session)

        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            with patch("src.workers.tasks.run_pipeline_task.delay") as delay:
                await service.reconcile_if_stalled(task)
                redis.values[suspect_key] = str(
                    (datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp()
                )
                redis.values[f"task:{task.id}:dispatch-guard"] = "1"
                await service.reconcile_if_stalled(task)

        delay.assert_not_called()
        assert task.run_generation == 0

    async def test_stall_health_signals_prevent_resume(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.status = "processing"
        task.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=1)
        redis = FakeRedis()
        suspect_key = f"task:{task.id}:stall-suspected-at"
        redis.values[suspect_key] = "1"
        redis.values[f"task:{task.id}:heartbeat"] = "alive"

        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            await TaskRuntimeService(db_session).reconcile_if_stalled(task)

        assert suspect_key not in redis.values

        redis.values[f"task:{task.id}:worker-lock"] = "owner"
        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            with patch("src.workers.tasks.run_pipeline_task.delay") as delay:
                await TaskRuntimeService(db_session).reconcile_if_stalled(task)
        delay.assert_not_called()

    async def test_confirmed_stall_dispatches_one_new_generation(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.status = "processing"
        task.current_stage = TaskStage.TRANSCRIBING.value
        task.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.flush()
        redis = FakeRedis()
        redis.values[f"task:{task.id}:stall-suspected-at"] = str(
            (datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp()
        )

        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            with patch("src.workers.tasks.run_pipeline_task.delay") as delay:
                updated = await TaskRuntimeService(db_session).reconcile_if_stalled(task)

        assert updated.run_generation == 1
        delay.assert_called_once_with(
            str(task.id),
            task.source_audio_url,
            TaskStage.TRANSCRIBING.value,
            True,
            1,
        )
        assert redis.values[f"task:{task.id}:auto-resume-count"] == "1"

        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            with patch("src.workers.tasks.run_pipeline_task.delay") as second_delay:
                await TaskRuntimeService(db_session).reconcile_if_stalled(updated)
        second_delay.assert_not_called()

    async def test_resume_cap_marks_failed_and_refunds_once(self, db_session, mock_user):
        mock_user.monthly_used = 1
        task = await create_task(db_session, mock_user.id)
        task.status = "processing"
        task.current_stage = TaskStage.TRANSCRIBING.value
        task.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.flush()
        redis = FakeRedis()
        redis.values[f"task:{task.id}:stall-suspected-at"] = str(
            (datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp()
        )
        redis.values[f"task:{task.id}:auto-resume-count"] = "1"
        service = TaskRuntimeService(db_session)

        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            with patch("src.services.task_runtime_service.publish_task_progress_message"):
                updated = await service.reconcile_if_stalled(task)
                await service.reconcile_if_stalled(updated)

        await db_session.refresh(mock_user)
        assert updated.status == "failed"
        assert mock_user.monthly_used == 0

    async def test_dispatch_failure_keeps_suspect_and_does_not_consume_resume(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.status = "processing"
        task.current_stage = TaskStage.TRANSCRIBING.value
        task.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.flush()
        redis = FakeRedis()
        suspect_key = f"task:{task.id}:stall-suspected-at"
        redis.values[suspect_key] = str(
            (datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp()
        )

        with patch("src.services.task_runtime_service.get_redis_async", return_value=redis):
            with patch(
                "src.workers.tasks.run_pipeline_task.delay",
                side_effect=RuntimeError("broker unavailable"),
            ):
                updated = await TaskRuntimeService(db_session).reconcile_if_stalled(task)

        assert updated.status == "processing"
        assert updated.run_generation == 1
        assert suspect_key in redis.values
        assert f"task:{task.id}:auto-resume-count" not in redis.values
        assert f"task:{task.id}:dispatch-guard" not in redis.values
    async def test_mark_task_processing_updates_status(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        service = TaskRuntimeService(db_session)

        with patch('src.services.task_runtime_service.publish_task_progress_message') as publish:
            updated = await service.mark_task_processing(task.id)

        assert updated.status == 'processing'
        assert updated.current_stage == TaskStage.UPLOADED.value
        assert updated.error_message is None
        publish.assert_called_once()

    async def test_resumed_stage_progress_never_moves_backwards(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.status = 'processing'
        task.current_stage = TaskStage.SYNTHESIZING.value
        task.progress_percent = 91
        await db_session.commit()
        service = TaskRuntimeService(db_session)

        with patch('src.services.task_runtime_service.publish_task_progress_message'):
            started = await service.mark_stage_started(task.id, TaskStage.SYNTHESIZING)
            replayed = await service.mark_stage_progress(task.id, TaskStage.SYNTHESIZING, 20)

        assert started.progress_percent == 91
        assert replayed.progress_percent == 91

    async def test_mark_failed_sets_error_and_refunds_once(self, db_session, mock_user):
        mock_user.monthly_used = 1
        task = await create_task(db_session, mock_user.id)
        service = TaskRuntimeService(db_session)

        with patch('src.services.task_runtime_service.publish_task_progress_message'):
            await service.mark_stage_started(task.id, TaskStage.TRANSLATING)
            progressed = await service.mark_stage_progress(task.id, TaskStage.TRANSLATING, 80)
            updated = await service.mark_failed(task.id, TaskStage.TRANSLATING, 'translation failed')
            await service.mark_failed(task.id, TaskStage.TRANSLATING, 'translation failed')

        await db_session.refresh(mock_user)

        assert updated.status == 'failed'
        assert updated.current_stage == TaskStage.TRANSLATING.value
        assert updated.progress_percent == progressed.progress_percent
        assert updated.error_message == 'translation failed'
        assert updated.finished_at is not None
        assert mock_user.monthly_used == 0

    async def test_mark_completed_can_recover_failed_task_with_existing_output(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        task.status = 'failed'
        task.current_stage = TaskStage.SYNTHESIZING.value
        task.progress_percent = 80
        task.error_message = 'SoftTimeLimitExceeded()'
        service = TaskRuntimeService(db_session)
        ctx = PipelineContext(
            task_id=str(task.id),
            source_audio_url='uploads/test/source.mp3',
            output_audio_url=f'{task.id}/output/final_podcast.mp3',
        )

        with patch('src.services.task_runtime_service.settings.PCT_CLEANUP_INTERMEDIATES_ON_COMPLETION', False):
            with patch('src.services.task_runtime_service.publish_task_progress_message') as publish:
                updated = await service.mark_completed(task.id, ctx)

        assert updated.status == 'completed'
        assert updated.current_stage == TaskStage.MIXING.value
        assert updated.progress_percent == 100
        assert updated.output_audio_url == f'{task.id}/output/final_podcast.mp3'
        assert updated.error_message is None
        assert updated.finished_at is not None
        publish.assert_called_once()

    async def test_mark_completed_cleans_intermediates_and_clears_source(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        service = TaskRuntimeService(db_session)
        ctx = PipelineContext(
            task_id=str(task.id),
            source_audio_url='uploads/test/source.mp3',
            output_audio_url=f'{task.id}/output/final_podcast.mp3',
        )

        with patch('src.services.task_runtime_service.publish_task_progress_message'):
            with patch('src.services.task_runtime_service.ArtifactCleanupService') as CleanupService:
                with patch('src.services.task_runtime_service.StorageService') as Storage:
                    CleanupService.return_value.cleanup_task_intermediates = AsyncMock(return_value=3)
                    Storage.return_value.delete_object = AsyncMock()
                    updated = await service.mark_completed(task.id, ctx)

        await db_session.refresh(task)

        assert updated.status == 'completed'
        assert task.source_audio_url is None
        CleanupService.return_value.cleanup_task_intermediates.assert_awaited_once_with(task.id)
        Storage.return_value.delete_object.assert_awaited_once_with('uploads/test/source.mp3')

    async def test_persist_pipeline_state_writes_speakers_and_segments(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        service = TaskRuntimeService(db_session)
        ctx = PipelineContext(
            task_id=str(task.id),
            source_audio_url='uploads/test/source.mp3',
            source_language='en',
            target_language='zh',
            speakers=[
                {
                    'id': 'SPEAKER_00',
                    'label': 'SPEAKER_00',
                    'ref_audio_url': 'task/speakers/SPEAKER_00_ref.wav',
                }
            ],
            segments=[
                {
                    'speaker_id': 'SPEAKER_00',
                    'start': 0.0,
                    'end': 1.5,
                    'text': 'hello',
                    'translation': 'hello zh',
                }
            ],
            synth_segments=[
                {
                    'segment_id': 0,
                    'audio_url': 'task/synth/0.wav',
                }
            ],
        )

        await service.persist_pipeline_state(task.id, ctx)

        speakers = (await db_session.execute(select(Speaker).where(Speaker.task_id == task.id))).scalars().all()
        segments = (await db_session.execute(select(Segment).where(Segment.task_id == task.id))).scalars().all()

        assert len(speakers) == 1
        assert speakers[0].label == 'SPEAKER_00'
        assert len(segments) == 1
        assert segments[0].original_text == 'hello'
        assert segments[0].translated_text == 'hello zh'
        assert segments[0].synth_audio_url == 'task/synth/0.wav'
        await db_session.refresh(task)
        assert task.config['source_language'] == 'en'
        assert task.config['target_language'] == 'zh'

    async def test_build_pipeline_context_hydrates_persisted_state(self, db_session, mock_user):
        task = await create_task(db_session, mock_user.id)
        service = TaskRuntimeService(db_session)
        ctx = PipelineContext(
            task_id=str(task.id),
            source_audio_url='uploads/test/source.mp3',
            source_language='en',
            speakers=[
                {
                    'id': 'SPEAKER_00',
                    'label': 'SPEAKER_00',
                    'ref_audio_url': 'task/speakers/SPEAKER_00_ref.wav',
                }
            ],
            segments=[
                {
                    'speaker_id': 'SPEAKER_00',
                    'start': 0.0,
                    'end': 1.5,
                    'text': 'hello',
                    'translation': 'hello zh',
                    'synth_audio_url': 'task/synth/0.wav',
                }
            ],
        )

        await service.persist_pipeline_state(task.id, ctx)
        restored = await service.build_pipeline_context(task.id, 'uploads/test/source.mp3')

        assert restored.source_language == 'en'
        assert restored.target_language == 'zh'
        assert restored.speakers == [
            {
                'id': 'SPEAKER_00',
                'label': 'SPEAKER_00',
                'ref_audio_url': 'task/speakers/SPEAKER_00_ref.wav',
                'voice_embedding_url': None,
                'gender': None,
                'pitch_hz': None,
                'voice_provider': None,
                'voice_id': None,
                'voice_model': None,
                'enrollment_status': None,
                'fallback_reason': None,
            }
        ]
        assert restored.segments == [
            {
                'speaker_id': 'SPEAKER_00',
                'start': 0.0,
                'end': 1.5,
                'text': 'hello',
                'translation': 'hello zh',
                'synth_audio_url': 'task/synth/0.wav',
            }
        ]

    async def test_mark_paused_preserves_quota_and_stage_run(self, db_session, mock_user):
        mock_user.monthly_used = 1
        task = await create_task(db_session, mock_user.id)
        service = TaskRuntimeService(db_session)

        with patch('src.services.task_runtime_service.publish_task_progress_message'):
            await service.mark_stage_started(task.id, TaskStage.SYNTHESIZING)
            progressed = await service.mark_stage_progress(task.id, TaskStage.SYNTHESIZING, 80)
            updated = await service.mark_paused(
                task.id,
                TaskStage.SYNTHESIZING,
                'DashScope TTS provider is unavailable: Arrearage',
                pause_reason_code='provider_billing_required',
                provider_error_code='Arrearage',
            )

        await db_session.refresh(mock_user)
        runs = (
            await db_session.execute(select(TaskStageRun).where(TaskStageRun.task_id == task.id))
        ).scalars().all()

        assert updated.status == 'paused'
        assert updated.progress_percent == progressed.progress_percent
        assert updated.pause_reason_code == 'provider_billing_required'
        assert updated.provider_error_code == 'Arrearage'
        assert updated.paused_at is not None
        assert updated.finished_at is None
        assert mock_user.monthly_used == 1
        assert len(runs) == 1
        assert runs[0].status == 'paused'
        assert runs[0].error_code == 'Arrearage'


def test_truncate_task_error_message_preserves_database_limit():
    error_message = "x" * 1200

    truncated = truncate_task_error_message(error_message)

    assert truncated is not None
    assert len(truncated) == 1000
    assert truncated.endswith("...[truncated]")
