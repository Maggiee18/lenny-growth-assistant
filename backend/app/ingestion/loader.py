"""Load raw transcript files from a local directory (recursively).

Supported formats (see data/transcripts/README.md for the exact schema):
  - .md     YAML-frontmatter markdown, matching the schema used by the
            official "Lenny's Newsletter" transcript data repo:
            ---
            title: "..."
            date: "YYYY-MM-DD"
            guest: "..."
            post_url: "https://..."
            description: "..."
            ---
            <speaker-labeled transcript body>
  - .json   {"title", "episode", "source_url", "published_at", "transcript"}
  - .txt    plain text, filename used as title unless a "Title: ..." header line is present
  - .vtt    WebVTT captions (cue timestamps stripped, cue text concatenated)

We never fabricate metadata: a field that is not present in the source file
is left null rather than guessed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawTranscript:
    title: str
    episode: str | None
    source_url: str | None
    published_at: str | None
    text: str
    source_path: str


def _load_json(path: Path) -> RawTranscript:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RawTranscript(
        title=data.get("title") or path.stem,
        episode=data.get("episode"),
        source_url=data.get("source_url"),
        published_at=data.get("published_at"),
        text=data.get("transcript", ""),
        source_path=str(path),
    )


def _load_txt(path: Path) -> RawTranscript:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    title = path.stem
    episode = None
    source_url = None
    published_at = None
    body_start = 0
    for i, line in enumerate(lines[:6]):
        m = re.match(r"^(Title|Episode|Source|Published):\s*(.+)$", line.strip(), re.IGNORECASE)
        if m:
            key, val = m.group(1).lower(), m.group(2).strip()
            if key == "title":
                title = val
            elif key == "episode":
                episode = val
            elif key == "source":
                source_url = val
            elif key == "published":
                published_at = val
            body_start = i + 1
        elif line.strip() == "" and body_start:
            body_start = i + 1
        else:
            break
    text = "\n".join(lines[body_start:]).strip() or raw
    return RawTranscript(title, episode, source_url, published_at, text, str(path))


_VTT_TIMESTAMP = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->")


def _load_vtt(path: Path) -> RawTranscript:
    lines = path.read_text(encoding="utf-8").splitlines()
    cues = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.upper() == "WEBVTT" or stripped.isdigit():
            continue
        if _VTT_TIMESTAMP.match(stripped):
            continue
        cues.append(stripped)
    return RawTranscript(title=path.stem, episode=None, source_url=None, published_at=None, text=" ".join(cues), source_path=str(path))


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_FRONTMATTER_FIELD_RE = re.compile(r'^([A-Za-z_]+):\s*"?(.*?)"?\s*$')


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}, raw
    block, body = match.group(1), match.group(2)
    fields: dict[str, str] = {}
    for line in block.splitlines():
        m = _FRONTMATTER_FIELD_RE.match(line.strip())
        if m:
            fields[m.group(1).strip().lower()] = m.group(2).strip()
    return fields, body.strip()


def _load_md(path: Path) -> RawTranscript:
    raw = path.read_text(encoding="utf-8")
    fields, body = _parse_frontmatter(raw)
    if not fields:
        # Not our known frontmatter schema -- treat as plain text.
        return _load_txt(path)
    return RawTranscript(
        title=fields.get("title") or path.stem,
        episode=fields.get("guest"),
        source_url=fields.get("post_url"),
        published_at=fields.get("date"),
        text=body,
        source_path=str(path),
    )


LOADERS = {".json": _load_json, ".txt": _load_txt, ".vtt": _load_vtt, ".md": _load_md}


def discover_transcript_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        return []
    return sorted(
        p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in LOADERS
    )


def load_transcript(path: Path) -> RawTranscript:
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"Unsupported transcript format: {path.suffix}")
    return loader(path)
