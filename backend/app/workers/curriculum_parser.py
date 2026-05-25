"""
Parses curriculum input (JSON or free text/markdown) into a structured
objective tree. Free text goes through DeepSeek for conversion.
"""
import json
import asyncio
from loguru import logger
from app.llm import chat

SYSTEM_PROMPT = """\
You convert educational curriculum outlines into structured JSON.
Output ONLY valid JSON — no prose, no markdown fences, no commentary.
"""

USER_PROMPT_TEMPLATE = """\
Convert the following curriculum outline into this JSON structure:

{{
  "title": "Curriculum title inferred from content",
  "objectives": [
    {{
      "code": "1",
      "text": "...",
      "bloom_level": "understand",
      "children": [
        {{
          "code": "1.1",
          "text": "...",
          "bloom_level": "apply",
          "children": []
        }}
      ]
    }}
  ]
}}

Rules:
- bloom_level must be one of: remember, understand, apply, analyze, evaluate, create
- Assign bloom_level based on action verbs in the objective text (e.g. "list" → remember, "explain" → understand, "calculate" → apply)
- If no bloom level is clear, use "understand"
- Preserve hierarchy exactly as in the source
- code field: use the numbering from the source if present, otherwise generate 1, 1.1, 1.2, 2, etc.
- If no title is present, infer from content

Input curriculum:
{raw_content}
"""


async def parse_curriculum(raw_content: str, source_format: str) -> dict:
    """Returns {'title': str, 'objectives': [...]} structured dict."""
    if source_format == "json":
        return _parse_json(raw_content)

    # markdown / free text → LLM
    return await _parse_with_llm(raw_content)


def _parse_json(raw: str) -> dict:
    data = json.loads(raw)
    # Accept both {title, objectives} and bare list
    if isinstance(data, list):
        return {"title": "Müfredat", "objectives": data}
    return data


async def _parse_with_llm(raw_content: str) -> dict:
    prompt = USER_PROMPT_TEMPLATE.format(raw_content=raw_content)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(3):
        try:
            response = await chat(
                "topic_extraction",  # uses same provider as topic extraction (DeepSeek)
                messages,
                temperature=0.1,
                max_tokens=4096,
            )
            cleaned = _strip_fences(response)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Curriculum parse attempt {attempt + 1} failed: {e}")
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Output was not valid JSON. Try again. Return ONLY the JSON object."})
    raise ValueError("LLM could not produce valid JSON after 3 attempts")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # drop ```json line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
