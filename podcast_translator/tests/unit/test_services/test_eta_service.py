from datetime import datetime, timedelta, timezone

from src.pipeline.context import TaskStage
from src.services.eta_service import estimate_task_eta_seconds


class FakeStageRun:
    def __init__(self, *, stage, started_at, items_total=None, items_done=None):
        self.stage = stage
        self.started_at = started_at
        self.finished_at = None
        self.items_total = items_total
        self.items_done = items_done


def test_eta_returns_none_without_enough_signal():
    assert (
        estimate_task_eta_seconds(
            status="processing",
            current_stage=TaskStage.TRANSLATING.value,
            progress_percent=65,
            audio_duration=None,
            stage_runs=[],
        )
        is None
    )


def test_eta_uses_stage_items_progress():
    now = datetime.now(timezone.utc)
    run = FakeStageRun(
        stage=TaskStage.TRANSCRIBING.value,
        started_at=now - timedelta(seconds=20),
        items_total=10,
        items_done=2,
    )

    eta = estimate_task_eta_seconds(
        status="processing",
        current_stage=TaskStage.TRANSCRIBING.value,
        progress_percent=50,
        audio_duration=600,
        stage_runs=[run],
        now=now,
    )

    assert eta is not None
    assert eta >= 80


class FinishedStageRun:
    def __init__(self, *, stage, started_at, finished_at):
        self.stage = stage
        self.started_at = started_at
        self.finished_at = finished_at
        self.items_total = None
        self.items_done = None


def test_eta_self_adapts_from_measured_stage_durations():
    """A finished stage that ran 2x its GPU-baseline estimate should scale up the ETA for the
    remaining factor-based stages."""
    now = datetime.now(timezone.utc)
    # SEPARATING expected = 200 * 0.35 = 70s; actual = 140s -> realized multiplier ~2.0
    slow = FinishedStageRun(
        stage=TaskStage.SEPARATING.value,
        started_at=now - timedelta(seconds=210),
        finished_at=now - timedelta(seconds=70),
    )
    eta_adaptive = estimate_task_eta_seconds(
        status="processing",
        current_stage=TaskStage.TRANSLATING.value,
        progress_percent=70,
        audio_duration=200,
        stage_runs=[slow],
    )
    eta_baseline = estimate_task_eta_seconds(
        status="processing",
        current_stage=TaskStage.TRANSLATING.value,
        progress_percent=70,
        audio_duration=200,
        stage_runs=[],
    )
    assert eta_adaptive is not None and eta_baseline is not None
    assert eta_adaptive > eta_baseline * 1.8
