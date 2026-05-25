import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Course, Source
from app.models.source import SourceType, SourceStatus
from app.schemas.course import CourseCreate, CourseUpdate, CourseOut
from app.schemas.source import SourceOut, YouTubeAddRequest
from app.services.storage import upload_bytes

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.post("", response_model=CourseOut, status_code=201)
async def create_course(body: CourseCreate, db: AsyncSession = Depends(get_db)):
    course = Course(**body.model_dump())
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


@router.get("", response_model=list[CourseOut])
async def list_courses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Course).order_by(Course.created_at.desc()))
    return result.scalars().all()


@router.get("/{course_id}", response_model=CourseOut)
async def get_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    return course


@router.patch("/{course_id}", response_model=CourseOut)
async def update_course(course_id: uuid.UUID, body: CourseUpdate, db: AsyncSession = Depends(get_db)):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(course, k, v)
    await db.commit()
    await db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204)
async def delete_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    await db.delete(course)
    await db.commit()


@router.get("/{course_id}/sources", response_model=list[SourceOut])
async def list_sources(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Source).where(Source.course_id == course_id).order_by(Source.uploaded_at.desc())
    )
    return result.scalars().all()


@router.post("/{course_id}/sources/upload", response_model=SourceOut, status_code=201)
async def upload_source(
    course_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")

    source_type = _detect_type(file.filename or "")
    source = Source(
        course_id=course_id,
        type=source_type,
        status=SourceStatus.pending,
        original_filename=file.filename,
    )
    db.add(source)
    await db.flush()

    key = f"courses/{course_id}/sources/{source.id}/original{_ext(file.filename or '')}"
    data = await file.read()
    upload_bytes(key, data, file.content_type or "application/octet-stream")
    source.storage_key = key

    await db.commit()
    await db.refresh(source)

    _enqueue_ingestion(source)
    return source


@router.post("/{course_id}/sources/youtube", response_model=SourceOut, status_code=201)
async def add_youtube(course_id: uuid.UUID, body: YouTubeAddRequest, db: AsyncSession = Depends(get_db)):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")

    source = Source(
        course_id=course_id,
        type=SourceType.youtube,
        status=SourceStatus.pending,
        external_url=body.url,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    _enqueue_ingestion(source)
    return source


@router.delete("/{course_id}/sources/{source_id}", status_code=204)
async def delete_source(course_id: uuid.UUID, source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    source = await db.get(Source, source_id)
    if not source or source.course_id != course_id:
        raise HTTPException(404, "Source not found")
    await db.delete(source)
    await db.commit()


@router.post("/{course_id}/sources/{source_id}/retry", response_model=SourceOut)
async def retry_source(course_id: uuid.UUID, source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    source = await db.get(Source, source_id)
    if not source or source.course_id != course_id:
        raise HTTPException(404, "Source not found")
    if source.status not in (SourceStatus.failed, SourceStatus.processed):
        raise HTTPException(422, "Only failed or processed sources can be retried")
    source.status = SourceStatus.pending
    source.error_message = None
    await db.commit()
    await db.refresh(source)
    _enqueue_ingestion(source)
    return source


def _detect_type(filename: str) -> SourceType:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mapping = {
        "pdf": SourceType.pdf,
        "mp3": SourceType.audio, "wav": SourceType.audio, "m4a": SourceType.audio, "ogg": SourceType.audio,
        "mp4": SourceType.video, "mkv": SourceType.video, "avi": SourceType.video, "mov": SourceType.video,
        "png": SourceType.image, "jpg": SourceType.image, "jpeg": SourceType.image, "webp": SourceType.image,
        "txt": SourceType.text, "md": SourceType.text,
        "json": SourceType.curriculum,
    }
    return mapping.get(ext, SourceType.text)


def _ext(filename: str) -> str:
    return f".{filename.rsplit('.', 1)[-1]}" if "." in filename else ""


def _enqueue_ingestion(source: Source):
    import redis
    from rq import Queue
    from app.config import settings

    conn = redis.from_url(settings.redis_url)
    queue_name = "gpu_queue" if source.type in (SourceType.audio, SourceType.video, SourceType.youtube) else "vps_queue"
    q = Queue(queue_name, connection=conn)
    q.enqueue("app.workers.ingestion.dispatch.process_source", str(source.id))
