import os
import tempfile
import logging
import threading
import bisect
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from faster_whisper import WhisperModel

from src.config import settings
from src.pipeline.base_stage import StageProcessor
from src.pipeline.context import PipelineContext, TaskStage
from src.services.storage_service import StorageService
from src.pipeline.utils import run_sync
from src.services.user_api_key_service import resolve_provider_credentials_sync

logger = logging.getLogger(__name__)

def compute_overlap(a_start, a_end, b_start, b_end):
    """计算两个时间段的重叠时长"""
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    return max(0, overlap_end - overlap_start)

def align_whisper_to_diarization(whisper_segments: list, diarization_segments: list) -> list:
    """
    BUG-07 修复：将 O(N*M) 暴力遍历优化为 O(N log M)
    
    策略：
    1. 将 diarization segments 按 start 排序，提取 start 值列表
    2. 对每个 whisper segment，用 bisect 定位最近的 diarization 候选区
    3. 只检查有可能重叠的少量 diarization segments（向左向右扫描直到不再重叠）
    """
    if not diarization_segments:
        return [
            {
                "speaker_id": "UNKNOWN",
                "start": w["start"],
                "end": w["end"],
                "text": w["text"],
            }
            for w in whisper_segments
        ]
    
    # 按 start 排序
    sorted_d_segs = sorted(diarization_segments, key=lambda s: s["start"])
    d_starts = [s["start"] for s in sorted_d_segs]
    n_d = len(sorted_d_segs)
    
    aligned = []
    for w_seg in whisper_segments:
        w_start, w_end = w_seg["start"], w_seg["end"]
        
        # 用 bisect 找到第一个 start >= w_start 的 diarization segment 索引
        idx = bisect.bisect_left(d_starts, w_start)
        
        best_speaker = "UNKNOWN"
        max_overlap = 0.0
        
        # 向左扫描（idx-1, idx-2, ...）直到 d_seg.end < w_start
        i = idx - 1
        while i >= 0:
            d_seg = sorted_d_segs[i]
            if d_seg["end"] <= w_start:
                break  # 不可能再有重叠
            overlap = compute_overlap(w_start, w_end, d_seg["start"], d_seg["end"])
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = d_seg.get("speaker_id", "UNKNOWN")
            i -= 1
        
        # 向右扫描（idx, idx+1, ...）直到 d_seg.start >= w_end
        i = idx
        while i < n_d:
            d_seg = sorted_d_segs[i]
            if d_seg["start"] >= w_end:
                break  # 不可能再有重叠
            overlap = compute_overlap(w_start, w_end, d_seg["start"], d_seg["end"])
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = d_seg.get("speaker_id", "UNKNOWN")
            i += 1
        
        aligned.append({
            "speaker_id": best_speaker,
            "start": w_start,
            "end": w_end,
            "text": w_seg["text"],
        })
    
    return aligned


class ASRTranscriptionStage(StageProcessor):
    # ── BUG-06 修复：类级别模型缓存，避免每次 process() 都重新加载 Whisper large-v3 ──
    _model_cache = None
    _model_lock = threading.Lock()

    def __init__(self, next_processor: 'StageProcessor' = None):
        super().__init__(next_processor)
        self.storage_service = StorageService()

    @classmethod
    def _get_model(cls) -> WhisperModel:
        """线程安全地获取或初始化 WhisperModel（单例）"""
        if cls._model_cache is not None:
            return cls._model_cache
        with cls._model_lock:
            if cls._model_cache is not None:
                return cls._model_cache
            logger.info(
                "Initializing Faster-Whisper model %s on %s (compute_type=%s, one-time load)...",
                settings.PCT_ASR_MODEL,
                settings.PCT_ASR_DEVICE,
                settings.PCT_ASR_COMPUTE_TYPE,
            )
            cls._model_cache = WhisperModel(
                settings.PCT_ASR_MODEL,
                device=settings.PCT_ASR_DEVICE,
                compute_type=settings.PCT_ASR_COMPUTE_TYPE,
            )
            logger.info("Faster-Whisper model loaded.")
            return cls._model_cache

    @property
    def stage(self) -> TaskStage:
        return TaskStage.TRANSCRIBING

    def restore_from_artifacts(self, ctx: PipelineContext) -> bool:
        if not ctx.segments:
            return False
        if not all(str(segment.get("text") or "").strip() for segment in ctx.segments):
            return False

        logger.info("Task %s: reusing persisted ASR transcription for %s segments.", ctx.task_id, len(ctx.segments))
        return True

    def _configure_huggingface_download(self, ctx: PipelineContext) -> None:
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        try:
            credentials = resolve_provider_credentials_sync(ctx.user_id, "huggingface")
        except ValueError:
            logger.warning("Task %s: saved Hugging Face token cannot be used for ASR download.", ctx.task_id, exc_info=True)
            return
        if credentials is None:
            return
        os.environ["HF_TOKEN"] = credentials.api_key
        os.environ["HUGGING_FACE_HUB_TOKEN"] = credentials.api_key

    def process(self, ctx: PipelineContext) -> PipelineContext:
        """
        ASR 语音转写核心逻辑：
        1. 获取 vocal_track_url（人声轨道）
        2. 调用 faster-whisper (large-v3) 提取文本与时间
        3. 利用优化后的 O(N log M) 重叠算法将转写语句对齐到 Pyannote Speaker 区间
        4. 重构并覆盖 ctx.segments 为拥有 speaker_id, start, end, text 的丰富列表
        """
        target_audio_url = ctx.vocal_track_url or ctx.source_audio_url
        if not target_audio_url:
            raise ValueError(f"Task {ctx.task_id}: no audio URL provided for ASR transcription.")

        if not ctx.segments:
            logger.warning(f"Task {ctx.task_id}: ctx.segments is empty. Proceeding without speaker alignment.")

        logger.info(f"Task {ctx.task_id}: Starting ASR transcription...")
        self._configure_huggingface_download(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            source_ext = Path(target_audio_url).suffix or ".wav"
            local_audio_path = temp_dir_path / f"input{source_ext}"

            logger.info(f"Task {ctx.task_id}: Downloading audio {target_audio_url} for transcription...")
            run_sync(self.storage_service.download_file(
                object_name=target_audio_url,
                dest_path=str(local_audio_path)
            ))

            # BUG-06 修复：使用类级别缓存的模型，不再每次都加载
            model = self._get_model()
            
            logger.info(f"Task {ctx.task_id}: Executing audio transcription...")
            segments_generator, info = model.transcribe(
                str(local_audio_path),
                beam_size=settings.PCT_ASR_BEAM_SIZE,
            )
            
            logger.info(f"Task {ctx.task_id}: Detected language '{info.language}' with probability {info.language_probability}")

            # ── BUG-08 修复：将 Whisper 检测到的源语言写入 PipelineContext ──
            ctx.source_language = info.language
            logger.info(f"Task {ctx.task_id}: Source language set to '{ctx.source_language}' in PipelineContext.")

            whisper_segments = []
            for segment in segments_generator:
                whisper_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
            
            logger.info(f"Task {ctx.task_id}: Transcription complete. Re-aligning with Diarization segments (optimized)...")

            # BUG-07 修复：使用优化后的 O(N log M) 对齐算法
            ctx.segments = align_whisper_to_diarization(whisper_segments, ctx.segments or [])
            logger.info(f"Task {ctx.task_id}: Alignment finished, successfully combined Text and Speakers for {len(ctx.segments)} segments.")

            return ctx
