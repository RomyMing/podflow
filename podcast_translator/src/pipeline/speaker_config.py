"""Lightweight, dependency-free speaker-count helpers.

Shared by the diarization stage (``s2_speaker_diarization``) and the long-audio pipeline
(``long_audio``). Kept free of torch/pyannote imports so ``long_audio`` — which lazy-imports
the heavy stages — can resolve the speaker cap without pulling ML dependencies at import time.
"""

# Product cap for the current beta: 1–4 speakers (0 = auto-estimate).
MAX_INTERNAL_SPEAKERS = 4


def resolve_speaker_count_bounds(config: dict | None, *, relax_min: bool = False) -> tuple[int, int]:
    """Resolve (min_speakers, max_speakers) for diarization from ``config['speaker_count']``.

    - ``0`` (or missing) → auto-estimate within ``(1, MAX_INTERNAL_SPEAKERS)``.
    - fixed ``N`` (1–4) → ``(N, N)`` normally.
    - ``relax_min=True`` (used for long-audio per-chunk diarization) → ``(1, N)`` so a chunk
      where fewer speakers actually talk is not forced to invent phantom speakers; the final
      global speaker count is reconciled by the long-audio cross-chunk clustering.
    """
    raw_count = (config or {}).get("speaker_count", 0)
    try:
        speaker_count = int(raw_count or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("speaker_count must be an integer from 0 to 4.") from exc

    if speaker_count <= 0:
        return 1, MAX_INTERNAL_SPEAKERS
    if speaker_count > MAX_INTERNAL_SPEAKERS:
        raise ValueError("当前内测版最多支持 4 位说话人。")
    if relax_min:
        return 1, speaker_count
    return speaker_count, speaker_count
