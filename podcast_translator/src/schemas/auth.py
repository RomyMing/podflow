from pydantic import BaseModel, Field
from datetime import datetime

class SendSMSRequest(BaseModel):
    phone: str = Field(..., description="Phone number to send SMS to")

class SMSLoginRequest(BaseModel):
    phone: str = Field(..., description="Phone number")
    code: str = Field(..., description="6-digit verification code")

class WechatLoginRequest(BaseModel):
    code: str = Field(..., description="WeChat OAuth authorization code")

class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    exp: datetime
