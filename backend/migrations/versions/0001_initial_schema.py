"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enums (one-time creation; columns use create_type=False) ---
    for stmt in [
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='source_type') THEN CREATE TYPE source_type AS ENUM ('pdf','audio','video','youtube','image','text','curriculum'); END IF; END $$",
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='source_status') THEN CREATE TYPE source_status AS ENUM ('pending','processing','processed','indexed','failed'); END IF; END $$",
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='generation_status') THEN CREATE TYPE generation_status AS ENUM ('planning','awaiting_approval','generating','qa_running','compiling','completed','failed','cancelled'); END IF; END $$",
    ]:
        op.execute(stmt)

    # --- courses ---
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("language", sa.String(8), nullable=False, server_default="tr"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # --- sources ---
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Enum("pdf","audio","video","youtube","image","text","curriculum", name="source_type", create_type=False), nullable=False),
        sa.Column("status", sa.Enum("pending","processing","processed","indexed","failed", name="source_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("original_filename", sa.Text),
        sa.Column("storage_key", sa.Text),
        sa.Column("external_url", sa.Text),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sources_course_id_status", "sources", ["course_id", "status"])

    # --- source_chunks ---
    op.create_table(
        "source_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("location", postgresql.JSONB, nullable=False),
        sa.Column("qdrant_point_id", sa.Text),
        sa.Column("embedded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_id", "chunk_index", name="uq_source_chunks_source_index"),
    )
    op.create_index("ix_source_chunks_source_id", "source_chunks", ["source_id"])

    # --- curricula ---
    op.create_table(
        "curricula",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("source_format", sa.String(32)),
        sa.Column("raw_content", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_curricula_course_id", "curricula", ["course_id"])

    # --- objectives ---
    op.create_table(
        "objectives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("curriculum_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("objectives.id", ondelete="CASCADE")),
        sa.Column("code", sa.String(32)),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("bloom_level", sa.String(16)),
        sa.Column("position", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_objectives_curriculum_parent", "objectives", ["curriculum_id", "parent_id"])

    # --- topic_nodes ---
    op.create_table(
        "topic_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topic_nodes.id", ondelete="CASCADE")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("position", sa.Integer),
        sa.Column("status", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("ai_confidence", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_topic_nodes_course_parent", "topic_nodes", ["course_id", "parent_id"])

    # --- topic_node_objectives ---
    op.create_table(
        "topic_node_objectives",
        sa.Column("topic_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topic_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("objective_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("objectives.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
    )

    # --- topic_node_sources ---
    op.create_table(
        "topic_node_sources",
        sa.Column("topic_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topic_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_chunks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("similarity", sa.Float),
    )

    # --- fascicle_generations ---
    op.create_table(
        "fascicle_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Enum(
            "planning","awaiting_approval","generating","qa_running",
            "compiling","completed","failed","cancelled",
            name="generation_status", create_type=False,
        ), nullable=False, server_default="planning"),
        sa.Column("topic_graph_snapshot", postgresql.JSONB),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
    )
    op.create_index("ix_generations_course_id", "fascicle_generations", ["course_id"])

    # --- sections ---
    op.create_table(
        "sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fascicle_generations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topic_nodes.id"), nullable=False),
        sa.Column("position", sa.Integer),
        sa.Column("pass1_outline", postgresql.JSONB),
        sa.Column("pass2_expanded_md", sa.Text),
        sa.Column("pass3_enriched_md", sa.Text),
        sa.Column("pass4_questions_md", sa.Text),
        sa.Column("final_md", sa.Text),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sections_generation_position", "sections", ["generation_id", "position"])

    # --- test_questions ---
    op.create_table(
        "test_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("question_format", sa.String(16)),
        sa.Column("options", postgresql.JSONB),
        sa.Column("correct_answer", sa.Text),
        sa.Column("explanation", sa.Text),
        sa.Column("difficulty", sa.String(16)),
        sa.Column("objective_ids", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_test_questions_section_id", "test_questions", ["section_id"])

    # --- qa_reports ---
    op.create_table(
        "qa_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pass_number", sa.Integer),
        sa.Column("objective_coverage", postgresql.JSONB),
        sa.Column("has_unused_source", sa.Boolean),
        sa.Column("unused_source_summary", sa.Text),
        sa.Column("recommendation", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_qa_reports_section_id", "qa_reports", ["section_id"])

    # --- artifacts ---
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fascicle_generations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(16)),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_artifacts_generation_id", "artifacts", ["generation_id"])

    # updated_at auto-trigger for courses and topic_nodes
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    for tbl in ("courses", "topic_nodes"):
        op.execute(f"""
            CREATE TRIGGER trg_{tbl}_updated_at
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """)


def downgrade() -> None:
    for tbl in ("courses", "topic_nodes"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tbl}_updated_at ON {tbl};")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at;")

    op.drop_table("artifacts")
    op.drop_table("qa_reports")
    op.drop_table("test_questions")
    op.drop_table("sections")
    op.drop_table("fascicle_generations")
    op.drop_table("topic_node_sources")
    op.drop_table("topic_node_objectives")
    op.drop_table("topic_nodes")
    op.drop_table("objectives")
    op.drop_table("curricula")
    op.drop_table("source_chunks")
    op.drop_table("sources")
    op.drop_table("courses")

    op.execute("DROP TYPE IF EXISTS generation_status;")
    op.execute("DROP TYPE IF EXISTS source_status;")
    op.execute("DROP TYPE IF EXISTS source_type;")
