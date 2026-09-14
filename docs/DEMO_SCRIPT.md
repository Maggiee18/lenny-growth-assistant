# Demo video script (2–3 minutes, camera on)

Matches the assignment's ask: explain the problem, show the product, demonstrate local Ollama, cover one technical trade-off.

## The timing reality — read this first

On CPU-only Ollama inference, real measured response times were: a plain Q&A turn ~60–130s, a Ship 30 essay ~6 minutes, an artifact ~1–2 min. You cannot show any of these happening live in real time inside a 2–3 minute video — so don't try to. Two options:

**Option A — Pre-generate, then narrate over the results (recommended, simplest).**
Before recording, open the app and actually ask the 3–4 questions you'll show. Let them finish. Now you have a session full of real, already-rendered answers/sources/artifacts sitting on screen. During recording, scroll through and narrate over what's already there — you're not waiting for anything. Do ONE thing live on camera (see below) to prove it's real, not a screenshot.

**Option B — Record everything live, speed up the waiting in editing.**
Record the real thing end-to-end (longer, e.g. 10–15 min raw), then in any video editor (iMovie/Clipchamp/DaVinci Resolve, all free) speed up or cut the "spinner is spinning" segments to a couple seconds, keeping your narration voice-over normal speed. More work, but proves everything is genuinely live.

Go with A unless you enjoy video editing.

## Proven-working prompts (already tested live against your real ingested data — use these, don't improvise on camera)

| Ask this | You'll see |
|---|---|
| `What do guests say about product-market fit?` | Real answer citing Jen Abel, Mark Pincus, and Adam Ward episodes with real excerpts, source links, relevance scores |
| `What is the current stock price of a random public company today?` | Clean abstention — "I couldn't find enough evidence..." — **fast (~8s), good for a live on-camera moment** |
| `Write a Ship 30 for 30 essay about product-market fit` | A ~1,000+ word essay with headings/bullets/bold, grounded in the same real sources, landing in the target word band |
| `Generate an HTML page about growth loops` | A clean rendered HTML artifact in the sandboxed viewer |
| `Create a markdown one-pager summarizing this conversation` | A markdown artifact grounded in the actual chat history |

## Script

**[0:00–0:20] — Camera on, problem framing**

> "Hi, I'm [name]. This is The Lenny Growth Assistant — a take-home for the Forward Deployed Engineer role. Product and growth teams have a huge amount of knowledge locked in Lenny's Podcast, but getting a trustworthy answer out of dozens of hours of transcripts means manual searching, and there's no easy way to turn what you find into something reusable. This app answers questions grounded strictly in the transcripts, always shows its sources, and can turn an answer into a Ship 30 essay or a shareable artifact."

**[0:20–0:55] — Grounded Q&A + sources (pre-generated, narrate over it)**

- Screen: the already-open session showing the product-market-fit question and its answer.
- Point at the provider badge: "Local · Ollama · llama3.1:8b" — this is running the mandatory local model, not a cloud API.
- Point at the source cards below the answer: "Every grounded answer shows exactly which episodes it came from — title, guest, an excerpt, a relevance score, and a link back to the source. Nothing here is invented."

**[0:55–1:15] — Abstention, done LIVE on camera**

> "The most important guarantee is that it doesn't make things up when it doesn't know."

- Actually type the stock-price question live and hit send — it resolves in ~8 seconds, so this is safe to show in real time.
- "It says clearly it couldn't find evidence, instead of guessing."

**[1:15–2:00] — Ship 30 essay + artifact viewer (pre-generated, narrate over it)**

- Screen: the already-generated Ship 30 essay in the artifact panel.
- "Asking for a Ship 30 essay routes to a dedicated multi-stage pipeline — it builds a structured outline from the evidence first, then writes the essay from that outline, so it can't wander into invented stories. It lands right around the ~1,250-word target, with headings, bullets, and bold for skimmability."
- Toggle Source/Rendered to show the raw markdown briefly.
- Switch to the pre-generated HTML artifact: "HTML artifacts render inside a sandboxed iframe with scripts fully disabled — even if something went wrong, it can't execute code or touch the rest of the app."

**[2:00–2:35] — One technical trade-off**

> "One trade-off worth calling out: deciding whether a message is a plain question or an artifact request uses a deterministic keyword classifier, not the model's own function-calling. Ollama's function-calling support varies a lot by model, and I wanted this to behave identically on local Ollama or cloud Anthropic. The cost is an unusually-phrased request could get misrouted; the benefit is it's fast, free, and fully unit-tested independent of what the model does."

*(Swap in if you'd rather: the two-layer artifact security model — sanitize server-side, then re-isolate client-side in a zero-permission iframe sandbox; or a real bug found via live testing — an over-tuned vector index that could silently return zero search results, found and fixed by actually running the full stack instead of just testing against mocks.)*

**[2:35–2:50] — Close**

> "That's The Lenny Growth Assistant — grounded answers with real sources, a structured essay-writing skill, and safely-rendered artifacts, all running locally by default. Thanks for watching."

---

## Before recording

- [ ] `docker compose ps` — all 4 services healthy
- [ ] `curl http://localhost:8000/health` → `"status": "ok"`
- [ ] Pre-generate the Q&A answer, the Ship 30 essay, and the HTML artifact (run the prompts above, let them finish) so you have real content to narrate over
- [ ] Do one dry run of the live abstention question so you know it actually takes ~8s, not longer
- [ ] Camera and mic both on for the whole recording (assignment requires camera-enabled)
- [ ] Keep a browser tab on the app the whole time — no need to show terminal/Docker unless you want to briefly prove it's local
