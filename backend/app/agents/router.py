"""Deterministic intent routing.

Design decision (see architecture.md "Agent routing"): rather than relying
on model-native function calling -- which Ollama models support
inconsistently and Anthropic supports differently -- routing is a small,
fully unit-testable, provider-agnostic classifier. This keeps agent behavior
identical no matter which LLM_PROVIDER is active, and makes "correct tool
routing" a fast deterministic test instead of a flaky model-dependent one.
"""
from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    SHIP30 = "generate_ship30"
    MARKDOWN_ARTIFACT = "generate_markdown_artifact"
    HTML_ARTIFACT = "generate_html_artifact"
    GROUNDED_QA = "answer_from_sources"


_SHIP30_PATTERNS = [
    r"\bship\s*30\b",
    r"\bship30\b",
    r"1[,.]?250[- ]word",
    r"\bessay\b.*\b(write|draft|generate)\b",
    r"\b(write|draft|generate)\b.*\bessay\b",
]

_HTML_PATTERNS = [
    r"\bhtml\b",
    r"\bhtml/css\b",
    r"\bweb ?page\b",
    r"\blanding page\b",
]

_MARKDOWN_PATTERNS = [
    r"\bmarkdown\b",
    r"\b(\.md)\b",
    r"\bartifact\b",
    r"\bsummary doc(ument)?\b",
    r"\bcheat ?sheet\b",
    r"\bone[- ]pager\b",
]


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_intent(user_message: str) -> Intent:
    text = user_message.strip()
    if _matches_any(_SHIP30_PATTERNS, text):
        return Intent.SHIP30
    if _matches_any(_HTML_PATTERNS, text):
        return Intent.HTML_ARTIFACT
    if _matches_any(_MARKDOWN_PATTERNS, text):
        return Intent.MARKDOWN_ARTIFACT
    return Intent.GROUNDED_QA
