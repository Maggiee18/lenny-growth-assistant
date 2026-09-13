"""Provider abstraction.

The agent and retrieval layers depend only on this interface, never on a
concrete SDK. `LLM_PROVIDER=ollama|anthropic` selects the chat implementation
at startup (see providers.factory). Embeddings are always produced by Ollama
regardless of the chat provider, because Anthropic does not expose an
embeddings endpoint -- this is a deliberate, documented split (see
architecture.md "Model switching").
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResult:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_model: str = ""
    stop_reason: str = ""


class ProviderUnavailable(Exception):
    """Raised when a provider cannot be reached or is misconfigured."""


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def is_available(self) -> tuple[bool, str]:
        """Return (available, detail) without raising."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> ChatResult:
        """Single non-streaming chat completion, with optional tool-use."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """Yield text chunks. Used for the streaming chat endpoint."""

    @property
    @abstractmethod
    def model(self) -> str: ...


class EmbeddingProvider(ABC):
    @abstractmethod
    async def is_available(self) -> tuple[bool, str]: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...
