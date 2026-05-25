from pydantic import BaseModel
import uuid
from datetime import datetime
from app.models.source import SourceType, SourceStatus


class SourceOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    type: SourceType
    status: SourceStatus
    original_filename: str | None
    storage_key: str | None
    external_url: str | None
    metadata_: dict
    error_message: str | None
    uploaded_at: datetime
    processed_at: datetime | None
    indexed_at: datetime | None

    model_config = {"from_attributes": True}


class YouTubeAddRequest(BaseModel):
    url: str
