"""PodcastAgent: the conversational orchestrator.

Flow for every user turn:
  1. classify_intent(message)          -- router.py, deterministic
  2. search_transcripts(message)       -- always retrieve first; every
     downstream tool reasons over the same evidence set
  3. dispatch to the matching tool (agents/tools.py)
  4. return a uniform AgentTurnResult the API layer persists and serializes

Conversation context is preserved by passing prior turns (as ChatMessage)
into answer_from_sources, so follow-up questions ("what about churn?") are
answered with the running conversation in view, not just the latest message.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import anthropic
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.router import Intent, classify_intent
from app.agents.tools import (
    ToolResult,
    answer_from_sources,
    generate_html_artifact_tool,
    generate_markdown_artifact_tool,
    generate_ship30_tool,
    search_transcripts,
)
from app.core.config import Settings
from app.core.errors import ModelFailureError, ProviderUnavailableError, RetrievalError
from app.core.logging import Timer, get_logger
from app.providers.base import ChatMessage, EmbeddingProvider, LLMProvider
from app.retrieval.retriever import RetrievedChunk

logger = get_logger(__name__)

# Dependency failures we translate into a clean, provider-aware AppError
# instead of letting a raw connection/timeout exception surface as a bare
# 500 (see architecture.md "Failure handling" and section 19's Ollama-down /
# timeout / cloud-key-missing requirements).
_TRANSIENT_PROVIDER_ERRORS = (httpx.HTTPError, anthropic.APIError)


def friendly_provider_detail(provider_name: str, exc: Exception) -> str:
    if isinstance(exc, httpx.ConnectError) and "ollama" in provider_name:
        return "Cannot reach Ollama. Make sure it's running (`ollama serve`) and reachable at OLLAMA_BASE_URL."
    if isinstance(exc, httpx.TimeoutException):
        return f"The {provider_name} request timed out. The model may be overloaded or too large for this machine."
    return str(exc)[:300]


async def guard_retrieval(coro, *, provider_name: str):
    """Run a retrieval coroutine, translating transport failures into RetrievalError."""
    try:
        return await coro
    except _TRANSIENT_PROVIDER_ERRORS as exc:
        logger.error("retrieval_dependency_failure", provider=provider_name, error=str(exc))
        raise RetrievalError(
            "Retrieval is temporarily unavailable.",
            detail=friendly_provider_detail(provider_name, exc),
        ) from exc


async def guard_generation(coro, *, provider_name: str):
    """Run a chat-generation coroutine, translating transport/auth failures into an AppError."""
    try:
        return await coro
    except _TRANSIENT_PROVIDER_ERRORS as exc:
        logger.error("generation_dependency_failure", provider=provider_name, error=str(exc))
        if isinstance(exc, anthropic.AuthenticationError):
            raise ProviderUnavailableError(
                "The configured cloud provider rejected the API key.",
                detail="Check ANTHROPIC_API_KEY, or switch LLM_PROVIDER=ollama to use the local model instead.",
            ) from exc
        raise ModelFailureError(
            f"The {provider_name} model is unavailable right now.",
            detail=friendly_provider_detail(provider_name, exc),
        ) from exc


@dataclass
class AgentTurnResult:
    intent: Intent
    content: str
    sources: list[RetrievedChunk] = field(default_factory=list)
    abstained: bool = False
    artifact_type: str | None = None
    artifact_title: str | None = None
    artifact_content: str | None = None
    validation_warnings: list[str] = field(default_factory=list)
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0


class PodcastAgent:
    def __init__(
        self,
        chat_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
    ):
        self.chat_provider = chat_provider
        self.embedding_provider = embedding_provider
        self.settings = settings

    async def handle_turn(
        self,
        db: AsyncSession,
        user_message: str,
        history: list[ChatMessage],
    ) -> AgentTurnResult:
        intent = classify_intent(user_message)
        logger.info("agent_intent_classified", intent=intent.value)

        with Timer() as retrieval_timer:
            chunks = await guard_retrieval(
                search_transcripts(db, self.embedding_provider, user_message, self.settings),
                provider_name=self.embedding_provider.name,
            )

        logger.info(
            "retrieval_complete",
            result_count=len(chunks),
            latency_ms=retrieval_timer.elapsed_ms,
            top_score=chunks[0].relevance_score if chunks else None,
        )

        with Timer() as gen_timer:
            tool_result = await guard_generation(
                self._dispatch(intent, user_message, history, chunks),
                provider_name=self.chat_provider.name,
            )

        return AgentTurnResult(
            intent=intent,
            content=tool_result.content,
            sources=tool_result.sources,
            abstained=tool_result.abstained,
            artifact_type=self._artifact_type_for(intent, tool_result),
            artifact_title=tool_result.artifact_title,
            artifact_content=tool_result.artifact_markdown or tool_result.artifact_html,
            validation_warnings=tool_result.validation_warnings,
            retrieval_latency_ms=retrieval_timer.elapsed_ms,
            generation_latency_ms=gen_timer.elapsed_ms,
        )

    async def _dispatch(
        self,
        intent: Intent,
        user_message: str,
        history: list[ChatMessage],
        chunks: list[RetrievedChunk],
    ) -> ToolResult:
        if intent == Intent.SHIP30:
            return await generate_ship30_tool(self.chat_provider, user_message, chunks)
        if intent == Intent.MARKDOWN_ARTIFACT:
            return await generate_markdown_artifact_tool(self.chat_provider, user_message, chunks)
        if intent == Intent.HTML_ARTIFACT:
            return await generate_html_artifact_tool(self.chat_provider, user_message, chunks)
        return await answer_from_sources(self.chat_provider, user_message, history, chunks)

    @staticmethod
    def _artifact_type_for(intent: Intent, tool_result: ToolResult) -> str | None:
        if tool_result.artifact_markdown and intent == Intent.SHIP30:
            return "ship30"
        if tool_result.artifact_markdown:
            return "markdown"
        if tool_result.artifact_html:
            return "html"
        return None
