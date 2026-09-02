from src.pipeline.speaker_gender import ensure_mixed_fallback_genders


def test_two_speaker_fallback_genders_are_balanced_by_relative_pitch():
    speakers = [
        {"id": "SPEAKER_00", "gender": "male", "pitch_hz": 137.4},
        {"id": "SPEAKER_01", "gender": "male", "pitch_hz": 127.1},
    ]

    changed = ensure_mixed_fallback_genders(speakers)

    assert changed is True
    assert speakers == [
        {"id": "SPEAKER_00", "gender": "female", "pitch_hz": 137.4},
        {"id": "SPEAKER_01", "gender": "male", "pitch_hz": 127.1},
    ]


def test_two_speaker_fallback_genders_leave_existing_pair_unchanged():
    speakers = [
        {"id": "SPEAKER_00", "gender": "female", "pitch_hz": 210.0},
        {"id": "SPEAKER_01", "gender": "male", "pitch_hz": 120.0},
    ]

    changed = ensure_mixed_fallback_genders(speakers)

    assert changed is False
    assert speakers[0]["gender"] == "female"
    assert speakers[1]["gender"] == "male"
