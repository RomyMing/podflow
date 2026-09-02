from datetime import datetime, timezone
from typing import Iterable

from src.config import settings
from src.pipeline.context import TaskStage
from src.pipeline.progress import get_stage_progress_from_overall

# Clamp the learned/configured speed multiplier to a sane band so one weird stage timing
# cannot produce absurd ETAs.
_MULTIPLIER_MIN = 0.1
_MULTIPLIER_MAX = 50.0


ACTIVE_STATUSES = {"pending", "processing"}
ETA_MAX_SECONDS = 7 * 24 * 60 * 60

STAGE_DURATION_FACTORS: dict[TaskStage, float] = {
    TaskStage.PREPARING: 0.02,
    TaskStage.SEPARATING: 0.35,
    TaskStage.DIARIZING: 0.30,
    TaskStage.TRANSCRIBING: 0.25,
    TaskStage.TRANSLATING: 0.04,
    TaskStage.SYNTHESIZING: 0.25,
    TaskStage.ALIGNING: 0.03,
    TaskStage.MIXING: 0.08,
}

STAGE_ORDER: tuple[TaskStage, ...] = (
    TaskStage.PREPARING,
    TaskStage.SEPARATING,
    TaskStage.DIARIZING,
    TaskStage.TRANSCRIBING,
    TaskStage.TRANSLATING,
    TaskStage.SYNTHESIZING,
    TaskStage.ALIGNING,
    TaskStage.MIXING,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _bounded_eta(seconds: float | None) -> float | None:
    if seconds is None:
        return None
    if seconds < 0:
        return 0.0
    return float(min(seconds, ETA_MAX_SECONDS))


def _adaptive_multiplier(stage_runs: Iterable[object] | None, audio_duration: float | None) -> float:
    """Self-calibrating speed factor: compare how long finished stages actually took versus
    their GPU-baseline estimate (audio_duration * factor). Falls back to the configured
    multiplier when there is not enough measured data yet (e.g. CPU-only boxes set it high)."""
    configured = float(getattr(settings, "PCT_ETA_DURATION_MULTIPLIER", 1.0) or 1.0)
    if not audio_duration or audio_duration <= 0:
        return max(_MULTIPLIER_MIN, min(configured, _MULTIPLIER_MAX))

    actual_total = 0.0
    expected_total = 0.0
    for run in stage_runs or []:
        started_at = _as_aware(getattr(run, "started_at", None))
        finished_at = _as_aware(getattr(run, "finished_at", None))
        if started_at is None or finished_at is None:
            continue
        try:
            stage = TaskStage(getattr(run, "stage", None))
        except ValueError:
            continue
        factor = STAGE_DURATION_FACTORS.get(stage, 0.0)
        if factor <= 0:
            continue
        actual_total += max(0.0, (finished_at - started_at).total_seconds())
        expected_total += audio_duration * factor

    if expected_total <= 0 or actual_total <= 0:
        return max(_MULTIPLIER_MIN, min(configured, _MULTIPLIER_MAX))
    return max(_MULTIPLIER_MIN, min(actual_total / expected_total, _MULTIPLIER_MAX))


def _find_active_stage_run(stage_runs: Iterable[object] | None, stage: TaskStage) -> object | None:
    candidates = [
        run
        for run in (stage_runs or [])
        if getattr(run, "stage", None) == stage.value
        and getattr(run, "finished_at", None) is None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda run: getattr(run, "started_at", None) or datetime.min)


def estimate_task_eta_seconds(
    *,
    status: str,
    current_stage: str | None,
    progress_percent: int,
    audio_duration: float | None,
    stage_runs: Iterable[object] | None = None,
    now: datetime | None = None,
) -> float | None:
    if status not in ACTIVE_STATUSES or not current_stage:
        return None

    try:
        stage = TaskStage(current_stage)
    except ValueError:
        return None
    if stage not in STAGE_ORDER:
        return None

    now = _as_aware(now) or _utc_now()
    multiplier = _adaptive_multiplier(stage_runs, audio_duration)
    stage_progress = get_stage_progress_from_overall(stage, progress_percent)
    active_run = _find_active_stage_run(stage_runs, stage)
    elapsed_seconds: float | None = None
    if active_run is not None:
        started_at = _as_aware(getattr(active_run, "started_at", None))
        if started_at is not None:
            elapsed_seconds = max(0.0, (now - started_at).total_seconds())

    current_remaining: float | None = None
    if active_run is not None and elapsed_seconds is not None:
        items_total = getattr(active_run, "items_total", None)
        items_done = getattr(active_run, "items_done", None)
        if items_total and items_done and items_total > 0 and items_done > 0:
            estimated_total = elapsed_seconds * float(items_total) / float(items_done)
            current_remaining = max(0.0, estimated_total - elapsed_seconds)
        elif stage_progress > 0:
            estimated_total = elapsed_seconds * 100.0 / float(stage_progress)
            current_remaining = max(0.0, estimated_total - elapsed_seconds)

    if current_remaining is None and audio_duration and audio_duration > 0:
        factor = STAGE_DURATION_FACTORS.get(stage, 0.0)
        current_remaining = audio_duration * factor * multiplier * max(0, 100 - stage_progress) / 100.0

    stage_index = STAGE_ORDER.index(stage)
    future_remaining = 0.0
    if audio_duration and audio_duration > 0:
        for future_stage in STAGE_ORDER[stage_index + 1:]:
            future_remaining += audio_duration * STAGE_DURATION_FACTORS.get(future_stage, 0.0) * multiplier

    if current_remaining is None and future_remaining <= 0:
        return None
    return _bounded_eta((current_remaining or 0.0) + future_remaining)
