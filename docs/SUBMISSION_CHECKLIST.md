# Final submission checklist

## Suggested GitHub repository description

> Grounded conversational AI assistant over Lenny's Podcast transcripts — FastAPI + pgvector RAG, Ollama/Anthropic provider switching, a Ship 30 for 30 essay skill, and sandboxed Markdown/HTML artifact generation. Next.js + TypeScript frontend, Docker Compose deployment.

Suggested topics/tags: `rag`, `fastapi`, `nextjs`, `pgvector`, `ollama`, `anthropic`, `llm-agent`, `typescript`

## Steps to actually submit

1. **Push to a public GitHub repo** (not done automatically in this session — no `gh` CLI available and pushing to a public remote needs your explicit account/credentials):
   ```bash
   gh repo create lenny-growth-assistant --public --source=. --remote=origin --push
   # or, without gh:
   git remote add origin https://github.com/<you>/lenny-growth-assistant.git
   git branch -M main
   git push -u origin main
   ```
2. **Run the real stack once before recording/submitting** — this is the one thing that hasn't been executed end-to-end (see README "Known limitations"):
   ```bash
   cp .env.example .env
   docker compose up --build
   docker compose exec ollama ollama pull llama3.1:8b
   docker compose exec ollama ollama pull nomic-embed-text
   python scripts/fetch_lennys_transcripts.py --limit 20
   curl -X POST http://localhost:8000/api/ingestion/run -H "Content-Type: application/json" -d '{}'
   ```
   Confirm `/health` returns `"status": "ok"`, ask a real question in the UI, generate a Ship 30 essay, generate an HTML artifact.
3. **Run the eval harness** against the real stack and skim the results: `python eval/run_eval.py --base-url http://localhost:8000`.
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
