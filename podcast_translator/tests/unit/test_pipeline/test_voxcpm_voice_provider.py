from pathlib import Path

from src.pipeline.voice_providers import VoxCpmVoiceProvider


class FakeVoxCpmModel:
    def __init__(self):
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return [0.0, 0.1, -0.1]  # stand-in waveform


def test_voxcpm_provider_synthesizes_from_reference(monkeypatch):
    fake_model = FakeVoxCpmModel()
    # Avoid importing the heavy voxcpm package or loading any real model.
    monkeypatch.setattr(VoxCpmVoiceProvider, "_get_model", classmethod(lambda cls, model_id: fake_model))

    written = {}

    def fake_export(self, wav, sample_rate, output_path):
        written["wav"] = wav
        written["sample_rate"] = sample_rate
        Path(output_path).write_bytes(b"mp3-bytes")

    # Stub the soundfile/ffmpeg conversion so the test needs no native deps.
    monkeypatch.setattr(VoxCpmVoiceProvider, "_export_mp3", fake_export)

    provider = VoxCpmVoiceProvider()
    scratch = Path("scratch")
    scratch.mkdir(exist_ok=True)
    reference = scratch / "voxcpm_ref_test.wav"
    output = scratch / "voxcpm_out_test.mp3"
    try:
        reference.write_bytes(b"wav")
        provider.synthesize_to_file(
            text="你好，欢迎收听。",
            prompt_wav_path=str(reference),
            output_path=str(output),
        )

        assert output.read_bytes() == b"mp3-bytes"
        assert written["sample_rate"] == VoxCpmVoiceProvider.SAMPLE_RATE
        assert len(fake_model.calls) == 1
        call = fake_model.calls[0]
        assert call["text"] == "你好，欢迎收听。"
        assert call["prompt_wav_path"] == str(reference)
        # prompt_text is omitted when not supplied (zero-shot, audio-only clone).
        assert "prompt_text" not in call
    finally:
        reference.unlink(missing_ok=True)
        output.unlink(missing_ok=True)


def test_voxcpm_provider_passes_prompt_text_when_given(monkeypatch):
    fake_model = FakeVoxCpmModel()
    monkeypatch.setattr(VoxCpmVoiceProvider, "_get_model", classmethod(lambda cls, model_id: fake_model))
    monkeypatch.setattr(
        VoxCpmVoiceProvider,
        "_export_mp3",
        lambda self, wav, sample_rate, output_path: Path(output_path).write_bytes(b"mp3"),
    )

    provider = VoxCpmVoiceProvider()
    scratch = Path("scratch")
    scratch.mkdir(exist_ok=True)
    reference = scratch / "voxcpm_ref_pt.wav"
    output = scratch / "voxcpm_out_pt.mp3"
    try:
        reference.write_bytes(b"wav")
        provider.synthesize_to_file(
            text="target",
            prompt_wav_path=str(reference),
            output_path=str(output),
            prompt_text="reference transcript",
        )
        assert fake_model.calls[0]["prompt_text"] == "reference transcript"
    finally:
        reference.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
