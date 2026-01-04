from sqlalchemy import String, DateTime, func, UniqueConstraint, Boolean, Integer
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


class ParticipantAddendum(Base):
    __tablename__ = "participant_addendum"
    __table_args__ = (
        UniqueConstraint("session_id", "participant_code", name="uq_addendum_session_participant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    participant_code: Mapped[str] = mapped_column(String(64), index=True)

    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    piece_title_favourite: Mapped[str | None] = mapped_column(String(80), nullable=True)
    piece_description_one_line: Mapped[str | None] = mapped_column(String(180), nullable=True)
    authorship_attribution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    authorship_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    return_likelihood: Mapped[int | None] = mapped_column(Integer, nullable=True)
    return_conditions: Mapped[str | None] = mapped_column(String(300), nullable=True)

    context_of_use: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    context_other: Mapped[str | None] = mapped_column(String(80), nullable=True)

    target_user: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_user_other: Mapped[str | None] = mapped_column(String(80), nullable=True)

    remove_one_thing: Mapped[str | None] = mapped_column(String(180), nullable=True)
    add_one_thing: Mapped[str | None] = mapped_column(String(180), nullable=True)

    collaboration_expectation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    collaboration_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)

    confidence_recreate_tomorrow: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
