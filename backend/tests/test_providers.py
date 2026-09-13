import httpx
import pytest
import respx

from app.providers.base import ChatMessage
from app.providers.ollama_provider import OllamaEmbeddingProvider, OllamaProvider


@respx.mock
async def test_ollama_is_available_true_when_model_present():
    respx.get("http://ollama.test/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "llama3.1:8b"}]})
    )
    provider = OllamaProvider("http://ollama.test", "llama3.1:8b")
    ok, detail = await provider.is_available()
    assert ok is True


@respx.mock
async def test_ollama_is_available_false_when_model_missing():
    respx.get("http://ollama.test/api/tags").mock(return_value=httpx.Response(200, json={"models": []}))
    provider = OllamaProvider("http://ollama.test", "llama3.1:8b")
    ok, detail = await provider.is_available()
    assert ok is False
    assert "ollama pull" in detail.lower()


@respx.mock
async def test_ollama_is_available_false_when_connection_refused():
    respx.get("http://ollama.test/api/tags").mock(side_effect=httpx.ConnectError("refused"))
    provider = OllamaProvider("http://ollama.test", "llama3.1:8b")
    ok, detail = await provider.is_available()
    assert ok is False
    assert "running" in detail.lower()


@respx.mock
async def test_ollama_chat_returns_content():
    respx.post("http://ollama.test/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": "hello from ollama"}, "done_reason": "stop"})
    )
    provider = OllamaProvider("http://ollama.test", "llama3.1:8b")
    result = await provider.chat([ChatMessage(role="user", content="hi")])
    assert result.content == "hello from ollama"


@respx.mock
async def test_ollama_embedding_provider_embeds_each_text():
    respx.get("http://ollama.test/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "nomic-embed-text"}]})
    )
    respx.post("http://ollama.test/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})
    )
    provider = OllamaEmbeddingProvider("http://ollama.test", "nomic-embed-text", dimensions=3)
    ok, _ = await provider.is_available()
    assert ok is True
    vectors = await provider.embed(["a", "b"])
    assert len(vectors) == 2
    assert vectors[0] == [0.1, 0.2, 0.3]


async def test_anthropic_provider_reports_unavailable_without_api_key():
    from app.providers.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider(api_key="", model="claude-sonnet-5")
    ok, detail = await provider.is_available()
    assert ok is False
    assert "not set" in detail.lower()


def test_factory_builds_ollama_provider_by_default():
    from app.core.config import Settings
    from app.providers.factory import build_chat_provider

    settings = Settings(llm_provider="ollama", database_url="sqlite+aiosqlite:///:memory:")
    provider = build_chat_provider(settings)
    assert provider.name == "ollama"


def test_factory_builds_anthropic_provider_when_configured():
    from app.core.config import Settings
    from app.providers.factory import build_chat_provider

    settings = Settings(llm_provider="anthropic", anthropic_api_key="sk-test", database_url="sqlite+aiosqlite:///:memory:")
    provider = build_chat_provider(settings)
    assert provider.name == "anthropic"


def test_factory_embeddings_always_ollama_regardless_of_chat_provider():
    from app.core.config import Settings
    from app.providers.factory import build_embedding_provider

    settings = Settings(llm_provider="anthropic", anthropic_api_key="sk-test", database_url="sqlite+aiosqlite:///:memory:")
    provider = build_embedding_provider(settings)
    assert provider.name == "ollama-embeddings"
