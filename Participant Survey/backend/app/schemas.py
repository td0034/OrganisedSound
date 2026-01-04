import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Dict, List, Optional, Literal

PARTICIPANT_CODE_RE = re.compile(r"^\d{4}[A-Za-z]$")
CONTEXT_OF_USE_OPTIONS = {
    "home_sketching",
    "studio_production",
    "live_performance",
    "gallery_installation",
    "festival_public_space",
    "education_workshop",
    "wellbeing_relaxation",
    "other"
}
TARGET_USER_OPTIONS = {
    "complete_beginner",
    "hobbyist",
    "musician_performer",
    "composer_producer",
    "audience_participant",
    "educator_facilitator",
    "other"
}

class SaveSectionRequest(BaseModel):
    participant_id: str = Field(min_length=1, max_length=64)
    section_key: str = Field(min_length=1, max_length=64)
    payload: Dict[str, Any]


def normalize_participant_code(value: str) -> str:
    normalized = (value or "").strip().upper()
    if not PARTICIPANT_CODE_RE.match(normalized):
        raise ValueError("participant_code must be 4 digits + 1 letter")
    return normalized


class SaveAddendumRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    participant_code: str = Field(min_length=1, max_length=64)
    skipped: bool = False

    piece_title_favourite: Optional[str] = Field(default=None, max_length=80)
    piece_description_one_line: Optional[str] = Field(default=None, max_length=180)
    authorship_attribution: Optional[Literal["me", "system", "shared", "unsure"]] = None
    authorship_reason: Optional[str] = Field(default=None, max_length=300)

    return_likelihood: Optional[int] = Field(default=None, ge=1, le=7)
    return_conditions: Optional[str] = Field(default=None, max_length=300)

    context_of_use: Optional[List[str]] = None
    context_other: Optional[str] = Field(default=None, max_length=80)

    target_user: Optional[Literal[
        "complete_beginner",
        "hobbyist",
        "musician_performer",
        "composer_producer",
        "audience_participant",
        "educator_facilitator",
        "other"
    ]] = None
    target_user_other: Optional[str] = Field(default=None, max_length=80)

    remove_one_thing: Optional[str] = Field(default=None, max_length=180)
    add_one_thing: Optional[str] = Field(default=None, max_length=180)

    collaboration_expectation: Optional[Literal["easier_visuals", "easier_notes", "about_same", "not_sure"]] = None
    collaboration_reason: Optional[str] = Field(default=None, max_length=240)

    confidence_recreate_tomorrow: Optional[int] = Field(default=None, ge=1, le=7)

    @field_validator("participant_code")
    @classmethod
    def _validate_participant_code(cls, v: str) -> str:
        return normalize_participant_code(v)

    @field_validator("session_id")
    @classmethod
    def _normalize_session_id(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("context_of_use", mode="before")
    @classmethod
    def _coerce_context(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return [v]
        return v

    @model_validator(mode="after")
    def _validate_required(self):
        if self.context_of_use:
            invalid = [v for v in self.context_of_use if v not in CONTEXT_OF_USE_OPTIONS]
            if invalid:
                raise ValueError(f"Invalid context_of_use values: {invalid}")

        if not self.skipped:
            missing = []
            if not self.piece_title_favourite:
                missing.append("piece_title_favourite")
            if not self.authorship_attribution:
                missing.append("authorship_attribution")
            if self.return_likelihood is None:
                missing.append("return_likelihood")
            if not self.context_of_use:
                missing.append("context_of_use")
            if not self.target_user:
                missing.append("target_user")
            if not self.collaboration_expectation:
                missing.append("collaboration_expectation")
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")

            if self.context_of_use and "other" in self.context_of_use and not self.context_other:
                raise ValueError("context_other is required when context_of_use includes 'other'")
            if self.target_user == "other" and not self.target_user_other:
                raise ValueError("target_user_other is required when target_user is 'other'")

        return self


class SkipAddendumRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    participant_code: str = Field(min_length=1, max_length=64)

    @field_validator("participant_code")
    @classmethod
    def _validate_participant_code(cls, v: str) -> str:
        return normalize_participant_code(v)

    @field_validator("session_id")
    @classmethod
    def _normalize_session_id(cls, v: str) -> str:
        return (v or "").strip()
