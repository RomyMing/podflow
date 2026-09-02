from abc import ABC, abstractmethod

class TextSegment:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text

class TranslationStrategy(ABC):
    @abstractmethod
    async def translate(self, segments: list[TextSegment], context: str) -> list[str]:
        pass
