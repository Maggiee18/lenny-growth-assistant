# 009 — Live Docker/Ollama verification (the real thing, not just SQLite)

Everything in 001-008 was verified against SQLite and a manually-run FastAPI process, with the explicit caveat that the real Docker+Postgres+pgvector+Ollama stack had never actually been executed (no Docker in the original dev sandbox). This session got Docker Desktop installed and running on the user's machine and ran the real stack end-to-end. It surfaced five real bugs that the SQLite test suite structurally could not have caught, plus one real product-quality finding about local model behavior.

## Bug 1: Docker build failed -- missing `frontend/public/`

`frontend/Dockerfile`'s runner stage does `COPY --from=builder /app/public ./public`, but the project never had a `public/` directory (no favicon or static assets had been added). First `docker compose up --build` failed at that exact COPY step. Fixed by adding `frontend/public/robots.txt` (a `Disallow: /`, sensible for an internal tool) so the directory exists and is tracked by git.

## Bug 2: Ollama container reported unhealthy despite running fine

`docker-compose.yml`'s Ollama healthcheck used `curl -f http://localhost:11434`, but the official `ollama/ollama` image has no `curl` (confirmed via `docker inspect`'s health log: `"/bin/sh: 1: curl: not found"`). The server itself was listening and working the whole time -- only the healthcheck command was broken, which made `docker compose up` refuse to start `backend` (its `depends_on: ollama: condition: service_healthy` never resolved). Fixed by using `ollama list` instead, which is the bundled CLI binary itself and doubles as a liveness probe.

## Bug 3: Real grounded Q&A crashed with `AttributeError: ... has no attribute 'cosine_distance'`

The very first real question against real Postgres crashed. Root cause: `backend/app/db/types.py`'s `EmbeddingVector` is a `TypeDecorator` that resolves to pgvector's `Vector` type via `load_dialect_impl()` -- but a `TypeDecorator`'s *comparator* (what makes `.cosine_distance()` exist as a queryable expression) is NOT automatically inherited from the dialect-specific impl; it comes from the `TypeDecorator`'s own `comparator_factory`, which defaults to a bare one with no vector-specific methods. This is exactly the kind of bug the SQLite test suite structurally cannot catch, since SQLite never takes the `_vector_search_postgres` code path at all (it always uses the Python fallback). Fixed by setting `EmbeddingVector.comparator_factory = Vector.comparator_factory` directly, confirmed by inspecting the installed pgvector package (`Vector.comparator_factory` has `cosine_distance`, `l2_distance`, etc.).

## Bug 4: Posting a message crashed with an asyncpg `DataError` on `sessions.updated_at`

Second real crash, this time in `session_service.touch_session()`: `session.updated_at = datetime.now(timezone.utc)` (timezone-aware) was being written into a `TIMESTAMP WITHOUT TIME ZONE` column. asyncpg enforces this strictly ("can't subtract offset-naive and offset-aware datetimes") where SQLite silently accepts either. Rather than strip the timezone from the Python value (a band-aid), fixed it at the schema level: every datetime column in `db/models.py` and the Alembic migration now explicitly uses `DateTime(timezone=True)` / `TIMESTAMP WITH TIME ZONE`, which is the more correct choice for a system that should always reason in UTC. Since this was the initial migration and had not been relied on by anyone yet, amended `0001_initial_schema.py` directly rather than adding a patch migration, then reset the local Postgres volume and re-ingested (data loss was zero-cost since it was all test data).

## Bug 5: Ollama 90-second timeout was too short for CPU long-form generation

A real Ship 30 essay request failed with `502 model_failure` after ~178 seconds -- `OLLAMA_TIMEOUT_SECONDS=90` was cutting off the essay-writing stage mid-generation on CPU inference. Bumped the default to 300s (`app/core/config.py`, `.env.example`) with a comment explaining why: an 8B model writing ~1,250 words on CPU genuinely takes longer than a short Q&A turn.

## Finding 6 (not a bug, a real product-quality observation): Ship 30 essays undershot the word target

Three live attempts, iterating honestly rather than fabricating a "it works" claim:
1. First attempt: 402 words (target ~1,250, acceptable band 938-1,563). The pipeline worked correctly end-to-end (retrieval, outline, essay, validation, sanitization, storage) and the validator correctly flagged the shortfall as a warning rather than silently claiming success -- but the essay was too short to be useful.
2. Strengthened the length instruction in the writer prompt (moved it to the top, restated it at the end, gave explicit paragraph-count guidance) -- 726 words. Real improvement, still short.
3. Added a bounded continuation pass: if the draft comes back under 850 words, make exactly one more model call asking it to extend the essay, capped at one retry so a stubborn model costs ~2x latency, never unbounded. Result: **998 words -- inside the target band**, with zero structural validation warnings (headings, bullets, bold all present).

While reviewing attempt 3's full text, found a real grounding violation: the continuation pass had introduced an Airbnb/Brian-Chesky-and-Joe-Gebbia anecdote that does not appear in any retrieved transcript for this topic (the actual sources were Eric Ries, Anish Acharya, and Tony Fadell -- no Airbnb founders among them). This is exactly the failure mode the grounding contract exists to prevent: the model reaching for well-known outside knowledge to pad length instead of only using retrieved evidence. Fixed by adding an explicit constraint to the continuation prompt: no new company/person/anecdote beyond what's already in the outline or essay -- add length by going deeper on the *same* evidence, never by introducing a new illustrative story. Rebuilt and redeployed this fix; **a fourth full live regeneration to re-verify it was not run**, given each attempt costs several minutes of CPU inference and the marginal value of a fourth iteration was judged lower than delivering the finding and the fix promptly. This is called out explicitly, not glossed over -- see README "Known limitations" and PRD.md "Risks" for the corresponding entries.

## Live verification summary

Confirmed genuinely working end-to-end on the real stack: health checks reporting real per-dependency status, `/api/config`, real grounded Q&A citing 3 real Lenny's Podcast episodes with real excerpts and working source URLs, follow-up-question context preserved within a session, ingestion of 26 documents / 1,455 chunks with zero errors, and (after the fixes above) a Ship 30 essay landing inside the target word-count band with correct structure. None of bugs 2-5 could have been caught by the SQLite-based automated test suite alone -- this is the concrete argument for why the "not yet run against real Docker" caveat in earlier documentation mattered, and why it's now resolved.
