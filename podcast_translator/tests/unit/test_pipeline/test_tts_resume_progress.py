import sys
import types

from src.pipeline.context import PipelineContext

try:
    import dashscope  # noqa: F401
except ModuleNotFoundError:
    dashscope = types.ModuleType("dashscope")
    dashscope_audio = types.ModuleType("dashscope.audio")
    dashscope_tts_v2 = types.ModuleType("dashscope.audio.tts_v2")
    dashscope_tts_v2.SpeechSynthesizer = type("SpeechSynthesizer", (), {})
    dashscope_tts_v2.VoiceEnrollmentService = type("VoiceEnrollmentService", (), {})
    sys.modules["dashscope"] = dashscope
    sys.modules["dashscope.audio"] = dashscope_audio
    sys.modules["dashscope.audio.tts_v2"] = dashscope_tts_v2

try:
    import pydub  # noqa: F401
except ModuleNotFoundError:
    pydub = types.ModuleType("pydub")
    pydub.AudioSegment = type("AudioSegment", (), {})
    sys.modules["pydub"] = pydub

from src.pipeline.stages.s5_voice_clone_tts import CosyVoiceTTSStage, SynthUnit


def test_reused_tts_units_report_incremental_progress(monkeypatch):
    stage = CosyVoiceTTSStage()
    ctx = PipelineContext(
        task_id="task-1",
        source_audio_url="source.mp3",
        segments=[
            {
                "speaker_id": "SPEAKER_00",
                "start": float(index),
                "end": float(index + 1),
                "translation": f"text {index}",
                "synth_audio_url": f"task-1/synths/{index}.mp3",
            }
            for index in range(5)
        ],
    )
    units = [
        SynthUnit(
            segment_id=index,
            segment_ids=[index],
            speaker_id="SPEAKER_00",
            text=f"text {index}",
            start=float(index),
            end=float(index + 1),
        )
        for index in range(5)
    ]
    item_updates = []
    progress_updates = []

    monkeypatch.setattr("src.pipeline.stages.s5_voice_clone_tts.settings.PCT_TTS_BATCH_SIZE", 2)
    monkeypatch.setattr(stage, "_build_synth_units", lambda _segments: units)
    monkeypatch.setattr(
        stage,
        "_load_existing_synth_unit",
        lambda _ctx, unit, _temp_dir: {
            "segment_id": unit.segment_id,
            "segment_ids": unit.segment_ids,
            "audio_url": f"task-1/synths/{unit.segment_id}.mp3",
            "duration": 1.0,
            "speaker_id": unit.speaker_id,
            "tts_mode": "reused",
            "tts_voice": None,
        },
    )
    monkeypatch.setattr(
        stage,
        "_report_items_progress",
        lambda _ctx, **kwargs: item_updates.append(kwargs.get("items_done")),
    )
    monkeypatch.setattr(stage, "_report_progress", lambda _ctx, progress: progress_updates.append(progress))

    result = stage.process(ctx)

    assert len(result.synth_segments) == 5
    assert progress_updates == [40, 80, 100]
    assert item_updates[:2] == [2, 4]
    assert item_updates[-2:] == [5, 5]
