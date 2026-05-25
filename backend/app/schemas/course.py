from pydantic import BaseModel
import uuid
from datetime import datetime


class CourseCreate(BaseModel):
    name: str
    description: str | None = None
    language: str = "tr"


class CourseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    language: str | None = None


class CourseOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    language: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
