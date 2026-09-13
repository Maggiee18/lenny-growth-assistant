from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import TranscriptChunk, TranscriptDocument
from app.ingestion.chunker import chunk_text
from app.ingestion.loader import discover_transcript_files, load_transcript
from app.ingestion.normalizer import content_hash, normalize_text
from app.providers.base import EmbeddingProvider
from app.schemas.ingestion import IngestionRunResponse

logger = get_logger(__name__)


async def run_ingestion(
    db: AsyncSession,
    embedding_provider: EmbeddingProvider,
    source_dir: Path,
    *,
    force_reingest: bool = False,
    chunk_target_tokens: int = 350,
    chunk_overlap_tokens: int = 60,
) -> IngestionRunResponse:
    files = discover_transcript_files(source_dir)
    documents_seen = 0
    documents_ingested = 0
    documents_skipped = 0
    chunks_created = 0
    errors: list[str] = []

    for path in files:
        documents_seen += 1
        try:
            raw = load_transcript(path)
            normalized = normalize_text(raw.text)
            if not normalized:
                errors.append(f"{path.name}: empty transcript after normalization, skipped")
                continue
            digest = content_hash(normalized)

            existing = await db.scalar(
                select(TranscriptDocument).where(TranscriptDocument.content_hash == digest)
            )
            if existing and not force_reingest:
                documents_skipped += 1
                logger.info("ingestion_skip_duplicate", file=path.name, document_id=str(existing.id))
                continue
            if existing and force_reingest:
                await db.delete(existing)
                await db.flush()

            document = TranscriptDocument(
                title=raw.title,
                episode=raw.episode,
                source_url=raw.source_url,
                published_at=_parse_date(raw.published_at),
                content_hash=digest,
                doc_metadata={"source_path": raw.source_path},
            )
            db.add(document)
            await db.flush()

            pieces = chunk_text(normalized, chunk_target_tokens, chunk_overlap_tokens)
            if not pieces:
                errors.append(f"{path.name}: no chunks produced")
                continue

            vectors = await embedding_provider.embed([c.text for c in pieces])
            for chunk, vector in zip(pieces, vectors):
                db.add(
                    TranscriptChunk(
                        document_id=document.id,
                        chunk_index=chunk.index,
                        content=chunk.text,
                        embedding=vector,
                        chunk_metadata={"token_count": chunk.token_count},
                    )
                )
                chunks_created += 1

            await db.commit()
            documents_ingested += 1
            logger.info(
                "ingestion_document_complete",
                file=path.name,
                document_id=str(document.id),
                chunks=len(pieces),
            )
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            errors.append(f"{path.name}: {exc}")
            logger.error("ingestion_document_failed", file=path.name, error=str(exc))

    return IngestionRunResponse(
        documents_seen=documents_seen,
        documents_ingested=documents_ingested,
        documents_skipped_duplicate=documents_skipped,
        chunks_created=chunks_created,
        errors=errors,
    )


def _parse_date(value: str | None):
    if not value:
        return None
    from datetime import datetime

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
