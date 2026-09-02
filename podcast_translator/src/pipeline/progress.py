import math

from src.pipeline.context import TaskStage

# Relative wall-clock cost of each stage (fraction of audio duration on a GPU baseline).
# Kept in sync with eta_service.STAGE_DURATION_FACTORS so the progress bar advances roughly
# in proportion to real time instead of in equal-looking jumps.
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

# Stages whose processing time is dominated by an opaque external/ML call that does not
# emit per-item progress (Demucs separation, Whisper ASR, ffmpeg align/mix). For these the
# bar would otherwise freeze at the band start, so a heartbeat reports an elapsed-based
# estimate. Stages that DO report items (translation, TTS, and the chunked long-audio
# separation/diarization/transcription) are excluded.
OPAQUE_PROGRESS_STAGES: frozenset[TaskStage] = frozenset(
    {
        TaskStage.SEPARATING,
        TaskStage.DIARIZING,
        TaskStage.TRANSCRIBING,
        TaskStage.ALIGNING,
        TaskStage.MIXING,
    }
)


def _build_bands() -> tuple[dict[TaskStage, int], dict[TaskStage, int]]:
    """Distribute the 2..100 range across work stages proportionally to their duration
    factors, so each stage's bar width matches its expected share of wall-clock time."""
    work_stages = [
        TaskStage.PREPARING,
        TaskStage.SEPARATING,
        TaskStage.DIARIZING,
        TaskStage.TRANSCRIBING,
        TaskStage.TRANSLATING,
        TaskStage.SYNTHESIZING,
        TaskStage.ALIGNING,
        TaskStage.MIXING,
    ]
    span_start, span_end = 2, 100
    total = sum(STAGE_DURATION_FACTORS[s] for s in work_stages)
    start_map: dict[TaskStage, int] = {TaskStage.UPLOADED: 0}
    end_map: dict[TaskStage, int] = {TaskStage.UPLOADED: span_start}

    cursor = float(span_start)
    for stage in work_stages:
        start = cursor
        cursor += (span_end - span_start) * STAGE_DURATION_FACTORS[stage] / total
        start_map[stage] = int(round(start))
        end_map[stage] = int(round(cursor))
    # Force the final stage to land exactly on 100.
    end_map[work_stages[-1]] = 100

    start_map[TaskStage.COMPLETED] = 100
    end_map[TaskStage.COMPLETED] = 100
    start_map[TaskStage.FAILED] = 100
    end_map[TaskStage.FAILED] = 100
    return start_map, end_map


STAGE_PROGRESS, STAGE_END_PROGRESS = _build_bands()


def get_stage_progress(stage: TaskStage) -> int:
    return STAGE_PROGRESS.get(stage, 0)


def get_overall_progress(stage: TaskStage, stage_progress: int = 0) -> int:
    start = STAGE_PROGRESS.get(stage, 0)
    end = STAGE_END_PROGRESS.get(stage, start)
    bounded_stage_progress = max(0, min(int(stage_progress), 100))
    return min(100, start + round((end - start) * bounded_stage_progress / 100))


def get_stage_progress_from_overall(stage: TaskStage, overall_progress: int = 0) -> int:
    start = STAGE_PROGRESS.get(stage, 0)
    end = STAGE_END_PROGRESS.get(stage, start)
    if end <= start:
        return 100 if overall_progress >= end else 0

    bounded_overall = max(start, min(int(overall_progress), end))
    return max(0, min(100, round((bounded_overall - start) * 100 / (end - start))))


def estimate_stage_progress(
    stage: TaskStage,
    elapsed_seconds: float,
    audio_duration: float | None,
    *,
    multiplier: float = 1.0,
    cap: int = 95,
) -> int:
    """Elapsed-time based within-stage progress (0..cap) for opaque stages that emit no
    per-item progress. Never returns 100 so the bar only completes when the stage actually
    finishes. When the expected duration is known we extrapolate linearly; otherwise we use
    a bounded asymptotic curve so the bar still creeps forward."""
    if elapsed_seconds <= 0:
        return 0
    factor = STAGE_DURATION_FACTORS.get(stage, 0.0)
    expected = (audio_duration or 0.0) * factor * max(multiplier, 0.1)
    if expected > 0:
        pct = round(100.0 * elapsed_seconds / expected)
    else:
        # No audio duration yet: approach ~cap with a 2-minute time constant.
        pct = round(100.0 * (1.0 - math.exp(-elapsed_seconds / 120.0)))
    return max(0, min(cap, pct))
