# The Lenny Growth Assistant

A full-stack, grounded conversational assistant over Lenny's Podcast / Newsletter transcripts. Ask product and growth questions, get answers with cited transcript sources, generate a Ship 30 for 30-style essay, and produce Markdown or HTML artifacts that render live next to the chat.

Built for a Forward Deployed Engineer take-home assignment — see [PRD.md](PRD.md), [architecture.md](architecture.md), and [design.md](design.md) for the discovery brief, system design, and UX rationale. For evaluators: [docs/EVALUATOR_CHECKLIST.md](docs/EVALUATOR_CHECKLIST.md) maps every requirement to its implementation; [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) and [docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md) cover the demo video and submission steps.

## Contents

- [Architecture overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Quickstart (Docker Compose)](#quickstart-docker-compose)
- [Environment variables](#environment-variables)
- [Local (non-Docker) setup](#local-non-docker-setup)
- [Cloud model setup (Anthropic)](#cloud-model-setup-anthropic)
- [Transcript ingestion](#transcript-ingestion)
- [Running tests](#running-tests)
- [Evaluation harness](#evaluation-harness)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)
- [Known limitations](#known-limitations)

## Architecture overview

```
frontend/   Next.js 14 + TypeScript + Tailwind — chat UI, artifact viewer
backend/    FastAPI + SQLAlchemy (async) — API, agent, retrieval, skills
  app/
    agents/     PodcastAgent orchestrator + deterministic intent router + tools
    api/        FastAPI routers (health, sessions, messages, artifacts, ingestion)
    core/       config, structured logging, error taxonomy
    db/         SQLAlchemy models + cross-dialect type shims
    ingestion/  transcript loading, normalization, chunking, pipeline
    providers/  LLMProvider abstraction: OllamaProvider / AnthropicProvider
    retrieval/  pgvector similarity search + keyword fallback
    skills/     ship30/ (essay pipeline), artifacts/ (markdown + HTML sanitizer)
    services/   session/message/artifact/health orchestration used by routes
  alembic/    DB migrations (Postgres + pgvector)
  tests/      pytest suite (83 tests, runs on in-memory SQLite, no Docker needed)
data/transcripts/   transcript sources (see its own README) — not committed for real data
eval/       eval/questions.json + run_eval.py evaluation harness
agent-transcripts/  engineering logs of AI-assisted development, including failures/fixes
docs: PRD.md, architecture.md, design.md
```

Full detail — DB schema, API contract, ingestion/retrieval flow, agent routing, security model, deployment topology — is in [architecture.md](architecture.md).

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Compose v2) — recommended path
- Or, for a non-Docker local setup: Python 3.11+, Node 20+, PostgreSQL 16 with the `pgvector` extension, and [Ollama](https://ollama.com) installed natively
- ~8GB free RAM if running an 8B Ollama model locally

## Quickstart (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres (with `pgvector` pre-installed via the `pgvector/pgvector:pg16` image), Ollama, the FastAPI backend (runs Alembic migrations automatically on boot), and the Next.js frontend.

Then, in a second terminal, pull the models and ingest transcripts:

```bash
# 1. Pull the local models (one-time, ~5GB download for llama3.1:8b)
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull nomic-embed-text

# 2. Get some transcripts to ingest (see "Transcript ingestion" below)
python scripts/fetch_lennys_transcripts.py --limit 20

# 3. Ingest them
curl -X POST http://localhost:8000/api/ingestion/run -H "Content-Type: application/json" -d '{}'
```

Open **http://localhost:3000**. The provider badge in the header should read "Local · Ollama · llama3.1:8b".

To stop: `docker compose down` (add `-v` to also delete the Postgres/Ollama volumes).

## Environment variables

See [`.env.example`](.env.example) for the full, commented list with safe defaults. Summary:

**Required**
| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async Postgres URL the app connects with |
| `SYNC_DATABASE_URL` | Sync Postgres URL Alembic migrations use |
| `LLM_PROVIDER` | `ollama` (default) or `anthropic` |

**Local model (Ollama) — required for the default demo path**
| Variable | Default |
|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` (Docker) / `http://localhost:11434` (local) |
| `OLLAMA_CHAT_MODEL` | `llama3.1:8b` |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` |

**Cloud model (Anthropic) — optional**
| Variable | Default |
|---|---|
| `ANTHROPIC_API_KEY` | empty — app runs fully on Ollama without it |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` |

**Optional (retrieval/artifacts tuning)**: `RETRIEVAL_TOP_K`, `RETRIEVAL_SIMILARITY_THRESHOLD`, `EMBEDDING_DIMENSIONS`, `CHUNK_TARGET_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `ARTIFACT_MAX_HTML_BYTES`.

Never commit a real `.env` — it's git-ignored. No secret is ever logged (see `core/logging.py`'s redaction of `*_key`/`token`/`password`/`secret` fields).

## Local (non-Docker) setup

Requires a native PostgreSQL 16 with `pgvector` installed, and Ollama running locally.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example .env   # edit DATABASE_URL etc. to point at your local Postgres
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Cloud model setup (Anthropic)

1. Get an API key from the [Anthropic Console](https://console.anthropic.com/).
2. Set `ANTHROPIC_API_KEY=sk-...` and `LLM_PROVIDER=anthropic` in `.env`.
3. Restart the backend (`docker compose up -d --build backend` or re-run `uvicorn`).
4. The provider badge should now read "Cloud · Anthropic · claude-sonnet-5". `GET /api/config` reports `anthropic_configured`; `GET /health` reports whether the key actually authenticates.

**Fallback behavior**: embeddings always use Ollama regardless of `LLM_PROVIDER` (Anthropic has no embeddings API) — Ollama must be running for ingestion and retrieval either way. If `ANTHROPIC_API_KEY` is missing while `LLM_PROVIDER=anthropic`, `/health` reports the anthropic dependency as unhealthy with a clear detail message rather than crashing the app; chat requests return a structured `503 provider_unavailable` error until the key is set or the provider is switched back to `ollama`.

## Transcript ingestion

See [`data/transcripts/README.md`](data/transcripts/README.md) for full detail. Short version:

```bash
# Real data: official Lenny's Newsletter "starter pack" (50 real episodes, free tier)
python scripts/fetch_lennys_transcripts.py --limit 20   # downloads into data/transcripts/lennys_podcast/ (git-ignored)

# Then ingest whatever is in data/transcripts/ (both the real ones above and the
# bundled 5-episode synthetic fallback dataset get picked up automatically)
python backend/scripts/ingest.py
# or, with the API running:
curl -X POST http://localhost:8000/api/ingestion/run -H "Content-Type: application/json" -d '{}'
```

Re-running ingestion is always safe — documents are deduped by content hash.

## Running tests

```bash
# Backend (83 tests, runs on in-memory SQLite -- no Postgres/Docker needed)
cd backend
pip install -r requirements.txt
pytest -q                              # or: pytest --cov=app --cov-report=term-missing

# Frontend
cd frontend
npm install
npm run typecheck
npm test
npm run build
```

A manual UI test plan (states, accessibility, responsive behavior) is in [design.md](design.md#manual-ui-test-plan).

## Evaluation harness

```bash
# with the full stack running (docker compose up) and transcripts ingested:
python eval/run_eval.py --base-url http://localhost:8000
```

Runs the 9 categories in `eval/questions.json` (strong-evidence questions, a follow-up, a multi-source question, a poorly-supported question, a fully unsupported question, and one request each for Ship 30 / Markdown / HTML artifacts) and reports retrieval hit rate, source-citation presence, abstention correctness, and artifact generation success. See PRD.md "Success metrics" for target vs. measured framing.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `/health` shows `"ollama": {"healthy": false}` | Ollama isn't running, or the model isn't pulled. Run `ollama serve` and `ollama pull llama3.1:8b`. |
| Chat requests return `503 retrieval_failure` | Embedding provider (always Ollama) is unreachable — same fix as above, and confirm `ollama pull nomic-embed-text`. |
| Chat requests return `502 model_failure` | The chat provider (Ollama or Anthropic) is reachable but errored/timed out — check `OLLAMA_TIMEOUT_SECONDS` / model size vs. available RAM, or Anthropic API status. |
| Every question gets abstained | No transcripts ingested yet — run the ingestion step above, and confirm `POST /api/ingestion/run` reports `documents_ingested > 0`. |
| `alembic upgrade head` fails with "extension vector does not exist" | You're pointing at a plain `postgres` image instead of `pgvector/pgvector:pg16` — check `DATABASE_URL`'s host/port. |
| Frontend shows "Could not reach the backend" | Check `NEXT_PUBLIC_API_BASE_URL` matches where the backend is actually listening, and that CORS (`API_CORS_ORIGINS`) includes the frontend's origin. |

## Security notes

Generated HTML is treated as untrusted end-to-end: server-side sanitization (`bleach`, explicit allow-list, script/iframe/object/embed/form stripped with their content) plus client-side rendering inside a `<iframe sandbox="">` with an **empty** sandbox value (no scripts, no forms, no same-origin access, no top navigation). Markdown artifacts render via `react-markdown` with no raw-HTML plugin, so embedded HTML in markdown is always literal text, never executed markup. Full detail, including what's explicitly allowed/blocked and why, is in [design.md](design.md#artifact-viewer-security) and [architecture.md](architecture.md#security-model).

Retrieved transcript content is treated as untrusted data by every prompt — system prompts explicitly instruct the model to ignore instruction-like text inside transcript excerpts (a prompt-injection mitigation, not a hard guarantee; see PRD.md "Risks").

## Known limitations

- **Docker/Postgres/Ollama were not available in the development sandbox used to build this** (no admin rights to install system software). The full Docker Compose stack, Alembic migration DDL, and pgvector queries were written and reviewed carefully but could not be executed end-to-end in that environment — they were validated by: (a) an 83-test pytest suite running the same ORM models and service layer against SQLite via a documented cross-dialect shim, (b) manually running the real FastAPI app with `uvicorn` against a real (file-based) SQLite database and exercising every endpoint with `curl`, and (c) `npm run build`/`vitest`/`tsc` for the frontend. **Before relying on this for a real evaluation, run `docker compose up --build` on a machine with Docker/Ollama installed** — this is the intended, documented path and is expected to work, but it has not been executed by the author of this session.
- Tool routing is a deterministic keyword/pattern classifier (see `architecture.md` "Agent routing"), not model-driven function calling — a deliberate trade-off for reliability and provider-parity, but it means a request phrased very differently from the patterns in `agents/router.py` could be misrouted to plain Q&A instead of artifact generation.
- No authentication — sessions are identified by UUID only, `user_id` is an optional free-text field. Fine for a local internal-tool demo; not production-ready multi-tenant auth (see PRD.md "Assumptions").
- The bundled fallback transcript dataset (`data/transcripts/sample_synthetic/`) is small (5 episodes) and synthetic — realistic retrieval quality requires running `scripts/fetch_lennys_transcripts.py` against the real dataset.
- Streaming responses are not implemented for the chat endpoint (see architecture.md "Streaming" for the trade-off); the UI shows clear loading/retrieving states instead.
- `npm audit` reports known CVEs in frontend dev-tooling (Next.js, Vite/Vitest, PostCSS) at their latest patched versions within the current major line. Most concern Next.js features this app doesn't use (Server Actions, Image Optimization routes, custom middleware) or Vitest's dev-only API/UI server. Not chased into a major-version migration (Next 15+/React 19, Vitest 3/4) given the regression risk of doing so untested under a deadline — `npm audit fix --force` is available if a maintainer wants to take that on.
