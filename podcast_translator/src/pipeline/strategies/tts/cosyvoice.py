"""CosyVoice TTS 策略实现"""
import logging
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from src.config import settings
from src.pipeline.strategies.tts.base import TTSStrategy

logger = logging.getLogger(__name__)


class CosyVoiceStrategy(TTSStrategy):
    """基于 DashScope CosyVoice 的 TTS 策略"""

    def __init__(self):
        api_key = settings.PCT_DASHSCOPE_API_KEY.get_secret_value() if settings.PCT_DASHSCOPE_API_KEY else None
        if api_key:
            dashscope.api_key = api_key

    async def synthesize(self, text: str, reference_audio: str = None, speaker_embedding: bytes = None) -> bytes:
        """
        合成语音。
        - 如果提供 reference_audio：使用 CosyVoice Zero-Shot 克隆
        - 否则：使用预置音色
        """
        try:
            if reference_audio:
                synthesizer = SpeechSynthesizer(
                    model="cosyvoice-v1",
                    voice="longxiaochun",
                )
                audio = synthesizer.call(text, prompt_audio=reference_audio)
            else:
                synthesizer = SpeechSynthesizer(
                    model="sambert-zhiqi-v1",
                    voice="zhiqi",
                )
                audio = synthesizer.call(text)

            if audio.get_audio_data() is not None:
                return audio.get_audio_data()
            else:
                raise RuntimeError(f"TTS synthesis returned no data: {audio.get_response()}")
        except Exception as e:
            if reference_audio:
                logger.warning(f"CosyVoice Zero-Shot failed ({e}), falling back to standard voice...")
                return await self.synthesize(text, reference_audio=None)
            raise
