import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Course, Curriculum, Objective
from app.schemas.curriculum import CurriculumCreate, CurriculumOut, ObjectiveOut
from app.workers.curriculum_parser import parse_curriculum

router = APIRouter(prefix="/api/courses", tags=["curriculum"])


@router.get("/{course_id}/curriculum", response_model=list[CurriculumOut])
async def list_curricula(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Curriculum).where(Curriculum.course_id == course_id).order_by(Curriculum.created_at)
    )
    curricula = result.scalars().all()
    out = []
    for c in curricula:
        objectives = await _load_objective_tree(c.id, db)
        out.append(CurriculumOut(
            id=c.id,
            course_id=c.course_id,
            title=c.title,
            source_format=c.source_format,
            created_at=c.created_at,
            objectives=objectives,
        ))
    return out


@router.post("/{course_id}/curriculum", response_model=CurriculumOut, status_code=201)
async def create_curriculum(
    course_id: uuid.UUID,
    body: CurriculumCreate,
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")

    # Parse raw content → structured dict
    try:
        parsed = await parse_curriculum(body.raw_content, body.source_format)
    except Exception as e:
        raise HTTPException(422, f"Could not parse curriculum: {e}")

    curriculum = Curriculum(
        course_id=course_id,
        title=parsed.get("title") or body.title,
        source_format=body.source_format,
        raw_content=body.raw_content,
    )
    db.add(curriculum)
    await db.flush()  # get curriculum.id

    # Recursively insert objectives
    await _insert_objectives(curriculum.id, parsed.get("objectives", []), parent_id=None, db=db)

    await db.commit()

    objectives = await _load_objective_tree(curriculum.id, db)
    return CurriculumOut(
        id=curriculum.id,
        course_id=curriculum.course_id,
        title=curriculum.title,
        source_format=curriculum.source_format,
        created_at=curriculum.created_at,
        objectives=objectives,
    )


@router.delete("/{course_id}/curriculum/{curriculum_id}", status_code=204)
async def delete_curriculum(
    course_id: uuid.UUID,
    curriculum_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    c = await db.get(Curriculum, curriculum_id)
    if not c or c.course_id != course_id:
        raise HTTPException(404, "Curriculum not found")
    await db.delete(c)
    await db.commit()


# --- helpers ---

async def _insert_objectives(
    curriculum_id: uuid.UUID,
    items: list[dict],
    parent_id: uuid.UUID | None,
    db: AsyncSession,
    position_offset: int = 0,
):
    for i, item in enumerate(items):
        obj = Objective(
            curriculum_id=curriculum_id,
            parent_id=parent_id,
            code=item.get("code"),
            text=item.get("text", ""),
            bloom_level=item.get("bloom_level"),
            position=position_offset + i,
        )
        db.add(obj)
        await db.flush()
        children = item.get("children") or []
        if children:
            await _insert_objectives(curriculum_id, children, obj.id, db)


async def _load_objective_tree(curriculum_id: uuid.UUID, db: AsyncSession) -> list[ObjectiveOut]:
    result = await db.execute(
        select(Objective)
        .where(Objective.curriculum_id == curriculum_id)
        .order_by(Objective.position)
    )
    all_objs = result.scalars().all()

    # Build tree in Python
    by_id: dict[uuid.UUID, ObjectiveOut] = {}
    roots: list[ObjectiveOut] = []

    for obj in all_objs:
        node = ObjectiveOut(
            id=obj.id,
            parent_id=obj.parent_id,
            code=obj.code,
            text=obj.text,
            bloom_level=obj.bloom_level,
            position=obj.position,
            children=[],
        )
        by_id[obj.id] = node

    for obj in all_objs:
        node = by_id[obj.id]
        if obj.parent_id and obj.parent_id in by_id:
            by_id[obj.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots
