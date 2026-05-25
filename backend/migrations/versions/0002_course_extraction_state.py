"""course extraction state

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("courses", sa.Column(
        "topic_extraction_status",
        sa.String(16),
        nullable=True,
        comment="null | running | done | failed",
    ))
    op.add_column("courses", sa.Column(
        "gap_report",
        postgresql.JSONB,
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("courses", "gap_report")
    op.drop_column("courses", "topic_extraction_status")
