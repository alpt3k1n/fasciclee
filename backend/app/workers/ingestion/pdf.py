"""PDF ingestion: PyMuPDF → text extraction → chunking → SourceChunk records."""
import re
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.orm import Session

from app.models import Source, SourceChunk
from app.services.storage import download_bytes


CHUNK_TOKEN_TARGET = 400
OVERLAP_SENTENCES = 2


def process_pdf(source: Source, db: Session):
    import fitz  # PyMuPDF

    data = download_bytes(source.storage_key)
    doc = fitz.open(stream=data, filetype="pdf")

    source.metadata_["page_count"] = len(doc)
    chunks_data = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text", sort=True).strip()

        if len(text) < 50:
            # Likely scanned — OCR fallback
            text = _ocr_page(page)

        if not text:
            continue

        page_chunks = _chunk_text(text, page_num)
        chunks_data.extend(page_chunks)

    doc.close()

    chunk_index = 0
    for item in chunks_data:
        chunk = SourceChunk(
            source_id=source.id,
            chunk_index=chunk_index,
            text=item["text"],
            location=item["location"],
        )
        db.add(chunk)
        chunk_index += 1

    source.processed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"PDF {source.id}: {chunk_index} chunks created from {source.metadata_['page_count']} pages")


def _ocr_page(page) -> str:
    try:
        import pytesseract
        from PIL import Image
        import io
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang="tur+eng")
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return ""


def _chunk_text(text: str, page_num: int) -> list[dict]:
    sentences = _split_sentences(text)
    chunks = []
    current: list[str] = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = len(sent.split())
        if current_tokens + sent_tokens > CHUNK_TOKEN_TARGET and current:
            chunks.append({
                "text": " ".join(current),
                "location": {"page": page_num},
            })
            current = current[-OVERLAP_SENTENCES:] if len(current) > OVERLAP_SENTENCES else current[:]
            current_tokens = sum(len(s.split()) for s in current)
        current.append(sent)
        current_tokens += sent_tokens

    if current:
        chunks.append({
            "text": " ".join(current),
            "location": {"page": page_num},
        })

    return chunks


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]
