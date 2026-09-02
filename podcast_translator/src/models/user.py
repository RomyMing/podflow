import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Boolean, CheckConstraint
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.task import Task

class User(Base):
    """
    用户模型，支持手机号验证码和微信授权登录。
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    wechat_openid: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    nickname: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    
    # 状态控制
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 配额系统
    monthly_quota: Mapped[int] = mapped_column(Integer, default=5)
    monthly_used: Mapped[int] = mapped_column(Integer, default=0)
    quota_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    api_keys: Mapped[list["UserApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('phone IS NOT NULL OR wechat_openid IS NOT NULL', name='chk_user_identity'),
    )
