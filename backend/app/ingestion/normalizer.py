from __future__ import annotations

import hashlib
import re

_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")
_SPEAKER_TAG_RE = re.compile(r"^\s*\[\d{1,2}:\d{2}(?::\d{2})?\]\s*")
# "**Speaker Name** (00:12:34):" -> "Speaker Name:" -- keeps attribution,
# drops the timestamp noise that adds tokens without adding retrieval value.
_BOLD_SPEAKER_TIMESTAMP_RE = re.compile(
    r"^\*\*(?P<speaker>[^*]+)\*\*\s*\(\d{1,2}:\d{2}(?::\d{2})?\)\s*:\s*"
)


def normalize_text(raw: str) -> str:
    """Collapse whitespace, strip inline timestamp tags, keep speaker labels."""
    lines = []
    for line in raw.splitlines():
        line = _BOLD_SPEAKER_TIMESTAMP_RE.sub(lambda m: f"{m.group('speaker').strip()}: ", line)
        line = _SPEAKER_TAG_RE.sub("", line)
        line = _WHITESPACE_RE.sub(" ", line).strip()
        lines.append(line)
    text = "\n".join(lines)
    text = _BLANKLINES_RE.sub("\n\n", text)
    return text.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
