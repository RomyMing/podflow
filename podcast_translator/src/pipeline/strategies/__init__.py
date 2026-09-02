"""
ARCH-01 修复：策略模式工厂 — 根据 config.py 中的 Provider 配置动态选择具体策略实现

使用方法:
    from src.pipeline.strategies import StrategyFactory
    
    asr = StrategyFactory.create_asr_strategy()    # 根据 PCT_ASR_PROVIDER 返回
    tts = StrategyFactory.create_tts_strategy()    # 根据 PCT_TTS_PROVIDER 返回
    translator = StrategyFactory.create_translation_strategy()  # 根据 PCT_TRANSLATION_PROVIDER 返回
"""
import logging
from src.config import settings

logger = logging.getLogger(__name__)


class StrategyFactory:
    """统一策略工厂 — 根据环境变量 / Settings 动态分发"""

    @staticmethod
    def create_asr_strategy():
        """创建 ASR 策略实例"""
        provider = settings.PCT_ASR_PROVIDER
        if provider == "whisper":
            from src.pipeline.strategies.asr.whisper import WhisperStrategy
            return WhisperStrategy()
        elif provider == "sensevoice":
            from src.pipeline.strategies.asr.sensevoice import SenseVoiceStrategy
            return SenseVoiceStrategy()
        else:
            raise ValueError(f"Unknown ASR provider: {provider}. Supported: whisper, sensevoice")

    @staticmethod
    def create_tts_strategy():
        """创建 TTS 策略实例"""
        provider = settings.PCT_TTS_PROVIDER
        if provider == "cosyvoice":
            from src.pipeline.strategies.tts.cosyvoice import CosyVoiceStrategy
            return CosyVoiceStrategy()
        elif provider == "fish_speech":
            from src.pipeline.strategies.tts.fish_speech import FishSpeechStrategy
            return FishSpeechStrategy()
        else:
            raise ValueError(f"Unknown TTS provider: {provider}. Supported: cosyvoice, fish_speech")

    @staticmethod
    def create_translation_strategy():
        """创建翻译策略实例"""
        provider = settings.PCT_TRANSLATION_PROVIDER
        if provider == "openai":
            from src.pipeline.strategies.translation.openai_gpt import OpenAITranslationStrategy
            return OpenAITranslationStrategy()
        elif provider == "deepseek":
            from src.pipeline.strategies.translation.deepseek import DeepSeekTranslationStrategy
            return DeepSeekTranslationStrategy()
        else:
            raise ValueError(f"Unknown Translation provider: {provider}. Supported: openai, deepseek")

    @staticmethod
    def create_separation_strategy():
        """创建音源分离策略实例（当前仅支持 Demucs）"""
        from src.pipeline.strategies.separation.demucs import DemucsStrategy
        return DemucsStrategy()
