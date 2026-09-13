from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from app.core.logging import get_logger
from app.providers.base import ChatMessage, ChatResult, EmbeddingProvider, LLMProvider, ToolCall

logger = get_logger(__name__)


def _to_ollama_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    out = []
    for m in messages:
        if m.role == "tool":
            # Ollama has no first-class tool role for most models; fold tool
            # results back in as a labeled system observation.
            out.append({"role": "user", "content": f"[tool result: {m.name}]\n{m.content}"})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


class OllamaProvider(LLMProvider):
    """Chat provider backed by a local Ollama server.

    Ollama's tool-calling support varies a lot by model, so the agent layer
    does not rely on native function-calling here: PodcastAgent (see
    agents/agent.py) does its own intent routing and only uses this provider
    for plain chat completions. `tools=` is accepted for interface parity but
    ignored -- ChatResult.tool_calls is always empty for this provider.
    """

    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 90.0):
        self.base_url = base_url.rstrip("/")
        self._model = model
        self.timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    async def is_available(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                tags = [m["name"] for m in resp.json().get("models", [])]
                if not any(self._model.split(":")[0] in t for t in tags):
                    return False, f"Ollama is running but model '{self._model}' is not pulled. Run: ollama pull {self._model}"
                return True, "ok"
        except httpx.ConnectError:
            return False, f"Cannot reach Ollama at {self.base_url}. Is it running? (`ollama serve`)"
        except Exception as exc:  # noqa: BLE001
            return False, f"Ollama health check failed: {exc}"

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> ChatResult:
        payload = {
            "model": self._model,
            "messages": _to_ollama_messages(messages),
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data.get("message", {}).get("content", "")
        return ChatResult(content=content, tool_calls=[], raw_model=self._model, stop_reason=data.get("done_reason", "stop"))

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": _to_ollama_messages(messages),
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    piece = chunk.get("message", {}).get("content", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        break


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama-embeddings"

    def __init__(self, base_url: str, model: str, dimensions: int, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dimensions = dimensions
        self.timeout = timeout

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def is_available(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                tags = [m["name"] for m in resp.json().get("models", [])]
                if not any(self.model.split(":")[0] in t for t in tags):
                    return False, f"Embedding model '{self.model}' not pulled. Run: ollama pull {self.model}"
                return True, "ok"
        except Exception as exc:  # noqa: BLE001
            return False, f"Ollama embeddings unavailable: {exc}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for text in texts:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings", json={"model": self.model, "prompt": text}
                )
                resp.raise_for_status()
                vectors.append(resp.json()["embedding"])
        return vectors
