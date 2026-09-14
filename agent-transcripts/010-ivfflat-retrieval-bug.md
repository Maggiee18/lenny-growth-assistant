# 010 — A real retrieval-correctness bug: under-tuned ivfflat index

**Found via:** running the eval harness (`eval/run_eval.py`) for the first time against the live stack. `q1-product-strong` ("What do guests say makes onboarding effective?") returned `abstained: true, source_count: 0` in 1.8 seconds -- fast enough that no LLM call happened at all, meaning retrieval itself found nothing, not that the model declined to answer.

This was surprising: the synthetic sample dataset has an entire episode about activation/onboarding (`ep01-activation.json`), and a nearly identical live question about "improving activation" had worked fine earlier in the session with real cited sources. Rather than assume it was just an unlucky relevance-threshold miss and move on, investigated directly.

## Diagnosis

Confirmed the document existed (`SELECT title FROM transcript_documents WHERE source_url LIKE '%example.com%'` showed all 5 synthetic episodes present). Then reproduced the zero-result retrieval directly against the live container:

```python
[vec] = await emb.embed(["What do guests say makes onboarding effective?"])
results = await _vector_search_postgres(db, vec, 10)
# -> 0 results, reproducibly
```

A different query ("What do guests say about product-market fit?") returned 10 results with sensible scores through the exact same function. Ruled out, in order: an exception being silently swallowed (added explicit `traceback.print_exc()`, none raised), a malformed embedding (checked for NaN/Inf, none, values looked normal), a stale/wrong DB connection (basic `SELECT count(*)` in the same script context correctly saw all 1,455 chunks), and a zero-norm stored vector (`vector_norm(embedding) = 0` matched zero rows).

The real cause, found by comparing a plain `LIMIT 3` (no `ORDER BY`) query -- which returned real distances immediately -- against the actual `ORDER BY` query -- which returned nothing: `EXPLAIN` showed the query planner using `ix_transcript_chunks_embedding`, an `ivfflat` index built with `lists = 100` (from the original migration, chosen without thinking hard about it at the time) against a table with only ~1,455 rows. IVFFlat is an *approximate* nearest-neighbor index: it partitions vectors into `lists` clusters and, by default, only probes 1 cluster per query (`probes = 1`). With 100 clusters carved out of 1,455 rows (~14.5 rows/cluster on average, uneven after k-means), some clusters end up nearly or entirely empty. When a query vector's nearest centroid happens to be one of those sparse/empty clusters, the search returns very few or literally zero candidate rows *before* `LIMIT` ever applies -- this is not a relevance-threshold miss, it's the index approximating so aggressively that it skips the actual best-matching rows entirely.

pgvector's own sizing guidance is roughly `lists ≈ rows / 1000` for typical workloads. 100 lists for ~1,500 rows is roughly 65x over-provisioned for this dataset size.

## Fix

Added `alembic/versions/0002_drop_undertuned_ivfflat_index.py`, which drops the index outright. At this project's stated expected scale (PRD.md: "tens to low hundreds of episodes, thousands of chunks"), an exact sequential cosine-distance scan is both fast enough (confirmed: still sub-second including the embedding call) and, more importantly, *cannot* have this failure mode -- there is no approximation to get unlucky with. This is a direct application of the assignment's own stated retrieval priority: "accuracy > explainability > complexity" -- the fancy approximate index was actively hurting the #1 priority (accuracy) to buy speed the dataset doesn't need at this size. If the corpus eventually grows past roughly 100K+ chunks, a properly-tuned `ivfflat` (`lists = rows/1000`, and/or a higher `probes` value) or an `HNSW` index should be reconsidered then -- documented as a forward-looking note in `architecture.md`, not implemented now, since building for a scale the project doesn't have would itself be over-engineering.

**Verified:** re-ran the exact failing query after applying the migration -- 10 results returned, all with sensible relevance scores (0.60-0.64), all well above the 0.55 similarity threshold. Full backend test suite (89 tests) still green (SQLite never exercises this Postgres-index-specific code path either way, which is itself worth noting: this class of bug is *only* catchable by testing against real Postgres with a realistically-sized dataset -- exactly the value of the live end-to-end testing this session did).
