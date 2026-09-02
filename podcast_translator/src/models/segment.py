import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, Text, ForeignKey
from src.models.base import Base

class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    speaker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("speakers.id"))
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    original_text: Mapped[str | None] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text)
    original_audio_url: Mapped[str | None] = mapped_column(String(500))
    synth_audio_url: Mapped[str | None] = mapped_column(String(500))

    task: Mapped["Task"] = relationship(back_populates="segments")
    speaker: Mapped["Speaker"] = relationship(back_populates="segments")
