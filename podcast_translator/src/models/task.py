import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(50))
    current_stage: Mapped[str | None] = mapped_column(String(50))
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    source_file_name: Mapped[str | None] = mapped_column(String(255))
    source_audio_url: Mapped[str | None] = mapped_column(String(500))
    output_audio_url: Mapped[str | None] = mapped_column(String(500))
    audio_duration: Mapped[float | None] = mapped_column(Float)
    config: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(String(1000))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    run_generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="tasks")
    speakers: Mapped[list["Speaker"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    stage_runs: Mapped[list["TaskStageRun"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStageRun.started_at",
        lazy="selectin",
    )
