# 005 — Provider abstraction (Ollama + Anthropic)

**Goal:** `LLMProvider` interface with `OllamaProvider` and `AnthropicProvider` implementations, switchable via `LLM_PROVIDER` with no code changes.

## Design notes

- `app/providers/base.py` defines `LLMProvider` (chat + streaming) and a separate `EmbeddingProvider` interface.
- **Embeddings always use Ollama**, regardless of `LLM_PROVIDER` — Anthropic has no embeddings endpoint. This is called out explicitly in both the provider factory and `architecture.md` so it doesn't look like an oversight: choosing `LLM_PROVIDER=anthropic` switches chat generation only; ingestion/retrieval embeddings still require a local Ollama with an embedding model pulled (`nomic-embed-text` by default).
- `is_available()` on every provider returns `(bool, human_readable_detail)` rather than raising, so `/health` and `/api/config` can report actionable status ("Ollama is running but model 'llama3.1:8b' is not pulled. Run: ollama pull llama3.1:8b") instead of a stack trace.

## Failure found via manual smoke test: unhandled provider errors leaked as raw 500s

**Attempted:** ran the FastAPI app directly (`uvicorn`, SQLite backend, no Ollama running) and exercised the full session → message flow with `curl`, per assignment §31 ("actually test it").

**Failed because:** `POST /api/sessions/{id}/messages` with Ollama down returned a bare `{"error":{"category":"internal_error","message":"An unexpected error occurred."}}` with a raw `httpx.ConnectError` traceback in the server log. This directly violates §19 ("Handle ... unavailable Ollama ... gracefully. Errors shown to users should be understandable.") — the category was always `internal_error` regardless of the actual cause, which is exactly the kind of un-diagnosable failure the assignment calls out.

**Root cause:** `PodcastAgent.handle_turn()` and `create_artifact_on_demand()` called provider methods with no exception translation; FastAPI's catch-all handler turned everything into a generic 500.

**Fix:** added `guard_retrieval()` / `guard_generation()` wrappers in `app/agents/agent.py` that catch `httpx.HTTPError` and `anthropic.APIError` and re-raise as the existing `RetrievalError` / `ModelFailureError` / `ProviderUnavailableError` `AppError` subclasses, with a provider-aware, actionable `detail` string (e.g. "Cannot reach Ollama. Make sure it's running (`ollama serve`)..."). Applied at both call sites (chat turns and on-demand artifact generation).

**Verified:**
1. Added `tests/test_resilience.py` (a fake provider that always raises `httpx.ConnectError`) — pins the behavior as a regression test.
2. Re-ran the manual `curl` smoke test against the live SQLite-backed server: the same request now returns `503 {"error":{"category":"retrieval_failure","message":"Retrieval is temporarily unavailable.","detail":"Cannot reach Ollama. Make sure it's running (`ollama serve`) and reachable at OLLAMA_BASE_URL."}}` — clear, categorized, no stack trace to the client.
3. Also caught a second-order bug while fixing this: the friendly-detail matcher checked `provider_name == "ollama"` but the embedding provider's `.name` is `"ollama-embeddings"`, so the friendlier message wasn't firing for retrieval failures. Changed to a substring check (`"ollama" in provider_name`) and re-verified live.
