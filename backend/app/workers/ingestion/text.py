"""Plain text / curriculum ingestion."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import Source, SourceChunk
from app.services.storage import download_bytes
from app.workers.ingestion.pdf import _chunk_text


def process_text(source: Source, db: Session):
    data = download_bytes(source.storage_key)
    text = data.decode("utf-8", errors="replace")
    chunks = _chunk_text(text, page_num=1)
    for i, item in enumerate(chunks):
        db.add(SourceChunk(
            source_id=source.id,
            chunk_index=i,
            text=item["text"],
            location={"offset": i},
        ))
    source.processed_at = datetime.now(timezone.utc)
    db.commit()
