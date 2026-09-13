# Final submission checklist

## Suggested GitHub repository description

> Grounded conversational AI assistant over Lenny's Podcast transcripts — FastAPI + pgvector RAG, Ollama/Anthropic provider switching, a Ship 30 for 30 essay skill, and sandboxed Markdown/HTML artifact generation. Next.js + TypeScript frontend, Docker Compose deployment.

Suggested topics/tags: `rag`, `fastapi`, `nextjs`, `pgvector`, `ollama`, `anthropic`, `llm-agent`, `typescript`

## Steps to actually submit

1. ~~Push to a public GitHub repo~~ **Done**: [github.com/Maggiee18/lenny-growth-assistant](https://github.com/Maggiee18/lenny-growth-assistant)
2. ~~Run the real stack~~ **Done** — `docker compose up --build` was run live end-to-end on this machine: all 4 services healthy, real ingestion (26 documents / 1,455 chunks), real grounded Q&A with cited sources, a follow-up question, and a Ship 30 essay landing in the target word band. Five real bugs were found and fixed in the process (see `agent-transcripts/009-live-docker-verification.md`) and one grounding-fidelity issue was found, fixed, and not yet re-verified with a further live run (see README "Known limitations"). The stack is still running — reopen the app at http://localhost:3000 any time, or re-run the commands below from scratch if you want a clean verification:
   ```bash
   cp .env.example .env
   docker compose up --build
   docker compose exec ollama ollama pull llama3.1:8b
   docker compose exec ollama ollama pull nomic-embed-text
   python scripts/fetch_lennys_transcripts.py --limit 20
   curl -X POST http://localhost:8000/api/ingestion/run -H "Content-Type: application/json" -d '{}'
   ```
3. **Run the eval harness** against the real stack for a fuller measurement than the ad-hoc manual testing done this session covered: `python eval/run_eval.py --base-url http://localhost:8000`.
4. **Record the demo video** using [DEMO_SCRIPT.md](DEMO_SCRIPT.md) (camera on, 2–3 minutes), upload to YouTube (unlisted is fine unless the form asks for public).
5. **Double-check no secrets are committed**: `git log --all -p | grep -iE "sk-ant|api[_-]?key"` should return nothing; `.env` should never appear in `git ls-files`.
6. **Fill out the submission form**: https://forms.gle/LgotDHNVxW1mbzNE7 — repo URL, video URL. Due 15/09/26 EOD.

## Pre-flight sanity check

```bash
git ls-files | grep -E "\.env$"        # must be empty
git ls-files | grep -E "node_modules|\.venv"   # must be empty
cd backend && pytest -q                # should show all passing
cd ../frontend && npm run build        # should succeed
```
