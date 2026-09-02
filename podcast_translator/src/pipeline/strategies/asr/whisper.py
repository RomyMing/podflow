"""Whisper ASR 策略实现"""
import logging
import threading
from faster_whisper import WhisperModel
from src.pipeline.strategies.asr.base import ASRStrategy, TranscriptionResult

logger = logging.getLogger(__name__)


class WhisperStrategy(ASRStrategy):
    """基于 Faster-Whisper large-v3 的 ASR 策略"""
    
    _model_cache = None
    _model_lock = threading.Lock()

    @classmethod
    def _get_model(cls) -> WhisperModel:
        if cls._model_cache is not None:
            return cls._model_cache
        with cls._model_lock:
            if cls._model_cache is not None:
                return cls._model_cache
            logger.info("WhisperStrategy: Loading Faster-Whisper large-v3...")
            cls._model_cache = WhisperModel("large-v3", device="auto", compute_type="default")
            logger.info("WhisperStrategy: Model loaded.")
            return cls._model_cache

    async def transcribe(self, audio_path: str, language: str = None) -> TranscriptionResult:
        model = self._get_model()
        segments_gen, info = model.transcribe(audio_path, beam_size=5, language=language)
        
        word_timestamps = []
        full_text_parts = []
        for seg in segments_gen:
            text = seg.text.strip()
            full_text_parts.append(text)
            word_timestamps.append({
                "start": seg.start,
                "end": seg.end,
                "text": text,
            })
        
        return TranscriptionResult(
            text=" ".join(full_text_parts),
            word_timestamps=word_timestamps,
        )
