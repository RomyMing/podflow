import math

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("pyannote.audio")

from src.pipeline.stages.s2_speaker_diarization import (
    SpeakerDiarizationStage,
    build_reference_waveform,
    resolve_speaker_count_bounds,
)


def _tone(frequency_hz: float, sample_rate: int = 16_000, seconds: float = 40.0) -> torch.Tensor:
    samples = int(sample_rate * seconds)
    t = torch.arange(samples, dtype=torch.float32) / sample_rate
    return (0.4 * torch.sin(2 * math.pi * frequency_hz * t)).unsqueeze(0)


def test_resolve_speaker_count_bounds_supports_auto_and_internal_range():
    assert resolve_speaker_count_bounds({"speaker_count": 0}) == (1, 4)
    assert resolve_speaker_count_bounds({"speaker_count": 3}) == (3, 3)

    with pytest.raises(ValueError, match="最多支持 4 位"):
        resolve_speaker_count_bounds({"speaker_count": 5})


def test_build_reference_waveform_combines_clean_high_energy_slices():
    waveform = _tone(180)
    intervals = [
        (0.0, 4.0, 4.0),
        (6.0, 18.0, 12.0),
        (20.0, 36.0, 16.0),
    ]

    reference, selected = build_reference_waveform(intervals, waveform, 16_000)

    assert reference is not None
    duration = reference.shape[-1] / 16_000
    assert 10 <= duration <= 30.5
    assert selected


def test_embedding_load_failure_is_isolated_by_credential(monkeypatch):
    import pyannote.audio

    load_calls = []

    class FakeModel:
        @classmethod
        def from_pretrained(cls, _model_name, *, token=None, use_auth_token=None):
            credential = token or use_auth_token
            load_calls.append(credential)
            if credential == "denied-token":
                raise RuntimeError("model access denied")
            return cls()

        def to(self, _device):
            return self

    class FakeInference:
        def __init__(self, model, *, window):
            self.model = model
            self.window = window

    monkeypatch.setattr(pyannote.audio, "Model", FakeModel)
    monkeypatch.setattr(pyannote.audio, "Inference", FakeInference)
    monkeypatch.setattr(SpeakerDiarizationStage, "_embedding_cache", {})
    monkeypatch.setattr(SpeakerDiarizationStage, "_embedding_disabled_keys", set())

    assert SpeakerDiarizationStage._get_embedding_inference("denied-token") is None
    assert SpeakerDiarizationStage._get_embedding_inference("denied-token") is None
    allowed = SpeakerDiarizationStage._get_embedding_inference("allowed-token")

    assert isinstance(allowed, FakeInference)
    assert load_calls == ["denied-token", "allowed-token"]
