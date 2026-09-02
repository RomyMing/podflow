import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    monthly_quota: int
    monthly_used: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

class QuotaResponse(BaseModel):
    total: int
    used: int
    remaining: int
    reset_at: Optional[datetime] = None


ApiKeyProvider = Literal["dashscope", "openai", "deepseek", "huggingface", "elevenlabs"]


class UserApiKeyUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    region: Optional[str] = None
    enabled: bool = True


class UserApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    masked_key: str
    base_url: Optional[str] = None
    region: Optional[str] = None
    enabled: bool
    verified_at: Optional[datetime] = None
    last_error: Optional[str] = None
    updated_at: datetime
