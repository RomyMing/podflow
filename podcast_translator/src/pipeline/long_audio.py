import json
import logging
import math
import subprocess
import tempfile
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.config import settings
from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.pause import raise_if_user_paused
from src.pipeline.speaker_config import MAX_INTERNAL_SPEAKERS, resolve_speaker_count_bounds
from src.pipeline.utils import run_sync
from src.services.storage_service import StorageService

logger = logging.getLogger(__name__)

# Cosine-similarity threshold for treating two speaker embeddings as the same person across
# chunks. Embeddings are L2-normalized in s2, so a plain cosine score in [-1, 1] applies.
SPEAKER_EMBEDDING_MATCH_THRESHOLD = 0.75


@dataclass
class AudioChunk:
    index: int
    core_start: float
    core_end: float
    padded_start: float
    padded_end: float
    source_url: str
    vocal_url: str
    background_url: str
    diarization_url: str
    transcription_url: str
    mixed_url: str

    @property
    def padded_duration(self) -> float:
        return max(0.0, self.padded_end - self.padded_start)

    @property
    def core_duration(self) -> float:
        return max(0.0, self.core_end - self.core_start)

    @property
    def pad_left(self) -> float:
        return max(0.0, self.core_start - self.padded_start)


class LongAudioPipeline:
    def __init__(self, start_stage: TaskStage = TaskStage.SEPARATING):
        self.start_stage = start_stage
        self.storage_service = StorageService()
        self._translation_stage: Any = None

    def _needs_chunk_front_half(self) -> bool:
        return self.start_stage in {
            TaskStage.UPLOADED,
            TaskStage.PREPARING,
            TaskStage.SEPARATING,
            TaskStage.DIARIZING,
            TaskStage.TRANSCRIBING,
        }

    def _needs_translation(self) -> bool:
        return self._needs_chunk_front_half() or self.start_stage == TaskStage.TRANSLATING

    def _reports_preparing_stage(self) -> bool:
        return self.start_stage in {TaskStage.UPLOADED, TaskStage.PREPARING}

    def execute_task(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.source_audio_url:
            raise ValueError(f"Task {ctx.task_id}: source_audio_url is missing.")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            source_ext = Path(ctx.source_audio_url).suffix or ".mp3"
            local_source_path = temp_dir_path / f"source{source_ext}"

            report_preparing = self._reports_preparing_stage()
            if report_preparing:
                self._stage_started(ctx, TaskStage.PREPARING)
            run_sync(self.storage_service.download_file(ctx.source_audio_url, str(local_source_path)))
            duration = probe_audio_duration(str(local_source_path))
            if duration <= 0:
                raise RuntimeError("Could not determine source audio duration.")
            if duration > settings.PCT_MAX_AUDIO_DURATION_SECONDS:
                max_minutes = settings.PCT_MAX_AUDIO_DURATION_SECONDS // 60
                raise RuntimeError(f"Audio duration exceeds the {max_minutes} minute limit.")

            is_long_audio = duration >= settings.PCT_LONG_AUDIO_THRESHOLD_SECONDS
            self._audio_prepared(
                ctx,
                duration,
                {
                    "source_duration_seconds": duration,
                    "long_audio_pipeline": is_long_audio,
                },
            )

            if not is_long_audio:
                if report_preparing:
                    self._stage_progress(ctx, TaskStage.PREPARING, 100)
                short_start_stage = (
                    TaskStage.SEPARATING
                    if self.start_stage in {TaskStage.UPLOADED, TaskStage.PREPARING}
                    else self.start_stage
                )
                from src.pipeline.orchestrator import PodcastTranslatorPipeline

                return PodcastTranslatorPipeline(start_stage=short_start_stage).execute_task(ctx)

            chunks = self._build_chunks(ctx.task_id, duration)
            self._save_manifest(ctx, chunks, duration, "prepared")
            if report_preparing:
                self._stage_progress(ctx, TaskStage.PREPARING, 100)

            persisted_segments = list(ctx.segments or [])
            if self._needs_chunk_front_half():
                self._run_chunk_front_half_pipeline(ctx, local_source_path, chunks, persisted_segments)

            if self._needs_translation():
                from src.pipeline.stages.s4_translation import TranslationStage

                self._run_stage(ctx, TaskStage.TRANSLATING, lambda: TranslationStage().process(ctx))
                self._persist_stage_state(ctx, TaskStage.TRANSLATING)

            from src.pipeline.stages.s5_voice_clone_tts import CosyVoiceTTSStage

            self._run_stage(ctx, TaskStage.SYNTHESIZING, lambda: CosyVoiceTTSStage().process(ctx))
            self._persist_stage_state(ctx, TaskStage.SYNTHESIZING)

            from src.pipeline.stages.s6_temporal_alignment import TemporalAlignmentStage

            self._run_stage(ctx, TaskStage.ALIGNING, lambda: TemporalAlignmentStage().process(ctx))
            self._persist_stage_state(ctx, TaskStage.ALIGNING)

            self._run_stage(ctx, TaskStage.MIXING, lambda: self._mix_chunks(ctx, chunks, temp_dir_path))
            self._persist_stage_state(ctx, TaskStage.MIXING)

        return ctx

    def _build_chunks(self, task_id: str, duration: float) -> list[AudioChunk]:
        chunk_seconds = max(60, settings.PCT_AUDIO_CHUNK_SECONDS)
        overlap_seconds = max(0, min(settings.PCT_AUDIO_CHUNK_OVERLAP_SECONDS, chunk_seconds // 4))
        chunk_count = max(1, math.ceil(duration / chunk_seconds))
        chunks: list[AudioChunk] = []
        for index in range(chunk_count):
            core_start = float(index * chunk_seconds)
            core_end = min(float(duration), float((index + 1) * chunk_seconds))
            padded_start = max(0.0, core_start - overlap_seconds)
            padded_end = min(float(duration), core_end + overlap_seconds)
            prefix = f"{task_id}/chunks/{index:04d}"
            chunks.append(
                AudioChunk(
                    index=index,
                    core_start=core_start,
                    core_end=core_end,
                    padded_start=padded_start,
                    padded_end=padded_end,
                    source_url=f"{prefix}/source.wav",
                    vocal_url=f"{prefix}/vocals.wav",
                    background_url=f"{prefix}/no_vocals.wav",
                    diarization_url=f"{prefix}/diarization.json",
                    transcription_url=f"{prefix}/transcription.json",
                    mixed_url=f"{prefix}/mixed.mp3",
                )
            )
        return chunks

    def _run_chunk_front_half_pipeline(
        self,
        ctx: PipelineContext,
        source_path: Path,
        chunks: list[AudioChunk],
        persisted_segments: list[dict],
    ) -> None:
        if not chunks:
            return

        invalidated_stages = getattr(ctx, "invalidated_stages", set()) or set()
        separation_invalidated = TaskStage.SEPARATING.value in invalidated_stages
        diarization_invalidated = separation_invalidated or TaskStage.DIARIZING.value in invalidated_stages
        transcription_invalidated = diarization_invalidated or TaskStage.TRANSCRIBING.value in invalidated_stages
        if separation_invalidated:
            invalidated_stages.update(
                {
                    TaskStage.DIARIZING.value,
                    TaskStage.TRANSCRIBING.value,
                    TaskStage.TRANSLATING.value,
                    TaskStage.SYNTHESIZING.value,
                    TaskStage.ALIGNING.value,
                    TaskStage.MIXING.value,
                }
            )
        elif diarization_invalidated:
            invalidated_stages.update(
                {
                    TaskStage.TRANSCRIBING.value,
                    TaskStage.TRANSLATING.value,
                    TaskStage.SYNTHESIZING.value,
                    TaskStage.ALIGNING.value,
                    TaskStage.MIXING.value,
                }
            )
        elif transcription_invalidated:
            invalidated_stages.update(
                {
                    TaskStage.TRANSLATING.value,
                    TaskStage.SYNTHESIZING.value,
                    TaskStage.ALIGNING.value,
                    TaskStage.MIXING.value,
                }
            )

        max_in_flight = max(1, int(settings.PCT_CHUNK_PIPELINE_MAX_IN_FLIGHT))
        stage_workers = max(1, int(settings.PCT_CHUNK_PIPELINE_STAGE_WORKERS))
        # A downstream resume already has translations in persisted task state. Do not call
        # the provider on raw chunk artifacts before those persisted fields are merged back.
        overlap_translation = bool(settings.PCT_OVERLAP_TRANSLATION_WITH_FRONT_HALF) and self.start_stage in {
            TaskStage.UPLOADED,
            TaskStage.PREPARING,
            TaskStage.SEPARATING,
            TaskStage.DIARIZING,
            TaskStage.TRANSCRIBING,
            TaskStage.TRANSLATING,
        }
        translation_futures: list[Future] = []
        self._stage_started(ctx, TaskStage.SEPARATING)
        self._stage_items_progress(ctx, TaskStage.SEPARATING, items_total=len(chunks), items_done=0)

        next_chunk_index = 0
        completed_chunks = 0
        stage_started = {
            TaskStage.DIARIZING: False,
            TaskStage.TRANSCRIBING: False,
        }
        stage_done_counts = {
            TaskStage.SEPARATING: 0,
            TaskStage.DIARIZING: 0,
            TaskStage.TRANSCRIBING: 0,
        }
        stage_done_indices: dict[TaskStage, set[int]] = {
            TaskStage.SEPARATING: set(),
            TaskStage.DIARIZING: set(),
            TaskStage.TRANSCRIBING: set(),
        }
        reported_completed: set[TaskStage] = set()
        diarization_payloads: dict[int, dict] = {}
        transcription_payloads: dict[int, dict] = {}
        futures: dict[Future, tuple[TaskStage, AudioChunk]] = {}

        def submit_separation(executor: ThreadPoolExecutor, chunk: AudioChunk) -> None:
            future = executor.submit(
                self._ensure_chunk_split_and_separated,
                ctx,
                source_path,
                chunk,
                separation_invalidated,
            )
            futures[future] = (TaskStage.SEPARATING, chunk)

        with (
            ThreadPoolExecutor(max_workers=stage_workers, thread_name_prefix="pct-chunk-separate") as separation_pool,
            ThreadPoolExecutor(max_workers=stage_workers, thread_name_prefix="pct-chunk-diarize") as diarization_pool,
            ThreadPoolExecutor(max_workers=stage_workers, thread_name_prefix="pct-chunk-transcribe") as transcription_pool,
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="pct-chunk-translate") as translation_pool,
        ):
            while next_chunk_index < len(chunks) and next_chunk_index < max_in_flight:
                submit_separation(separation_pool, chunks[next_chunk_index])
                next_chunk_index += 1

            while futures:
                if overlap_translation:
                    self._raise_on_translation_failure(ctx, translation_futures, pending_futures=futures)
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    stage, chunk = futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        self._stage_failed(ctx, stage, str(exc))
                        for pending in futures:
                            pending.cancel()
                        raise

                    stage_done_counts[stage] += 1
                    stage_done_indices[stage].add(chunk.index)
                    update_task_progress = (
                        stage == TaskStage.TRANSCRIBING
                        or (stage == TaskStage.DIARIZING and not stage_started[TaskStage.TRANSCRIBING])
                        or (stage == TaskStage.SEPARATING and not stage_started[TaskStage.DIARIZING])
                    )
                    self._report_chunk_stage_progress(
                        ctx,
                        stage,
                        chunks,
                        stage_done_indices[stage],
                        chunk,
                        update_task_progress=update_task_progress,
                    )

                    if stage == TaskStage.SEPARATING:
                        if not stage_started[TaskStage.DIARIZING]:
                            self._stage_started(ctx, TaskStage.DIARIZING)
                            self._stage_items_progress(ctx, TaskStage.DIARIZING, items_total=len(chunks), items_done=0)
                            stage_started[TaskStage.DIARIZING] = True
                        diarization_future = diarization_pool.submit(
                            self._ensure_chunk_diarized,
                            ctx,
                            chunk,
                            diarization_invalidated,
                        )
                        futures[diarization_future] = (TaskStage.DIARIZING, chunk)
                    elif stage == TaskStage.DIARIZING:
                        diarization_payloads[chunk.index] = result
                        if not stage_started[TaskStage.TRANSCRIBING]:
                            self._stage_started(ctx, TaskStage.TRANSCRIBING)
                            self._stage_items_progress(ctx, TaskStage.TRANSCRIBING, items_total=len(chunks), items_done=0)
                            stage_started[TaskStage.TRANSCRIBING] = True
                        transcription_future = transcription_pool.submit(
                            self._ensure_chunk_transcribed,
                            ctx,
                            chunk,
                            result,
                            transcription_invalidated,
                        )
                        futures[transcription_future] = (TaskStage.TRANSCRIBING, chunk)
                    elif stage == TaskStage.TRANSCRIBING:
                        transcription_payloads[chunk.index] = result
                        if overlap_translation:
                            translation_futures.append(
                                translation_pool.submit(
                                    self._translate_chunk_segments,
                                    ctx,
                                    chunk,
                                    result.get("segments") or [],
                                    result.get("source_language"),
                                )
                            )
                        completed_chunks += 1
                        if next_chunk_index < len(chunks):
                            submit_separation(separation_pool, chunks[next_chunk_index])
                            next_chunk_index += 1

                    if (
                        stage == TaskStage.SEPARATING
                        and stage_done_counts[TaskStage.SEPARATING] == len(chunks)
                        and stage not in reported_completed
                    ):
                        self._complete_chunk_pipeline_stage(
                            ctx,
                            chunks,
                            TaskStage.SEPARATING,
                            "separated",
                            update_task_progress=not stage_started[TaskStage.DIARIZING],
                        )
                        reported_completed.add(stage)

                    if (
                        stage_done_counts[TaskStage.DIARIZING] == len(chunks)
                        and TaskStage.DIARIZING not in reported_completed
                    ):
                        ctx.segments = self._aggregate_diarization_payloads(ctx, chunks, diarization_payloads)
                        self._complete_chunk_pipeline_stage(
                            ctx,
                            chunks,
                            TaskStage.DIARIZING,
                            "diarized",
                            update_task_progress=not stage_started[TaskStage.TRANSCRIBING],
                        )
                        reported_completed.add(TaskStage.DIARIZING)

                    if completed_chunks == len(chunks):
                        break

        # The translation pool is joined on `with` exit; surface any failure (incl.
        # TaskPausedError) before aggregation so translations are complete and the run
        # pauses/fails cleanly rather than aggregating a half-translated transcript.
        if overlap_translation:
            self._raise_on_translation_failure(ctx, translation_futures)

        transcription_segments, source_language = self._aggregate_transcription_payloads(
            ctx,
            chunks,
            transcription_payloads,
        )
        ctx.segments = self._merge_persisted_segment_fields(transcription_segments, persisted_segments)
        if source_language:
            ctx.source_language = source_language
        self._complete_chunk_pipeline_stage(ctx, chunks, TaskStage.TRANSCRIBING, "transcribed")

    def _translate_chunk_segments(
        self,
        ctx: PipelineContext,
        chunk: AudioChunk,
        segments: list[dict],
        source_language: str | None,
    ) -> None:
        """Translate one chunk's transcript slice in place (overlap path).

        Lazily builds a single ``TranslationStage`` reused across chunks so provider
        credentials are resolved once. Runs on the background translation pool while the
        front-half keeps separating/transcribing later chunks; the added ``translation``
        fields then flow into the aggregated global segments via ``_segment_to_global``.
        """
        core_segments = [segment for segment in segments if self._segment_belongs_to_chunk_core(segment, chunk)]
        if not core_segments:
            return
        if self._translation_stage is None:
            from src.pipeline.stages.s4_translation import TranslationStage

            self._translation_stage = TranslationStage()
        self._translation_stage.translate_segments(ctx, core_segments, source_lang=source_language)

    def _raise_on_translation_failure(
        self,
        ctx: PipelineContext,
        translation_futures: list[Future],
        *,
        pending_futures: dict[Future, Any] | None = None,
    ) -> None:
        """Surface a background translation failure (incl. ``TaskPausedError``).

        Mirrors the front-half failure path: reports the TRANSLATING stage as failed,
        cancels any still-pending work, and re-raises so the worker pauses/fails the task.
        """
        for tf in translation_futures:
            if not tf.done():
                continue
            exc = tf.exception()
            if exc is None:
                continue
            if pending_futures:
                for pending in pending_futures:
                    pending.cancel()
            for other in translation_futures:
                other.cancel()
            self._stage_failed(ctx, TaskStage.TRANSLATING, str(exc))
            raise exc

    def _ensure_chunk_split_and_separated(
        self,
        ctx: PipelineContext,
        source_path: Path,
        chunk: AudioChunk,
        separation_invalidated: bool,
    ) -> None:
        from src.pipeline.stages.s1_source_separation import SourceSeparationStage

        if separation_invalidated or not self._object_exists(chunk.source_url):
            with tempfile.TemporaryDirectory() as temp_dir:
                local_chunk_path = Path(temp_dir) / f"chunk_{chunk.index:04d}.wav"
                run_command(
                    [
                        "ffmpeg",
                        "-y",
                        "-ss",
                        f"{chunk.padded_start:.3f}",
                        "-t",
                        f"{chunk.padded_duration:.3f}",
                        "-i",
                        str(source_path),
                        "-ar",
                        "44100",
                        "-ac",
                        "2",
                        str(local_chunk_path),
                    ]
                )
                run_sync(
                    self.storage_service.upload_file(
                        str(local_chunk_path),
                        chunk.source_url,
                        content_type="audio/wav",
                    )
                )

        if separation_invalidated or not (
            self._object_exists(chunk.vocal_url) and self._object_exists(chunk.background_url)
        ):
            raise_if_user_paused(ctx.task_id, TaskStage.SEPARATING)
            chunk_ctx = PipelineContext(
                task_id=f"{ctx.task_id}/chunks/{chunk.index:04d}",
                user_id=ctx.user_id,
                config=ctx.config,
                source_audio_url=chunk.source_url,
                target_language=ctx.target_language,
            )
            SourceSeparationStage().process(chunk_ctx)

    def _ensure_chunk_diarized(
        self,
        ctx: PipelineContext,
        chunk: AudioChunk,
        diarization_invalidated: bool,
    ) -> dict:
        from src.pipeline.stages.s2_speaker_diarization import SpeakerDiarizationStage

        payload = None if diarization_invalidated else self._load_json_object(chunk.diarization_url)
        if payload is not None:
            return payload

        raise_if_user_paused(ctx.task_id, TaskStage.DIARIZING)
        chunk_ctx = PipelineContext(
            task_id=f"{ctx.task_id}/chunks/{chunk.index:04d}",
            user_id=ctx.user_id,
            config=self._chunk_diarization_config(ctx),
            source_audio_url=chunk.source_url,
            vocal_track_url=chunk.vocal_url,
            target_language=ctx.target_language,
        )
        SpeakerDiarizationStage().process(chunk_ctx)
        payload = {
            "speakers": chunk_ctx.speakers or [],
            "segments": chunk_ctx.segments or [],
        }
        self._save_json_object(chunk.diarization_url, payload)
        return payload

    def _ensure_chunk_transcribed(
        self,
        ctx: PipelineContext,
        chunk: AudioChunk,
        diarization_payload: dict,
        transcription_invalidated: bool,
    ) -> dict:
        from src.pipeline.stages.s3_asr_transcription import ASRTranscriptionStage

        payload = None if transcription_invalidated else self._load_json_object(chunk.transcription_url)
        if payload is not None:
            return payload

        raise_if_user_paused(ctx.task_id, TaskStage.TRANSCRIBING)
        chunk_ctx = PipelineContext(
            task_id=f"{ctx.task_id}/chunks/{chunk.index:04d}",
            user_id=ctx.user_id,
            config=ctx.config,
            source_audio_url=chunk.source_url,
            vocal_track_url=chunk.vocal_url,
            target_language=ctx.target_language,
            speakers=diarization_payload.get("speakers") or [],
            segments=diarization_payload.get("segments") or [],
        )
        ASRTranscriptionStage().process(chunk_ctx)
        payload = {
            "source_language": chunk_ctx.source_language,
            "segments": chunk_ctx.segments or [],
        }
        self._save_json_object(chunk.transcription_url, payload)
        return payload

    def _aggregate_diarization_payloads(
        self,
        ctx: PipelineContext,
        chunks: list[AudioChunk],
        payloads: dict[int, dict],
    ) -> list[dict]:
        global_speakers: dict[str, dict] = {}
        all_segments: list[dict] = []
        for chunk in chunks:
            payload = payloads.get(chunk.index)
            if payload is None:
                raise RuntimeError(f"Missing diarization payload for chunk {chunk.index}.")
            local_map = self._map_chunk_speakers(ctx, payload.get("speakers") or [], global_speakers)
            for segment in payload.get("segments") or []:
                global_segment = self._segment_to_global(segment, chunk, local_map)
                if global_segment is not None:
                    all_segments.append(global_segment)
        ctx.speakers = list(global_speakers.values())
        return sorted(all_segments, key=lambda item: (item["start"], item["end"]))

    def _aggregate_transcription_payloads(
        self,
        ctx: PipelineContext,
        chunks: list[AudioChunk],
        payloads: dict[int, dict],
    ) -> tuple[list[dict], str | None]:
        global_speakers: dict[str, dict] = {}
        all_segments: list[dict] = []
        languages: list[str] = []
        for chunk in chunks:
            diarization_payload = self._load_json_object(chunk.diarization_url)
            if diarization_payload is None:
                raise RuntimeError(f"Missing diarization payload for chunk {chunk.index}.")
            local_map = self._map_chunk_speakers(ctx, diarization_payload.get("speakers") or [], global_speakers)
            payload = payloads.get(chunk.index)
            if payload is None:
                raise RuntimeError(f"Missing transcription payload for chunk {chunk.index}.")
            if payload.get("source_language"):
                languages.append(str(payload["source_language"]))
            for segment in payload.get("segments") or []:
                global_segment = self._segment_to_global(segment, chunk, local_map)
                if global_segment is not None and str(global_segment.get("text") or "").strip():
                    all_segments.append(global_segment)
        ctx.speakers = list(global_speakers.values())
        source_language = Counter(languages).most_common(1)[0][0] if languages else None
        return sorted(all_segments, key=lambda item: (item["start"], item["end"])), source_language

    def _report_chunk_stage_progress(
        self,
        ctx: PipelineContext,
        stage: TaskStage,
        chunks: list[AudioChunk],
        done_indices: set[int],
        chunk: AudioChunk,
        *,
        update_task_progress: bool = True,
    ) -> None:
        items_done = len(done_indices)
        progress = round(items_done * 100 / len(chunks))
        processed_seconds = sum(chunks[index].core_duration for index in done_indices)
        total_seconds = chunks[-1].core_end if chunks else None
        if update_task_progress:
            self._stage_progress(ctx, stage, progress)
        self._stage_items_progress(
            ctx,
            stage,
            items_total=len(chunks),
            items_done=items_done,
            processed_seconds=processed_seconds,
            total_seconds=total_seconds,
            chunk_index=chunk.index + 1,
            chunk_count=len(chunks),
        )

    def _complete_chunk_pipeline_stage(
        self,
        ctx: PipelineContext,
        chunks: list[AudioChunk],
        stage: TaskStage,
        manifest_status: str,
        *,
        update_task_progress: bool = True,
    ) -> None:
        invalidated_stages = getattr(ctx, "invalidated_stages", None)
        if invalidated_stages is not None:
            invalidated_stages.discard(stage.value)
        if update_task_progress:
            self._stage_progress(ctx, stage, 100)
        self._save_manifest(ctx, chunks, None, manifest_status)
        self._persist_stage_state(ctx, stage)

    def _split_and_separate(self, ctx: PipelineContext, source_path: Path, chunks: list[AudioChunk]) -> None:
        from src.pipeline.stages.s1_source_separation import SourceSeparationStage

        invalidated_stages = getattr(ctx, "invalidated_stages", set()) or set()
        separation_invalidated = TaskStage.SEPARATING.value in invalidated_stages
        if separation_invalidated:
            invalidated_stages.update(
                {
                    TaskStage.DIARIZING.value,
                    TaskStage.TRANSCRIBING.value,
                    TaskStage.TRANSLATING.value,
                    TaskStage.SYNTHESIZING.value,
                    TaskStage.ALIGNING.value,
                    TaskStage.MIXING.value,
                }
            )
        for position, chunk in enumerate(chunks, start=1):
            raise_if_user_paused(ctx.task_id, TaskStage.SEPARATING)
            if separation_invalidated or not self._object_exists(chunk.source_url):
                with tempfile.TemporaryDirectory() as temp_dir:
                    local_chunk_path = Path(temp_dir) / f"chunk_{chunk.index:04d}.wav"
                    run_command(
                        [
                            "ffmpeg",
                            "-y",
                            "-ss",
                            f"{chunk.padded_start:.3f}",
                            "-t",
                            f"{chunk.padded_duration:.3f}",
                            "-i",
                            str(source_path),
                            "-ar",
                            "44100",
                            "-ac",
                            "2",
                            str(local_chunk_path),
                        ]
                    )
                    run_sync(
                        self.storage_service.upload_file(
                            str(local_chunk_path),
                            chunk.source_url,
                            content_type="audio/wav",
                        )
                    )

            if separation_invalidated or not (
                self._object_exists(chunk.vocal_url) and self._object_exists(chunk.background_url)
            ):
                chunk_ctx = PipelineContext(
                    task_id=f"{ctx.task_id}/chunks/{chunk.index:04d}",
                    user_id=ctx.user_id,
                    config=ctx.config,
                    source_audio_url=chunk.source_url,
                    target_language=ctx.target_language,
                )
                SourceSeparationStage().process(chunk_ctx)

            self._stage_progress(ctx, TaskStage.SEPARATING, round(position * 100 / len(chunks)))
            self._stage_items_progress(ctx, TaskStage.SEPARATING, items_total=len(chunks), items_done=position)
        self._save_manifest(ctx, chunks, None, "separated")

    def _diarize_chunks(self, ctx: PipelineContext, chunks: list[AudioChunk]) -> list[dict]:
        from src.pipeline.stages.s2_speaker_diarization import SpeakerDiarizationStage

        global_speakers: dict[str, dict] = {}
        all_segments: list[dict] = []
        invalidated_stages = getattr(ctx, "invalidated_stages", set()) or set()
        diarization_invalidated = TaskStage.DIARIZING.value in invalidated_stages
        if diarization_invalidated:
            invalidated_stages.update(
                {
                    TaskStage.TRANSCRIBING.value,
                    TaskStage.TRANSLATING.value,
                    TaskStage.SYNTHESIZING.value,
                    TaskStage.ALIGNING.value,
                    TaskStage.MIXING.value,
                }
            )
        for position, chunk in enumerate(chunks, start=1):
            payload = None if diarization_invalidated else self._load_json_object(chunk.diarization_url)
            if payload is None:
                raise_if_user_paused(ctx.task_id, TaskStage.DIARIZING)
                chunk_ctx = PipelineContext(
                    task_id=f"{ctx.task_id}/chunks/{chunk.index:04d}",
                    user_id=ctx.user_id,
                    config=self._chunk_diarization_config(ctx),
                    source_audio_url=chunk.source_url,
                    vocal_track_url=chunk.vocal_url,
                    target_language=ctx.target_language,
                )
                SpeakerDiarizationStage().process(chunk_ctx)
                payload = {
                    "speakers": chunk_ctx.speakers or [],
                    "segments": chunk_ctx.segments or [],
                }
                self._save_json_object(chunk.diarization_url, payload)

            local_map = self._map_chunk_speakers(ctx, payload.get("speakers") or [], global_speakers)
            for segment in payload.get("segments") or []:
                global_segment = self._segment_to_global(segment, chunk, local_map)
                if global_segment is not None:
                    all_segments.append(global_segment)

            ctx.speakers = list(global_speakers.values())
            self._stage_progress(ctx, TaskStage.DIARIZING, round(position * 100 / len(chunks)))
            self._stage_items_progress(ctx, TaskStage.DIARIZING, items_total=len(chunks), items_done=position)

        self._save_manifest(ctx, chunks, None, "diarized")
        return sorted(all_segments, key=lambda item: (item["start"], item["end"]))

    def _transcribe_chunks(self, ctx: PipelineContext, chunks: list[AudioChunk]) -> tuple[list[dict], str | None]:
        from src.pipeline.stages.s3_asr_transcription import ASRTranscriptionStage

        global_speakers: dict[str, dict] = {}
        all_segments: list[dict] = []
        languages: list[str] = []
        invalidated_stages = getattr(ctx, "invalidated_stages", set()) or set()
        transcription_invalidated = TaskStage.TRANSCRIBING.value in invalidated_stages
        if transcription_invalidated:
            invalidated_stages.update(
                {
                    TaskStage.TRANSLATING.value,
                    TaskStage.SYNTHESIZING.value,
                    TaskStage.ALIGNING.value,
                    TaskStage.MIXING.value,
                }
            )

        for position, chunk in enumerate(chunks, start=1):
            diarization_payload = self._load_json_object(chunk.diarization_url)
            if diarization_payload is None:
                raise RuntimeError(f"Missing diarization payload for chunk {chunk.index}.")
            local_map = self._map_chunk_speakers(ctx, diarization_payload.get("speakers") or [], global_speakers)

            payload = None if transcription_invalidated else self._load_json_object(chunk.transcription_url)
            if payload is None:
                raise_if_user_paused(ctx.task_id, TaskStage.TRANSCRIBING)
                chunk_ctx = PipelineContext(
                    task_id=f"{ctx.task_id}/chunks/{chunk.index:04d}",
                    user_id=ctx.user_id,
                    config=ctx.config,
                    source_audio_url=chunk.source_url,
                    vocal_track_url=chunk.vocal_url,
                    target_language=ctx.target_language,
                    speakers=diarization_payload.get("speakers") or [],
                    segments=diarization_payload.get("segments") or [],
                )
                ASRTranscriptionStage().process(chunk_ctx)
                payload = {
                    "source_language": chunk_ctx.source_language,
                    "segments": chunk_ctx.segments or [],
                }
                self._save_json_object(chunk.transcription_url, payload)

            if payload.get("source_language"):
                languages.append(str(payload["source_language"]))

            for segment in payload.get("segments") or []:
                global_segment = self._segment_to_global(segment, chunk, local_map)
                if global_segment is not None and str(global_segment.get("text") or "").strip():
                    all_segments.append(global_segment)

            ctx.speakers = list(global_speakers.values())
            self._stage_progress(ctx, TaskStage.TRANSCRIBING, round(position * 100 / len(chunks)))
            self._stage_items_progress(ctx, TaskStage.TRANSCRIBING, items_total=len(chunks), items_done=position)

        ctx.speakers = list(global_speakers.values())
        source_language = Counter(languages).most_common(1)[0][0] if languages else None
        self._save_manifest(ctx, chunks, None, "transcribed")
        return sorted(all_segments, key=lambda item: (item["start"], item["end"])), source_language

    def _resolve_global_speaker_cap(self, ctx: PipelineContext) -> int:
        """Max number of distinct global speakers to reconcile across chunks: the configured
        ``speaker_count`` when fixed, otherwise the auto cap (``MAX_INTERNAL_SPEAKERS``)."""
        try:
            _, max_speakers = resolve_speaker_count_bounds(getattr(ctx, "config", None))
        except ValueError:
            return MAX_INTERNAL_SPEAKERS
        return max(1, max_speakers)

    def _chunk_diarization_config(self, ctx: PipelineContext) -> dict:
        """Config copy for per-chunk diarization with chunk_diarization=True, which relaxes the
        per-chunk min_speakers to 1 (see s2 resolve_speaker_count_bounds). Copied so the task's
        real config is never mutated."""
        config = dict(getattr(ctx, "config", None) or {})
        config["chunk_diarization"] = True
        return config

    def _map_chunk_speakers(
        self,
        ctx: PipelineContext,
        local_speakers: list[dict],
        global_speakers: dict[str, dict],
    ) -> dict[str, str]:
        max_global_speakers = self._resolve_global_speaker_cap(ctx)
        local_map: dict[str, str] = {}
        used_global_ids: set[str] = set()
        for local_speaker in local_speakers:
            local_id = str(local_speaker.get("id") or local_speaker.get("label") or "UNKNOWN")
            gender = local_speaker.get("gender")
            pitch_hz = local_speaker.get("pitch_hz")
            embedding = local_speaker.get("embedding")
            matched_id = self._find_matching_global_speaker(
                global_speakers, gender, pitch_hz, used_global_ids, embedding
            )
            if matched_id is None and len(global_speakers) < max_global_speakers:
                matched_id = f"SPEAKER_{len(global_speakers):02d}"
                global_speakers[matched_id] = {
                    "id": matched_id,
                    "label": matched_id,
                    "ref_audio_url": local_speaker.get("ref_audio_url"),
                    "embedding": [float(value) for value in embedding] if embedding else None,
                    "embedding_count": 1 if embedding else 0,
                    "gender": gender,
                    "pitch_hz": pitch_hz,
                }
            elif matched_id is None:
                # Diarization found more distinct voices in this chunk than the speaker cap
                # allows. Fold the extra voice into an existing global speaker (least-bad) and
                # warn loudly rather than silently bleeding voices together.
                available_ids = [sid for sid in global_speakers if sid not in used_global_ids]
                matched_id = available_ids[0] if available_ids else next(iter(global_speakers))
                logger.warning(
                    "Task %s: chunk speaker %s exceeds the speaker cap of %s; force-mapping to %s. "
                    "Set speaker_count to the true number of voices to avoid voice bleed.",
                    ctx.task_id,
                    local_id,
                    max_global_speakers,
                    matched_id,
                )
            else:
                self._merge_into_global_speaker(global_speakers[matched_id], local_speaker, embedding)
            local_map[local_id] = matched_id
            used_global_ids.add(matched_id)
        return local_map

    def _merge_into_global_speaker(
        self, global_speaker: dict, local_speaker: dict, embedding: list[float] | None
    ) -> None:
        if not global_speaker.get("ref_audio_url") and local_speaker.get("ref_audio_url"):
            global_speaker["ref_audio_url"] = local_speaker.get("ref_audio_url")
        if embedding:
            self._accumulate_embedding(global_speaker, embedding)

    def _accumulate_embedding(self, global_speaker: dict, embedding: list[float]) -> None:
        """Fold a freshly observed embedding into the global speaker's running centroid so
        later chunks match against an average voiceprint rather than just the first sighting."""
        existing = global_speaker.get("embedding")
        count = int(global_speaker.get("embedding_count") or 0)
        if not existing or count <= 0 or len(existing) != len(embedding):
            global_speaker["embedding"] = [float(value) for value in embedding]
            global_speaker["embedding_count"] = 1
            return
        merged = [(old * count + new) / (count + 1) for old, new in zip(existing, embedding)]
        norm = math.sqrt(sum(value * value for value in merged)) or 1.0
        global_speaker["embedding"] = [value / norm for value in merged]
        global_speaker["embedding_count"] = count + 1

    def _find_matching_global_speaker(
        self,
        global_speakers: dict[str, dict],
        gender: str | None,
        pitch_hz: float | None,
        excluded_ids: set[str] | None = None,
        embedding: list[float] | None = None,
    ) -> str | None:
        excluded_ids = excluded_ids or set()
        # Prefer voiceprint (embedding) matching when available — robust across many chunks,
        # including same-gender / similar-pitch speakers. Fall back to gender+pitch only when
        # the local speaker has no embedding (embedding model unavailable in s2).
        if embedding:
            best_id: str | None = None
            best_similarity: float | None = None
            for speaker_id, speaker in global_speakers.items():
                if speaker_id in excluded_ids:
                    continue
                similarity = self._embedding_similarity(embedding, speaker.get("embedding"))
                if similarity is None:
                    continue
                if similarity >= SPEAKER_EMBEDDING_MATCH_THRESHOLD and (
                    best_similarity is None or similarity > best_similarity
                ):
                    best_id = speaker_id
                    best_similarity = similarity
            return best_id

        best_id = None
        best_distance: float | None = None
        for speaker_id, speaker in global_speakers.items():
            if speaker_id in excluded_ids:
                continue
            if gender and speaker.get("gender") and gender != speaker.get("gender"):
                continue
            existing_pitch = speaker.get("pitch_hz")
            if pitch_hz is None or existing_pitch is None:
                if best_id is None:
                    best_id = speaker_id
                continue
            distance = abs(float(existing_pitch) - float(pitch_hz))
            if distance <= 35 and (best_distance is None or distance < best_distance):
                best_id = speaker_id
                best_distance = distance
        return best_id

    @staticmethod
    def _embedding_similarity(left: list[float] | None, right: list[float] | None) -> float | None:
        if not left or not right or len(left) != len(right):
            return None
        dot = 0.0
        left_norm = 0.0
        right_norm = 0.0
        for x, y in zip(left, right):
            dot += x * y
            left_norm += x * x
            right_norm += y * y
        if left_norm <= 0.0 or right_norm <= 0.0:
            return None
        return dot / math.sqrt(left_norm * right_norm)

    @staticmethod
    def _segment_belongs_to_chunk_core(segment: dict, chunk: AudioChunk) -> bool:
        local_start = float(segment.get("start", 0.0))
        local_end = float(segment.get("end", 0.0))
        global_start = chunk.padded_start + local_start
        global_end = chunk.padded_start + local_end
        center = (global_start + global_end) / 2.0
        is_last_chunk_edge = abs(chunk.core_end - chunk.padded_end) < 0.001
        return center >= chunk.core_start and (center < chunk.core_end or is_last_chunk_edge)

    def _segment_to_global(self, segment: dict, chunk: AudioChunk, local_map: dict[str, str]) -> dict | None:
        if not self._segment_belongs_to_chunk_core(segment, chunk):
            return None

        local_start = float(segment.get("start", 0.0))
        local_end = float(segment.get("end", 0.0))
        global_start = chunk.padded_start + local_start
        global_end = chunk.padded_start + local_end

        speaker_id = str(segment.get("speaker_id") or "UNKNOWN")
        global_segment = dict(segment)
        global_segment["speaker_id"] = local_map.get(speaker_id, speaker_id)
        global_segment["start"] = max(chunk.core_start, global_start)
        global_segment["end"] = min(chunk.core_end, global_end)
        if global_segment["end"] <= global_segment["start"]:
            return None
        return global_segment

    def _merge_persisted_segment_fields(self, current_segments: list[dict], persisted_segments: list[dict]) -> list[dict]:
        if not current_segments or not persisted_segments:
            return current_segments

        if len(current_segments) == len(persisted_segments) and all(
            self._segments_match(current, persisted)
            for current, persisted in zip(current_segments, persisted_segments)
        ):
            return [
                self._copy_resume_fields(dict(current), persisted)
                for current, persisted in zip(current_segments, persisted_segments)
            ]

        persisted_by_key: dict[tuple[float, float, str], dict] = {}
        for persisted in persisted_segments:
            key = self._segment_match_key(persisted)
            if key not in persisted_by_key:
                persisted_by_key[key] = persisted

        merged_segments: list[dict] = []
        for current in current_segments:
            persisted = persisted_by_key.get(self._segment_match_key(current))
            merged_segments.append(self._copy_resume_fields(dict(current), persisted) if persisted else current)
        return merged_segments

    def _segments_match(self, current: dict, persisted: dict) -> bool:
        return (
            abs(float(current.get("start", 0.0)) - float(persisted.get("start", 0.0))) <= 0.05
            and abs(float(current.get("end", 0.0)) - float(persisted.get("end", 0.0))) <= 0.05
            and str(current.get("speaker_id") or "") == str(persisted.get("speaker_id") or "")
        )

    def _segment_match_key(self, segment: dict) -> tuple[float, float, str]:
        return (
            round(float(segment.get("start", 0.0)), 1),
            round(float(segment.get("end", 0.0)), 1),
            str(segment.get("speaker_id") or ""),
        )

    def _copy_resume_fields(self, current: dict, persisted: dict) -> dict:
        translation = persisted.get("translation") or persisted.get("translated_text")
        if translation and not current.get("translation"):
            current["translation"] = translation

        for field in ("synth_audio_url", "original_audio_url"):
            if persisted.get(field) and not current.get(field):
                current[field] = persisted[field]
        return current

    def _mix_chunks(self, ctx: PipelineContext, chunks: list[AudioChunk], temp_dir_path: Path) -> PipelineContext:
        if not ctx.synth_segments:
            raise RuntimeError("Long audio mixing cannot run because no synthesized audio clips were generated.")

        synth_by_id = {item.get("segment_id"): item for item in ctx.synth_segments}
        segment_pairs: list[tuple[dict, dict]] = []
        for index, segment in enumerate(ctx.segments or []):
            synth = synth_by_id.get(index)
            if synth and synth.get("audio_url"):
                segment_pairs.append((segment, synth))

        mixed_paths: list[Path] = []
        invalidated_stages = getattr(ctx, "invalidated_stages", set()) or set()
        mixing_invalidated = TaskStage.MIXING.value in invalidated_stages
        for position, chunk in enumerate(chunks, start=1):
            chunk_pairs = [
                (segment, synth)
                for segment, synth in segment_pairs
                if float(synth.get("aligned_end", segment.get("end", 0.0))) > chunk.core_start
                and float(synth.get("aligned_start", segment.get("start", 0.0))) < chunk.core_end
            ]
            local_mixed = temp_dir_path / f"mixed_{chunk.index:04d}.mp3"
            if not mixing_invalidated and self._object_exists(chunk.mixed_url):
                run_sync(self.storage_service.download_file(chunk.mixed_url, str(local_mixed)))
            else:
                self._mix_single_chunk(ctx, chunk, chunk_pairs, local_mixed, temp_dir_path)
                run_sync(
                    self.storage_service.upload_file(
                        str(local_mixed),
                        chunk.mixed_url,
                        content_type="audio/mpeg",
                    )
                )
            mixed_paths.append(local_mixed)
            self._stage_progress(ctx, TaskStage.MIXING, round(position * 90 / len(chunks)))
            self._stage_items_progress(ctx, TaskStage.MIXING, items_total=len(chunks), items_done=position)

        final_path = temp_dir_path / "final_podcast.mp3"
        concat_list = temp_dir_path / "concat.txt"
        concat_list.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in mixed_paths),
            encoding="utf-8",
        )
        run_command(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(final_path),
            ]
        )
        final_obj_name = f"{ctx.task_id}/output/final_podcast.mp3"
        run_sync(self.storage_service.upload_file(str(final_path), final_obj_name, content_type="audio/mpeg"))
        ctx.output_audio_url = final_obj_name
        self._stage_progress(ctx, TaskStage.MIXING, 100)
        self._save_manifest(ctx, chunks, None, "mixed")
        return ctx

    def _mix_single_chunk(
        self,
        ctx: PipelineContext,
        chunk: AudioChunk,
        segment_pairs: list[tuple[dict, dict]],
        output_path: Path,
        temp_dir_path: Path,
    ) -> None:
        inputs: list[str] = []
        filters: list[str] = []
        mix_labels = ["[bg]"]
        if self._object_exists(chunk.background_url):
            local_bg_path = temp_dir_path / f"bg_{chunk.index:04d}.wav"
            run_sync(self.storage_service.download_file(chunk.background_url, str(local_bg_path)))
            inputs.extend(["-i", str(local_bg_path)])
            filters.append(
                f"[0:a]atrim=start={chunk.pad_left:.3f}:duration={chunk.core_duration:.3f},"
                "asetpts=PTS-STARTPTS,volume=0.4[bg]"
            )
        else:
            inputs.extend(
                [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{chunk.core_duration:.3f}",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                ]
            )
            filters.append("[0:a]asetpts=PTS-STARTPTS[bg]")

        for input_index, (segment, synth) in enumerate(segment_pairs, start=1):
            audio_url = synth.get("audio_url")
            if not audio_url:
                continue
            suffix = Path(str(audio_url)).suffix or ".mp3"
            local_synth_path = temp_dir_path / f"synth_{chunk.index:04d}_{input_index}{suffix}"
            run_sync(self.storage_service.download_file(audio_url, str(local_synth_path)))
            inputs.extend(["-i", str(local_synth_path)])

            aligned_start = float(synth.get("aligned_start", segment.get("start", 0.0)))
            aligned_end = float(synth.get("aligned_end", segment.get("end", 0.0)))
            trim_start = max(0.0, chunk.core_start - aligned_start)
            trim_duration = max(0.0, min(aligned_end, chunk.core_end) - max(aligned_start, chunk.core_start))
            if trim_duration <= 0:
                continue
            delay_ms = max(0, int(round((aligned_start - chunk.core_start) * 1000)))
            label = f"[v{input_index}]"
            filters.append(
                f"[{input_index}:a]atrim=start={trim_start:.3f}:duration={trim_duration:.3f},"
                f"asetpts=PTS-STARTPTS,adelay={delay_ms}:all=1{label}"
            )
            mix_labels.append(label)

        filters.append("".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=first:normalize=0[out]")
        run_command(
            [
                "ffmpeg",
                "-y",
                *inputs,
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[out]",
                "-t",
                f"{chunk.core_duration:.3f}",
                "-b:a",
                "192k",
                str(output_path),
            ]
        )

    def _run_stage(self, ctx: PipelineContext, stage: TaskStage, callback):
        self._stage_started(ctx, stage)
        try:
            result = callback()
            invalidated_stages = getattr(ctx, "invalidated_stages", None)
            if invalidated_stages is not None:
                invalidated_stages.discard(stage.value)
            self._stage_progress(ctx, stage, 100)
            return result
        except Exception as exc:
            self._stage_failed(ctx, stage, str(exc))
            raise

    def _stage_started(self, ctx: PipelineContext, stage: TaskStage) -> None:
        hooks = getattr(ctx, "lifecycle_hooks", None)
        if hooks and hasattr(hooks, "on_stage_started"):
            hooks.on_stage_started(stage)

    def _stage_progress(self, ctx: PipelineContext, stage: TaskStage, progress: int) -> None:
        hooks = getattr(ctx, "lifecycle_hooks", None)
        if hooks and hasattr(hooks, "on_stage_progress"):
            hooks.on_stage_progress(stage, progress)

    def _stage_items_progress(
        self,
        ctx: PipelineContext,
        stage: TaskStage,
        *,
        items_total: int | None = None,
        items_done: int | None = None,
        cost_estimate: float | None = None,
        processed_seconds: float | None = None,
        total_seconds: float | None = None,
        chunk_index: int | None = None,
        chunk_count: int | None = None,
    ) -> None:
        hooks = getattr(ctx, "lifecycle_hooks", None)
        if hooks and hasattr(hooks, "on_stage_items_progress"):
            hooks.on_stage_items_progress(
                stage,
                items_total=items_total,
                items_done=items_done,
                cost_estimate=cost_estimate,
                processed_seconds=processed_seconds,
                total_seconds=total_seconds,
                chunk_index=chunk_index,
                chunk_count=chunk_count,
            )

    def _stage_failed(self, ctx: PipelineContext, stage: TaskStage, error_message: str) -> None:
        hooks = getattr(ctx, "lifecycle_hooks", None)
        if hooks and hasattr(hooks, "on_stage_failed"):
            hooks.on_stage_failed(stage, error_message)

    def _persist_stage_state(self, ctx: PipelineContext, stage: TaskStage) -> None:
        hooks = getattr(ctx, "lifecycle_hooks", None)
        if hooks and hasattr(hooks, "on_stage_completed"):
            hooks.on_stage_completed(stage, ctx)

    def _audio_prepared(self, ctx: PipelineContext, duration: float, config_updates: dict[str, Any]) -> None:
        hooks = getattr(ctx, "lifecycle_hooks", None)
        if hooks and hasattr(hooks, "on_audio_prepared"):
            hooks.on_audio_prepared(duration, config_updates)

    def _object_exists(self, object_name: str) -> bool:
        try:
            return run_sync(self.storage_service.object_exists(object_name))
        except Exception:
            logger.warning("Failed to check object %s.", object_name, exc_info=True)
            return False

    def _load_json_object(self, object_name: str) -> dict | None:
        if not self._object_exists(object_name):
            return None
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "payload.json"
            run_sync(self.storage_service.download_file(object_name, str(local_path)))
            return json.loads(local_path.read_text(encoding="utf-8"))

    def _save_json_object(self, object_name: str, payload: dict) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "payload.json"
            local_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            run_sync(self.storage_service.upload_file(str(local_path), object_name, content_type="application/json"))

    def _save_manifest(self, ctx: PipelineContext, chunks: list[AudioChunk], duration: float | None, status: str) -> None:
        manifest = {
            "task_id": ctx.task_id,
            "status": status,
            "duration": duration if duration is not None else (chunks[-1].core_end if chunks else None),
            "chunk_seconds": settings.PCT_AUDIO_CHUNK_SECONDS,
            "overlap_seconds": settings.PCT_AUDIO_CHUNK_OVERLAP_SECONDS,
            "chunks": [asdict(chunk) for chunk in chunks],
        }
        self._save_json_object(f"{ctx.task_id}/manifest.json", manifest)


def probe_audio_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def run_command(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or exc.stdout or str(exc)
        logger.error("Command failed: %s\n%s", " ".join(cmd), stderr)
        raise RuntimeError(stderr) from exc
