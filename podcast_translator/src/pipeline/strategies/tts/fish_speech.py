"""Fish Speech TTS 策略 — 占位实现"""
import logging
from src.pipeline.strategies.tts.base import TTSStrategy

logger = logging.getLogger(__name__)


class FishSpeechStrategy(TTSStrategy):
    """基于 Fish Speech 的 TTS 策略（占位，待接入）"""

    async def synthesize(self, text: str, reference_audio: str = None, speaker_embedding: bytes = None) -> bytes:
        raise NotImplementedError(
            "Fish Speech TTS strategy is not yet implemented. "
            "Please set PCT_TTS_PROVIDER=cosyvoice in .env"
        )
