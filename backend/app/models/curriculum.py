import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Curriculum(Base):
    __tablename__ = "curricula"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_format: Mapped[str | None] = mapped_column(String(32))  # 'json' | 'markdown' | 'manual'
    raw_content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    course: Mapped["Course"] = relationship(back_populates="curricula")
    objectives: Mapped[list["Objective"]] = relationship(back_populates="curriculum", cascade="all, delete-orphan")


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("objectives.id", ondelete="CASCADE"))
    code: Mapped[str | None] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    bloom_level: Mapped[str | None] = mapped_column(String(16))
    position: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="objectives")
    children: Mapped[list["Objective"]] = relationship(back_populates="parent")
    parent: Mapped["Objective | None"] = relationship(back_populates="children", remote_side="Objective.id")
