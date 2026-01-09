from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Literal

class CreateSessionRequest(BaseModel):
    rater_label: str = Field(min_length=1, max_length=64)

class SaveConsentRequest(BaseModel):
    token: str = Field(min_length=8, max_length=64)
    agreed: bool

class SaveRatingRequest(BaseModel):
    token: str = Field(min_length=8, max_length=64)
    clip_id: int
    watched_complete: bool
    watch_progress_sec: float = 0.0
    duration_sec: float = 0.0
    memorability: Optional[int] = Field(default=None, ge=1, le=7)
    perceived_agency: int = Field(ge=1, le=7)
    best_context: Optional[Literal[
        "installation_gallery",
        "live_performance",
        "background_ambience",
        "workshop_education",
        "unsure"
    ]] = None
    payload: Dict[str, Any]

class SaveSessionEndRequest(BaseModel):
    token: str = Field(min_length=8, max_length=64)
    payload: Dict[str, Any]
