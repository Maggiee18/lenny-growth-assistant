"""Cross-dialect column types.

Production always runs on PostgreSQL + pgvector (non-negotiable per
architecture.md). These wrappers let the *same* ORM models also compile
against SQLite, which is what the pytest suite uses so the full test suite
-- including session/message/artifact CRUD -- runs with zero external
dependencies. See EmbeddingVector for how vector search degrades gracefully
on non-Postgres backends (Python-side cosine similarity instead of the
pgvector index) -- retrieval.retriever picks the strategy at query time.
"""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator, Uuid

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class EmbeddingVector(TypeDecorator):
    """pgvector `Vector` on PostgreSQL, JSON-encoded float list elsewhere."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())


UuidPk = Uuid(as_uuid=True)
