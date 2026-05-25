"""Audio ingestion: Faster-Whisper → transcript → timecode-based chunks."""
import json
import tempfile
import os
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.orm import Session

from app.models import Source, SourceChunk
from app.services.storage import download_bytes, upload_bytes

CHUNK_DURATION_SEC = 60


def process_audio(source: Source, db: Session):
    data = download_bytes(source.storage_key)

    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
        f.write(data)
        tmp_path = f.name

    try:
        wav_path = _to_wav(tmp_path)
        segments = _transcribe(wav_path)
        transcript_key = f"courses/{source.course_id}/sources/{source.id}/extracted/transcript.json"
        upload_bytes(transcript_key, json.dumps(segments, ensure_ascii=False).encode(), "application/json")

        chunks = _chunk_segments(segments)
        for i, item in enumerate(chunks):
            chunk = SourceChunk(
                source_id=source.id,
                chunk_index=i,
                text=item["text"],
                location=item["location"],
            )
            db.add(chunk)

        source.processed_at = datetime.now(timezone.utc)
        source.metadata_["segment_count"] = len(segments)
        db.commit()
        logger.info(f"Audio {source.id}: {len(chunks)} chunks from {len(segments)} segments")
    finally:
        os.unlink(tmp_path)
        if "wav_path" in locals() and wav_path != tmp_path:
            os.unlink(wav_path)


def _to_wav(path: str) -> str:
    import subprocess
    out = path + ".wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-ar", "16000", "-ac", "1", "-f", "wav", out],
        check=True, capture_output=True
    )
    return out


def _transcribe(wav_path: str) -> list[dict]:
    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    segments, _ = model.transcribe(wav_path, language="tr", beam_size=5)
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]


def _chunk_segments(segments: list[dict]) -> list[dict]:
    chunks = []
    current_texts: list[str] = []
    chunk_start = 0.0
    current_end = 0.0

    for seg in segments:
        current_texts.append(seg["text"])
        current_end = seg["end"]
        duration = current_end - chunk_start
        if duration >= CHUNK_DURATION_SEC:
            chunks.append({
                "text": " ".join(current_texts),
                "location": {"start_sec": chunk_start, "end_sec": current_end, "duration_sec": duration},
            })
            current_texts = []
            chunk_start = current_end

    if current_texts:
        chunks.append({
            "text": " ".join(current_texts),
            "location": {"start_sec": chunk_start, "end_sec": current_end, "duration_sec": current_end - chunk_start},
        })
    return chunks
