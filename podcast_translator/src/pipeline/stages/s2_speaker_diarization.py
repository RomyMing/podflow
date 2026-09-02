import tempfile
import logging
import threading
import inspect
import hashlib
import time
from pathlib import Path
import torch
import torchaudio


def _patch_huggingface_hub_auth_token_compat() -> None:
    """Let pyannote 3.x pass use_auth_token to newer huggingface_hub releases."""
    try:
        import huggingface_hub
    except ImportError:
        return

    original = huggingface_hub.hf_hub_download
    if getattr(original, "_pct_use_auth_token_compat", False):
        return

    try:
        signature = inspect.signature(original)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and "use_auth_token" in signature.parameters:
        return

    def hf_hub_download_compat(*args, use_auth_token=None, **kwargs):
        if use_auth_token is not None and "token" not in kwargs:
            kwargs["token"] = use_auth_token
        return original(*args, **kwargs)

    hf_hub_download_compat._pct_use_auth_token_compat = True
    huggingface_hub.hf_hub_download = hf_hub_download_compat


_patch_huggingface_hub_auth_token_compat()

from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook

from src.config import settings
from src.core.provider_errors import TaskPausedError
from src.pipeline.base_stage import StageProcessor
from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.speaker_config import resolve_speaker_count_bounds
from src.pipeline.speaker_gender import ensure_mixed_fallback_genders
from src.pipeline.voice_analysis import estimate_speaker_gender
from src.services.storage_service import StorageService
from src.pipeline.utils import run_sync
from src.services.user_api_key_service import resolve_provider_credentials_sync

logger = logging.getLogger(__name__)

# Speaker-embedding model used to give each diarized speaker a fixed-length voiceprint.
# Long-audio cross-chunk speaker matching prefers these embeddings over the gender+pitch
# heuristic. Extraction is best-effort: if the model is unavailable (e.g. HF terms not
# accepted), embeddings stay None and matching falls back to gender+pitch.
SPEAKER_EMBEDDING_MODEL = "pyannote/embedding"
REFERENCE_MIN_SECONDS = 10.0
REFERENCE_MAX_SECONDS = 30.0
REFERENCE_MAX_SLICE_SECONDS = 12.0
REFERENCE_GAP_SECONDS = 0.2


def get_diarization_annotation(diarization_result):
    if hasattr(diarization_result, "exclusive_speaker_diarization"):
        annotation = diarization_result.exclusive_speaker_diarization
        if annotation is not None:
            return annotation

    if hasattr(diarization_result, "speaker_diarization"):
        annotation = diarization_result.speaker_diarization
        if annotation is not None:
            return annotation

    return diarization_result


def _slice_waveform(waveform: torch.Tensor, sample_rate: int, start: float, end: float) -> torch.Tensor:
    start_frame = max(0, int(start * sample_rate))
    end_frame = min(waveform.shape[-1], int(end * sample_rate))
    if end_frame <= start_frame:
        return waveform[:, 0:0]
    return waveform[:, start_frame:end_frame]


def _interval_energy(waveform: torch.Tensor, sample_rate: int, start: float, end: float) -> float:
    clip = _slice_waveform(waveform, sample_rate, start, end)
    if clip.numel() == 0:
        return 0.0
    return float(torch.sqrt(torch.mean(clip.float() ** 2)).item())


def build_reference_waveform(
    intervals: list[tuple[float, float, float]],
    waveform: torch.Tensor,
    sample_rate: int,
    *,
    min_seconds: float = REFERENCE_MIN_SECONDS,
    max_seconds: float = REFERENCE_MAX_SECONDS,
) -> tuple[torch.Tensor | None, list[dict]]:
    """Select high-energy speaker-only slices and concatenate them into one prompt clip."""
    candidates: list[dict] = []
    for start, end, duration in intervals:
        if duration <= 0.5:
            continue
        trim = min(0.25, duration * 0.1)
        clean_start = start + trim
        clean_end = end - trim
        clean_duration = max(0.0, clean_end - clean_start)
        if clean_duration <= 0.5:
            clean_start, clean_end, clean_duration = start, end, duration
        energy = _interval_energy(waveform, sample_rate, clean_start, clean_end)
        if energy <= 0:
            continue
        candidates.append(
            {
                "start": clean_start,
                "end": clean_end,
                "duration": clean_duration,
                "energy": energy,
            }
        )

    if not candidates:
        return None, []

    candidates.sort(key=lambda item: (item["energy"], item["duration"]), reverse=True)
    selected: list[dict] = []
    selected_clips: list[torch.Tensor] = []
    total_seconds = 0.0
    silence = torch.zeros(
        (waveform.shape[0], max(1, int(sample_rate * REFERENCE_GAP_SECONDS))),
        dtype=waveform.dtype,
        device=waveform.device,
    )

    for candidate in candidates:
        remaining = max_seconds - total_seconds
        if remaining <= 0:
            break
        take_seconds = min(candidate["duration"], REFERENCE_MAX_SLICE_SECONDS, remaining)
        clip_start = candidate["start"]
        clip_end = clip_start + take_seconds
        clip = _slice_waveform(waveform, sample_rate, clip_start, clip_end)
        if clip.numel() == 0:
            continue
        if selected_clips:
            selected_clips.append(silence)
            total_seconds += REFERENCE_GAP_SECONDS
        selected_clips.append(clip)
        total_seconds += clip.shape[-1] / sample_rate
        selected.append(
            {
                "start": round(clip_start, 3),
                "end": round(clip_end, 3),
                "duration": round(clip.shape[-1] / sample_rate, 3),
                "energy": round(candidate["energy"], 6),
            }
        )
        if total_seconds >= min_seconds:
            break

    if not selected_clips:
        return None, []
    return torch.cat(selected_clips, dim=1), selected


class SpeakerDiarizationStage(StageProcessor):
    # ── BUG-06 修复：类级别模型缓存，避免每次 process() 都耗 30-60s 重新加载 ──
    _pipeline_cache: dict[str, Pipeline] = {}
    _pipeline_lock = threading.Lock()
    # Speaker-embedding model cache (BUG-06 pattern). Failed credential hashes are latched
    # independently so one user's missing model access does not disable embeddings for every
    # task handled by this worker, while repeated chunks for that credential do not retry.
    _embedding_cache: dict[str, object] = {}
    _embedding_lock = threading.Lock()
    _embedding_disabled_keys: set[str] = set()

    def __init__(self, next_processor: 'StageProcessor' = None):
        super().__init__(next_processor)
        self.storage_service = StorageService()

    @classmethod
    def _get_pipeline(cls, hf_token: str) -> Pipeline:
        """线程安全地获取或初始化 pyannote Pipeline（单例）"""
        cache_key = hashlib.sha256(hf_token.encode("utf-8")).hexdigest()
        cached = cls._pipeline_cache.get(cache_key)
        if cached is not None:
            return cached
        with cls._pipeline_lock:
            # Double-check locking
            cached = cls._pipeline_cache.get(cache_key)
            if cached is not None:
                return cached
            logger.info("Initializing pyannote pipeline (one-time load)...")
            pipeline = cls._load_pipeline_with_retry(hf_token)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            pipeline.to(device)
            logger.info(f"Pyannote pipeline loaded on {device}.")
            cls._pipeline_cache[cache_key] = pipeline
            return pipeline

    @staticmethod
    def _load_pipeline_with_retry(hf_token: str) -> Pipeline:
        """Pipeline.from_pretrained reaches huggingface.co (even for cached models, to verify
        revisions) and, on a transient TLS/network blip, *returns None instead of raising*.
        Retry on None/exception, then surface a resumable pause rather than crashing on
        ``None.to(device)``."""
        attempts = max(1, int(settings.PCT_PREFLIGHT_RETRY_ATTEMPTS))
        backoff = max(0.0, float(settings.PCT_PREFLIGHT_RETRY_BACKOFF_SECONDS))
        last_error: str | None = None
        for attempt in range(attempts):
            try:
                try:
                    pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        token=hf_token,
                    )
                except TypeError as exc:
                    if "token" not in str(exc):
                        raise
                    pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=hf_token,
                    )
                if pipeline is not None:
                    return pipeline
                last_error = "Pipeline.from_pretrained returned None (Hugging Face unreachable or model access not granted)"
            except Exception as exc:  # noqa: BLE001 - transient network/TLS during load
                last_error = str(exc)
            if attempt < attempts - 1:
                logger.warning(
                    "Pyannote pipeline load failed (attempt %s/%s): %s; retrying",
                    attempt + 1, attempts, last_error,
                )
                time.sleep(backoff * (attempt + 1))

        raise TaskPausedError(
            f"Could not load the pyannote speaker-diarization model: {last_error}. "
            "This is usually a transient Hugging Face connectivity issue — please resume the task.",
            provider="huggingface",
            reason_code="provider_unavailable",
            provider_error_code="ModelLoadFailed",
        )

    @classmethod
    def _get_embedding_inference(cls, hf_token: str):
        """Load (and cache) the pyannote speaker-embedding inference. Best-effort: returns
        None — and latches embeddings off for this credential — if the model cannot be
        loaded, so diarization keeps working with the gender+pitch fallback."""
        cache_key = hashlib.sha256(("embedding:" + hf_token).encode("utf-8")).hexdigest()
        if cache_key in cls._embedding_disabled_keys:
            return None
        cached = cls._embedding_cache.get(cache_key)
        if cached is not None:
            return cached
        with cls._embedding_lock:
            cached = cls._embedding_cache.get(cache_key)
            if cached is not None:
                return cached
            if cache_key in cls._embedding_disabled_keys:
                return None
            try:
                from pyannote.audio import Inference, Model

                try:
                    model = Model.from_pretrained(SPEAKER_EMBEDDING_MODEL, token=hf_token)
                except TypeError as exc:
                    if "token" not in str(exc):
                        raise
                    model = Model.from_pretrained(SPEAKER_EMBEDDING_MODEL, use_auth_token=hf_token)
                if model is None:
                    raise RuntimeError("Model.from_pretrained returned None")
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                model.to(device)
                inference = Inference(model, window="whole")
                cls._embedding_cache[cache_key] = inference
                logger.info("Loaded pyannote speaker-embedding model '%s' on %s.", SPEAKER_EMBEDDING_MODEL, device)
                return inference
            except Exception as exc:  # noqa: BLE001 - embeddings are an optional enhancement
                cls._embedding_disabled_keys.add(cache_key)
                logger.warning(
                    "Speaker embedding model '%s' unavailable (%s); cross-chunk speaker matching will "
                    "fall back to gender+pitch. Accept the model terms on Hugging Face for robust "
                    "multi-speaker long-audio matching.",
                    SPEAKER_EMBEDDING_MODEL,
                    exc,
                )
                return None

    @classmethod
    def _compute_speaker_embedding(
        cls, hf_token: str, waveform: torch.Tensor, sample_rate: int
    ) -> list[float] | None:
        """Return an L2-normalized speaker embedding for ``waveform`` as a JSON-friendly list,
        or None if embeddings are unavailable."""
        inference = cls._get_embedding_inference(hf_token)
        if inference is None:
            return None
        try:
            import numpy as np

            clip = waveform if waveform.dim() == 2 else waveform.unsqueeze(0)
            raw = inference({"waveform": clip, "sample_rate": int(sample_rate)})
            vector = np.asarray(raw, dtype="float32").ravel()
            if vector.size == 0 or not np.all(np.isfinite(vector)):
                return None
            norm = float(np.linalg.norm(vector))
            if norm <= 0.0:
                return None
            return [float(value) for value in (vector / norm)]
        except Exception as exc:  # noqa: BLE001 - embeddings are an optional enhancement
            logger.warning("Speaker embedding computation failed (%s); using gender+pitch fallback.", exc)
            return None

    @property
    def stage(self) -> TaskStage:
        return TaskStage.DIARIZING

    def restore_from_artifacts(self, ctx: PipelineContext) -> bool:
        if not ctx.speakers or not ctx.segments:
            return False

        for speaker in ctx.speakers:
            ref_audio_url = speaker.get("ref_audio_url")
            if not ref_audio_url:
                return False
            try:
                if not run_sync(self.storage_service.object_exists(ref_audio_url)):
                    return False
            except Exception:
                logger.warning("Task %s: failed to check speaker ref artifact.", ctx.task_id, exc_info=True)
                return False

        logger.info("Task %s: reusing persisted diarization segments and speaker refs.", ctx.task_id)
        return True

    def _resolve_huggingface_token(self, ctx: PipelineContext) -> str:
        try:
            credentials = resolve_provider_credentials_sync(ctx.user_id, "huggingface")
        except ValueError as exc:
            raise TaskPausedError(
                str(exc),
                provider="huggingface",
                reason_code="provider_invalid_api_key",
                provider_error_code="credential_decryption_failed",
                stage=self.stage,
            ) from exc
        if credentials is None:
            raise TaskPausedError(
                "Hugging Face token is not configured. Pyannote speaker diarization needs authorization.",
                provider="huggingface",
                reason_code="provider_credentials_missing",
                stage=self.stage,
            )
        return credentials.api_key

    def process(self, ctx: PipelineContext) -> PipelineContext:
        """
        说话人分段核心处理逻辑：
        1. 获取待处理的音频文件（优先使用 vocal_track_url）
        2. 使用 pyannote.audio 进行 Diarization，并按 config 支持 1-4 位说话人
        3. 利用模型输出挑选高能量、较干净的参考音频片段并上传
        4. 更新返回上下文
        """
        target_audio_url = ctx.vocal_track_url or ctx.source_audio_url
        if not target_audio_url:
            raise ValueError(f"Task {ctx.task_id}: no audio URL provided for diarization.")

        # BUG-05 修复：原来缺少 f 前缀，ctx.task_id 不会被插值
        hf_token = self._resolve_huggingface_token(ctx)

        logger.info(f"Task {ctx.task_id}: Starting speaker diarization...")

        # 1. 下载输入的音频
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            source_ext = Path(target_audio_url).suffix or ".wav"
            local_audio_path = temp_dir_path / f"input{source_ext}"

            logger.info(f"Task {ctx.task_id}: Downloading audio {target_audio_url} for diarization...")
            run_sync(self.storage_service.download_file(
                object_name=target_audio_url,
                dest_path=str(local_audio_path)
            ))

            # 2. 获取缓存的 Pipeline 并执行（BUG-06：不再在此处每次加载模型）
            pipeline = self._get_pipeline(hf_token)
            # Long-audio per-chunk diarization sets chunk_diarization=True so a chunk with fewer
            # active speakers isn't forced to invent phantom ones; the global speaker count is
            # reconciled across chunks. The non-chunked path keeps min=max=speaker_count.
            relax_min = bool((ctx.config or {}).get("chunk_diarization"))
            min_speakers, max_speakers = resolve_speaker_count_bounds(ctx.config, relax_min=relax_min)
            logger.info(
                "Task %s: Executing pyannote pipeline with min_speakers=%s max_speakers=%s.",
                ctx.task_id,
                min_speakers,
                max_speakers,
            )
            with ProgressHook() as hook:
                diarization = pipeline(
                    str(local_audio_path),
                    min_speakers=min_speakers,
                    max_speakers=max_speakers,
                    hook=hook,
                )
            diarization_annotation = get_diarization_annotation(diarization)

            # 3. 解析结果与提取 reference audio
            ctx.segments = []
            speaker_segments = {} # {speaker_id: [(start, end, duration), ...]}
            
            for turn, _, speaker in diarization_annotation.itertracks(yield_label=True):
                duration = turn.end - turn.start
                ctx.segments.append({
                    "speaker_id": speaker,
                    "start": turn.start,
                    "end": turn.end
                })
                
                if speaker not in speaker_segments:
                    speaker_segments[speaker] = []
                speaker_segments[speaker].append((turn.start, turn.end, duration))

            # 载入音频提取片段供 CosyVoice 声音克隆使用
            waveform, sample_rate = torchaudio.load(str(local_audio_path))
            
            # 初始化上下文 speakers 列表
            ctx.speakers = []
            
            for speaker_id, intervals in speaker_segments.items():
                if not intervals:
                    continue
                ref_waveform, reference_segments = build_reference_waveform(intervals, waveform, sample_rate)
                if ref_waveform is None:
                    logger.warning("Task %s: no usable reference audio for speaker %s.", ctx.task_id, speaker_id)
                    continue

                ref_local_path = temp_dir_path / f"{speaker_id}_ref.wav"
                gender, pitch_hz = estimate_speaker_gender(ref_waveform, sample_rate)
                logger.info(
                    "Task %s: estimated speaker %s gender=%s pitch=%s from diarization reference.",
                    ctx.task_id,
                    speaker_id,
                    gender,
                    pitch_hz,
                )
                
                torchaudio.save(str(ref_local_path), ref_waveform, sample_rate)
                
                # 上传切片音频作为该说话者的参考音色
                ref_object_name = f"{ctx.task_id}/speakers/{speaker_id}_ref.wav"
                logger.info(f"Task {ctx.task_id}: Uploading ref audio for {speaker_id} -> {ref_object_name}")
                run_sync(self.storage_service.upload_file(
                    local_path=str(ref_local_path),
                    object_name=ref_object_name,
                    content_type="audio/wav"
                ))
                
                # 计算说话人声纹：让长音频跨分块匹配优先用 embedding，而非脆弱的 gender+pitch 启发式（best-effort）
                speaker_embedding = self._compute_speaker_embedding(hf_token, ref_waveform, sample_rate)

                # 更新 speaker 特征数据
                ctx.speakers.append({
                    "id": speaker_id,
                    "label": speaker_id,
                    "ref_audio_url": ref_object_name,
                    "embedding": speaker_embedding,
                    "gender": gender,
                    "pitch_hz": pitch_hz,
                    "reference_duration": round(ref_waveform.shape[-1] / sample_rate, 3),
                    "reference_segments": reference_segments,
                })

            if ensure_mixed_fallback_genders(ctx.speakers):
                logger.info(
                    "Task %s: normalized two-speaker fallback genders to keep male/female voices distinct.",
                    ctx.task_id,
                )

            self._report_items_progress(
                ctx,
                items_total=len(ctx.speakers or []),
                items_done=len(ctx.speakers or []),
                metrics={
                    "speaker_count": len(ctx.speakers or []),
                    "speaker_count_min": min_speakers,
                    "speaker_count_max": max_speakers,
                    "reference_audio_count": len([s for s in ctx.speakers or [] if s.get("ref_audio_url")]),
                },
            )

            logger.info(f"Task {ctx.task_id}: Diarization completed. Found {len(ctx.speakers)} speakers.")
            
            return ctx
