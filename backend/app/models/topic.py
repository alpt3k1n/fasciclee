import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, Integer, Float, ForeignKey, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class TopicNode(Base):
    __tablename__ = "topic_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("topic_nodes.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="auto")  # auto | user_edited | approved
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    course: Mapped["Course"] = relationship(back_populates="topic_nodes")
    children: Mapped[list["TopicNode"]] = relationship(back_populates="parent")
    parent: Mapped["TopicNode | None"] = relationship(back_populates="children", remote_side="TopicNode.id")
    objective_links: Mapped[list["TopicNodeObjective"]] = relationship(back_populates="topic_node", cascade="all, delete-orphan")
    source_links: Mapped[list["TopicNodeSource"]] = relationship(back_populates="topic_node", cascade="all, delete-orphan")


class TopicNodeObjective(Base):
    __tablename__ = "topic_node_objectives"

    topic_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topic_nodes.id", ondelete="CASCADE"), primary_key=True)
    objective_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("objectives.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    topic_node: Mapped["TopicNode"] = relationship(back_populates="objective_links")


class TopicNodeSource(Base):
    __tablename__ = "topic_node_sources"

    topic_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topic_nodes.id", ondelete="CASCADE"), primary_key=True)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("source_chunks.id", ondelete="CASCADE"), primary_key=True)
    similarity: Mapped[float | None] = mapped_column(Float)

    topic_node: Mapped["TopicNode"] = relationship(back_populates="source_links")
