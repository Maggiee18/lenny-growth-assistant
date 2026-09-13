# 004 — Agent architecture & routing decision

**Goal:** implement the agent layer per assignment §3.1 ("Anthropic Claude Agent SDK or Pi Coding Agent") with explicit tool boundaries.

## Decision: not using the Claude Agent SDK directly

The Claude Agent SDK is built around Claude's own tool-use loop (file system, bash, coding-agent primitives) and is inherently Anthropic-API-shaped. This project's non-negotiable requirement is a **provider-agnostic** agent — the same conversational/tool behavior must work identically on local Ollama (mandatory for the demo) and on Anthropic (optional cloud path). Ollama's function-calling support varies significantly by model and isn't reliable enough to build the *only* routing mechanism on top of it.

**Chose:** a custom, explicit tool-boundary agent (`app/agents/agent.py` + `app/agents/tools.py`) with a small, fully deterministic, unit-testable intent classifier (`app/agents/router.py`) instead of depending on model-native function calling for routing. Each of the five required capabilities (`search_transcripts`, `answer_from_sources`, `generate_ship30`, `generate_markdown_artifact`, `generate_html_artifact`) is a distinct, independently testable Python function — the "skill boundary" the assignment asks for is enforced by module structure, not by an LLM's tool-call JSON.

This is a documented, deliberate trade-off (see `architecture.md` "Agent routing" and `PRD.md` "Trade-offs") — it sacrifices some flexibility for reliability and provider-parity, which matters more given Ollama is the mandatory demo path.

## Retrieval-first, always

Every turn retrieves transcript evidence *before* dispatching to a tool, regardless of intent — so Ship 30/artifact generation is grounded in the same evidence set a plain QA turn would see, and so `generate_ship30` can refuse (raise `InsufficientEvidenceError`) when retrieval comes back thin, rather than silently writing an ungrounded essay.

## Verified

- `test_agent_routing.py`: intent classification for every category (ship30/html/markdown/plain QA), including an explicit priority test (an "HTML artifact" request must not fall through to the markdown pattern even though "artifact" also matches).
- End-to-end `PodcastAgent.handle_turn()` tests against an in-memory DB: ship30 intent + zero seeded evidence → abstains without calling the writer at all.
