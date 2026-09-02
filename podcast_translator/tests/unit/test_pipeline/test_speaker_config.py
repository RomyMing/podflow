import pytest

from src.pipeline.speaker_config import MAX_INTERNAL_SPEAKERS, resolve_speaker_count_bounds


def test_auto_mode_uses_full_internal_range():
    assert resolve_speaker_count_bounds({"speaker_count": 0}) == (1, MAX_INTERNAL_SPEAKERS)
    assert resolve_speaker_count_bounds(None) == (1, MAX_INTERNAL_SPEAKERS)


def test_fixed_count_pins_min_and_max():
    assert resolve_speaker_count_bounds({"speaker_count": 3}) == (3, 3)


def test_relax_min_drops_min_but_keeps_cap_for_chunks():
    # Long-audio per-chunk diarization: a chunk with fewer active speakers must not be forced
    # to invent phantom ones, while the cap still bounds the reconciled global count.
    assert resolve_speaker_count_bounds({"speaker_count": 3}, relax_min=True) == (1, 3)
    assert resolve_speaker_count_bounds({"speaker_count": 0}, relax_min=True) == (1, MAX_INTERNAL_SPEAKERS)


def test_out_of_range_raises():
    with pytest.raises(ValueError):
        resolve_speaker_count_bounds({"speaker_count": 5})


def test_non_integer_raises():
    with pytest.raises(ValueError):
        resolve_speaker_count_bounds({"speaker_count": "abc"})
