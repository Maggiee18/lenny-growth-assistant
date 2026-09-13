# Architecture

## System diagram

```
                        ┌─────────────────────────────┐
                        │        Browser (user)        │
                        └───────────────┬──────────────┘
                                        │ HTTP
                        ┌───────────────▼──────────────┐
                        │  frontend/ (Next.js, :3000)  │
                        │  Sidebar · Chat · Composer ·  │
                        │  ArtifactViewer (sandboxed)   │
                        └───────────────┬──────────────┘
                                        │ REST (JSON)
                        ┌───────────────▼──────────────┐
                        │  backend/ (FastAPI, :8000)   │
                        │  ┌─────────────────────────┐  │
                        │  │  api/routes             │  │
                        │  └──────────┬──────────────┘  │
                        │  ┌──────────▼──────────────┐  │
                        │  │  services/              │  │
                        │  │  session/message/       │  │
                        │  │  artifact/health         │  │
                        │  └──────────┬──────────────┘  │
                        │  ┌──────────▼──────────────┐  │
                        │  │  agents/PodcastAgent     │  │
                        │  │  router → tools          │  │
                        │  └───┬──────────────────┬───┘  │
                        │  ┌───▼─────┐      ┌─────▼───┐  │
                        │  │retrieval│      │ skills/  │  │
                        │  │(pgvector)│     │ ship30,  │  │
                        │  └───┬─────┘      │ artifacts│  │
                        │      │            └─────┬───┘  │
                        │  ┌───▼────────────────────▼──┐ │
                        │  │  providers/ (LLMProvider)  │ │
                        │  └───┬────────────────────┬──┘ │
                        └──────┼────────────────────┼────┘
                               │                    │
                    ┌──────────▼─────────┐  ┌───────▼────────┐
                    │  Ollama (:11434)    │  │ Anthropic API   │
                    │  chat + embeddings  │  │ chat (optional) │
                    └─────────────────────┘  └────────────────┘
                               │
                    ┌──────────▼─────────┐
                    │ PostgreSQL+pgvector │
                    │ (:5432)             │
                    └─────────────────────┘
```

## Database schema

Five tables (`backend/app/db/models.py`, migration `backend/alembic/versions/0001_initial_schema.py`):

- **sessions** — `id` (UUID pk), `user_id` (nullable string), `title`, `provider`, `created_at`, `updated_at`.
- **messages** — `id`, `session_id` (FK → sessions, cascade delete), `role` (`user`/`assistant`/`system`), `content`, `message_metadata` (JSONB: intent, abstained flag, retrieval/generation latency, source list), `created_at`.
- **transcript_documents** — `id`, `title`, `episode`, `source_url`, `published_at`, `content_hash` (unique — dedup key), `doc_metadata` (JSONB), `created_at`.
- **transcript_chunks** — `id`, `document_id` (FK, cascade delete), `chunk_index`, `content`, `embedding` (`vector(768)`, ivfflat cosine index), `chunk_metadata` (JSONB: token count), `created_at`. Unique on `(document_id, chunk_index)`.
- **artifacts** — `id`, `session_id` (FK, nullable, SET NULL on delete), `message_id` (FK, nullable, SET NULL), `artifact_type` (`markdown`/`html`/`ship30`), `title`, `content`, `artifact_metadata` (JSONB: validation warnings), `created_at`.

**Cross-dialect note:** the ORM models use `sqlalchemy.types.Uuid`, a `JSON().with_variant(JSONB(), "postgresql")` wrapper, and a custom `EmbeddingVector` type decorator (`backend/app/db/types.py`) instead of Postgres-only types directly. This lets the exact same models run against SQLite for the test suite (no Docker/Postgres required to run `pytest`) while production always uses real pgvector types — the Alembic migration itself is Postgres-specific (`CREATE EXTENSION vector`, native `JSONB`, `ivfflat` index) since migrations only ever run against the real deployment target.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | App + dependency health (database always checked; the *active* provider — Ollama or Anthropic — checked, the inactive one reported for visibility but not load-bearing) |
| GET | `/api/config` | Active provider/model, Ollama availability, Anthropic configured flag, retrieval settings — no secrets |
| POST | `/api/sessions` | Create a session |
| GET | `/api/sessions` | List sessions (with message counts), newest-updated first |
| GET | `/api/sessions/{id}` | Session detail with full message history |
| POST | `/api/sessions/{id}/messages` | Post a user message; runs the agent turn; returns assistant message + sources + abstention flag + artifact id if one was generated |
| POST | `/api/artifacts` | Generate an artifact on demand for a session (not tied to a specific chat turn) |
| GET | `/api/artifacts/{id}` | Fetch a generated artifact |
| POST | `/api/ingestion/run` | Run the ingestion pipeline against a transcript directory |

All error responses share one shape: `{"error": {"category": "...", "message": "...", "detail": "..."}}`. Categories: `validation_error` (422), `not_found` (404), `retrieval_failure` / `provider_unavailable` (503), `model_failure` (502), `database_failure` (503), `artifact_sanitization_failure` (422), `ingestion_failure` (500), `internal_error` (500 — truly unexpected only). See `backend/app/core/errors.py`.

## Component boundaries

- **api/routes** — HTTP contract only (Pydantic validation, status codes); no business logic.
- **services/** — orchestrates persistence + calls into agents/skills; owns transactions.
- **agents/** — `PodcastAgent` (turn orchestration), `router.py` (intent classification), `tools.py` (the 5 explicit tool functions). Depends only on `providers.base` interfaces, never on a concrete SDK.
- **retrieval/** — pgvector query + keyword fallback; returns a provider-agnostic `RetrievedChunk` shape.
- **skills/ship30, skills/artifacts** — self-contained content-generation pipelines with their own schema/validator modules.
- **providers/** — the only place that imports `httpx` (Ollama) or `anthropic` (cloud SDK) directly.
- **ingestion/** — loading/normalizing/chunking, independent of the API layer (also runnable as a CLI: `backend/scripts/ingest.py`).

## Ingestion flow

```
data/transcripts/**/*.{md,json,txt,vtt}
    → loader.py (format-specific parsing, never fabricates metadata)
    → normalizer.py (whitespace/timestamp cleanup, speaker-label normalization)
    → content_hash() (SHA-256 of normalized text — dedup key)
    → [if content_hash already ingested and not --force: skip]
    → chunker.py (paragraph-aware, ~350 tokens, ~60 token overlap)
    → embedding_provider.embed() (always Ollama, e.g. nomic-embed-text)
    → INSERT transcript_documents, transcript_chunks (embedding column populated)
```

Re-ingestion is always safe: unchanged files are skipped (content-hash match), `--force` re-ingests. Every chunk carries `document_id`, so an answer's cited chunk can always be traced back to `transcript_documents.source_url`/`title`/`episode`.

## Retrieval flow

```
user query
    → embedding_provider.embed([query])          (Ollama)
    → PostgreSQL: ORDER BY embedding <=> query_vector LIMIT top_k   (pgvector cosine distance)
    → similarity = 1 - distance; keep chunks with similarity >= RETRIEVAL_SIMILARITY_THRESHOLD
    → if none clear the threshold: Postgres full-text keyword fallback (ts_rank_cd / plainto_tsquery)
    → return RetrievedChunk[] (chunk_id, document_id, title, episode, source_url, content, score, method)
```

On any non-PostgreSQL SQLAlchemy bind (only true in the test suite), the same function transparently falls back to a pure-Python cosine-similarity scan and a substring-based keyword scorer — see `backend/app/retrieval/retriever.py`'s module docstring. Production always takes the pgvector path.

## Agent routing

```
user message
    → router.classify_intent(message)   -- deterministic regex/keyword classifier, 4 outcomes:
         SHIP30 | HTML_ARTIFACT | MARKDOWN_ARTIFACT | GROUNDED_QA
    → search_transcripts(message)       -- ALWAYS runs first, regardless of intent
    → dispatch:
         SHIP30            → skills/ship30/writer.generate_ship30 (2-stage: outline → essay)
         HTML_ARTIFACT     → tools.generate_html_artifact_tool → sanitizer.sanitize_html
         MARKDOWN_ARTIFACT → tools.generate_markdown_artifact_tool → markdown.validate_markdown
         GROUNDED_QA       → tools.answer_from_sources
    → AgentTurnResult (content, sources, abstained, artifact_type/content, latencies)
```

**Why not the Claude Agent SDK's native tool-use loop, or Ollama's function calling:** the assignment requires the *same* agent behavior on both a mandatory local Ollama model and an optional Anthropic model. Ollama's function-calling support varies significantly by model and is not reliable enough to be the *only* routing mechanism; building routing on top of it would make behavior provider-dependent in exactly the dimension that's supposed to be swappable. The chosen design keeps the "explicit skill/tool boundary" the assignment asks for (each capability is a distinct, independently unit-tested Python function) while making routing itself deterministic and provider-agnostic. This is a documented trade-off (see `agent-transcripts/004-agent-routing.md` and PRD.md "Trade-offs"), not an oversight — a request phrased very differently from `agents/router.py`'s patterns could be misrouted, which is the main risk it accepts.

## Model / provider switching

`LLM_PROVIDER=ollama|anthropic` (env var, no code change) selects the chat provider via `providers/factory.py`. Both implement the same `LLMProvider` ABC (`providers/base.py`): `chat()`, `stream_chat()`, `is_available()`, `.model`. Embeddings are provided by a separate `EmbeddingProvider` interface that is **always** backed by Ollama, regardless of `LLM_PROVIDER` — Anthropic has no embeddings endpoint, so this isn't a configurable choice, it's a hard architectural fact, documented in the factory module and surfaced in README/PRD so it doesn't read as a bug.

The frontend's `ProviderBadge` component reads `GET /api/config` and renders "Local · Ollama · <model>" or "Cloud · Anthropic · <model>" with a health-colored dot, so the active provider is always visible, not just configured.

## Security model

**Prompt-injection / untrusted transcript content:** every generation prompt that includes retrieved transcript text explicitly instructs the model that the excerpts are untrusted data, not instructions, and to ignore any instruction-like text found inside them (`agents/tools.py::_GROUNDED_QA_SYSTEM_PROMPT` and the Ship 30 / artifact prompts). This is a prompt-level mitigation, not a hard technical guarantee (see PRD.md "Risks").

**Artifact rendering (the assignment's explicit "Security expectation"):** two independent layers.
1. *Server-side sanitization* (`skills/artifacts/sanitizer.py`): a regex pre-pass removes `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>` **and their inner content** (bleach alone strips the tag but keeps inner text — see `agent-transcripts/006-artifact-security.md` for the bug this caught), then `bleach.clean()` enforces an explicit tag/attribute/protocol allow-list (structural + text tags, inline `<style>`, `http(s)`/`mailto` links and images only, no event-handler attributes, no `javascript:` URLs).
2. *Client-side isolation* (`frontend/components/ArtifactViewer.tsx`): the sanitized HTML is rendered inside `<iframe sandbox="">` — an **empty** sandbox attribute, the most restrictive setting available. This unconditionally disables script execution, form submission, top-level navigation, popups, and same-origin access (no access to cookies/localStorage/parent DOM), independent of whatever layer 1 did. `allow-scripts`/`allow-same-origin` are deliberately never added — generated artifacts never need to execute JavaScript.

Markdown artifacts get a parallel, independent guarantee: `react-markdown` is used without the `rehype-raw` plugin, so any raw HTML embedded in markdown text is rendered as literal escaped text, never parsed as markup. There is no `dangerouslySetInnerHTML` anywhere in the frontend.

**Secrets:** never logged (see `core/logging.py`'s `_REDACT_KEYS` processor), never returned by `/api/config` (verified by `test_config_endpoint_exposes_provider_without_secrets`), never committed (`.env` git-ignored, `.env.example` has empty defaults for secrets).

## Deployment topology

`docker-compose.yml` defines four services: `postgres` (`pgvector/pgvector:pg16`, healthchecked), `ollama` (official image, healthchecked, model pull is a separate one-time step since baking an 8B model into the image would bloat it enormously), `backend` (runs `alembic upgrade head` then `uvicorn` on container start, depends on both healthchecks), `frontend` (Next.js standalone build). The host's `./data` directory is bind-mounted to the *container filesystem root's* `/data` (not `/app/data`) — this is intentional: `Settings.transcripts_dir`'s default is computed as "3 parents up from `config.py`'s own file location," which resolves to the repo root when running from source and to the container filesystem root when running in Docker (since only `backend/`'s contents are copied to `/app`), so the exact same code path works in both environments with zero special-casing (see `backend/app/core/config.py::_default_transcripts_dir`'s docstring).

## Failure handling

Every dependency failure mode named in the assignment (§19) maps to a specific, tested behavior:

| Failure | Behavior |
|---|---|
| Ollama unreachable | `httpx.ConnectError` caught in `agents/agent.py::guard_retrieval`/`guard_generation`, re-raised as `RetrievalError`/`ModelFailureError` with an actionable detail ("Cannot reach Ollama. Make sure it's running..."); `/health` reports it separately from database health |
| Ollama model not pulled | `OllamaProvider.is_available()` inspects `/api/tags` and returns a specific "model not pulled, run: ollama pull ..." message |
| Model timeout | `httpx.TimeoutException` caught the same way, distinct detail message mentioning the timeout |
| Anthropic key missing/invalid | `AnthropicProvider.is_available()` reports it without raising; a chat attempt with an invalid key raises `anthropic.AuthenticationError`, translated to `ProviderUnavailableError` with a message suggesting switching back to `LLM_PROVIDER=ollama` |
| Empty retrieval | `answer_from_sources` returns the fixed abstention message rather than calling the model at all; Ship 30 raises `InsufficientEvidenceError` before generating anything |
| Database unavailable | `services/health_service.check_database` catches and reports `healthy: false` with the exception text truncated to 200 chars; SQLAlchemy errors elsewhere surface as 500s with a logged (not client-facing) traceback |
| Artifact sanitization failure (oversized payload, dangerous pattern surviving cleaning) | `ArtifactSanitizationError` → 422 with a specific detail, never a silent pass-through |
| Ingestion failure (bad file, embedding call fails mid-run) | Per-file try/except in `ingestion/pipeline.py`; the run continues for remaining files and reports errors in the response body rather than aborting the whole batch |

This translation logic is centralized in two small guard functions (`guard_retrieval`, `guard_generation` in `agents/agent.py`) applied at both call sites that hit a provider (chat message turns and on-demand artifact generation) — found and fixed via manual smoke-testing during development (see `agent-transcripts/005-ollama.md`); pinned as a regression test in `tests/test_resilience.py`.

## Testing strategy

83 backend tests run against in-memory SQLite via the cross-dialect model shim described above — zero external dependencies required to run `pytest`. This covers the full service/API/agent/retrieval/ingestion/security logic. What it does *not* cover: the real pgvector `ivfflat` index's actual ANN behavior at scale, and real model output quality — both require the real Docker stack (`eval/run_eval.py` is the tool for the latter). Frontend: Vitest component tests + `tsc --noEmit` + a production `next build`.
