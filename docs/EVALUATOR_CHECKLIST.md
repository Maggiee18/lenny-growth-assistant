# Evaluator checklist

Every assignment requirement, mapped to where it's implemented. Section numbers refer to the take-home assignment.

## §3.1 API, sessions, persistence

| Requirement | Where |
|---|---|
| FastAPI backend | [backend/app/main.py](../backend/app/main.py) |
| Agent layer (Claude Agent SDK or Pi Coding Agent) | Custom provider-agnostic agent instead — see [architecture.md § Agent routing](../architecture.md#agent-routing) for the explicit trade-off rationale |
| New chat / independent session context | `POST /api/sessions`, [backend/app/services/session_service.py](../backend/app/services/session_service.py); isolation verified in [test_sessions.py::test_sessions_are_isolated_from_each_other](../backend/tests/test_sessions.py) |
| Persistence in PostgreSQL (sessions, timestamps, user metadata) | [backend/app/db/models.py](../backend/app/db/models.py), migration [0001_initial_schema.py](../backend/alembic/versions/0001_initial_schema.py) |
| Clear request/response contracts, validation, structured errors, health endpoints | [backend/app/schemas/](../backend/app/schemas/), [backend/app/core/errors.py](../backend/app/core/errors.py), `GET /health` |

## §3.2 Flexible LLM configuration

| Requirement | Where |
|---|---|
| Config-only provider switch | `LLM_PROVIDER` env var, [backend/app/providers/factory.py](../backend/app/providers/factory.py) |
| Cloud provider (Anthropic) | [backend/app/providers/anthropic_provider.py](../backend/app/providers/anthropic_provider.py) |
| Local provider (Ollama), mandatory demo path | [backend/app/providers/ollama_provider.py](../backend/app/providers/ollama_provider.py) |
| Provider visible in UI | [frontend/components/ProviderBadge.tsx](../frontend/components/ProviderBadge.tsx), reads `GET /api/config` |
| Documented fallback behavior | [README.md § Cloud model setup](../README.md#cloud-model-setup-anthropic) |

## §3.3 Knowledge base

| Requirement | Where |
|---|---|
| Real transcript data source identified and used | `LennysNewsletter/lennys-newsletterpodcastdata`; [scripts/fetch_lennys_transcripts.py](../scripts/fetch_lennys_transcripts.py); rationale in [agent-transcripts/003-rag.md](../agent-transcripts/003-rag.md) |
| Ingestion explained (load/chunk/index/refresh/trace) | [architecture.md § Ingestion flow](../architecture.md#ingestion-flow), [data/transcripts/README.md](../data/transcripts/README.md) |
| Grounding cites relevant transcript/source | `SourceCitation` schema, source cards in [frontend/components/SourceCard.tsx](../frontend/components/SourceCard.tsx) |

## §4.1 Grounded conversational assistant

| Requirement | Where |
|---|---|
| RAG over transcripts only | [backend/app/agents/tools.py::answer_from_sources](../backend/app/agents/tools.py) |
| Follow-up questions / session context | `_load_history` in [message_service.py](../backend/app/services/message_service.py); tested in `test_followup_question_has_prior_turn_in_history` |
| Abstains when unsupported | `ABSTENTION_MESSAGE`; tested in [test_grounding.py](../backend/tests/test_grounding.py), [test_messages.py](../backend/tests/test_messages.py) |

## §4.2 Ship 30 for 30 skill

| Requirement | Where |
|---|---|
| Dedicated skill, not a one-off prompt | [backend/app/skills/ship30/](../backend/app/skills/ship30/) — `skill.md`, `schema.py`, `writer.py`, `validator.py` |
| ~1,250 words, hook, headings/bullets/bold, grounded, takeaway | Encoded in `writer.py`'s two-stage prompt + `validator.py`'s structural checks; tested in [test_ship30.py](../backend/tests/test_ship30.py) |

## §4.3 Artifacts + viewer + security

| Requirement | Where |
|---|---|
| Markdown + HTML/CSS generation | [backend/app/skills/artifacts/](../backend/app/skills/artifacts/) |
| In-app artifact viewer beside chat | [frontend/components/ArtifactViewer.tsx](../frontend/components/ArtifactViewer.tsx) |
| Untrusted HTML — sanitization + isolation explained | [design.md § Artifact viewer security](../design.md#artifact-viewer-security-design-rationale), [architecture.md § Security model](../architecture.md#security-model); bug found/fixed in [agent-transcripts/006-artifact-security.md](../agent-transcripts/006-artifact-security.md) |

## §5 Deployment & operational readiness

| Requirement | Where |
|---|---|
| One-command startup | `docker compose up --build`, [docker-compose.yml](../docker-compose.yml) |
| `.env.example` with safe defaults, no secrets | [.env.example](../.env.example), [frontend/.env.example](../frontend/.env.example) |
| Structured logs | [backend/app/core/logging.py](../backend/app/core/logging.py) (JSON, request-id/session-id context, secret redaction) |
| Resilience: missing keys, Ollama down, timeouts, empty retrieval, DB down | [architecture.md § Failure handling](../architecture.md#failure-handling); regression tests in [test_resilience.py](../backend/tests/test_resilience.py) |
| Handoff docs | This checklist + README/architecture/design |

## §6 Required deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Public GitHub repository | Pushed: [github.com/Maggiee18/lenny-growth-assistant](https://github.com/Maggiee18/lenny-growth-assistant) |
| 2 | README.md | [README.md](../README.md) |
| 3 | PRD | [PRD.md](../PRD.md) |
| 4 | design.md | [design.md](../design.md) |
| 5 | architecture.md | [architecture.md](../architecture.md) |
| 6 | Agent transcripts | [agent-transcripts/](../agent-transcripts/) (9 logs, failures included — including a full live Docker/Ollama debugging session in `009-live-docker-verification.md`) |
| 7 | Tests + manual UI test plan | [backend/tests/](../backend/tests/) (85 tests), [frontend/tests/](../frontend/tests/) (11 tests), [design.md § Manual UI test plan](../design.md#manual-ui-test-plan) |
| 8 | Demo video | **Not recorded** — script provided in [docs/DEMO_SCRIPT.md](DEMO_SCRIPT.md); recording requires a camera, which this session cannot do on your behalf |

## What has and hasn't been executed (be precise about this)

**Executed and verified live, for real, on the real stack:** `docker compose up --build` (all 4 services healthy), real Postgres+pgvector (the Alembic migration ran against it and real `cosine_distance` vector queries executed), real Ollama (`llama3.1:8b` + `nomic-embed-text` pulled and used), real ingestion (26 documents / 1,455 chunks, zero errors, from the actual official Lenny's Newsletter transcript repo), a real grounded Q&A turn citing 3 real episodes with real excerpts, a real follow-up question preserving session context, and a real Ship 30 essay landing inside the target word-count band after live iteration. This live run found and fixed 5 real bugs the SQLite test suite couldn't catch — full account in `agent-transcripts/009-live-docker-verification.md`. Also: all 85 backend tests (SQLite), frontend `tsc`/Vitest/`next build`.

**Not executed this session:** the full `eval/run_eval.py` 9-category harness against real inference (only 2 ad-hoc live questions plus 3 Ship 30 attempts were run manually — a full harness pass would give a more complete picture); real Anthropic/cloud provider output (only Ollama was tested live, `ANTHROPIC_API_KEY` was left unset); the demo video recording. **One real, unresolved caveat from the live run**: a Ship 30 continuation pass was observed introducing one ungrounded anecdote before the prompt was tightened to forbid it — that fix was deployed but not re-verified with a fourth live generation. See README § Known limitations and PRD.md § Risks for the honest framing.
