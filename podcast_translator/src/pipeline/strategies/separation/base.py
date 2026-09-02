from abc import ABC, abstractmethod

class SeparationResult:
    def __init__(self, vocal_track: str, background_track: str):
        self.vocal_track = vocal_track
        self.background_track = background_track

class SeparationStrategy(ABC):
    @abstractmethod
    async def separate(self, audio_path: str) -> SeparationResult:
        pass
