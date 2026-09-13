#!/usr/bin/env python3
"""CLI wrapper around the ingestion pipeline.

    python scripts/ingest.py                       # ingest data/transcripts
    python scripts/ingest.py --source-dir /path     # ingest a custom directory
    python scripts/ingest.py --force                # re-ingest even if content hash matches

Requires the same environment variables as the API (DATABASE_URL,
OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL) -- run this after `docker compose up`
and after `ollama pull <embedding model>`.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.ingestion.pipeline import run_ingestion
from app.providers.factory import build_embedding_provider


async def main_async(source_dir: Path | None, force: bool) -> int:
    settings = get_settings()
    source_dir = source_dir or Path(settings.transcripts_dir)
    embedding_provider = build_embedding_provider(settings)

    available, detail = await embedding_provider.is_available()
    if not available:
        print(f"ERROR: embedding provider unavailable: {detail}", file=sys.stderr)
        print("Start Ollama and pull the embedding model, e.g.:", file=sys.stderr)
        print(f"  ollama pull {settings.ollama_embedding_model}", file=sys.stderr)
        return 1

    factory = get_session_factory()
    async with factory() as db:
        result = await run_ingestion(
            db,
            embedding_provider,
            source_dir,
            force_reingest=force,
            chunk_target_tokens=settings.chunk_target_tokens,
            chunk_overlap_tokens=settings.chunk_overlap_tokens,
        )

    print(f"Documents seen:      {result.documents_seen}")
    print(f"Documents ingested:  {result.documents_ingested}")
    print(f"Documents skipped:   {result.documents_skipped_duplicate} (duplicate content hash)")
    print(f"Chunks created:      {result.chunks_created}")
    if result.errors:
        print(f"Errors ({len(result.errors)}):", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--force", action="store_true", help="Re-ingest even if content hash already exists.")
    args = parser.parse_args()
    return asyncio.run(main_async(args.source_dir, args.force))


if __name__ == "__main__":
    raise SystemExit(main())
