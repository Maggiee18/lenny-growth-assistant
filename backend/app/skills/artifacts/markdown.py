from __future__ import annotations

import re

from app.core.errors import ArtifactSanitizationError

_RAW_HTML_BLOCK = re.compile(r"<\s*(script|iframe|object|embed|style|on\w+)\b", re.IGNORECASE)


def validate_markdown(raw_markdown: str, *, max_bytes: int = 200_000) -> str:
    """Markdown artifacts are rendered client-side with raw HTML disabled
    (see frontend ArtifactViewer), but we still reject obvious script-bearing
    payloads server-side rather than relying on a single layer of defense.
    """
    if not raw_markdown.strip():
        raise ArtifactSanitizationError("Generated Markdown was empty.")
    if len(raw_markdown.encode("utf-8")) > max_bytes:
        raise ArtifactSanitizationError("Generated Markdown exceeds the maximum allowed size.")
    if _RAW_HTML_BLOCK.search(raw_markdown):
        raise ArtifactSanitizationError(
            "Generated Markdown contains disallowed raw HTML.",
            detail="script/iframe/object/embed/style/event-handler tags are not allowed in markdown artifacts",
        )
    return raw_markdown.strip()


def derive_title(markdown_text: str, fallback: str = "Untitled artifact") -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback
