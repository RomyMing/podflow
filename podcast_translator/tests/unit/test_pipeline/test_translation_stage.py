import json
import types

import pytest

from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.checkpoint import apply_context_dict, context_to_dict
from src.pipeline.stages.s4_translation import TranslationBatchError, TranslationStage


def make_stage() -> TranslationStage:
    return object.__new__(TranslationStage)


def test_parse_translation_response_accepts_id_objects():
    stage = make_stage()
    raw = json.dumps(
        {
            "translations": [
                {"id": "0", "translation": "第一句"},
                {"index": 1, "translation": "第二句"},
            ]
        },
        ensure_ascii=False,
    )

    assert stage._parse_translation_response(raw, 2) == ["第一句", "第二句"]


def test_parse_translation_response_rejects_merged_segments():
    stage = make_stage()
    raw = json.dumps({"translations": ["第一句"]}, ensure_ascii=False)

    with pytest.raises(TranslationBatchError, match="Mismatch array lengths"):
        stage._parse_translation_response(raw, 2)


def test_translate_batch_splits_invalid_batch_without_original_fallback():
    stage = make_stage()
    calls = []

    async def fake_call_llm(texts, _system_prompt):
        calls.append(tuple(texts))
        if len(texts) > 1:
            return texts[:-1]
        return [f"译文：{texts[0]}"]

    stage._call_llm_for_batch = fake_call_llm

    originals = [
        "this is the first source sentence",
        "this is the second source sentence",
    ]
    translations = stage._translate_batch(originals, "prompt", "en", "zh", 0)

    assert translations == [
        "译文：this is the first source sentence",
        "译文：this is the second source sentence",
    ]
    assert translations[0] != originals[0]
    assert translations[1] != originals[1]
    assert calls.count(tuple(originals)) == 3


def test_translate_batch_raises_instead_of_falling_back_to_original():
    stage = make_stage()

    async def fake_call_llm(_texts, _system_prompt):
        return None

    stage._call_llm_for_batch = fake_call_llm

    with pytest.raises(RuntimeError, match="refusing to fall back to original text"):
        stage._translate_batch(["this should not become the translation"], "prompt", "en", "zh", 0)


def test_translate_segments_translates_in_place_and_is_idempotent():
    stage = make_stage()
    calls = []

    def fake_translate_batch(self, original_texts, _system_prompt, _source_lang, _target_lang, _batch_start):
        calls.append(tuple(original_texts))
        return [f"中文译文 {index}" for index, _text in enumerate(original_texts)]

    stage._translate_batch = types.MethodType(fake_translate_batch, stage)
    ctx = PipelineContext(task_id="t1", source_audio_url="t1/s.mp3", target_language="zh")
    segments = [
        {"text": "hello world this is one"},
        {"text": "another english sentence here"},
    ]

    changed = stage.translate_segments(ctx, segments, source_lang="en")

    assert changed is True
    assert segments[0]["translation"] == "中文译文 0"
    assert segments[1]["translation"] == "中文译文 1"
    # The per-slice path must not carry the whole-task downstream invalidation.
    assert ctx.synth_segments is None
    assert not ctx.invalidated_stages

    calls.clear()
    again = stage.translate_segments(ctx, segments, source_lang="en")

    assert again is False
    assert calls == []


def test_translate_segments_same_language_copies_text():
    stage = make_stage()
    ctx = PipelineContext(task_id="t1", source_audio_url="t1/s.mp3", target_language="en")
    segments = [{"text": "keep me as is"}]

    changed = stage.translate_segments(ctx, segments, source_lang="en")

    assert changed is True
    assert segments[0]["translation"] == "keep me as is"


def test_process_clears_downstream_artifacts_when_translation_reruns():
    stage = make_stage()

    def fake_translate_batch(self, original_texts, _system_prompt, _source_lang, _target_lang, _batch_start):
        return [f"中文译文 {index}" for index, _text in enumerate(original_texts)]

    stage._translate_batch = types.MethodType(fake_translate_batch, stage)
    ctx = PipelineContext(
        task_id="task-1",
        source_audio_url="task-1/source.mp3",
        source_language="en",
        target_language="zh",
        segments=[
            {
                "text": "this segment is already translated",
                "translation": "这一段已经翻译好了",
                "synth_audio_url": "task-1/synths/seg_0.mp3",
            },
            {
                "text": "this used to have stale generated audio",
                "translation": "this used to have stale generated audio",
                "synth_audio_url": "task-1/synths/seg_1.mp3",
            }
        ],
        synth_segments=[
            {"segment_id": 0, "audio_url": "task-1/synths/seg_0.mp3"},
            {"segment_id": 1, "audio_url": "task-1/synths/seg_1.mp3"},
        ],
        output_audio_url="task-1/output/final_podcast.mp3",
    )

    result = stage.process(ctx)

    assert result.segments[0]["translation"] == "这一段已经翻译好了"
    assert result.segments[0]["synth_audio_url"] == "task-1/synths/seg_0.mp3"
    assert result.segments[1]["translation"] == "中文译文 0"
    assert "synth_audio_url" not in result.segments[1]
    assert result.synth_segments is None
    assert result.output_audio_url is None
    assert TaskStage.SYNTHESIZING.value in result.invalidated_stages
    assert TaskStage.ALIGNING.value in result.invalidated_stages
    assert TaskStage.MIXING.value in result.invalidated_stages

    payload = context_to_dict(result)
    assert isinstance(payload["invalidated_stages"], list)

    restored = PipelineContext(task_id="task-1", source_audio_url="task-1/source.mp3")
    apply_context_dict(restored, payload)
    assert isinstance(restored.invalidated_stages, set)
    assert TaskStage.MIXING.value in restored.invalidated_stages
