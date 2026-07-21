from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class PlaybackEvent(Base):
    __tablename__ = "playback_events"
    __table_args__ = (
        UniqueConstraint("session_id", "event_type", "occurred_at", name="uq_playback_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    item_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    series_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    item_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    play_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position_seconds: Mapped[float] = mapped_column(Float, default=0)
    runtime_seconds: Mapped[float] = mapped_column(Float, default=0)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
