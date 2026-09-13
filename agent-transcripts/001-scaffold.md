# 001 — Scaffold & requirements pass

**Goal:** turn the take-home brief into an explicit requirements checklist and repo skeleton before writing application code.

## What was done

- Read the assignment doc (`Forward_Deployed_Engineer_Take_Home_Assignment.docx`) in full via `python-docx` (the file couldn't be read as plain text — Claude Code's `Read` tool rejects binary `.docx`).
- Audited the dev environment before assuming any tooling was available:
  - `docker`, `wsl`, `ollama`, `psql` — **none installed** on this Windows machine.
  - Python 3.10.11 and Node 24 — available.
  - Network egress to PyPI/npm/GitHub — available.
- This changes what "verify everything" (assignment §31) can mean *in this session*: Docker Compose / real Postgres+pgvector / real Ollama inference cannot be executed here. Decision: build the full Docker stack correctly for an evaluator machine that *does* have these tools, and verify everything else exhaustively in-sandbox (unit/integration tests, a real running FastAPI process against SQLite, frontend build/typecheck/tests). This trade-off is documented in README.md "Known limitations."
- Chose not to install Docker/Ollama into this environment myself — that's a system-level change outside a take-home assignment's scope and outside what should happen without the user driving it.

## Requirements checklist (condensed)

Extracted every explicit requirement from the assignment into categories: API/sessions/persistence, provider abstraction, knowledge base/ingestion, grounded QA, Ship 30 skill, artifacts + viewer + security, deployment/ops, tests, eval harness, docs (README/PRD/architecture/design), agent transcripts, demo video. Tracked against implementation throughout; see the final evaluator checklist in the session's closing summary for the completed mapping.

## Key ambiguity resolved: transcript data source

The brief says "use the transcripts from Lenny's Podcast / Newsletter transcript repository" without a URL. Rather than guessing, searched for it (see `003-rag.md`) instead of fabricating a synthetic dataset outright.
