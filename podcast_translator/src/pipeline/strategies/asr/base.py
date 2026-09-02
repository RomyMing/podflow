from abc import ABC, abstractmethod

class TranscriptionResult:
    def __init__(self, text: str, word_timestamps: list):
        self.text = text
        self.word_timestamps = word_timestamps

class ASRStrategy(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        pass
