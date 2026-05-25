"""
LLM Router: maps generation pass → provider.
All providers expose OpenAI-compatible chat completions;
DeepSeek and Groq use the openai SDK with custom base_url.
Anthropic uses its own SDK.
"""
from typing import Literal, Any
from openai import AsyncOpenAI
from app.config import settings

PassName = Literal[
    "topic_extraction",
    "pass1_outline",
    "pass2_expand",
    "pass3_enrich",
    "pass4_questions",
    "pass5_qa",
]

_PASS_CONFIG_MAP: dict[PassName, str] = {
    "topic_extraction": "llm_topic_extraction",
    "pass1_outline": "llm_pass1_outline",
    "pass2_expand": "llm_pass2_expand",
    "pass3_enrich": "llm_pass3_enrich",
    "pass4_questions": "llm_pass4_questions",
    "pass5_qa": "llm_pass5_qa",
}


def _get_openai_client(provider: str) -> tuple[AsyncOpenAI, str]:
    if provider == "deepseek":
        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        return client, settings.deepseek_model
    elif provider == "groq":
        client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        return client, settings.groq_model
    else:
        raise ValueError(f"Unknown provider for openai-compat client: {provider}")


async def chat(
    pass_name: PassName,
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    response_format: dict | None = None,
) -> str:
    provider = getattr(settings, _PASS_CONFIG_MAP[pass_name])

    if provider == "anthropic":
        return await _chat_anthropic(messages, temperature=temperature, max_tokens=max_tokens)

    client, model = _get_openai_client(provider)

    kwargs: dict[str, Any] = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if response_format:
        kwargs["response_format"] = response_format

    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def _chat_anthropic(
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_messages = [m for m in messages if m["role"] != "system"]
    resp = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        temperature=temperature,
        system=system or "",
        messages=user_messages,
    )
    return resp.content[0].text
