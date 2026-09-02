import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Float, String, ForeignKey
from src.models.base import Base

class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    label: Mapped[str] = mapped_column(String(50)) # e.g., 'SPEAKER_00'
    voice_embedding_url: Mapped[str | None] = mapped_column(String(500))
    reference_audio_url: Mapped[str | None] = mapped_column(String(500))
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pitch_hz: Mapped[float | None] = mapped_column(Float, nullable=True)
    voice_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    voice_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enrollment_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    task: Mapped["Task"] = relationship(back_populates="speakers")
    segments: Mapped[list["Segment"]] = relationship(back_populates="speaker")
