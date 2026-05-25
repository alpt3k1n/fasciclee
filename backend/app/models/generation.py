import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, Integer, BigInteger, Boolean, ForeignKey, DateTime, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import enum
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class GenerationStatus(str, enum.Enum):
    planning = "planning"
    awaiting_approval = "awaiting_approval"
    generating = "generating"
    qa_running = "qa_running"
    compiling = "compiling"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class FascicleGeneration(Base):
    __tablename__ = "fascicle_generations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[GenerationStatus] = mapped_column(SAEnum(GenerationStatus, name="generation_status"), nullable=False, default=GenerationStatus.planning)
    topic_graph_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    course: Mapped["Course"] = relationship(back_populates="generations")
    sections: Mapped[list["Section"]] = relationship(back_populates="generation", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="generation", cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fascicle_generations.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topic_nodes.id"), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer)
    pass1_outline: Mapped[dict | None] = mapped_column(JSONB)
    pass2_expanded_md: Mapped[str | None] = mapped_column(Text)
    pass3_enriched_md: Mapped[str | None] = mapped_column(Text)
    pass4_questions_md: Mapped[str | None] = mapped_column(Text)
    final_md: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    generation: Mapped["FascicleGeneration"] = relationship(back_populates="sections")
    test_questions: Mapped[list["TestQuestion"]] = relationship(back_populates="section", cascade="all, delete-orphan")
    qa_reports: Mapped[list["QAReport"]] = relationship(back_populates="section", cascade="all, delete-orphan")


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_format: Mapped[str | None] = mapped_column(String(16))  # mcq | short_answer | vaka_based
    options: Mapped[list | None] = mapped_column(JSONB)
    correct_answer: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(16))
    objective_ids: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    section: Mapped["Section"] = relationship(back_populates="test_questions")


class QAReport(Base):
    __tablename__ = "qa_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True)
    pass_number: Mapped[int | None] = mapped_column(Integer)
    objective_coverage: Mapped[dict | None] = mapped_column(JSONB)
    has_unused_source: Mapped[bool | None] = mapped_column(Boolean)
    unused_source_summary: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    section: Mapped["Section"] = relationship(back_populates="qa_reports")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fascicle_generations.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str | None] = mapped_column(String(16))  # pdf | html | sources_json
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    generation: Mapped["FascicleGeneration"] = relationship(back_populates="artifacts")
