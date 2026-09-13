# 008 — Documentation, eval harness, and final verification

## Evaluation harness

Wrote `eval/questions.json` (9 categories per assignment §24) and `eval/run_eval.py`, which drives a live backend over HTTP and reports retrieval hit rate, source citation presence, abstention correctness, session continuity, provider routing, and artifact generation success. Smoke-tested the script's *mechanics* (not its results) against a live FastAPI process with Ollama intentionally down: confirmed it handles per-question HTTP errors without crashing the whole run, chains the follow-up question into the same session correctly, and writes a valid JSON report. Real accuracy numbers require the actual Docker+Ollama stack, which this session could not run (see `001-scaffold.md`) — the harness itself is what's being delivered and verified here, not a claimed score.

## Documentation

Wrote README.md, PRD.md, architecture.md, design.md against what was actually built — cross-checked every file path, endpoint, and schema field mentioned in the docs against the real source tree rather than writing them from the plan alone. Explicitly separated "target metric" from "measured result" in PRD.md per the assignment's instruction not to present invented numbers as real measurements.

## Alembic migration compiled offline

Ran `alembic upgrade head --sql` (offline SQL generation, no live database connection required) to catch any migration syntax errors before an evaluator hits them. It compiled cleanly to valid PostgreSQL DDL, including the `CREATE EXTENSION vector`, `JSONB` columns, and the `ivfflat` cosine-distance index — this is strong evidence the Docker Postgres path will work, though it is not a substitute for actually running it.

## Final state

- Backend: 83 pytest tests passing, 82% coverage, migration verified offline, live `curl` smoke test passed for the full session/message/artifact flow including the Ollama-down resilience fix.
- Frontend: `tsc --noEmit` clean, 11 Vitest tests passing, `next build` production build succeeds.
- Docker Compose file, both Dockerfiles, and `.env.example` written and reviewed but **not executed** in this session (no Docker in the dev sandbox) — this is the single most important caveat for an evaluator and is called out at the top of README.md's "Known limitations," not buried.
- `npm audit` / `pip` dependency check: frontend has known transitive dev-tooling CVEs (Next.js, Vite/Vitest, PostCSS) at the pinned versions bumped to the latest patch releases within their current major line; most concern Next.js features this app doesn't use (Server Actions, Image Optimization, custom middleware) or Vitest's dev-only API server. Not chased further into a major-version migration (Next 15/React 19, Vitest 3/4) given the time remaining and the regression risk of doing that untested — documented as a known limitation rather than silently left unmentioned.
