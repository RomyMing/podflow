"""OpenAI GPT 翻译策略实现"""
import logging
from openai import AsyncOpenAI
from src.config import settings
from src.pipeline.strategies.translation.base import TranslationStrategy, TextSegment

logger = logging.getLogger(__name__)


class OpenAITranslationStrategy(TranslationStrategy):
    """基于 OpenAI GPT-4o 的翻译策略"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.PCT_OPENAI_API_KEY.get_secret_value(),
            base_url=settings.PCT_OPENAI_BASE_URL,
        )

    async def translate(self, segments: list[TextSegment], context: str = "") -> list[str]:
        texts = [seg.text for seg in segments]
        numbered = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts))
        
        system_prompt = context or "You are a professional translator. Translate each numbered line faithfully."
        
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": numbered},
            ],
            temperature=0.3,
        )
        
        raw = response.choices[0].message.content or ""
        lines = [line.strip() for line in raw.strip().split("\n") if line.strip()]
        
        # 尝试解析 [N] 前缀
        translations = []
        for line in lines:
            if line and line[0] == '[':
                bracket_end = line.find(']')
                if bracket_end > 0:
                    line = line[bracket_end+1:].strip()
            translations.append(line)
        
        # 如果数量不匹配，用原文兜底
        while len(translations) < len(texts):
            translations.append(texts[len(translations)])
        
        return translations[:len(texts)]
