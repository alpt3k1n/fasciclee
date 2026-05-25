"""
RQ job entry point: routes to the correct processor based on source type.
Runs on either vps_queue or gpu_queue worker.
"""
import uuid
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models.source import SourceType, SourceStatus


def process_source(source_id: str):
    engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
    with Session(engine) as db:
        from app.models import Source
        source = db.get(Source, uuid.UUID(source_id))
        if not source:
            logger.error(f"Source {source_id} not found")
            return

        source.status = SourceStatus.processing
        db.commit()

        try:
            if source.type == SourceType.pdf:
                from app.workers.ingestion.pdf import process_pdf
                process_pdf(source, db)
            elif source.type == SourceType.audio:
                from app.workers.ingestion.audio import process_audio
                process_audio(source, db)
            elif source.type == SourceType.youtube:
                from app.workers.ingestion.youtube import process_youtube
                process_youtube(source, db)
            elif source.type == SourceType.image:
                from app.workers.ingestion.image import process_image
                process_image(source, db)
            elif source.type in (SourceType.text, SourceType.curriculum):
                from app.workers.ingestion.text import process_text
                process_text(source, db)
            else:
                raise ValueError(f"Unsupported source type: {source.type}")

            source.status = SourceStatus.processed
            db.commit()
            logger.info(f"Source {source_id} processed → embedding")

            from app.workers.ingestion.embed import embed_source
            embed_source(str(source.id))

        except Exception as e:
            logger.exception(f"Failed to process source {source_id}")
            source.status = SourceStatus.failed
            source.error_message = str(e)
            db.commit()
