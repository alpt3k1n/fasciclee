from pydantic import BaseModel
import uuid
from datetime import datetime


class TopicNodeOut(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    title: str
    summary: str | None
    position: int | None
    status: str
    ai_confidence: float | None
    objective_codes: list[str] = []
    children: list["TopicNodeOut"] = []

    model_config = {"from_attributes": True}


class TopicNodeUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    parent_id: uuid.UUID | None = None
    position: int | None = None


class GapReportItem(BaseModel):
    objective_code: str
    objective_text: str
    issue: str
    severity: str  # high | medium | low


class TopicGraphOut(BaseModel):
    extraction_status: str | None
    nodes: list[TopicNodeOut]
    gap_report: list[GapReportItem]
    all_approved: bool
