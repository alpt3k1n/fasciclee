import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Course, FascicleGeneration, Section, TopicNode
from app.models.generation import GenerationStatus
from app.schemas.generation_api import GenerationOut, GenerationCreate, SectionOut
from app.config import settings

router = APIRouter(tags=["generation"])


@router.get("/api/courses/{course_id}/generations", response_model=list[GenerationOut])
async def list_generations(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FascicleGeneration)
        .where(FascicleGeneration.course_id == course_id)
        .order_by(FascicleGeneration.started_at.desc())
    )
    gens = result.scalars().all()
    out = []
    for g in gens:
        sections = await _load_sections(g.id, db)
        out.append(GenerationOut(
            id=g.id, course_id=g.course_id, status=g.status.value,
            config=g.config, started_at=g.started_at,
            completed_at=g.completed_at, error_message=g.error_message,
            sections=sections,
        ))
    return out


@router.post("/api/courses/{course_id}/generate", response_model=GenerationOut, status_code=202)
async def start_generation(
    course_id: uuid.UUID,
    body: GenerationCreate,
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")

    # Check all nodes approved
    nodes_result = await db.execute(
        select(TopicNode).where(TopicNode.course_id == course_id)
    )
    nodes = nodes_result.scalars().all()
    if not nodes:
        raise HTTPException(422, "No topic nodes found — extract and approve topic graph first")
    if any(n.status != "approved" for n in nodes):
        raise HTTPException(422, "All topic nodes must be approved before generating")

    gen = FascicleGeneration(
        course_id=course_id,
        status=GenerationStatus.generating,
        config={
            "depth": body.depth,
            "language": body.language or course.language,
            "test_question_count": body.test_question_count,
            "include_clinical_correlations": body.include_clinical_correlations,
        },
    )
    db.add(gen)
    await db.flush()

    # Snapshot topic graph
    gen.topic_graph_snapshot = [
        {"id": str(n.id), "title": n.title, "parent_id": str(n.parent_id) if n.parent_id else None}
        for n in sorted(nodes, key=lambda n: n.position or 0)
    ]

    # Create section stubs
    for i, node in enumerate(sorted(nodes, key=lambda n: n.position or 0)):
        db.add(Section(
            generation_id=gen.id,
            topic_node_id=node.id,
            position=i,
            status="pending",
        ))

    await db.commit()
    await db.refresh(gen)

    # Enqueue
    import redis
    from rq import Queue
    conn = redis.from_url(settings.redis_url)
    q = Queue("vps_queue", connection=conn)
    q.enqueue(
        "app.workers.generation.run_generation",
        str(gen.id),
        job_timeout=3600,
    )

    sections = await _load_sections(gen.id, db)
    return GenerationOut(
        id=gen.id, course_id=gen.course_id, status=gen.status.value,
        config=gen.config, started_at=gen.started_at,
        completed_at=gen.completed_at, error_message=gen.error_message,
        sections=sections,
    )


@router.get("/api/generations/{generation_id}", response_model=GenerationOut)
async def get_generation(generation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    gen = await db.get(FascicleGeneration, generation_id)
    if not gen:
        raise HTTPException(404, "Generation not found")
    sections = await _load_sections(gen.id, db)
    return GenerationOut(
        id=gen.id, course_id=gen.course_id, status=gen.status.value,
        config=gen.config, started_at=gen.started_at,
        completed_at=gen.completed_at, error_message=gen.error_message,
        sections=sections,
    )


@router.post("/api/generations/{generation_id}/cancel", status_code=204)
async def cancel_generation(generation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    gen = await db.get(FascicleGeneration, generation_id)
    if not gen:
        raise HTTPException(404, "Generation not found")
    if gen.status not in (GenerationStatus.generating, GenerationStatus.qa_running):
        raise HTTPException(409, "Generation is not running")
    gen.status = GenerationStatus.cancelled
    await db.commit()


async def _load_sections(generation_id: uuid.UUID, db: AsyncSession) -> list[SectionOut]:
    result = await db.execute(
        select(Section, TopicNode)
        .join(TopicNode, Section.topic_node_id == TopicNode.id)
        .where(Section.generation_id == generation_id)
        .order_by(Section.position)
    )
    return [
        SectionOut(
            id=s.id, topic_node_id=s.topic_node_id, topic_node_title=n.title,
            position=s.position, status=s.status, retry_count=s.retry_count,
            pass1_outline=s.pass1_outline, pass2_expanded_md=s.pass2_expanded_md,
            pass3_enriched_md=s.pass3_enriched_md, pass4_questions_md=s.pass4_questions_md,
            final_md=s.final_md, generated_at=s.generated_at,
        )
        for s, n in result.all()
    ]
