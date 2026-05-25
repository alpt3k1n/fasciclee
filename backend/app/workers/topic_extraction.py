"""
Topic graph extraction worker.
Runs on vps_queue (LLM call, no GPU needed).

Flow:
  1. Load curriculum tree + source chunk summaries
  2. Build extraction prompt → call DeepSeek
  3. Parse JSON → insert TopicNode records
  4. Link nodes to source chunks (via proposed_source_ids from LLM)
  5. Save gap_report on Course
"""
import uuid
import json
import asyncio
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings

SYSTEM_PROMPT = """\
You design topic hierarchies for educational fascicles.
Output ONLY valid JSON matching the exact schema provided. No prose, no fences.
"""

USER_TEMPLATE = """\
Course: {course_name}
Language: {language}

Curriculum objectives (hierarchical):
{curriculum_yaml}

Available source materials:
{source_summaries}

Task: Propose a topic graph that:
1. Covers EVERY leaf objective in the curriculum
2. Groups objectives into coherent topic nodes (1-3 objectives per leaf node)
3. Maintains a parent-child hierarchy mirroring the curriculum
4. For each node, identifies which source IDs contribute to it
5. Notes confidence (0.0-1.0) based on source coverage

Output this exact JSON schema (no other text):
{{
  "topic_tree": [
    {{
      "tmp_id": "n1",
      "title": "...",
      "summary": "1-2 sentence summary of what this node covers",
      "parent_tmp_id": null,
      "objective_codes": ["1.1", "1.2"],
      "proposed_source_ids": ["<uuid>", "<uuid>"],
      "ai_confidence": 0.85
    }}
  ],
  "gap_report": [
    {{
      "objective_code": "3.4",
      "objective_text": "...",
      "issue": "No source material covers this objective",
      "severity": "high"
    }}
  ]
}}

Constraints:
- Every leaf objective must appear in at least one node's objective_codes
- proposed_source_ids must only contain IDs from the sources listed above
- severity must be: high | medium | low
- parent_tmp_id must be null for root nodes or match another node's tmp_id
"""


def extract_topic_graph(course_id: str):
    """RQ job entry point."""
    engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
    with Session(engine) as db:
        from app.models import Course, Curriculum, Objective, Source, SourceChunk, TopicNode, TopicNodeObjective, TopicNodeSource
        from app.models.source import SourceStatus

        course = db.get(Course, uuid.UUID(course_id))
        if not course:
            logger.error(f"Course {course_id} not found")
            return

        course.topic_extraction_status = "running"
        db.commit()

        try:
            # 1. Load curriculum tree
            curricula = db.execute(
                select(Curriculum).where(Curriculum.course_id == course.id)
            ).scalars().all()
            if not curricula:
                raise ValueError("No curriculum found — add a curriculum before extracting topic graph")

            all_objectives = db.execute(
                select(Objective).where(
                    Objective.curriculum_id.in_([c.id for c in curricula])
                ).order_by(Objective.position)
            ).scalars().all()

            curriculum_yaml = _objectives_to_yaml(all_objectives)

            # 2. Load source summaries (indexed sources only)
            sources = db.execute(
                select(Source).where(
                    Source.course_id == course.id,
                    Source.status == SourceStatus.indexed,
                )
            ).scalars().all()

            if not sources:
                raise ValueError("No indexed sources yet — wait for ingestion to complete")

            source_summaries = _build_source_summaries(sources, db)

            # 3. Call LLM
            prompt = USER_TEMPLATE.format(
                course_name=course.name,
                language=course.language,
                curriculum_yaml=curriculum_yaml,
                source_summaries=source_summaries,
            )
            result = asyncio.run(_call_llm(prompt))

            # 4. Delete existing auto-extracted nodes (keep user_edited/approved)
            existing = db.execute(
                select(TopicNode).where(
                    TopicNode.course_id == course.id,
                    TopicNode.status == "auto",
                )
            ).scalars().all()
            for node in existing:
                db.delete(node)
            db.flush()

            # 5. Insert new nodes
            obj_by_code = {o.code: o for o in all_objectives if o.code}
            src_by_id = {str(s.id): s for s in sources}

            tmp_to_db: dict[str, TopicNode] = {}
            nodes_data = result.get("topic_tree", [])

            # Two-pass: first create all nodes, then link parents
            for i, node_data in enumerate(nodes_data):
                node = TopicNode(
                    course_id=course.id,
                    title=node_data.get("title", ""),
                    summary=node_data.get("summary"),
                    position=i,
                    status="auto",
                    ai_confidence=node_data.get("ai_confidence"),
                )
                db.add(node)
                db.flush()
                tmp_to_db[node_data["tmp_id"]] = node

            # Link parents
            for node_data in nodes_data:
                parent_tmp = node_data.get("parent_tmp_id")
                if parent_tmp and parent_tmp in tmp_to_db:
                    tmp_to_db[node_data["tmp_id"]].parent_id = tmp_to_db[parent_tmp].id

            db.flush()

            # Link objectives and sources
            for node_data in nodes_data:
                node = tmp_to_db[node_data["tmp_id"]]

                for code in node_data.get("objective_codes", []):
                    if code in obj_by_code:
                        link = TopicNodeObjective(
                            topic_node_id=node.id,
                            objective_id=obj_by_code[code].id,
                        )
                        db.add(link)

                # Link top chunks from proposed sources
                for src_id in node_data.get("proposed_source_ids", []):
                    if src_id in src_by_id:
                        chunks = db.execute(
                            select(SourceChunk)
                            .where(SourceChunk.source_id == uuid.UUID(src_id))
                            .order_by(SourceChunk.chunk_index)
                            .limit(5)
                        ).scalars().all()
                        for chunk in chunks:
                            db.add(TopicNodeSource(
                                topic_node_id=node.id,
                                source_chunk_id=chunk.id,
                            ))

            # 6. Save gap report
            course.gap_report = result.get("gap_report", [])
            course.topic_extraction_status = "done"
            db.commit()
            logger.info(f"Topic graph extracted for course {course_id}: {len(nodes_data)} nodes")

        except Exception as e:
            logger.exception(f"Topic extraction failed for course {course_id}")
            course.topic_extraction_status = "failed"
            db.commit()
            raise


async def _call_llm(user_prompt: str) -> dict:
    from app.llm import chat

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    for attempt in range(3):
        try:
            raw = await chat("topic_extraction", messages, temperature=0.2, max_tokens=8192)
            cleaned = _strip_fences(raw)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM JSON parse failed (attempt {attempt + 1}): {e}")
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "Output was not valid JSON. Return ONLY the JSON object with no other text."})
    raise ValueError("LLM failed to produce valid JSON after 3 attempts")


def _objectives_to_yaml(objectives: list, indent: int = 0) -> str:
    from collections import defaultdict
    by_parent: dict = defaultdict(list)
    for o in objectives:
        by_parent[o.parent_id].append(o)

    def render(parent_id, level):
        lines = []
        for obj in sorted(by_parent[parent_id], key=lambda x: x.position or 0):
            prefix = "  " * level + "- "
            code = f"[{obj.code}] " if obj.code else ""
            bloom = f" ({obj.bloom_level})" if obj.bloom_level else ""
            lines.append(f"{prefix}{code}{obj.text}{bloom}")
            lines.extend(render(obj.id, level + 1))
        return lines

    return "\n".join(render(None, 0))


def _build_source_summaries(sources: list, db: Session) -> str:
    from app.models import SourceChunk
    lines = []
    for src in sources:
        chunks = db.execute(
            select(SourceChunk)
            .where(SourceChunk.source_id == src.id)
            .order_by(SourceChunk.chunk_index)
            .limit(3)
        ).scalars().all()
        preview = " … ".join(c.text[:150] for c in chunks)
        name = src.original_filename or src.external_url or src.type.value
        total_chunks = db.execute(
            select(SourceChunk).where(SourceChunk.source_id == src.id)
        ).scalars().all()
        lines.append(
            f'- ID: {src.id} | Type: {src.type.value} | Name: "{name}" | '
            f'Chunks: {len(total_chunks)} | Preview: {preview[:300]}'
        )
    return "\n".join(lines)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
