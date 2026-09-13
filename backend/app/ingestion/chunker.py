"""Paragraph-aware chunking.

We split on paragraph boundaries first so a chunk never cuts a sentence in
half where avoidable, then greedily pack paragraphs up to `target_tokens`,
carrying `overlap_tokens` worth of trailing text into the next chunk so
retrieval doesn't lose context at a chunk boundary. Token counts use
tiktoken's cl100k encoding as a fast, model-agnostic proxy -- it doesn't need
to be exact, just consistent.
"""
from __future__ import annotations

from dataclasses import dataclass

import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


@dataclass
class Chunk:
    index: int
    text: str
    token_count: int


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if paragraphs:
        return paragraphs
    return [p.strip() for p in text.split("\n") if p.strip()]


def chunk_text(text: str, target_tokens: int = 350, overlap_tokens: int = 60) -> list[Chunk]:
    if not text.strip():
        return []
    paragraphs = _split_paragraphs(text)
    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0

    def flush():
        nonlocal current, current_tokens
        if not current:
            return
        joined = "\n\n".join(current)
        chunks.append(Chunk(index=len(chunks), text=joined, token_count=_count_tokens(joined)))

    for para in paragraphs:
        para_tokens = _count_tokens(para)
        if para_tokens > target_tokens * 2:
            # Oversized paragraph (rare): split on sentences as a fallback.
            sentences = [s.strip() for s in para.replace("\n", " ").split(". ") if s.strip()]
            para_chunks = []
            buf, buf_tokens = [], 0
            for s in sentences:
                st = _count_tokens(s)
                if buf_tokens + st > target_tokens and buf:
                    para_chunks.append(". ".join(buf) + ".")
                    buf, buf_tokens = [], 0
                buf.append(s)
                buf_tokens += st
            if buf:
                para_chunks.append(". ".join(buf) + ".")
            for pc in para_chunks:
                if current_tokens + _count_tokens(pc) > target_tokens and current:
                    flush()
                    current, current_tokens = [], 0
                current.append(pc)
                current_tokens += _count_tokens(pc)
            continue

        if current_tokens + para_tokens > target_tokens and current:
            flush()
            # carry overlap: keep trailing paragraphs worth ~overlap_tokens
            overlap: list[str] = []
            overlap_count = 0
            for p in reversed(current):
                pt = _count_tokens(p)
                if overlap_count + pt > overlap_tokens:
                    break
                overlap.insert(0, p)
                overlap_count += pt
            current = overlap
            current_tokens = overlap_count

        current.append(para)
        current_tokens += para_tokens

    flush()
    return chunks
