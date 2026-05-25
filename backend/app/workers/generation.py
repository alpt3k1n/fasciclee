"""
Generation worker (vps_queue).
Runs all 5 passes for each section sequentially.
Pass 5 QA can trigger retry of Pass 2/3/4 with gap hints (max 2 retries).
"""
import uuid
import json
import asyncio
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings

MAX_RETRIES = 2

STYLE_GUIDE = """\
Style rules (ALWAYS follow):
- Authoritative, accessible tone — teach, don't list
- Structure: explanation → example → clinical correlation → edge cases
- Terminology: include both Turkish and English terms on first mention (e.g. "iskemik inme (ischemic stroke)")
- Citations: every factual claim ends with [src: <chunk_id>]
- Math: $...$ inline, $$...$$ display (KaTeX syntax)
- Tables: pipe tables only
- Custom blocks (use fenced divs):
  ::: klinik
  [clinical pearl / correlation]
  :::
  ::: tanım
  **Term:** definition
  :::
  ::: mnemonics
  [memory aid]
  :::
  ::: vaka
  [clinical case]
  :::
  ::: dikkat
  [warning / common pitfall]
  :::
"""


# ─────────────────────────── Entry point ───────────────────────────

def run_generation(generation_id: str):
    engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
    with Session(engine) as db:
        from app.models import FascicleGeneration, Section, TopicNode
        from app.models.generation import GenerationStatus

        gen = db.get(FascicleGeneration, uuid.UUID(generation_id))
        if not gen:
            logger.error(f"Generation {generation_id} not found")
            return

        sections = db.execute(
            select(Section, TopicNode)
            .join(TopicNode, Section.topic_node_id == TopicNode.id)
            .where(Section.generation_id == gen.id)
            .order_by(Section.position)
        ).all()

        try:
            preceding_summary = ""
            for section, node in sections:
                # Re-check for cancellation each section
                db.refresh(gen)
                if gen.status == GenerationStatus.cancelled:
                    logger.info(f"Generation {generation_id} cancelled")
                    return

                logger.info(f"[Gen {generation_id}] Section {section.position}: {node.title}")
                _run_section(section, node, gen.config, preceding_summary, db)
                db.refresh(section)
                if section.final_md:
                    # Use last ~200 chars as continuity hint for next section
                    preceding_summary = f"Previous section: '{node.title}' — {section.final_md[-200:]}"

            gen.status = GenerationStatus.completed
            gen.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Generation {generation_id} completed")

        except Exception as e:
            logger.exception(f"Generation {generation_id} failed")
            gen.status = GenerationStatus.failed
            gen.error_message = str(e)
            gen.completed_at = datetime.now(timezone.utc)
            db.commit()


# ─────────────────────────── Section runner ───────────────────────────

def _run_section(section, node, config: dict, preceding_summary: str, db: Session):
    from app.models import SourceChunk, TopicNodeSource, Objective, TopicNodeObjective

    # Load source chunks for this node
    link_rows = db.execute(
        select(TopicNodeSource).where(TopicNodeSource.topic_node_id == node.id)
    ).scalars().all()
    chunk_ids = [r.source_chunk_id for r in link_rows]
    chunks = []
    if chunk_ids:
        chunks = db.execute(
            select(SourceChunk).where(SourceChunk.id.in_(chunk_ids))
        ).scalars().all()

    # Load objectives
    obj_rows = db.execute(
        select(Objective)
        .join(TopicNodeObjective, TopicNodeObjective.objective_id == Objective.id)
        .where(TopicNodeObjective.topic_node_id == node.id)
    ).scalars().all()

    sources_block = _format_sources(chunks)
    objectives_block = _format_objectives(obj_rows)
    language = config.get("language", "tr")
    depth = config.get("depth", "comprehensive")
    q_count = config.get("test_question_count", 5)

    # ── Pass 1: Outline ──
    outline = asyncio.run(_pass1_outline(node, sources_block, objectives_block, preceding_summary, language, depth))
    section.pass1_outline = outline
    section.status = "pass1_done"
    db.commit()

    # ── Pass 2: Expand ──
    expanded_md = asyncio.run(_pass2_expand(outline, node, sources_block, objectives_block, language))
    section.pass2_expanded_md = expanded_md
    section.status = "pass2_done"
    db.commit()

    # ── Pass 3: Enrich ──
    enriched_md = asyncio.run(_pass3_enrich(expanded_md, outline, objectives_block, node.title, language))
    section.pass3_enriched_md = enriched_md
    section.status = "pass3_done"
    db.commit()

    # ── Pass 4: Test questions ──
    questions_json, questions_md = asyncio.run(
        _pass4_questions(enriched_md, objectives_block, node.title, language, q_count)
    )
    section.pass4_questions_md = questions_md
    section.status = "pass4_done"
    _save_test_questions(section, questions_json, db)
    db.commit()

    # ── Pass 5: QA + optional retry ──
    _run_qa_loop(section, node, chunks, enriched_md, questions_md, objectives_block,
                 sources_block, language, depth, q_count, db)


def _run_qa_loop(section, node, chunks, enriched_md, questions_md,
                 objectives_block, sources_block, language, depth, q_count, db: Session):
    from app.models import QAReport

    current_enriched = enriched_md
    current_questions = questions_md

    for attempt in range(MAX_RETRIES + 1):
        qa = asyncio.run(_pass5_qa(current_enriched, current_questions, objectives_block, sources_block))
        report = QAReport(
            section_id=section.id,
            pass_number=attempt + 1,
            objective_coverage=qa.get("objective_coverage"),
            has_unused_source=bool(qa.get("unused_source_content")),
            unused_source_summary=json.dumps(qa.get("unused_source_content", []))[:500],
            recommendation=qa.get("overall_recommendation", "accept"),
        )
        db.add(report)
        db.commit()

        rec = qa.get("overall_recommendation", "accept")
        logger.info(f"Section {section.position} QA attempt {attempt+1}: {rec}")

        if rec == "accept" or attempt >= MAX_RETRIES:
            section.final_md = current_enriched + "\n\n" + current_questions
            section.status = "completed"
            section.generated_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Build gap hints for retry
        gaps = [
            f"- [{c['code']}] {c.get('gap_note','')}"
            for c in qa.get("objective_coverage", [])
            if c.get("status") in ("partial", "missing")
        ]
        gap_hint = "Previously missed:\n" + "\n".join(gaps) if gaps else ""

        if rec in ("retry_pass2", "retry_pass3"):
            outline = section.pass1_outline or {}
            current_enriched = asyncio.run(
                _pass2_expand(outline, node, sources_block, objectives_block, language, gap_hint=gap_hint)
            )
            section.pass2_expanded_md = current_enriched
            current_enriched = asyncio.run(
                _pass3_enrich(current_enriched, outline, objectives_block, node.title, language)
            )
            section.pass3_enriched_md = current_enriched
            db.commit()
        elif rec == "retry_pass4":
            _, current_questions = asyncio.run(
                _pass4_questions(current_enriched, objectives_block, node.title, language, q_count, gap_hint=gap_hint)
            )
            section.pass4_questions_md = current_questions
            db.commit()

        section.retry_count = attempt + 1
        db.commit()


# ─────────────────────────── Pass 1 ───────────────────────────

async def _pass1_outline(node, sources_block, objectives_block, preceding_summary, language, depth) -> dict:
    from app.llm import chat

    messages = [
        {"role": "system", "content": f"You generate educational fascicle section outlines in {language}.\n{STYLE_GUIDE}\nOutput ONLY valid JSON. No prose."},
        {"role": "user", "content": f"""\
Section: "{node.title}"
{f'Summary: {node.summary}' if node.summary else ''}
{f'Context: {preceding_summary}' if preceding_summary else ''}

Learning objectives:
{objectives_block}

Source material:
{sources_block}

Depth: {depth}

Generate a detailed JSON outline:
{{
  "section_title": "...",
  "intro_paragraph": "1-2 sentence opener",
  "subsections": [
    {{
      "title": "...",
      "objectives_addressed": ["1.1"],
      "key_concepts": ["concept A"],
      "must_include": ["specific facts, formulas, classifications"],
      "examples_needed": true,
      "clinical_correlation": "if applicable, else null",
      "edge_cases": ["..."],
      "estimated_paragraph_count": 3
    }}
  ],
  "concluding_paragraph": "ties it together"
}}

Constraints:
- Every objective must appear in at least one subsection
- Prefer 4-7 subsections for comprehensive depth
- Include edge cases and atypical presentations
"""}
    ]
    for attempt in range(3):
        try:
            raw = await chat("pass1_outline", messages, temperature=0.2, max_tokens=3000)
            return json.loads(_strip_fences(raw))
        except json.JSONDecodeError:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "Invalid JSON. Return ONLY the JSON object."})
    return {"section_title": node.title, "intro_paragraph": "", "subsections": [], "concluding_paragraph": ""}


# ─────────────────────────── Pass 2 ───────────────────────────

async def _pass2_expand(outline: dict, node, sources_block, objectives_block, language, gap_hint: str = "") -> str:
    from app.llm import chat

    subsections = outline.get("subsections", [])
    if not subsections:
        # Fallback: single-pass full section
        return await _expand_full(outline, node, sources_block, objectives_block, language, gap_hint)

    parts = [f"# {outline.get('section_title', node.title)}\n\n{outline.get('intro_paragraph', '')}"]

    for sub in subsections:
        messages = [
            {"role": "system", "content": f"You write prose for educational fascicle sections in {language}.\n{STYLE_GUIDE}\nOutput pure Markdown only. No JSON, no meta-commentary."},
            {"role": "user", "content": f"""\
Section: "{outline.get('section_title', node.title)}"
Subsection: "{sub['title']}"
Objectives: {', '.join(sub.get('objectives_addressed', []))}
Key concepts: {', '.join(sub.get('key_concepts', []))}
Must include: {', '.join(sub.get('must_include', []))}
Edge cases: {', '.join(sub.get('edge_cases', []))}
{f'Clinical correlation: {sub["clinical_correlation"]}' if sub.get('clinical_correlation') else ''}
{f'IMPORTANT gaps to address: {gap_hint}' if gap_hint else ''}

Source material:
{sources_block}

Write {sub.get('estimated_paragraph_count', 3)} paragraphs. Rules:
1. Cite every factual claim: [src: <chunk_id>]
2. Use prose, not bullet lists (lists only for genuine enumerations)
3. Don't compress — teach fully
4. Bilingual terminology on first mention
"""}
        ]
        raw = await chat("pass2_expand", messages, temperature=0.3, max_tokens=2500)
        parts.append(f"\n## {sub['title']}\n\n{raw.strip()}")

    parts.append(f"\n{outline.get('concluding_paragraph', '')}")
    return "\n".join(parts)


async def _expand_full(outline, node, sources_block, objectives_block, language, gap_hint) -> str:
    from app.llm import chat
    messages = [
        {"role": "system", "content": f"Write a comprehensive educational fascicle section in {language}.\n{STYLE_GUIDE}\nOutput Markdown only."},
        {"role": "user", "content": f"""\
Section: "{node.title}"
Objectives: {objectives_block}
{f'Gaps to address: {gap_hint}' if gap_hint else ''}
Sources: {sources_block}
Write a comprehensive section. Cite every fact [src: chunk_id].
"""}
    ]
    return await chat("pass2_expand", messages, temperature=0.3, max_tokens=4000)


# ─────────────────────────── Pass 3 ───────────────────────────

async def _pass3_enrich(expanded_md: str, outline: dict, objectives_block, section_title: str, language: str) -> str:
    from app.llm import chat

    messages = [
        {"role": "system", "content": f"You enrich educational fascicle content in {language} with visual aids, mnemonics, and clinical blocks.\n{STYLE_GUIDE}\nOutput the full enriched Markdown only."},
        {"role": "user", "content": f"""\
Section: "{section_title}"
Objectives: {objectives_block}

Existing prose:
{expanded_md}

Enrich this content:
1. Add 1-2 Mermaid diagrams where they aid understanding (flowchart, comparison table)
   Use ```mermaid blocks
2. Add ::: klinik blocks for clinical pearls and pitfalls (aim 2-4)
3. Add ::: mnemonics blocks for memorable shortcuts
4. Add ::: tanım blocks for key terms not yet formally defined
5. Add ::: dikkat blocks for common exam traps / dangerous mistakes
6. Don't add blocks just for the sake of it — each must earn its place

Output: full section markdown with additions inline. Mark additions with <!-- enriched --> comment.
Preserve ALL existing prose and citations.
"""}
    ]
    return await chat("pass3_enrich", messages, temperature=0.4, max_tokens=5000)


# ─────────────────────────── Pass 4 ───────────────────────────

async def _pass4_questions(enriched_md: str, objectives_block: str, section_title: str,
                            language: str, q_count: int, gap_hint: str = "") -> tuple[list, str]:
    from app.llm import chat

    messages = [
        {"role": "system", "content": f"You generate high-quality medical/educational MCQs in {language}. Output JSON only."},
        {"role": "user", "content": f"""\
Section content (what was taught):
{enriched_md[:3000]}{'...' if len(enriched_md) > 3000 else ''}

Objectives:
{objectives_block}
{f'Focus especially on these gaps: {gap_hint}' if gap_hint else ''}

Generate {q_count} test questions:
- Mix Bloom levels matching objectives
- At least 1 question per leaf objective
- 1-2 vaka-based (case-based) questions for clinical sections
- 4-5 options per MCQ, plausible distractors (common confusions, not absurd)

Output JSON:
{{
  "questions": [
    {{
      "question_text": "...",
      "vaka_setup": "optional clinical case stem or null",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_answer": "A",
      "explanation": "Why A is correct + brief on wrong options",
      "difficulty": "medium",
      "objective_codes": ["1.2"],
      "bloom_level": "apply",
      "question_format": "mcq"
    }}
  ]
}}
"""}
    ]

    for attempt in range(3):
        try:
            raw = await chat("pass4_questions", messages, temperature=0.3, max_tokens=3000)
            data = json.loads(_strip_fences(raw))
            questions = data.get("questions", [])
            md = _questions_to_markdown(questions, language)
            return questions, md
        except json.JSONDecodeError:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "Invalid JSON. Return ONLY the JSON object."})

    return [], ""


def _questions_to_markdown(questions: list, language: str) -> str:
    if not questions:
        return ""
    header = "## Test Soruları" if language == "tr" else "## Practice Questions"
    parts = [header]
    for i, q in enumerate(questions, 1):
        stem = f"\n### Soru {i}" if language == "tr" else f"\n### Question {i}"
        if q.get("vaka_setup"):
            stem += f"\n\n*{q['vaka_setup']}*"
        stem += f"\n\n**{q['question_text']}**\n"
        for opt in q.get("options", []):
            stem += f"\n{opt}"
        stem += f"\n\n<details><summary>Cevap</summary>\n\n**{q.get('correct_answer', '?')}** — {q.get('explanation', '')}\n\n</details>"
        parts.append(stem)
    return "\n".join(parts)


# ─────────────────────────── Pass 5 QA ───────────────────────────

async def _pass5_qa(enriched_md: str, questions_md: str, objectives_block: str, sources_block: str) -> dict:
    from app.llm import chat

    messages = [
        {"role": "system", "content": "You are a strict curriculum reviewer. Output JSON only. No prose."},
        {"role": "user", "content": f"""\
Learning objectives this section must cover:
{objectives_block}

Generated section content:
{enriched_md[:4000]}{'...' if len(enriched_md) > 4000 else ''}

Test questions:
{questions_md[:1500]}{'...' if len(questions_md) > 1500 else ''}

Evaluate:
1. For each objective: covered | partial | missing (and why if not fully covered)
2. Important source content NOT in section but should be
3. Any internal contradictions

Output JSON:
{{
  "objective_coverage": [
    {{"code": "1.1", "status": "covered", "gap_note": null}},
    {{"code": "1.2", "status": "partial", "gap_note": "Missing acute management timeline"}}
  ],
  "unused_source_content": [
    {{"what_was_missed": "..."}}
  ],
  "consistency_issues": [],
  "overall_recommendation": "accept",
  "rationale": "1-2 sentence summary"
}}

overall_recommendation must be exactly one of: accept | retry_pass2 | retry_pass3 | retry_pass4 | manual_review
Use accept unless there are MISSING (not just partial) objectives.
"""}
    ]

    for attempt in range(3):
        try:
            raw = await chat("pass5_qa", messages, temperature=0.1, max_tokens=2000)
            return json.loads(_strip_fences(raw))
        except json.JSONDecodeError:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "Invalid JSON. Return ONLY the JSON object."})

    return {"objective_coverage": [], "overall_recommendation": "accept", "rationale": "QA parse failed, accepting"}


# ─────────────────────────── Helpers ───────────────────────────

def _format_sources(chunks) -> str:
    if not chunks:
        return "(No source chunks linked to this topic node)"
    parts = []
    for c in chunks[:20]:  # cap at 20 chunks per section
        parts.append(f"[id={c.id}] (loc={c.location}): {c.text[:400]}")
    return "\n\n".join(parts)


def _format_objectives(objectives) -> str:
    if not objectives:
        return "(No objectives linked)"
    return "\n".join(
        f"- [{o.code or '?'}] {o.text}" + (f" ({o.bloom_level})" if o.bloom_level else "")
        for o in objectives
    )


def _save_test_questions(section, questions: list, db: Session):
    from app.models import TestQuestion
    for q in questions:
        db.add(TestQuestion(
            section_id=section.id,
            question_text=q.get("question_text", ""),
            question_format=q.get("question_format", "mcq"),
            options=q.get("options"),
            correct_answer=q.get("correct_answer"),
            explanation=q.get("explanation"),
            difficulty=q.get("difficulty"),
            objective_ids=[],
        ))


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
