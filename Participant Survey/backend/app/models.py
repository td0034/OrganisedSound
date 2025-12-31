from sqlalchemy import String, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Participant(Base):
    __tablename__ = "participants"

    participant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResponseSection(Base):
    __tablename__ = "response_sections"
    __table_args__ = (
        UniqueConstraint("participant_id", "section_key", name="uq_participant_section"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(String(64), index=True)
    section_key: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
