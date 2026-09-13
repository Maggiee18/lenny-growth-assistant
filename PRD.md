# PRD — The Lenny Growth Assistant

## 1. User & problem

**Primary user:** a product manager, growth practitioner, or founder inside a company that has a working relationship with (or license to) Lenny's Podcast/Newsletter content — someone who wants concrete, evidence-backed answers to product/growth questions, without personally re-listening to dozens of hours of podcast episodes or re-reading a huge newsletter archive.

**Job to be done:** "When I have a specific product or growth question (e.g. 'how should I think about pricing for a usage-based product?'), help me get a grounded answer sourced from what people who've actually done this have said — and let me turn that answer into something I can reuse (an essay, a one-pager, a shareable page) without switching tools."

**Pain removed:** manual transcript searching across dozens of episodes, losing track of which guest said what, context-switching between a podcast player/newsletter archive and a writing tool, and the risk of citing something that was never actually said (hallucination) when writing content "inspired by" the material.

## 2. Success metrics

Distinguishing **target** (what we're designing for) from **measured** (what this specific session actually observed) per the assignment's explicit ask not to present invented numbers as real measurements.

| Metric | Target | Measured (this session) |
|---|---|---|
| Grounded answer rate (non-abstained answers include >=1 cited source) | >= 90% for in-scope questions | Not measured against real Ollama inference — no Ollama available in the dev sandbox (see README "Known limitations"). Verified structurally: `answer_from_sources` always attaches every retrieved chunk as a source when it doesn't abstain (unit-tested). |
| Unsupported-answer / hallucination rate | 0% fabricated quotes/stats | Verified via the grounding system prompt + `test_grounding.py` + `test_ship30.py`'s "insufficient evidence" guard, which is a code-level enforcement (retrieval count < 2 → refuse), not a measurement of model behavior. |
| Retrieval hit rate on in-scope questions | >= 80% | `eval/run_eval.py` computes this against a live stack; not run against real inference here (no Ollama in sandbox). |
| Task completion rate (user gets a usable artifact on request) | >= 95% | Verified end-to-end for the artifact *pipeline* (routing → generation → sanitization → persistence → render) via automated tests and a live `curl` smoke test; not measured against real model output quality. |
| Time from question to grounded answer | < 15s on a mid-range laptop with an 8B Ollama model | Not measured (no local Ollama in the dev sandbox). Structurally, retrieval + generation latency are logged per-turn (`retrieval_latency_ms`, `generation_latency_ms` in message metadata) so this is measurable once deployed. |

**Operational metric this PRD commits to as the primary success signal:** *grounded answer rate* on the `eval/questions.json` harness, because it's the one metric that most directly reflects the core promise ("answers strictly from the transcripts, cite sources, abstain otherwise") and is cheap to re-run after any change to retrieval, prompts, or the knowledge base.

## 3. Assumptions

Recorded because the original brief left them open:

1. This is an **internal knowledge-assistant tool**, not a consumer product — authentication/authorization is explicitly out of scope (a `user_id` free-text field exists for future multi-tenancy but nothing enforces it).
2. **Transcript data**: the brief said "use the transcripts from Lenny's Podcast / Newsletter transcript repository" without a link. Found the official `github.com/LennysNewsletter/lennys-newsletterpodcastdata` "starter pack" repo (see `agent-transcripts/003-rag.md`) — its license permits personal, non-commercial use and "publishing projects built with it," but forbids redistributing the raw files. So: real transcripts are fetched at setup time (not committed), and a small original/fictional dataset ships in the repo as an offline fallback so the app works without network access.
3. **Ollama is the primary, mandatory demo path**; Anthropic is a fully optional, config-only alternative for chat generation. Embeddings always run on Ollama regardless (Anthropic has no embeddings API) — documented explicitly so it doesn't read as an oversight.
4. **PostgreSQL + pgvector is sufficient** for the expected dataset size (tens to low hundreds of episodes, thousands of chunks) — no need for a dedicated vector database at this scale.
5. **No fine-tuning** — grounding is achieved entirely through retrieval + prompt constraints + a code-level abstention rule, not model weights.
6. **Generated HTML is untrusted**, full stop, even though "our own" model produced it — see `architecture.md` "Security model."
7. **Tool routing is deterministic** (keyword/pattern-based), not dependent on model-native function calling, because Ollama's function-calling support is inconsistent across models and this needs to behave identically regardless of `LLM_PROVIDER` (see `architecture.md` "Agent routing" and `agent-transcripts/004-agent-routing.md`).
8. **Docker/Postgres/Ollama were unavailable in the development sandbox** used to build this (no admin rights to install system software in that environment) — the full stack is built and reviewed for a Docker-equipped evaluator machine but could only be partially executed during development (see README "Known limitations" for exactly what was and wasn't run).

## 4. Scope

**In scope:**
- Grounded conversational Q&A over ingested transcripts, with session persistence and follow-up context.
- Explicit abstention when evidence is insufficient.
- Ship 30 for 30 essay generation as a dedicated, structured skill (not a one-off prompt).
- Markdown and HTML/CSS artifact generation with a secure in-app viewer.
- Provider switching (Ollama ⟷ Anthropic) via configuration only.
- Ingestion pipeline with source traceability, deduplication, and re-ingestion support.
- Structured logging, health checks, and graceful degradation for every named dependency failure mode.
- Docker Compose one-command startup.

**Explicitly excluded (and why):**
- **Authentication/authorization** — out of scope per assumption 1; would add significant surface area without changing the core technical evaluation.
- **Streaming chat responses** — considered, but non-streaming keeps the retrieval→generation→persistence flow simpler to make reliable and testable under the deadline; the UI compensates with explicit thinking/retrieving/generating states (see design.md). Documented as a trade-off, not an oversight.
- **Hybrid hybrid re-ranking / cross-encoder re-ranking** — vector search + a keyword fallback is enough at this dataset scale; added complexity wasn't worth the reliability risk under time pressure (assignment explicitly asks to prioritize "accuracy > explainability > complexity" and to not over-engineer retrieval).
- **Multi-tenant RBAC, Kubernetes, microservices, mobile/voice, fine-tuning** — none of these are required by the assignment and would work against "boring, reliable architecture."

## 5. User flows

**Flow A — grounded Q&A:**
1. User opens the app, sees the provider badge (Local · Ollama · llama3.1:8b) and an empty state.
2. Types a product/growth question → sees a "retrieving sources / generating" indicator → gets an answer with source cards (title, episode, excerpt, relevance score, link).
3. Asks a follow-up in the same session → the agent has the prior turn in context.
4. Asks something outside the knowledge base → gets an explicit "I couldn't find enough evidence..." message, not a fabricated answer.

**Flow B — Ship 30 essay:**
1. User asks "write a Ship 30 essay about pricing strategy."
2. Agent retrieves evidence, builds a structured outline (central insight, tension, evidence, hook, takeaway), then writes a ~1,250-word essay from that outline.
3. Essay appears in the artifact panel beside the chat; user can copy, download, or view the raw Markdown source.
4. If evidence is too thin, the agent says so instead of writing an ungrounded essay.

**Flow C — artifact generation:**
1. User asks for a Markdown summary or an HTML page.
2. Agent generates content, server-side sanitization runs (HTML path), the artifact panel opens automatically showing the rendered result.
3. User can toggle rendered/source view, copy, download, or close the panel.

## 6. Acceptance criteria

- [ ] A new session can be created and appears in the sidebar; two sessions never share message history.
- [ ] A grounded question returns an answer with >=1 source card when relevant transcripts exist.
- [ ] A question with no relevant transcript content returns the exact abstention message, not a generated guess.
- [ ] A follow-up question in the same session is answered with the prior turn visible in the model's context (verified via `test_followup_question_has_prior_turn_in_history`).
- [ ] A Ship 30 request produces a Markdown artifact within the 938–1,563 word band (±25% of ~1,250) when evidence is sufficient, and an explicit refusal when it isn't.
- [ ] An HTML artifact request never results in an unsanitized `<script>`, event handler, `javascript:` URL, `<iframe>`, `<object>`, `<embed>`, or `<form>` reaching the rendered output.
- [ ] Switching `LLM_PROVIDER` between `ollama` and `anthropic` requires no code change and is visibly reflected in the UI's provider badge.
- [ ] `/health` distinguishes database health from provider health and never returns a raw stack trace.
- [ ] Re-running ingestion on the same transcript files does not create duplicate documents.

## 7. Risks & trade-offs

| Risk | Mitigation | Residual risk |
|---|---|---|
| **Hallucination** — model states something not in the transcripts | Grounding system prompt explicitly forbids stating unsourced facts; code-level abstention when retrieval is empty/thin; sources always shown alongside answers so a user can verify | Prompt-level instructions are not a hard guarantee — a model can still ignore them. No output-side fact-checking is implemented. |
| **Latency** — local Ollama inference on CPU can be slow, especially for the two-stage Ship 30 pipeline | Kept prompts small and focused per stage; logged per-turn latency for visibility; UI shows explicit progress states so a slow response doesn't look broken | Not measured against a real model in this session (no Ollama in the dev sandbox) — real-world latency on the evaluator's machine is unverified. |
| **Cost** (cloud path) | Anthropic is opt-in only; default demo path costs nothing (Ollama) | If `LLM_PROVIDER=anthropic` is left on, cost scales with usage — no budget guardrails implemented. |
| **Local-model quality** — smaller local models may follow grounding instructions less reliably than a frontier cloud model | Kept the grounding contract simple and repeated it in every generation prompt; deterministic routing removes one failure mode (misrouting) so remaining quality risk is concentrated in answer *content*, not *dispatch* | Not empirically validated against a specific small model in this session. |
| **Data leakage / licensing** — redistributing copyrighted transcript content | Real transcripts are fetched at setup time, never committed to the repo (see assumption 2); fallback dataset is original/fictional | If an evaluator commits their own fetched `data/transcripts/lennys_podcast/` despite the `.gitignore`, that would violate the source license — documented clearly but not technically enforced beyond `.gitignore`. |
| **Unsafe artifact rendering** — LLM-generated HTML executing script/exfiltrating data | Two independent layers: server-side sanitization + client-side empty-sandbox iframe (see architecture.md "Security model") | A sanitizer bug combined with a browser sandbox-escape bug would both need to fail simultaneously for actual compromise — considered acceptable residual risk for this scope. |
| **Environment mismatch** — this was built without Docker/Postgres/Ollama available to the builder | Full stack written to the documented interfaces (pgvector's actual query API, Ollama's actual REST API, Docker Compose's actual healthcheck semantics) and cross-checked against each tool's real documentation; extensively tested via a cross-dialect SQLite path and live `curl` smoke tests instead | Not a substitute for running the real stack — explicitly flagged in README "Known limitations" as the first thing an evaluator should do. |

## 8. Implementation plan (as executed)

Phases followed roughly the order suggested by the assignment: requirements → repo/Docker scaffold → FastAPI + Postgres models → ingestion + pgvector → Ollama provider → Anthropic provider → agent + retrieval tools → grounded conversational UX → Ship 30 skill → artifact generation → secure artifact viewer → tests + eval harness → observability/resilience → documentation → end-to-end verification. See `agent-transcripts/` for the real log of what was attempted, what failed, and how it was fixed at each stage.
