import math
from collections.abc import MutableMapping
from typing import Any


VOICE_GENDERS = {"male", "female"}


def _normal_gender(value: Any) -> str | None:
    gender = str(value or "").strip().lower()
    return gender if gender in VOICE_GENDERS else None


def _normal_pitch(value: Any) -> float | None:
    try:
        pitch = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(pitch) or pitch <= 0:
        return None
    return pitch


def ensure_mixed_fallback_genders(speakers: list[MutableMapping[str, Any]] | None) -> bool:
    """Ensure a two-speaker fallback voice pair does not collapse to one preset gender.

    Pitch-based gender is only a fallback for choosing preset TTS voices. When a
    two-person conversation is detected but both speakers land in the same
    coarse bucket, use their relative pitch to keep the output voices distinct.
    """
    if not speakers or len(speakers) != 2:
        return False

    genders = [_normal_gender(speaker.get("gender")) for speaker in speakers]
    if set(genders) == VOICE_GENDERS:
        return False

    if genders.count("male") == 1 and genders.count("female") == 0:
        changed = False
        for index, speaker in enumerate(speakers):
            if genders[index] is None:
                speaker["gender"] = "female"
                changed = True
        return changed

    if genders.count("female") == 1 and genders.count("male") == 0:
        changed = False
        for index, speaker in enumerate(speakers):
            if genders[index] is None:
                speaker["gender"] = "male"
                changed = True
        return changed

    pitched_speakers: list[tuple[float, MutableMapping[str, Any]]] = []
    for speaker in speakers:
        pitch = _normal_pitch(speaker.get("pitch_hz"))
        if pitch is None:
            return False
        pitched_speakers.append((pitch, speaker))

    if pitched_speakers[0][0] == pitched_speakers[1][0]:
        return False

    lower, higher = sorted(pitched_speakers, key=lambda item: item[0])
    changed = lower[1].get("gender") != "male" or higher[1].get("gender") != "female"
    lower[1]["gender"] = "male"
    higher[1]["gender"] = "female"
    return changed
