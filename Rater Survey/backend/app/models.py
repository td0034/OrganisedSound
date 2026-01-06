from sqlalchemy import String, DateTime, func, UniqueConstraint, Boolean, Float, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Clip(Base):
    __tablename__ = "clips"
    clip_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    filesize: Mapped[int] = mapped_column(Integer)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Session(Base):
    __tablename__ = "sessions"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    rater_label: Mapped[str] = mapped_column(String(64), default="")
    playlist: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"clip_ids":[...]}
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("token", "clip_id", name="uq_token_clip"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), index=True)
    clip_id: Mapped[int] = mapped_column(Integer, index=True)

    watched_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    watch_progress_sec: Mapped[float] = mapped_column(Float, default=0.0)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)

    memorability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    perceived_agency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_context: Mapped[str | None] = mapped_column(String(64), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class SessionEnd(Base):
    __tablename__ = "session_end"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
