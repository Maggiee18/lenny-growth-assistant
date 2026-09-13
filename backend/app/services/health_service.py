from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LLMProviderName, Settings
from app.providers.factory import get_chat_provider, get_embedding_provider
from app.schemas.config import ConfigResponse, HealthDependency, HealthResponse


async def check_database(db: AsyncSession) -> HealthDependency:
    try:
        await db.execute(text("SELECT 1"))
        return HealthDependency(name="database", healthy=True)
    except Exception as exc:  # noqa: BLE001
        return HealthDependency(name="database", healthy=False, detail=str(exc)[:200])


async def check_ollama(settings: Settings) -> HealthDependency:
    from app.providers.ollama_provider import OllamaProvider

    provider = OllamaProvider(settings.ollama_base_url, settings.ollama_chat_model, timeout=5.0)
    healthy, detail = await provider.is_available()
    return HealthDependency(name="ollama", healthy=healthy, detail=None if healthy else detail)


async def check_anthropic(settings: Settings) -> HealthDependency:
    if not settings.anthropic_api_key:
        return HealthDependency(name="anthropic", healthy=False, detail="ANTHROPIC_API_KEY not configured (optional).")
    from app.providers.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model, timeout=5.0)
    healthy, detail = await provider.is_available()
    return HealthDependency(name="anthropic", healthy=healthy, detail=None if healthy else detail)


async def build_health_response(db: AsyncSession, settings: Settings) -> HealthResponse:
    deps = [await check_database(db)]
    # Only the active provider's dependency is load-bearing for overall status;
    # the inactive one is reported for visibility but doesn't degrade health.
    if settings.llm_provider == LLMProviderName.OLLAMA:
        deps.append(await check_ollama(settings))
    else:
        deps.append(await check_anthropic(settings))

    critical_ok = all(d.healthy for d in deps)
    status = "ok" if critical_ok else "degraded"
    if not deps[0].healthy:
        status = "down"
    return HealthResponse(status=status, dependencies=deps)


async def build_config_response(settings: Settings) -> ConfigResponse:
    from app.providers.ollama_provider import OllamaProvider

    ollama_probe = OllamaProvider(settings.ollama_base_url, settings.ollama_chat_model, timeout=3.0)
    ollama_ok, _ = await ollama_probe.is_available()
    provider = get_chat_provider()
    return ConfigResponse(
        provider=settings.llm_provider.value,
        model=provider.model,
        ollama_available=ollama_ok,
        anthropic_configured=bool(settings.anthropic_api_key),
        retrieval_top_k=settings.retrieval_top_k,
        retrieval_similarity_threshold=settings.retrieval_similarity_threshold,
    )
