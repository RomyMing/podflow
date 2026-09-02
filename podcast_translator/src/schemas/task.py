import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class TaskCreateRequest(BaseModel):
    config: Optional[Dict[str, Any]] = None


class TaskResumeRequest(BaseModel):
    config: Optional[Dict[str, Any]] = None


class TaskStageRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: str
    attempt: int
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    items_total: Optional[int] = None
    items_done: Optional[int] = None
    cost_estimate: Optional[float] = None
    error_code: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class TaskSpeakerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    gender: Optional[str] = None
    pitch_hz: Optional[float] = None
    voice_provider: Optional[str] = None
    voice_id: Optional[str] = None
    voice_model: Optional[str] = None
    enrollment_status: Optional[str] = None
    fallback_reason: Optional[str] = None


class TaskSegmentResponse(BaseModel):
    index: int
    speaker_label: Optional[str] = None
    start_time: float
    end_time: float
    original_text: Optional[str] = None
    translated_text: Optional[str] = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    current_stage: Optional[str] = None
    progress_percent: int
    source_file_name: Optional[str] = None
    source_audio_url: Optional[str] = None
    output_audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    eta_seconds: Optional[float] = None
    config: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    paused_at: Optional[datetime] = None
    pause_reason_code: Optional[str] = None
    provider_error_code: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None
    stage_runs: list[TaskStageRunResponse] = Field(default_factory=list)
    speakers: list[TaskSpeakerResponse] = Field(default_factory=list)


class WSProgressMessage(BaseModel):
    task_id: str
    stage: Optional[str] = None
    progress_percent: int
    status: str
    error_message: Optional[str] = None
    pause_reason_code: Optional[str] = None
    provider_error_code: Optional[str] = None
    output_audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    processed_seconds: Optional[float] = None
    total_seconds: Optional[float] = None
    chunk_index: Optional[int] = None
    chunk_count: Optional[int] = None
    stage_progress_percent: Optional[int] = None
    eta_seconds: Optional[float] = None
    finished_at: Optional[datetime] = None
    event: Optional[str] = None
