from abc import ABC, abstractmethod

class TTSStrategy(ABC):
    @abstractmethod
    async def synthesize(self, text: str, reference_audio: str, speaker_embedding: bytes) -> bytes:
        pass
