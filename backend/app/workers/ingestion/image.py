"""Image ingestion: OCR + optionally VLM description."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import Source, SourceChunk
from app.services.storage import download_bytes


def process_image(source: Source, db: Session):
    import pytesseract
    from PIL import Image
    import io

    data = download_bytes(source.storage_key)
    img = Image.open(io.BytesIO(data))
    ocr_text = pytesseract.image_to_string(img, lang="tur+eng").strip()

    combined = ocr_text or "[Image: no text detected]"
    db.add(SourceChunk(
        source_id=source.id,
        chunk_index=0,
        text=combined,
        location={"source_image_key": source.storage_key},
    ))
    source.processed_at = datetime.now(timezone.utc)
    db.commit()
