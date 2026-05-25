"""
Compilation endpoints.
POST /api/generations/{id}/compile   — enqueue compilation job
GET  /api/generations/{id}/artifacts — list artifacts with presigned URLs
"""
import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.config import settings
from app.models import FascicleGeneration, Artifact
from app.models.generation import GenerationStatus
from app.services.storage import get_presigned_url

router = APIRouter(prefix="/api", tags=["compilation"])


@router.post("/generations/{generation_id}/compile")
async def compile_generation(generation_id: str):
    try:
        gen_uuid = uuid.UUID(generation_id)
    except ValueError:
        raise HTTPException(400, "Invalid generation ID")

    async with AsyncSessionLocal() as db:
        gen = await db.get(FascicleGeneration, gen_uuid)
        if not gen:
            raise HTTPException(404, "Generation not found")
        if gen.status not in (GenerationStatus.completed, GenerationStatus.failed):
            raise HTTPException(422, f"Cannot compile a generation with status '{gen.status.value}'")

    import redis
    from rq import Queue
    conn = redis.from_url(settings.redis_url)
    q = Queue("vps_queue", connection=conn)
    job = q.enqueue(
        "app.workers.compilation.compile_generation",
        generation_id,
        job_timeout=600,
    )
    return {"job_id": job.id, "status": "queued"}


@router.get("/generations/{generation_id}/artifacts")
async def list_artifacts(generation_id: str):
    try:
        gen_uuid = uuid.UUID(generation_id)
    except ValueError:
        raise HTTPException(400, "Invalid generation ID")

    async with AsyncSessionLocal() as db:
        gen = await db.get(FascicleGeneration, gen_uuid)
        if not gen:
            raise HTTPException(404, "Generation not found")

        rows = (
            await db.execute(
                select(Artifact)
                .where(Artifact.generation_id == gen_uuid)
                .order_by(Artifact.created_at)
            )
        ).scalars().all()

    result = []
    for art in rows:
        url = None
        try:
            url = get_presigned_url(art.storage_key, expires_hours=1)
        except Exception:
            pass
        result.append({
            "id": str(art.id),
            "type": art.type,
            "storage_key": art.storage_key,
            "size_bytes": art.size_bytes,
            "created_at": art.created_at.isoformat() if art.created_at else None,
            "url": url,
        })
    return result
