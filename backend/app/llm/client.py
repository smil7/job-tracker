from functools import lru_cache

from openai import AsyncOpenAI

from app.config import settings


@lru_cache
def _client() -> AsyncOpenAI:
    # OpenRouter speaks the OpenAI chat completions protocol
    return AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.openrouter_api_key or "missing")


def get_llm() -> AsyncOpenAI:
    """FastAPI dependency; tests override it with a fake."""
    return _client()
