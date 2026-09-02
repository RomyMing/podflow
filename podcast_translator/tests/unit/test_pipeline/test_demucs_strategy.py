from src.config import settings
from src.pipeline.strategies.separation.demucs import DemucsStrategy


def test_demucs_command_uses_memory_safe_defaults():
    cmd = DemucsStrategy()._build_command("/tmp/in.wav", "/tmp/out", settings.PCT_DEMUCS_MODEL)

    joined = " ".join(cmd)
    assert "-n htdemucs" in joined
    assert "--two-stems=vocals" in joined
    # Memory guards present by default.
    assert "--segment" in cmd
    assert "-j" in cmd
    # Device not forced by default (autodetect).
    assert "-d" not in cmd
    # Audio path is the final positional argument.
    assert cmd[-1] == "/tmp/in.wav"


def test_demucs_command_respects_overrides(monkeypatch):
    monkeypatch.setattr(settings, "PCT_DEMUCS_SEGMENT_SECONDS", 0)
    monkeypatch.setattr(settings, "PCT_DEMUCS_JOBS", 0)
    monkeypatch.setattr(settings, "PCT_DEMUCS_DEVICE", "cpu")

    cmd = DemucsStrategy()._build_command("/tmp/in.wav", "/tmp/out", "htdemucs_ft")

    # Segment/jobs omitted when non-positive; device passed when set.
    assert "--segment" not in cmd
    assert "-j" not in cmd
    assert cmd[cmd.index("-d") + 1] == "cpu"
    assert cmd[cmd.index("-n") + 1] == "htdemucs_ft"
