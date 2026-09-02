"""SenseVoice ASR 策略 — 占位实现"""
import logging
from src.pipeline.strategies.asr.base import ASRStrategy, TranscriptionResult

logger = logging.getLogger(__name__)


class SenseVoiceStrategy(ASRStrategy):
    """基于阿里 SenseVoice 的 ASR 策略（占位，待接入 DashScope API）"""

    async def transcribe(self, audio_path: str, language: str = None) -> TranscriptionResult:
        raise NotImplementedError(
            "SenseVoice ASR strategy is not yet implemented. "
            "Please set PCT_ASR_PROVIDER=whisper in .env"
        )
