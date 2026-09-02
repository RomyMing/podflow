from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.long_audio import LongAudioPipeline
from src.pipeline.progress import get_overall_progress, get_stage_progress_from_overall


def test_build_chunks_creates_padded_core_windows():
    pipeline = LongAudioPipeline()

    chunks = pipeline._build_chunks("task-1", 1800.0)

    assert len(chunks) == 3
    assert chunks[0].core_start == 0.0
    assert chunks[0].core_end == 600.0
    assert chunks[0].padded_start == 0.0
    assert chunks[0].padded_end == 605.0
    assert chunks[1].core_start == 600.0
    assert chunks[1].padded_start == 595.0
    assert chunks[1].padded_end == 1205.0


def test_segment_to_global_discards_overlap_duplicates_and_offsets_time():
    pipeline = LongAudioPipeline()
    chunk = pipeline._build_chunks("task-1", 1800.0)[1]

    kept = pipeline._segment_to_global(
        {"speaker_id": "SPEAKER_00", "start": 10.0, "end": 15.0, "text": "hello"},
        chunk,
        {"SPEAKER_00": "SPEAKER_00"},
    )
    duplicate = pipeline._segment_to_global(
        {"speaker_id": "SPEAKER_00", "start": 1.0, "end": 2.0, "text": "overlap"},
        chunk,
        {"SPEAKER_00": "SPEAKER_00"},
    )

    assert kept is not None
    assert kept["start"] == 605.0
    assert kept["end"] == 610.0
    assert duplicate is None


def test_speaker_mapping_keeps_two_local_speakers_distinct():
    pipeline = LongAudioPipeline()
    global_speakers = {}
    ctx = PipelineContext(task_id="t", source_audio_url="s.mp3", config={"speaker_count": 2})

    local_map = pipeline._map_chunk_speakers(
        ctx,
        [
            {"id": "SPEAKER_00", "gender": None, "pitch_hz": None},
            {"id": "SPEAKER_01", "gender": None, "pitch_hz": None},
        ],
        global_speakers,
    )

    assert local_map == {
        "SPEAKER_00": "SPEAKER_00",
        "SPEAKER_01": "SPEAKER_01",
    }
    assert len(global_speakers) == 2


def test_stage_progress_interpolates_within_stage_ranges():
    from src.pipeline.progress import STAGE_END_PROGRESS, STAGE_PROGRESS

    # Band boundaries map to 0% / 100% of the stage and back.
    assert get_overall_progress(TaskStage.SEPARATING, 0) == STAGE_PROGRESS[TaskStage.SEPARATING]
    assert get_overall_progress(TaskStage.SEPARATING, 100) == STAGE_END_PROGRESS[TaskStage.SEPARATING]
    assert get_overall_progress(TaskStage.MIXING, 100) == 100

    # A mid-stage value stays inside the stage's band.
    mid = get_overall_progress(TaskStage.SEPARATING, 50)
    assert STAGE_PROGRESS[TaskStage.SEPARATING] <= mid <= STAGE_END_PROGRESS[TaskStage.SEPARATING]

    # Inverse mapping round-trips at the band edges.
    assert get_stage_progress_from_overall(TaskStage.SYNTHESIZING, STAGE_PROGRESS[TaskStage.SYNTHESIZING]) == 0
    assert get_stage_progress_from_overall(TaskStage.SYNTHESIZING, STAGE_END_PROGRESS[TaskStage.SYNTHESIZING]) == 100


def test_merge_persisted_segment_fields_preserves_resume_artifacts():
    pipeline = LongAudioPipeline()

    current = [
        {"speaker_id": "SPEAKER_00", "start": 1.0, "end": 2.0, "text": "hello"},
        {"speaker_id": "SPEAKER_01", "start": 3.0, "end": 4.0, "text": "there"},
    ]
    persisted = [
        {
            "speaker_id": "SPEAKER_00",
            "start": 1.0,
            "end": 2.0,
            "text": "hello",
            "translation": "你好",
            "synth_audio_url": "task/synths/seg_0.mp3",
        },
        {
            "speaker_id": "SPEAKER_01",
            "start": 3.0,
            "end": 4.0,
            "text": "there",
            "translation": "那里",
        },
    ]

    merged = pipeline._merge_persisted_segment_fields(current, persisted)

    assert merged[0]["translation"] == "你好"
    assert merged[0]["synth_audio_url"] == "task/synths/seg_0.mp3"
    assert merged[1]["translation"] == "那里"


def test_estimate_stage_progress_for_opaque_stages():
    from src.pipeline.progress import estimate_stage_progress

    # SEPARATING expected = 200 * 0.35 = 70s; at half that, ~50%.
    assert estimate_stage_progress(TaskStage.SEPARATING, 35, 200, multiplier=1.0) == 50
    # Never reaches 100 even when way over the estimate (so the bar finishes only on completion).
    assert estimate_stage_progress(TaskStage.SEPARATING, 100000, 200, multiplier=1.0) == 95
    assert estimate_stage_progress(TaskStage.SEPARATING, 0, 200) == 0
    # No audio duration yet: still creeps forward but stays under the cap.
    creeping = estimate_stage_progress(TaskStage.TRANSCRIBING, 120, None)
    assert 0 < creeping < 95
