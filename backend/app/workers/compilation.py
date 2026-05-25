"""
Compilation worker (vps_queue).
Assembles final markdown → processes citations → Pandoc → HTML + PDF → MinIO.
"""
import uuid
import re
import json
import subprocess
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings

TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
FILTERS_DIR = Path(__file__).parent.parent.parent.parent / "pandoc-filters"


def compile_generation(generation_id: str):
    """RQ job: assemble markdown, resolve citations, run Pandoc."""
    engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
    with Session(engine) as db:
        from app.models import FascicleGeneration, Section, TopicNode, Course, Artifact
        from app.models.generation import GenerationStatus

        gen = db.get(FascicleGeneration, uuid.UUID(generation_id))
        if not gen:
            logger.error(f"Generation {generation_id} not found")
            return

        gen.status = GenerationStatus.compiling
        db.commit()

        try:
            course = db.get(Course, gen.course_id)
            sections = db.execute(
                select(Section, TopicNode)
                .join(TopicNode, Section.topic_node_id == TopicNode.id)
                .where(Section.generation_id == gen.id, Section.status == "completed")
                .order_by(Section.position)
            ).all()

            if not sections:
                raise ValueError("No completed sections to compile")

            # 1. Assemble raw markdown
            raw_md = _assemble_markdown(course, gen, sections)

            # 2. Resolve [src: chunk_id] citations
            processed_md = _resolve_citations(raw_md, db)

            # 3. Convert ::: block → ::: {.block} for pandoc fenced_divs
            processed_md = _fix_fenced_divs(processed_md)

            # 4. Remove enrichment comments
            processed_md = re.sub(r'<!--\s*enriched[^>]*-->', '', processed_md)

            with tempfile.TemporaryDirectory() as tmpdir:
                md_path = os.path.join(tmpdir, "fascicle.md")
                html_path = os.path.join(tmpdir, "fascicle.html")
                pdf_path = os.path.join(tmpdir, "fascicle.pdf")

                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(processed_md)

                # 5. Also save raw assembled .md as artifact
                md_key = f"courses/{gen.course_id}/artifacts/{gen.id}/fascicle.md"
                from app.services.storage import upload_bytes
                upload_bytes(md_key, processed_md.encode("utf-8"), "text/markdown")
                db.add(Artifact(generation_id=gen.id, type="markdown", storage_key=md_key, size_bytes=len(processed_md.encode())))

                # 6. Pandoc → HTML
                html_ok = _run_pandoc_html(md_path, html_path)
                if html_ok:
                    with open(html_path, "rb") as f:
                        html_data = f.read()
                    html_key = f"courses/{gen.course_id}/artifacts/{gen.id}/fascicle.html"
                    upload_bytes(html_key, html_data, "text/html")
                    db.add(Artifact(generation_id=gen.id, type="html", storage_key=html_key, size_bytes=len(html_data)))
                    logger.info(f"HTML compiled: {len(html_data)} bytes")
                else:
                    logger.warning("HTML compilation failed — skipping")

                # 7. Pandoc → PDF (optional, requires xelatex)
                pdf_ok = _run_pandoc_pdf(md_path, pdf_path)
                if pdf_ok:
                    with open(pdf_path, "rb") as f:
                        pdf_data = f.read()
                    pdf_key = f"courses/{gen.course_id}/artifacts/{gen.id}/fascicle.pdf"
                    upload_bytes(pdf_key, pdf_data, "application/pdf")
                    db.add(Artifact(generation_id=gen.id, type="pdf", storage_key=pdf_key, size_bytes=len(pdf_data)))
                    logger.info(f"PDF compiled: {len(pdf_data)} bytes")
                else:
                    logger.warning("PDF compilation failed — only HTML/MD available")

            gen.status = GenerationStatus.completed
            gen.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Compilation done for generation {generation_id}")

        except Exception as e:
            logger.exception(f"Compilation failed for {generation_id}")
            gen.status = GenerationStatus.failed
            gen.error_message = f"Compilation: {e}"
            gen.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise


# ─── Markdown assembly ────────────────────────────────────────────────

def _assemble_markdown(course, gen, sections) -> str:
    lang = gen.config.get("language", "tr")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    frontmatter = f"""---
title: "{course.name}"
subtitle: "Otomatik Üretilmiş Fasikül"
date: "{now}"
lang: {lang}-TR
geometry: margin=2.2cm
fontsize: 11pt
toc: true
toc-depth: 3
numbersections: true
linkcolor: blue
header-includes:
  - \\input{{{TEMPLATES_DIR}/tcolorbox_defs.tex}}
---

"""
    parts = [frontmatter]
    for section, node in sections:
        if section.final_md:
            parts.append(section.final_md.strip())
            parts.append("\n\n")

    return "\n".join(parts)


# ─── Citation resolution ──────────────────────────────────────────────

def _resolve_citations(md: str, db: Session) -> str:
    from app.models import SourceChunk, Source

    # Collect all referenced chunk IDs
    chunk_ids_raw = set(re.findall(r'\[src:\s*([\w-]+)\]', md))
    if not chunk_ids_raw:
        return md

    valid_uuids = []
    for raw in chunk_ids_raw:
        try:
            valid_uuids.append(uuid.UUID(raw))
        except ValueError:
            pass

    if not valid_uuids:
        return md

    chunks = {
        str(c.id): c
        for c in db.execute(select(SourceChunk).where(SourceChunk.id.in_(valid_uuids))).scalars().all()
    }
    sources = {
        str(s.id): s
        for s in db.execute(select(Source).where(Source.id.in_([c.source_id for c in chunks.values()]))).scalars().all()
    }

    citation_counter = [0]
    seen: dict[str, str] = {}  # chunk_id → footnote label

    def replace(match):
        raw_id = match.group(1).strip()
        if raw_id in seen:
            return seen[raw_id]
        chunk = chunks.get(raw_id)
        if not chunk:
            return ""
        source = sources.get(str(chunk.source_id))
        if not source:
            return ""
        label = _format_citation(source, chunk)
        # pandoc inline footnote syntax
        ref = f"^[{label}]"
        seen[raw_id] = ref
        return ref

    return re.sub(r'\[src:\s*([\w-]+)\]', replace, md)


def _format_citation(source, chunk) -> str:
    name = source.original_filename or source.external_url or source.type.value
    loc = chunk.location or {}
    if source.type.value == "pdf":
        page = loc.get("page", "?")
        heading = loc.get("heading_path", [])
        if heading:
            return f"{name}, s.{page} ({' > '.join(heading[-2:])})"
        return f"{name}, s.{page}"
    elif source.type.value in ("audio", "video"):
        ts = int(loc.get("start_sec", 0))
        m, s = divmod(ts, 60)
        return f"{name}, {m}:{s:02d}"
    elif source.type.value == "youtube":
        ts = int(loc.get("start_sec", 0))
        m, s = divmod(ts, 60)
        url = loc.get("url", source.external_url or "")
        return f"{name}, {m}:{s:02d} ({url})"
    return name


# ─── Markdown pre-processing ──────────────────────────────────────────

def _fix_fenced_divs(md: str) -> str:
    """Convert ::: klinik → ::: {.klinik} for pandoc fenced_divs extension."""
    return re.sub(
        r'^:::\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s*$',
        lambda m: f'::: {{.{m.group(1).lower()}}}',
        md,
        flags=re.MULTILINE,
    )


# ─── Pandoc runners ───────────────────────────────────────────────────

def _run_pandoc_html(md_path: str, out_path: str) -> bool:
    css_path = TEMPLATES_DIR / "fascicle.css"
    template_path = TEMPLATES_DIR / "fascicle_template.html"
    filter_path = FILTERS_DIR / "custom_blocks.py"

    cmd = [
        "pandoc", md_path,
        "--from", "markdown+fenced_divs+footnotes+pipe_tables+raw_html+tex_math_dollars",
        "--to", "html5",
        "--standalone",
        "--toc",
        "--toc-depth=3",
        "--number-sections",
        "--mathjax",
        "-o", out_path,
    ]
    if css_path.exists():
        cmd += ["--css", str(css_path)]
    if template_path.exists():
        cmd += ["--template", str(template_path)]
    if filter_path.exists():
        cmd += ["--filter", str(filter_path)]

    return _run(cmd, "pandoc HTML")


def _run_pandoc_pdf(md_path: str, out_path: str) -> bool:
    filter_path = FILTERS_DIR / "custom_blocks.py"
    header_path = TEMPLATES_DIR / "tcolorbox_defs.tex"

    cmd = [
        "pandoc", md_path,
        "--from", "markdown+fenced_divs+footnotes+pipe_tables+tex_math_dollars",
        "--pdf-engine=xelatex",
        "--toc",
        "--number-sections",
        "-V", "mainfont=DejaVu Serif",
        "-V", "sansfont=DejaVu Sans",
        "-o", out_path,
    ]
    if filter_path.exists():
        cmd += ["--filter", str(filter_path)]

    return _run(cmd, "pandoc PDF")


def _run(cmd: list, label: str) -> bool:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning(f"{label} failed (rc={result.returncode}): {result.stderr[:500]}")
            return False
        return True
    except FileNotFoundError:
        logger.warning(f"{label}: pandoc not found in PATH")
        return False
    except subprocess.TimeoutExpired:
        logger.warning(f"{label}: timeout")
        return False
    except Exception as e:
        logger.warning(f"{label}: {e}")
        return False
