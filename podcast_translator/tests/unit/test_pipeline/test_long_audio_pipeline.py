import threading
import time
from pathlib import Path

import pytest

from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.long_audio import AudioChunk, LongAudioPipeline


def _chunk(
    index: int,
    core_start: float,
    core_end: float,
    *,
    padded_start: float | None = None,
    padded_end: float | None = None,
) -> AudioChunk:
    prefix = f"t/chunks/{index:04d}"
    return AudioChunk(
        index=index,
        core_start=core_start,
        core_end=core_end,
        padded_start=core_start if padded_start is None else padded_start,
        padded_end=core_end if padded_end is None else padded_end,
        source_url=f"{prefix}/source.wav",
        vocal_url=f"{prefix}/vocals.wav",
        background_url=f"{prefix}/background.wav",
        diarization_url=f"{prefix}/diarization.json",
        transcription_url=f"{prefix}/transcription.json",
        mixed_url=f"{prefix}/mixed.mp3",
    )


def test_chunk_front_half_pipeline_overlaps_adjacent_chunks(monkeypatch):
    pipeline = LongAudioPipeline()
    ctx = PipelineContext(task_id="task-1", source_audio_url="source.mp3", target_language="zh")
    chunks = pipeline._build_chunks("task-1", 1200.0)
    events = []
    event_lock = threading.Lock()
    diarization_payloads = {}

    monkeypatch.setattr("src.pipeline.long_audio.settings.PCT_CHUNK_PIPELINE_MAX_IN_FLIGHT", 2)
    monkeypatch.setattr("src.pipeline.long_audio.settings.PCT_CHUNK_PIPELINE_STAGE_WORKERS", 1)
    monkeypatch.setattr(pipeline, "_save_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "_persist_stage_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "_stage_started", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "_stage_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "_stage_items_progress", lambda *args, **kwargs: None)

    def record(name, index):
        with event_lock:
            events.append((name, index))

    def fake_split(ctx, source_path, chunk, invalidated):
        record("sep", chunk.index)

    def fake_diarize(ctx, chunk, invalidated):
        record("diarize", chunk.index)
        if chunk.index == 0:
            time.sleep(0.05)
        payload = {
            "speakers": [{"id": "SPEAKER_00", "label": "SPEAKER_00"}],
            "segments": [{"speaker_id": "SPEAKER_00", "start": 6.0, "end": 7.0}],
        }
        diarization_payloads[chunk.diarization_url] = payload
        return payload

    def fake_transcribe(ctx, chunk, diarization_payload, invalidated):
        record("transcribe", chunk.index)
        return {
            "source_language": "en",
            "segments": [{"speaker_id": "SPEAKER_00", "start": 6.0, "end": 7.0, "text": f"text {chunk.index}"}],
        }

    def fake_translate(ctx, chunk, segments, source_language):
        record("translate", segments[0]["text"] if segments else -1)
        for segment in segments:
            segment["translation"] = f"译文 {segment['text']}"

    monkeypatch.setattr(pipeline, "_ensure_chunk_split_and_separated", fake_split)
    monkeypatch.setattr(pipeline, "_ensure_chunk_diarized", fake_diarize)
    monkeypatch.setattr(pipeline, "_ensure_chunk_transcribed", fake_transcribe)
    monkeypatch.setattr(pipeline, "_translate_chunk_segments", fake_translate)
    monkeypatch.setattr(pipeline, "_load_json_object", lambda object_name: diarization_payloads.get(object_name))

    pipeline._run_chunk_front_half_pipeline(ctx, Path("source.mp3"), chunks, [])

    assert events.index(("sep", 1)) < events.index(("transcribe", 0))
    assert ctx.source_language == "en"
    assert [segment["text"] for segment in ctx.segments] == ["text 0", "text 1"]
    # Per-chunk translations performed during the front-half flow into the aggregated segments.
    assert [segment["translation"] for segment in ctx.segments] == ["译文 text 0", "译文 text 1"]


@pytest.mark.parametrize("start_stage", [TaskStage.SYNTHESIZING, TaskStage.ALIGNING, TaskStage.MIXING])
def test_downstream_resume_does_not_overlap_translation(monkeypatch, start_stage):
    pipeline = LongAudioPipeline(start_stage=start_stage)
    ctx = PipelineContext(task_id="t", source_audio_url="source.mp3")
    chunks = [_chunk(0, 0.0, 10.0)]
    calls = []

    monkeypatch.setattr(pipeline, "_save_manifest", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pipeline, "_ensure_chunk_split_and_separated", lambda *_args: None)
    monkeypatch.setattr(
        pipeline,
        "_ensure_chunk_diarized",
        lambda *_args: {"speakers": [], "segments": []},
    )
    monkeypatch.setattr(
        pipeline,
        "_ensure_chunk_transcribed",
        lambda *_args: {
            "source_language": "en",
            "segments": [{"speaker_id": "SPEAKER_00", "start": 1.0, "end": 2.0, "text": "hello"}],
        },
    )
    monkeypatch.setattr(pipeline, "_translate_chunk_segments", lambda *_args: calls.append(True))
    monkeypatch.setattr(pipeline, "_load_json_object", lambda _object_name: {"speakers": [], "segments": []})

    pipeline._run_chunk_front_half_pipeline(ctx, Path("source.mp3"), chunks, [])

    assert calls == []


def test_translation_resume_still_overlaps_translation(monkeypatch):
    pipeline = LongAudioPipeline(start_stage=TaskStage.TRANSLATING)
    ctx = PipelineContext(task_id="t", source_audio_url="source.mp3")
    chunks = [_chunk(0, 0.0, 10.0)]
    calls = []

    monkeypatch.setattr(pipeline, "_save_manifest", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pipeline, "_ensure_chunk_split_and_separated", lambda *_args: None)
    monkeypatch.setattr(
        pipeline,
        "_ensure_chunk_diarized",
        lambda *_args: {"speakers": [], "segments": []},
    )
    monkeypatch.setattr(
        pipeline,
        "_ensure_chunk_transcribed",
        lambda *_args: {
            "source_language": "en",
            "segments": [{"speaker_id": "SPEAKER_00", "start": 1.0, "end": 2.0, "text": "hello"}],
        },
    )
    monkeypatch.setattr(pipeline, "_translate_chunk_segments", lambda *_args: calls.append(True))
    monkeypatch.setattr(pipeline, "_load_json_object", lambda _object_name: {"speakers": [], "segments": []})

    pipeline._run_chunk_front_half_pipeline(ctx, Path("source.mp3"), chunks, [])

    assert calls == [True]


@pytest.mark.parametrize(
    ("start_stage", "needs_front_half", "needs_translation", "reports_preparing"),
    [
        (TaskStage.SEPARATING, True, True, False),
        (TaskStage.TRANSCRIBING, True, True, False),
        (TaskStage.TRANSLATING, False, True, False),
        (TaskStage.SYNTHESIZING, False, False, False),
        (TaskStage.ALIGNING, False, False, False),
        (TaskStage.MIXING, False, False, False),
    ],
)
def test_resume_stage_skips_completed_long_audio_phases(
    start_stage,
    needs_front_half,
    needs_translation,
    reports_preparing,
):
    pipeline = LongAudioPipeline(start_stage=start_stage)

    assert pipeline._needs_chunk_front_half() is needs_front_half
    assert pipeline._needs_translation() is needs_translation
    assert pipeline._reports_preparing_stage() is reports_preparing


def test_overlap_translation_only_translates_chunk_core_segments():
    pipeline = LongAudioPipeline()
    translated = []

    class FakeTranslationStage:
        def translate_segments(self, _ctx, segments, *, source_lang=None):
            translated.extend(segment["text"] for segment in segments)

    pipeline._translation_stage = FakeTranslationStage()
    chunk = _chunk(1, 10.0, 20.0, padded_start=8.0, padded_end=22.0)
    segments = [
        {"start": 0.0, "end": 1.0, "text": "left overlap"},
        {"start": 3.0, "end": 4.0, "text": "core"},
        {"start": 12.5, "end": 13.5, "text": "right overlap"},
    ]

    pipeline._translate_chunk_segments(
        PipelineContext(task_id="t", source_audio_url="source.mp3"),
        chunk,
        segments,
        "en",
    )

    assert translated == ["core"]


def test_chunk_contexts_propagate_user_id_and_config(monkeypatch):
    """Regression: per-chunk stage contexts must carry user_id (for per-user provider
    credentials like the gated Hugging Face token) and config (speaker_count, etc.).
    Missing user_id silently fell back to the system placeholder token -> 401 in diarization."""
    import sys
    import types
    import uuid

    captured = {}

    def fake_stage_module(modname, classname, key):
        mod = types.ModuleType(modname)

        class _FakeStage:
            def process(self, chunk_ctx):
                captured[key] = chunk_ctx
                return chunk_ctx

        setattr(mod, classname, _FakeStage)
        monkeypatch.setitem(sys.modules, modname, mod)

    fake_stage_module("src.pipeline.stages.s2_speaker_diarization", "SpeakerDiarizationStage", "diar")
    fake_stage_module("src.pipeline.stages.s3_asr_transcription", "ASRTranscriptionStage", "asr")
    fake_stage_module("src.pipeline.stages.s1_source_separation", "SourceSeparationStage", "sep")

    pipeline = LongAudioPipeline()
    monkeypatch.setattr(pipeline, "_load_json_object", lambda url: None)
    monkeypatch.setattr(pipeline, "_save_json_object", lambda *a, **k: None)

    uid = uuid.uuid4()
    cfg = {"speaker_count": 2, "target_language": "zh"}
    ctx = PipelineContext(task_id="t1", user_id=uid, source_audio_url="s.mp3", target_language="zh", config=cfg)
    chunk = pipeline._build_chunks("t1", 240.0)[0]

    pipeline._ensure_chunk_diarized(ctx, chunk, diarization_invalidated=True)
    pipeline._ensure_chunk_transcribed(ctx, chunk, {"speakers": [], "segments": []}, transcription_invalidated=True)

    for key in ("diar", "asr"):
        assert captured[key].user_id == uid, f"{key} chunk ctx missing user_id"
        # config (speaker_count, etc.) must still reach every per-chunk stage
        assert captured[key].config.get("speaker_count") == 2, f"{key} chunk ctx missing speaker_count"
        assert captured[key].config.get("target_language") == "zh", f"{key} chunk ctx missing config"

    # Per-chunk diarization relaxes min_speakers via chunk_diarization=True, on a *copy* of the
    # config; ASR receives the untouched config and the task's real config is never mutated.
    assert captured["diar"].config.get("chunk_diarization") is True
    assert "chunk_diarization" not in captured["asr"].config
    assert cfg == {"speaker_count": 2, "target_language": "zh"}, "task config must not be mutated"


def _ctx(speaker_count):
    return PipelineContext(task_id="t", source_audio_url="s.mp3", config={"speaker_count": speaker_count})


def test_resolve_global_speaker_cap_uses_config():
    pipeline = LongAudioPipeline()
    assert pipeline._resolve_global_speaker_cap(_ctx(3)) == 3
    assert pipeline._resolve_global_speaker_cap(_ctx(0)) == 4  # auto -> MAX_INTERNAL_SPEAKERS
    assert pipeline._resolve_global_speaker_cap(
        PipelineContext(task_id="t", source_audio_url="s.mp3", config=None)
    ) == 4


def test_embedding_similarity():
    pipeline = LongAudioPipeline()
    assert pipeline._embedding_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert pipeline._embedding_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert pipeline._embedding_similarity([1.0, 0.0], [1.0]) is None  # length mismatch
    assert pipeline._embedding_similarity(None, [1.0]) is None
    assert pipeline._embedding_similarity([0.0, 0.0], [1.0, 0.0]) is None  # zero vector


def test_map_chunk_speakers_matches_voice_across_chunks_by_embedding():
    """Embeddings keep identities stable even when local diarization ids and pitches are
    arranged so a pitch-only matcher would SWAP the two same-gender speakers."""
    pipeline = LongAudioPipeline()
    ctx = _ctx(2)
    global_speakers: dict[str, dict] = {}

    chunk0 = [
        {"id": "SPEAKER_00", "gender": "male", "pitch_hz": 120, "embedding": [1.0, 0.0, 0.0], "ref_audio_url": "a"},
        {"id": "SPEAKER_01", "gender": "male", "pitch_hz": 130, "embedding": [0.0, 1.0, 0.0], "ref_audio_url": "b"},
    ]
    assert pipeline._map_chunk_speakers(ctx, chunk0, global_speakers) == {
        "SPEAKER_00": "SPEAKER_00",
        "SPEAKER_01": "SPEAKER_01",
    }

    chunk1 = [
        {"id": "L0", "gender": "male", "pitch_hz": 128, "embedding": [0.98, 0.02, 0.0]},  # really speaker A
        {"id": "L1", "gender": "male", "pitch_hz": 122, "embedding": [0.02, 0.98, 0.0]},  # really speaker B
    ]
    assert pipeline._map_chunk_speakers(ctx, chunk1, global_speakers) == {"L0": "SPEAKER_00", "L1": "SPEAKER_01"}
    assert len(global_speakers) == 2


def test_map_chunk_speakers_caps_at_configured_speaker_count():
    pipeline = LongAudioPipeline()
    ctx = _ctx(2)
    global_speakers: dict[str, dict] = {}
    speakers = [
        {"id": "A", "embedding": [1.0, 0.0, 0.0]},
        {"id": "B", "embedding": [0.0, 1.0, 0.0]},
        {"id": "C", "embedding": [0.0, 0.0, 1.0]},  # third distinct voice must fold into an existing one
    ]
    mapping = pipeline._map_chunk_speakers(ctx, speakers, global_speakers)
    assert len(global_speakers) == 2
    assert mapping["A"] == "SPEAKER_00"
    assert mapping["B"] == "SPEAKER_01"
    assert mapping["C"] in {"SPEAKER_00", "SPEAKER_01"}


def test_map_chunk_speakers_auto_mode_allows_up_to_four():
    pipeline = LongAudioPipeline()
    ctx = _ctx(0)
    global_speakers: dict[str, dict] = {}
    speakers = [
        {"id": "A", "embedding": [1.0, 0.0, 0.0, 0.0]},
        {"id": "B", "embedding": [0.0, 1.0, 0.0, 0.0]},
        {"id": "C", "embedding": [0.0, 0.0, 1.0, 0.0]},
        {"id": "D", "embedding": [0.0, 0.0, 0.0, 1.0]},
    ]
    mapping = pipeline._map_chunk_speakers(ctx, speakers, global_speakers)
    assert len(global_speakers) == 4
    assert len(set(mapping.values())) == 4


def test_map_chunk_speakers_falls_back_to_pitch_without_embeddings():
    pipeline = LongAudioPipeline()
    ctx = _ctx(2)
    global_speakers: dict[str, dict] = {}
    pipeline._map_chunk_speakers(ctx, [{"id": "S0", "gender": "female", "pitch_hz": 210}], global_speakers)
    mapping = pipeline._map_chunk_speakers(ctx, [{"id": "LX", "gender": "female", "pitch_hz": 215}], global_speakers)
    assert mapping["LX"] == "SPEAKER_00"
    assert len(global_speakers) == 1


def test_three_speakers_stay_consistent_across_three_chunks():
    """180-min correctness: 3 voices with identical gender+pitch (so only embeddings can tell
    them apart) must map to the same 3 global ids across chunks, with shuffled local ids."""
    pipeline = LongAudioPipeline()
    ctx = _ctx(3)
    global_speakers: dict[str, dict] = {}
    base = {"A": [1.0, 0.0, 0.0], "B": [0.0, 1.0, 0.0], "C": [0.0, 0.0, 1.0]}
    chunk_local_ids = [
        {"A": "spk0", "B": "spk1", "C": "spk2"},
        {"A": "spk1", "B": "spk2", "C": "spk0"},
        {"A": "spk2", "B": "spk0", "C": "spk1"},
    ]
    global_for_true: dict[str, str] = {}
    for chunk_map in chunk_local_ids:
        speakers = [
            {"id": local_id, "embedding": list(base[true_id]), "gender": "male", "pitch_hz": 120}
            for true_id, local_id in chunk_map.items()
        ]
        mapping = pipeline._map_chunk_speakers(ctx, speakers, global_speakers)
        for true_id, local_id in chunk_map.items():
            global_for_true.setdefault(true_id, mapping[local_id])
            assert mapping[local_id] == global_for_true[true_id], "same voice must map to same global id"
    assert len(global_speakers) == 3
    assert len(set(global_for_true.values())) == 3
