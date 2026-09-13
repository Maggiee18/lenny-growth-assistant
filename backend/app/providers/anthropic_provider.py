from __future__ import annotations

from typing import Any, AsyncIterator

import anthropic

from app.core.logging import get_logger
from app.providers.base import ChatMessage, ChatResult, LLMProvider, ToolCall

logger = get_logger(__name__)


def _split_system(messages: list[ChatMessage]) -> tuple[str | None, list[ChatMessage]]:
    system_parts = [m.content for m in messages if m.role == "system"]
    rest = [m for m in messages if m.role != "system"]
    return ("\n\n".join(system_parts) or None, rest)


def _to_anthropic_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        if m.role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content,
                        }
                    ],
                }
            )
        else:
            out.append({"role": m.role, "content": m.content})
    return out


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float = 60.0):
        self._model = model
        self.timeout = timeout
        self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)

    @property
    def model(self) -> str:
        return self._model

    async def is_available(self) -> tuple[bool, str]:
        if not self.client.api_key:
            return False, "ANTHROPIC_API_KEY is not set."
        try:
            await self.client.messages.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, "ok"
        except anthropic.AuthenticationError:
            return False, "Anthropic API key is invalid."
        except anthropic.APIConnectionError:
            return False, "Cannot reach Anthropic API (network error)."
        except Exception as exc:  # noqa: BLE001
            return False, f"Anthropic health check failed: {exc}"

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> ChatResult:
        system, rest = _split_system(messages)
        kwargs: dict[str, Any] = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=_to_anthropic_messages(rest),
        )
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        resp = await self.client.messages.create(**kwargs)

        text_parts = []
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))
        return ChatResult(
            content="".join(text_parts),
            tool_calls=tool_calls,
            raw_model=resp.model,
            stop_reason=resp.stop_reason or "stop",
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        system, rest = _split_system(messages)
        kwargs: dict[str, Any] = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=_to_anthropic_messages(rest),
        )
        if system:
            kwargs["system"] = system
        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
