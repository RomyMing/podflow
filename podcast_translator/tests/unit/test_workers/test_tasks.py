import uuid

from src.pipeline.context import TaskStage
from src.workers.tasks import WorkerTaskLifecycleHooks, _is_resumable_failure, _resolve_resume_stage


def test_soft_time_limit_failure_is_resumable():
    assert _is_resumable_failure("SoftTimeLimitExceeded()")


def test_regular_pipeline_failure_is_not_resumable():
    assert not _is_resumable_failure("translation failed")


def test_resume_stage_keeps_interrupted_stage():
    # A failure mid-TTS resumes at TTS, not from scratch.
    assert _resolve_resume_stage("voice_clone_tts") == TaskStage.SYNTHESIZING
    assert _resolve_resume_stage("translation") == TaskStage.TRANSLATING


def test_resume_stage_falls_back_to_separation_for_early_or_unknown_stages():
    assert _resolve_resume_stage("uploaded") == TaskStage.SEPARATING
    assert _resolve_resume_stage("preparing") == TaskStage.SEPARATING
    assert _resolve_resume_stage(None) == TaskStage.SEPARATING
    assert _resolve_resume_stage("bogus_stage") == TaskStage.SEPARATING


def test_lifecycle_hook_remembers_current_stage(monkeypatch):
    hooks = WorkerTaskLifecycleHooks(str(uuid.uuid4()))
    monkeypatch.setattr(hooks, "_run", lambda callback: None)

    hooks.on_stage_started(TaskStage.TRANSLATING)

    assert hooks.current_stage == TaskStage.TRANSLATING
