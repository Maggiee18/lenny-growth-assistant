"""Vector similarity retrieval with a relevance threshold and keyword fallback.

Priority per architecture.md is accuracy > explainability > complexity, so
this stays a single well-understood path: pgvector cosine distance for
semantic recall, plus a lightweight Postgres full-text fallback when the
vector search returns nothing above threshold (e.g. an exact acronym or
product name a dense embedding might blur). Both paths return the same
RetrievedChunk shape so the agent/grounding layer doesn't need to know which
one fired.

Dialect note: production always runs on PostgreSQL, which does the cosine
search inside the database using the pgvector index. The pytest suite runs
against in-memory SQLite (see tests/conftest.py) so the ORM/service layers
are testable without Docker; on any non-PostgreSQL bind, this module falls
back to loading candidate embeddings and scoring them in Python. That
fallback is O(n) and only used by tests / non-Postgres dev setups -- it is
never the code path a real deployment takes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import TranscriptChunk, TranscriptDocument
from app.providers.base import EmbeddingProvider

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    title: str
    episode: str | None
    source_url: str | None
    content: str
    relevance_score: float
    retrieval_method: str  # "vector" | "keyword"


def _dialect_name(db: AsyncSession) -> str:
    return db.get_bind().dialect.name


async def retrieve(
    db: AsyncSession,
    embedding_provider: EmbeddingProvider,
    query: str,
    *,
    top_k: int = 6,
    similarity_threshold: float = 0.55,
) -> list[RetrievedChunk]:
    [query_vector] = await embedding_provider.embed([query])

    if _dialect_name(db) == "postgresql":
        results = await _vector_search_postgres(db, query_vector, top_k)
    else:
        results = await _vector_search_python(db, query_vector, top_k)

    above_threshold = [r for r in results if r.relevance_score >= similarity_threshold]
    if above_threshold:
        return above_threshold

    logger.info(
        "retrieval_below_threshold",
        query=query[:120],
        best_score=results[0].relevance_score if results else None,
    )

    return await _keyword_fallback(db, query, top_k)


async def _vector_search_postgres(
    db: AsyncSession, query_vector: list[float], top_k: int
) -> list[RetrievedChunk]:
    # cosine distance in pgvector: 0 = identical, 2 = opposite. similarity = 1 - distance.
    stmt = (
        select(
            TranscriptChunk.id,
            TranscriptChunk.document_id,
            TranscriptChunk.content,
            TranscriptDocument.title,
            TranscriptDocument.episode,
            TranscriptDocument.source_url,
            TranscriptChunk.embedding.cosine_distance(query_vector).label("distance"),
        )
        .join(TranscriptDocument, TranscriptChunk.document_id == TranscriptDocument.id)
        .where(TranscriptChunk.embedding.is_not(None))
        .order_by("distance")
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).all()
    return [
        RetrievedChunk(
            chunk_id=row.id,
            document_id=row.document_id,
            title=row.title,
            episode=row.episode,
            source_url=row.source_url,
            content=row.content,
            relevance_score=round(1 - float(row.distance), 4),
            retrieval_method="vector",
        )
        for row in rows
    ]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _vector_search_python(
    db: AsyncSession, query_vector: list[float], top_k: int
) -> list[RetrievedChunk]:
    stmt = (
        select(TranscriptChunk, TranscriptDocument)
        .join(TranscriptDocument, TranscriptChunk.document_id == TranscriptDocument.id)
        .where(TranscriptChunk.embedding.is_not(None))
    )
    rows = (await db.execute(stmt)).all()
    scored = [
        (
            _cosine_similarity(query_vector, chunk.embedding),
            chunk,
            document,
        )
        for chunk, document in rows
    ]
    scored.sort(key=lambda t: t[0], reverse=True)
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            title=document.title,
            episode=document.episode,
            source_url=document.source_url,
            content=chunk.content,
            relevance_score=round(score, 4),
            retrieval_method="vector",
        )
        for score, chunk, document in scored[:top_k]
    ]


async def _keyword_fallback(db: AsyncSession, query: str, top_k: int) -> list[RetrievedChunk]:
    """Keyword fallback for when vector search is weak or empty.

    Uses Postgres full-text search (`ts_rank_cd`/`plainto_tsquery`) in
    production; falls back to a simple case-insensitive substring/term-overlap
    score on other dialects (tests) so the fallback path itself stays
    testable without Docker.
    """
    if _dialect_name(db) == "postgresql":
        return await _keyword_fallback_postgres(db, query, top_k)
    return await _keyword_fallback_python(db, query, top_k)


async def _keyword_fallback_postgres(db: AsyncSession, query: str, top_k: int) -> list[RetrievedChunk]:
    stmt = text(
        """
        SELECT c.id, c.document_id, c.content, d.title, d.episode, d.source_url,
               ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', :query)) AS rank
        FROM transcript_chunks c
        JOIN transcript_documents d ON d.id = c.document_id
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', :query)
        ORDER BY rank DESC
        LIMIT :top_k
        """
    )
    try:
        rows = (await db.execute(stmt, {"query": query, "top_k": top_k})).all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("keyword_fallback_failed", error=str(exc))
        return []

    return [
        RetrievedChunk(
            chunk_id=row.id,
            document_id=row.document_id,
            title=row.title,
            episode=row.episode,
            source_url=row.source_url,
            content=row.content,
            relevance_score=round(min(float(row.rank), 1.0), 4),
            retrieval_method="keyword",
        )
        for row in rows
        if row.rank and row.rank > 0
    ]


async def _keyword_fallback_python(db: AsyncSession, query: str, top_k: int) -> list[RetrievedChunk]:
    terms = [t for t in query.lower().split() if len(t) > 2]
    if not terms:
        return []
    stmt = select(TranscriptChunk, TranscriptDocument).join(
        TranscriptDocument, TranscriptChunk.document_id == TranscriptDocument.id
    )
    rows = (await db.execute(stmt)).all()
    scored = []
    for chunk, document in rows:
        lowered = chunk.content.lower()
        hits = sum(lowered.count(t) for t in terms)
        if hits > 0:
            scored.append((hits / max(len(terms), 1), chunk, document))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            title=document.title,
            episode=document.episode,
            source_url=document.source_url,
            content=chunk.content,
            relevance_score=round(min(score, 1.0), 4),
            retrieval_method="keyword",
        )
        for score, chunk, document in scored[:top_k]
    ]
