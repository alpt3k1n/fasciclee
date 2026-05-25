"""YouTube ingestion: yt-dlp → subtitle or audio → chunks."""
import json
import tempfile
import os
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.orm import Session

from app.models import Source, SourceChunk
from app.services.storage import upload_bytes


def process_youtube(source: Source, db: Session):
    url = source.external_url
    with tempfile.TemporaryDirectory() as tmpdir:
        meta, subtitle_path, audio_path = _download(url, tmpdir)

        source.original_filename = meta.get("title", "youtube_video")
        source.metadata_.update({
            "title": meta.get("title"),
            "duration": meta.get("duration"),
            "video_id": meta.get("id"),
            "uploader": meta.get("uploader"),
        })

        if subtitle_path:
            segments = _parse_subtitles(subtitle_path)
        elif audio_path:
            from app.workers.ingestion.audio import _to_wav, _transcribe
            wav = _to_wav(audio_path)
            segments = _transcribe(wav)
            os.unlink(wav)
        else:
            raise RuntimeError("No subtitle or audio available")

        video_id = meta.get("id", "")
        for i, seg in enumerate(segments):
            chunk = SourceChunk(
                source_id=source.id,
                chunk_index=i,
                text=seg["text"],
                location={
                    "youtube_video_id": video_id,
                    "start_sec": seg["start"],
                    "end_sec": seg["end"],
                    "url": f"https://youtube.com/watch?v={video_id}&t={int(seg['start'])}s",
                },
            )
            db.add(chunk)

    source.processed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"YouTube {source.id}: {len(segments)} segments")


def _download(url: str, outdir: str) -> tuple[dict, str | None, str | None]:
    import yt_dlp
    ydl_opts = {
        "outtmpl": f"{outdir}/%(id)s.%(ext)s",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["tr", "en"],
        "subtitlesformat": "json3",
        "skip_download": False,
        "format": "bestaudio/best",
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    sub_path = None
    audio_path = None
    for fname in os.listdir(outdir):
        full = os.path.join(outdir, fname)
        if fname.endswith(".json3"):
            sub_path = full
        elif fname.endswith((".m4a", ".webm", ".mp3", ".ogg")):
            audio_path = full

    return info, sub_path, audio_path


def _parse_subtitles(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    segments = []
    for event in data.get("events", []):
        if "segs" not in event:
            continue
        text = "".join(s.get("utf8", "") for s in event["segs"]).strip()
        if not text:
            continue
        start = event.get("tStartMs", 0) / 1000
        dur = event.get("dDurationMs", 5000) / 1000
        segments.append({"start": start, "end": start + dur, "text": text})
    return segments
