from __future__ import annotations

from functools import lru_cache

from app.core.config import LLMProviderName, Settings, get_settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.ollama_provider import OllamaEmbeddingProvider, OllamaProvider


def build_chat_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == LLMProviderName.ANTHROPIC:
        return AnthropicProvider(
            api_key=settings.anthropic_api_key or "",
            model=settings.anthropic_model,
            timeout=settings.anthropic_timeout_seconds,
        )
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_chat_model,
        timeout=settings.ollama_timeout_seconds,
    )


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Embeddings always come from Ollama -- Anthropic has no embeddings API."""
    settings = settings or get_settings()
    return OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout=settings.ollama_timeout_seconds,
    )


@lru_cache
def get_chat_provider() -> LLMProvider:
    return build_chat_provider()


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider()


def reset_provider_cache() -> None:
    get_chat_provider.cache_clear()
    get_embedding_provider.cache_clear()
