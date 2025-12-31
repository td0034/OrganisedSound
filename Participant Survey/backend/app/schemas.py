from pydantic import BaseModel, Field
from typing import Any, Dict

class SaveSectionRequest(BaseModel):
    participant_id: str = Field(min_length=1, max_length=64)
    section_key: str = Field(min_length=1, max_length=64)
    payload: Dict[str, Any]
