from pydantic import BaseModel
import uuid
from datetime import datetime


class ObjectiveOut(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    code: str | None
    text: str
    bloom_level: str | None
    position: int | None
    children: list["ObjectiveOut"] = []

    model_config = {"from_attributes": True}


class CurriculumOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    source_format: str | None
    created_at: datetime
    objectives: list[ObjectiveOut] = []

    model_config = {"from_attributes": True}


class CurriculumCreate(BaseModel):
    title: str
    source_format: str  # 'json' | 'markdown' | 'manual'
    raw_content: str    # JSON string or markdown text


class ObjectiveCreate(BaseModel):
    code: str | None = None
    text: str
    bloom_level: str | None = None
    position: int | None = None
    children: list["ObjectiveCreate"] = []
