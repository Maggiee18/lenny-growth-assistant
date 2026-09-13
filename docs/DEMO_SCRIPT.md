# Demo video script (2–3 minutes, camera on)

Matches the assignment's ask: explain the problem, show the product, demonstrate local Ollama, cover one technical trade-off.

---

**[0:00–0:25] — Camera on, problem framing**

> "Hi, I'm [name]. This is The Lenny Growth Assistant — a take-home for the Forward Deployed Engineer role. The problem: product and growth teams have access to a huge amount of accumulated knowledge in Lenny's Podcast, but getting a specific, trustworthy answer out of dozens of hours of transcripts means manually searching, and there's no way to turn what you find into something reusable without a lot of copy-pasting. This app answers product/growth questions grounded strictly in the transcripts, shows its sources, and turns answers into a Ship 30 essay or an artifact you can actually use."

**[0:25–1:00] — Grounded Q&A + sources**

- Show the running app (`docker compose up`, already running).
- Point out the provider badge: "Local · Ollama · llama3.1:8b" — mandatory local demo path.
- Ask a real question the ingested transcripts cover (e.g. "What do guests say about pricing strategy?").
- Show the answer appearing with source cards — title, episode, excerpt, relevance score, link back to the source.
- Ask a follow-up in the same session to show context is preserved.

**[1:00–1:30] — Abstention + local Ollama demonstration**

> "The most important guarantee here is that it doesn't make things up."

- Ask something clearly outside the knowledge base ("what's the weather today?") — show the explicit "I couldn't find enough evidence..." response.
- Briefly show `docker compose ps` / the Ollama container running, or `ollama list`, to make the local-model claim concrete, not just asserted.

**[1:30–2:15] — Ship 30 essay + artifact viewer**

- Ask for a Ship 30 essay on a topic the transcripts cover.
- Show the artifact panel opening automatically beside the chat, the essay rendering with headings/bullets/bold, and mention the ~1,250-word target.
- Toggle to "Source" view to show the raw markdown.
- Ask for an HTML artifact, show it rendering in the panel.

**[2:15–2:45] — One technical trade-off**

Pick one and explain it briefly (don't rush all of them):

> "One trade-off worth calling out: tool routing — deciding whether a message is a plain question, a Ship 30 request, or an artifact request — is a deterministic keyword classifier, not the model's own function-calling. Ollama's function-calling support varies a lot by model, and I wanted routing to behave identically whether you're on local Ollama or cloud Anthropic. The cost is that a very unusually-phrased request could get misrouted; the benefit is it's fast, free, and fully unit-tested independent of model behavior."

*(Alternative trade-offs to swap in: the artifact security model — two independent layers, sanitize server-side and re-isolate client-side in a zero-permission iframe sandbox; or non-streaming responses in exchange for a simpler, more testable pipeline under the deadline.)*

**[2:45–3:00] — Close**

> "That's The Lenny Growth Assistant — grounded answers, a real content-generation skill, and safe artifact rendering, all running locally with Ollama by default. Thanks for watching."

---

**Before recording, make sure:**
- [ ] `docker compose up --build` is running and healthy (`docker compose ps`, `GET /health` returns `"status": "ok"`)
- [ ] Transcripts are ingested (`POST /api/ingestion/run` reports `documents_ingested > 0`)
- [ ] You've tried each demo question once off-camera so you know it actually returns something good
- [ ] Camera and mic are both on for the whole recording (assignment requires camera-enabled)
