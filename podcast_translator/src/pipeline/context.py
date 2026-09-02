from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional
import uuid


class TaskStage(Enum):
    UPLOADED = "uploaded"
    PREPARING = "preparing"
    SEPARATING = "source_separation"
    DIARIZING = "speaker_diarization"
    TRANSCRIBING = "asr_transcription"
    TRANSLATING = "translation"
    SYNTHESIZING = "voice_clone_tts"
    ALIGNING = "temporal_alignment"
    MIXING = "final_mixing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineContext:
    task_id: str
    source_audio_url: str
    user_id: Optional[uuid.UUID] = None
    status: str = "PENDING"
    error_message: Optional[str] = None
    source_language: Optional[str] = None
    target_language: str = "zh"
    config: dict | None = None
    vocal_track_url: Optional[str] = None
    background_track_url: Optional[str] = None
    speakers: Optional[List[dict]] = None
    segments: Optional[List[dict]] = None
    synth_segments: Optional[List[dict]] = None
    output_audio_url: Optional[str] = None
    invalidated_stages: set[str] = field(default_factory=set, repr=False)
    lifecycle_hooks: Any = field(default=None, repr=False)
