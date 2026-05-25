import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="tr")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    sources: Mapped[list["Source"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    curricula: Mapped[list["Curriculum"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    topic_nodes: Mapped[list["TopicNode"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    generations: Mapped[list["FascicleGeneration"]] = relationship(back_populates="course", cascade="all, delete-orphan")
