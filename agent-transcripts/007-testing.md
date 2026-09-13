# 007 — Test suite & frontend build verification

**Goal:** meaningful automated tests for API, retrieval, routing, persistence (backend) plus frontend component tests, run for real (not claimed).

## Backend

83 pytest tests, run against in-memory SQLite (see `002-database.md` for why that's possible), covering: health/config, session CRUD + isolation + validation (malformed UUID, missing session), message posting + grounding/abstention + follow-up context, retrieval (ranking, threshold, keyword fallback, top-k, source metadata), artifact creation + HTML sanitization + markdown validation, Ship 30 pipeline (insufficient-evidence guard, outline parsing, structure validation), ingestion (chunking, normalization, loader format parsing, idempotent re-ingestion), provider factory/availability (mocked via `respx`), and dependency-failure resilience.

Coverage: 82% (`pytest --cov=app`), with the weakest-covered modules being `anthropic_provider.py` (34% — the real streaming/chat paths need a live API key to exercise; `is_available()` without a key is tested) and `db/base.py` (engine/session-factory singletons, exercised indirectly through every DB test but not covered as isolated units).

Ran `pytest -q` after every meaningful change, not just once at the end — caught and fixed two real bugs mid-session (see `006-artifact-security.md`, `005-ollama.md`) this way.

## Frontend

- `npx tsc --noEmit` — clean, no type errors.
- `npx vitest run` — 11 tests (Composer keyboard behavior, ArtifactViewer rendering/sanitization/sandbox attribute) — all passing.
- `npm run build` (`next build`) — production build succeeds, including Next's own lint + type-check pass, output ~137KB first-load JS for the main route.

## Manual end-to-end verification

Ran the actual FastAPI app with `uvicorn` against a real (file-based) SQLite database and exercised it with `curl`: create session, post message (grounded + abstained + Ollama-down cases), get session detail, list sessions, malformed UUID, missing session. This is documented in detail in `005-ollama.md` since it's where the resilience bug was found. This is the closest verification possible in this sandbox to the assignment's "actually test it" requirement, short of a real Postgres+pgvector+Ollama stack (see `001-scaffold.md` for why that's not available here).
