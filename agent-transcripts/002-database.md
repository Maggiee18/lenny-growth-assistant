# 002 — Database schema & cross-dialect models

**Goal:** SQLAlchemy models + Alembic migration for `sessions`, `messages`, `transcript_documents`, `transcript_chunks`, `artifacts`.

## What was done

- Modeled the five tables per the assignment's recommended fields, using UUID primary keys, JSON metadata columns, and a `pgvector` `Vector(768)` column on `transcript_chunks.embedding`.
- Wrote `backend/alembic/versions/0001_initial_schema.py` by hand (rather than `alembic revision --autogenerate`) since there's no live Postgres in this sandbox to autogenerate against — the DDL was checked manually against SQLAlchemy's compiled `CREATE TABLE` statements instead.

## Failure: models didn't compile against SQLite

**Attempted:** run the (yet-to-be-written) pytest suite against an in-memory SQLite database, since there's no Postgres available here and the assignment wants a runnable, meaningful test suite.

**Failed because:** the models used `pgvector.sqlalchemy.Vector`, `sqlalchemy.dialects.postgresql.JSONB`, and `sqlalchemy.dialects.postgresql.UUID` directly — all three are Postgres-only types with no SQLite compilation path. `Base.metadata.create_all()` against a SQLite engine would raise immediately.

**Options considered:**
1. Require a real Postgres for all DB-touching tests (skip them here, run them only in CI/Docker).
2. Make the ORM layer cross-dialect so the *same* models run on SQLite for tests and Postgres for production, with retrieval choosing its SQL strategy per-dialect.

**Chose (2)** — a fake/mocked repository layer would test the mocks, not the actual ORM/SQL logic; a real cross-dialect model set tests the real code path for everything except the pgvector index itself. Implemented in `backend/app/db/types.py`:
- `Uuid(as_uuid=True)` (SQLAlchemy's built-in cross-dialect type) instead of `postgresql.UUID`.
- `JSON().with_variant(JSONB(), "postgresql")` instead of raw `JSONB`.
- A custom `EmbeddingVector(TypeDecorator)` that resolves to pgvector's `Vector` on PostgreSQL and to a plain `JSON` float-list everywhere else.

Then updated `retrieval/retriever.py` to branch on `db.get_bind().dialect.name`: the Postgres path runs the real `cosine_distance()` pgvector query; any other dialect (SQLite, in tests) runs a pure-Python cosine-similarity fallback and a term-overlap keyword fallback. Documented clearly in both files' docstrings that this fallback exists **only** to make the test suite dependency-free — production always takes the pgvector path.

**Verified:** `pytest` suite (80+ tests) runs green against in-memory SQLite with zero external dependencies; migration file still targets real Postgres/pgvector for the Docker deployment.
