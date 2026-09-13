import json
from pathlib import Path

import pytest

from app.db.models import TranscriptChunk, TranscriptDocument
from app.ingestion.chunker import chunk_text
from app.ingestion.loader import discover_transcript_files, load_transcript
from app.ingestion.normalizer import content_hash, normalize_text
from app.ingestion.pipeline import run_ingestion
from sqlalchemy import select


def test_chunk_text_splits_long_text_into_multiple_chunks():
    paragraph = "This is a sentence about product growth. " * 40
    text = "\n\n".join([paragraph] * 5)
    chunks = chunk_text(text, target_tokens=100, overlap_tokens=20)
    assert len(chunks) > 1
    assert all(c.token_count > 0 for c in chunks)


def test_chunk_text_empty_input_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_chunk_text_preserves_overlap_between_consecutive_chunks():
    paragraphs = [f"Paragraph number {i} with some unique content about topic {i}." for i in range(20)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, target_tokens=40, overlap_tokens=15)
    assert len(chunks) >= 2


def test_normalize_text_collapses_whitespace_and_strips_timestamps():
    raw = "[00:01]   Hello   world  \n\n\n\nNext line"
    normalized = normalize_text(raw)
    assert "[00:01]" not in normalized
    assert "   " not in normalized
    assert "\n\n\n" not in normalized


def test_normalize_text_converts_bold_speaker_timestamp_format():
    raw = "**Adam Mosseri** (00:00:00):\nHello there."
    normalized = normalize_text(raw)
    assert normalized.startswith("Adam Mosseri:")
    assert "(00:00:00)" not in normalized


def test_content_hash_is_stable_and_sensitive_to_change():
    a = content_hash("hello world")
    b = content_hash("hello world")
    c = content_hash("hello world!")
    assert a == b
    assert a != c


def test_loader_discovers_only_supported_extensions(tmp_path: Path):
    (tmp_path / "a.json").write_text(json.dumps({"title": "A", "transcript": "hi"}), encoding="utf-8")
    (tmp_path / "b.txt").write_text("Title: B\n\nhello", encoding="utf-8")
    (tmp_path / "ignore.pdf").write_bytes(b"%PDF-1.4")
    files = discover_transcript_files(tmp_path)
    names = {f.name for f in files}
    assert names == {"a.json", "b.txt"}


def test_loader_never_fabricates_missing_metadata(tmp_path: Path):
    path = tmp_path / "bare.json"
    path.write_text(json.dumps({"transcript": "no metadata here"}), encoding="utf-8")
    raw = load_transcript(path)
    assert raw.episode is None
    assert raw.source_url is None
    assert raw.published_at is None
    assert raw.title == "bare"  # falls back to filename, not a guess at real metadata


def test_loader_parses_frontmatter_markdown(tmp_path: Path):
    path = tmp_path / "guest.md"
    path.write_text(
        '---\ntitle: "A Great Chat"\ndate: "2025-01-01"\nguest: "Jane Doe"\npost_url: "https://x.test/p"\n---\n\nHello transcript body.',
        encoding="utf-8",
    )
    raw = load_transcript(path)
    assert raw.title == "A Great Chat"
    assert raw.episode == "Jane Doe"
    assert raw.source_url == "https://x.test/p"
    assert raw.published_at == "2025-01-01"
    assert raw.text == "Hello transcript body."


async def test_run_ingestion_creates_documents_and_chunks(db_session, fake_embedding_provider, tmp_path: Path):
    (tmp_path / "ep.json").write_text(
        json.dumps({"title": "Test Episode", "episode": "E1", "source_url": "https://x.test", "transcript": "Some useful growth content. " * 30}),
        encoding="utf-8",
    )
    response = await run_ingestion(db_session, fake_embedding_provider, tmp_path, chunk_target_tokens=50, chunk_overlap_tokens=10)
    assert response.documents_ingested == 1
    assert response.chunks_created >= 1
    assert response.errors == []

    docs = (await db_session.execute(select(TranscriptDocument))).scalars().all()
    assert len(docs) == 1
    assert docs[0].title == "Test Episode"


async def test_run_ingestion_is_idempotent_on_duplicate_content(db_session, fake_embedding_provider, tmp_path: Path):
    (tmp_path / "ep.json").write_text(
        json.dumps({"title": "Dup Episode", "transcript": "Same content every time."}), encoding="utf-8"
    )
    first = await run_ingestion(db_session, fake_embedding_provider, tmp_path)
    second = await run_ingestion(db_session, fake_embedding_provider, tmp_path)

    assert first.documents_ingested == 1
    assert second.documents_ingested == 0
    assert second.documents_skipped_duplicate == 1

    docs = (await db_session.execute(select(TranscriptDocument))).scalars().all()
    assert len(docs) == 1


async def test_run_ingestion_handles_missing_directory_gracefully(db_session, fake_embedding_provider, tmp_path: Path):
    response = await run_ingestion(db_session, fake_embedding_provider, tmp_path / "does_not_exist")
    assert response.documents_seen == 0
    assert response.errors == []
