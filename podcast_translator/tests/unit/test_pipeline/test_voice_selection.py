import math
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from src.core.provider_errors import TaskPausedError
from src.pipeline.context import PipelineContext
from src.pipeline.stages.s5_voice_clone_tts import CosyVoiceTTSStage, speaker_legacy_fallback_voice
from src.pipeline.voice_analysis import estimate_speaker_gender


def _sine_wave(frequency_hz: float, sample_rate: int = 16_000, seconds: float = 2.0) -> torch.Tensor:
    samples = int(sample_rate * seconds)
    t = torch.arange(samples, dtype=torch.float32) / sample_rate
    return (0.4 * torch.sin(2 * math.pi * frequency_hz * t)).unsqueeze(0)


def test_estimate_speaker_gender_classifies_low_pitch_as_male():
    gender, pitch_hz = estimate_speaker_gender(_sine_wave(120), 16_000)

    assert gender == "male"
    assert pitch_hz is not None
    assert 115 <= pitch_hz <= 125


def test_estimate_speaker_gender_avoids_second_harmonic_octave_error():
    sample_rate = 16_000
    samples = int(sample_rate * 2.0)
    t = torch.arange(samples, dtype=torch.float32) / sample_rate
    waveform = (
        (0.2 * torch.sin(2 * math.pi * 120 * t))
        + (1.0 * torch.sin(2 * math.pi * 240 * t))
    ).unsqueeze(0)

    gender, pitch_hz = estimate_speaker_gender(waveform, sample_rate)

    assert gender == "male"
    assert pitch_hz is not None
    assert 115 <= pitch_hz <= 125


def test_estimate_speaker_gender_classifies_high_pitch_as_female():
    gender, pitch_hz = estimate_speaker_gender(_sine_wave(220), 16_000)

    assert gender == "female"
    assert pitch_hz is not None
    assert 215 <= pitch_hz <= 225


def test_male_tts_fallback_keeps_legacy_voice_male(monkeypatch):
    calls = []

    class RecordingStage(CosyVoiceTTSStage):
        def _synthesize_with_voice(self, text: str, output_path: str, *, model: str, voice: str) -> None:
            calls.append((model, voice))
            if len(calls) == 1:
                raise RuntimeError("InvalidParameter")

    stage = RecordingStage()
    stage.api_key = "test-key"
    monkeypatch.setattr("src.pipeline.stages.s5_voice_clone_tts.settings.PCT_COSYVOICE_MODEL", "cosyvoice-v2")
    monkeypatch.setattr(
        "src.pipeline.stages.s5_voice_clone_tts.settings.PCT_COSYVOICE_FALLBACK_VOICE_MALE",
        "longxiaocheng_v2",
    )

    result = stage._synthesize_chunk(
        PipelineContext(task_id="task-1", source_audio_url="source.mp3"),
        "hello",
        "unused-out.mp3",
        {"id": "SPEAKER_00", "gender": "male"},
    )

    assert calls == [
        ("cosyvoice-v2", "longxiaocheng_v2"),
        ("cosyvoice-v1", "longxiaocheng"),
    ]
    assert result == {
        "mode": "legacy_fallback",
        "provider": "cosyvoice",
        "voice": "longxiaocheng",
        "model": "cosyvoice-v1",
    }
    assert speaker_legacy_fallback_voice("male") == "longxiaocheng"


def test_required_elevenlabs_tts_failure_pauses_task():
    class FailingElevenLabsProvider:
        def synthesize_to_file(self, **kwargs):
            raise RuntimeError("provider exploded")

    stage = CosyVoiceTTSStage()
    stage.elevenlabs_provider = FailingElevenLabsProvider()

    with pytest.raises(TaskPausedError) as exc_info:
        stage._synthesize_chunk(
            PipelineContext(task_id="task-1", source_audio_url="source.mp3"),
            "hello",
            "unused-out.mp3",
            {
                "id": "SPEAKER_00",
                "voice_provider": "elevenlabs",
                "voice_id": "voice-123",
                "voice_clone_mode": "required",
            },
        )

    assert exc_info.value.provider == "elevenlabs"
    assert exc_info.value.reason_code == "provider_unavailable"


def test_required_voice_clone_without_reference_pauses_task():
    stage = CosyVoiceTTSStage()
    ctx = PipelineContext(
        task_id="task-1",
        source_audio_url="source.mp3",
        config={"voice_clone_mode": "required", "voice_clone_provider": "elevenlabs"},
        speakers=[{"id": "SPEAKER_00", "label": "SPEAKER_00"}],
    )

    with pytest.raises(TaskPausedError) as exc_info:
        stage._build_speaker_profiles(ctx, temp_dir_path=Path("scratch"))

    assert exc_info.value.provider == "elevenlabs"
    assert exc_info.value.reason_code == "voice_reference_missing"
