from pydantic import BaseModel
import uuid
from datetime import datetime


class SectionOut(BaseModel):
    id: uuid.UUID
    topic_node_id: uuid.UUID
    topic_node_title: str
    position: int | None
    status: str
    retry_count: int
    pass1_outline: dict | None
    pass2_expanded_md: str | None
    pass3_enriched_md: str | None
    pass4_questions_md: str | None
    final_md: str | None
    generated_at: datetime | None

    model_config = {"from_attributes": True}


class GenerationOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    status: str
    config: dict
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    sections: list[SectionOut] = []

    model_config = {"from_attributes": True}


class GenerationCreate(BaseModel):
    depth: str = "comprehensive"
    language: str | None = None          # defaults to course.language
    test_question_count: int = 5
    include_clinical_correlations: bool = True
