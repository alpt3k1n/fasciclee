import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models import Course, TopicNode, TopicNodeObjective, Objective
from app.schemas.topic import TopicGraphOut, TopicNodeOut, TopicNodeUpdate, GapReportItem

router = APIRouter(prefix="/api/courses", tags=["topic-graph"])


@router.post("/{course_id}/extract-topic-graph", status_code=202)
async def trigger_extraction(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    if course.topic_extraction_status == "running":
        raise HTTPException(409, "Extraction already running")

    import redis
    from rq import Queue
    conn = redis.from_url(settings.redis_url)
    q = Queue("vps_queue", connection=conn)
    job = q.enqueue(
        "app.workers.topic_extraction.extract_topic_graph",
        str(course_id),
        job_timeout=300,
    )
    course.topic_extraction_status = "running"
    await db.commit()
    return {"job_id": job.id, "status": "queued"}


@router.get("/{course_id}/topic-graph", response_model=TopicGraphOut)
async def get_topic_graph(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")

    nodes = await _load_node_tree(course_id, db)
    gap_report = [GapReportItem(**g) for g in (course.gap_report or [])]

    def count_all(ns: list[TopicNodeOut]) -> int:
        total = 0
        for n in ns:
            total += 1 + count_all(n.children)
        return total

    def all_approved(ns: list[TopicNodeOut]) -> bool:
        for n in ns:
            if n.status != "approved":
                return False
            if not all_approved(n.children):
                return False
        return True

    total = count_all(nodes)
    return TopicGraphOut(
        extraction_status=course.topic_extraction_status,
        nodes=nodes,
        gap_report=gap_report,
        all_approved=total > 0 and all_approved(nodes),
    )


@router.patch("/{course_id}/topic-graph/{node_id}", response_model=TopicNodeOut)
async def update_node(
    course_id: uuid.UUID,
    node_id: uuid.UUID,
    body: TopicNodeUpdate,
    db: AsyncSession = Depends(get_db),
):
    node = await db.get(TopicNode, node_id)
    if not node or node.course_id != course_id:
        raise HTTPException(404, "Node not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(node, k, v)

    if node.status == "auto":
        node.status = "user_edited"

    await db.commit()
    return await _node_to_out(node, db)


@router.post("/{course_id}/topic-graph/{node_id}/approve", response_model=TopicNodeOut)
async def approve_node(
    course_id: uuid.UUID,
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    node = await db.get(TopicNode, node_id)
    if not node or node.course_id != course_id:
        raise HTTPException(404, "Node not found")
    node.status = "approved"
    await db.commit()
    return await _node_to_out(node, db)


@router.post("/{course_id}/topic-graph/approve-all", status_code=204)
async def approve_all(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TopicNode).where(TopicNode.course_id == course_id)
    )
    for node in result.scalars().all():
        node.status = "approved"
    await db.commit()


@router.delete("/{course_id}/topic-graph/{node_id}", status_code=204)
async def delete_node(
    course_id: uuid.UUID,
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    node = await db.get(TopicNode, node_id)
    if not node or node.course_id != course_id:
        raise HTTPException(404, "Node not found")
    await db.delete(node)
    await db.commit()


@router.post("/{course_id}/topic-graph/nodes", response_model=TopicNodeOut, status_code=201)
async def create_node(
    course_id: uuid.UUID,
    body: TopicNodeUpdate,
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    node = TopicNode(
        course_id=course_id,
        title=body.title or "Yeni Konu",
        summary=body.summary,
        parent_id=body.parent_id,
        position=body.position,
        status="user_edited",
    )
    db.add(node)
    await db.commit()
    return await _node_to_out(node, db)


# --- helpers ---

async def _load_node_tree(course_id: uuid.UUID, db: AsyncSession) -> list[TopicNodeOut]:
    result = await db.execute(
        select(TopicNode).where(TopicNode.course_id == course_id).order_by(TopicNode.position)
    )
    all_nodes = result.scalars().all()

    # Load objective codes for each node
    obj_codes: dict[uuid.UUID, list[str]] = {}
    if all_nodes:
        link_result = await db.execute(
            select(TopicNodeObjective, Objective)
            .join(Objective, TopicNodeObjective.objective_id == Objective.id)
            .where(TopicNodeObjective.topic_node_id.in_([n.id for n in all_nodes]))
        )
        for link, obj in link_result.all():
            obj_codes.setdefault(link.topic_node_id, []).append(obj.code or obj.text[:20])

    by_id: dict[uuid.UUID, TopicNodeOut] = {}
    roots: list[TopicNodeOut] = []

    for node in all_nodes:
        out = TopicNodeOut(
            id=node.id,
            parent_id=node.parent_id,
            title=node.title,
            summary=node.summary,
            position=node.position,
            status=node.status,
            ai_confidence=node.ai_confidence,
            objective_codes=obj_codes.get(node.id, []),
            children=[],
        )
        by_id[node.id] = out

    for node in all_nodes:
        out = by_id[node.id]
        if node.parent_id and node.parent_id in by_id:
            by_id[node.parent_id].children.append(out)
        else:
            roots.append(out)

    return roots


async def _node_to_out(node: TopicNode, db: AsyncSession) -> TopicNodeOut:
    link_result = await db.execute(
        select(TopicNodeObjective, Objective)
        .join(Objective, TopicNodeObjective.objective_id == Objective.id)
        .where(TopicNodeObjective.topic_node_id == node.id)
    )
    codes = [obj.code or obj.text[:20] for _, obj in link_result.all()]
    return TopicNodeOut(
        id=node.id,
        parent_id=node.parent_id,
        title=node.title,
        summary=node.summary,
        position=node.position,
        status=node.status,
        ai_confidence=node.ai_confidence,
        objective_codes=codes,
        children=[],
    )


# Fix missing import
from app.config import settings
