# Design

## UI/UX principles

1. **Trustworthy over flashy.** Every grounded answer shows its sources inline, right below the answer, not behind a click. Abstention is visually distinct (amber, not the default message color) so a user never mistakes "I don't know" for a normal answer.
2. **No blank-screen moments.** Every async operation (loading sessions, loading a conversation, sending a message, generating an artifact) has an explicit state — a skeleton/loading line, a "retrieving sources and generating..." indicator with staggered pulse dots, or a clear error banner. Never a silently frozen UI.
3. **The artifact viewer is first-class, not an afterthought.** It lives beside the chat (not a modal, not a new tab) and has its own toolbar (rendered/source toggle, copy, download, close) so a user never has to leave the app to see, verify, or export what was generated.
4. **Minimal, purposeful color.** One brand blue for primary actions and the active session; slate grays for structure; amber for abstention/caution; emerald for healthy provider status. No decorative animation beyond a small loading pulse.

## Information architecture

```
┌─────────────┬──────────────────────────────────────────┬───────────────────┐
│  Sidebar     │  Header (title, provider badge, artifact  │                   │
│  - New chat  │  toggle)                                   │                   │
│  - Session   ├──────────────────────────────────────────┤   Artifact panel  │
│    list      │  Conversation (messages, source cards,    │   (toggleable,    │
│              │  artifact-open buttons)                    │   45% width on    │
│              ├──────────────────────────────────────────┤   desktop, full-  │
│              │  Composer (suggestions, textarea, send)    │   screen overlay  │
│              │                                            │   on mobile)      │
└─────────────┴──────────────────────────────────────────┴───────────────────┘
```

Three panes on desktop (sessions / conversation / artifact); the artifact pane only claims space when there's something to show, so a plain Q&A session isn't visually cluttered by an empty panel.

## Key interaction states

| State | Treatment |
|---|---|
| Empty app (no sessions yet) | Sidebar: "No chats yet. Start one above." Conversation: an inviting prompt to start typing. |
| Empty artifact panel | "Artifacts you generate will appear here." (explicit, per assignment's suggested copy) plus a one-line hint. |
| Sending a message | Optimistic user bubble appears immediately; a pulsing "Retrieving sources and generating a grounded answer…" line appears below; composer disabled to prevent double-submits. |
| Grounded answer | Standard message bubble + a responsive grid of source cards (title, episode, relevance %, excerpt, source link). |
| Abstained answer | Amber-tinted bubble, no source cards, distinct from a normal answer at a glance (not just by reading the text). |
| Artifact generated | Assistant message gets an "Open artifact" button; the artifact panel auto-opens on generation so the user doesn't have to hunt for it. |
| Backend unreachable | A persistent red banner at the top of the chat pane with the actual connection error (not a generic "something went wrong"). |
| Provider unhealthy | Provider badge turns amber with a tooltip explaining the configured provider is unavailable, instead of silently failing on the next message. |
| Artifact render failure | "Unable to safely render this artifact." (per assignment's suggested copy) shown in place of the iframe/markdown view. |

## Responsive behavior

- **Desktop (≥768px):** three-pane layout as above; sidebar and artifact panel both static, no overlays.
- **Mobile/narrow (<768px):** sidebar becomes a slide-in drawer (hamburger button in the header, backdrop click to dismiss); the artifact panel becomes a full-screen overlay when open (its own close button returns to the chat) instead of squeezing into a fraction of a narrow screen. Verified via the browser's mobile viewport preset during manual testing.
- Message bubbles cap at `75ch` width so long-form answers stay readable on wide desktop screens instead of stretching edge-to-edge.

## Accessibility

- Every interactive control has a visible focus ring (`:focus-visible` outline defined globally in `app/globals.css`, not suppressed anywhere).
- Icon-only buttons (close artifact viewer, mobile sidebar toggle) have `aria-label`s.
- The suggestion-chip row is marked `role="list"`/`role="listitem"` so screen readers announce it as a set of options, not prose.
- The "sending" indicator uses `role="status" aria-live="polite"` so screen reader users hear that a response is coming without needing to poll the DOM.
- Error banners use `role="alert"`.
- Form labels: the composer's textarea has an associated (visually hidden but screen-reader-visible) `<label>`, not just a placeholder — placeholders disappear on focus and don't count as accessible names.
- Color is never the only signal: abstained answers differ in border/background *and* wording ("I couldn't find enough evidence..."), not color alone; the provider health dot is paired with text ("Local · Ollama · llama3.1:8b"), not a bare colored dot.

## Artifact viewer security (design rationale)

The artifact viewer is the one place in this app that renders content an LLM produced with minimal further transformation, so its design had to answer three questions explicitly (per the assignment's "Security expectation"):

**What's allowed:** structural/text HTML tags (headings, paragraphs, lists, tables, `<figure>`, semantic sectioning elements), inline `<style>` for CSS, `http(s)`/`mailto` links and images, a small safe attribute set (`class`, `id`, `style`, `title`, basic ARIA). Markdown artifacts get headings, lists, tables (via `remark-gfm`), emphasis, code spans/blocks, blockquotes, and links.

**What's blocked, and why:** `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>`, `<link>`, `<meta>`, `<base>` (each is a known vector for code execution, resource-loading exfiltration, or clickjacking); every `on*` event-handler attribute; `javascript:`/`data:text/html` URLs; any attribute not on the explicit allow-list. Blocked at the server (so the stored artifact content itself is clean) *and* re-blocked at render time via an empty-value `iframe sandbox` attribute, so even a sanitizer bug can't result in script execution, form submission, top navigation, or same-origin DOM/cookie access.

**Remaining limitations:** the sandboxed iframe cannot run any legitimate interactive JavaScript either — this is a deliberate scope cut (generated artifacts are meant to be documents/pages, not mini-apps); if a future requirement needs safe interactivity, that would need a different, more carefully scoped mechanism (e.g. a fixed set of approved, non-arbitrary widgets), not a loosened sandbox. CSS `url()` values are restricted to `data:image` and safe schemes to avoid using stylesheet loading as a tracking/exfiltration channel.

Two independent view modes are always available for every artifact — **Rendered** and **Source** — so a user can always inspect exactly what was generated before trusting or sharing it, rather than being forced to trust the rendered view.

## Important design decisions & trade-offs

- **Non-streaming chat responses.** Simpler to keep the retrieval → generation → persistence → response pipeline correct and testable under the deadline; compensated for with explicit, honest loading states rather than a token-by-token illusion of speed. Documented as a trade-off in architecture.md, not hidden.
- **Provider badge always visible, not just in settings.** The assignment explicitly requires the active provider be visible in the UI — put it in the persistent header rather than a settings page nobody opens, since "which model am I talking to" is directly relevant to how much a user should trust an answer.
- **Artifact panel opens automatically on generation but can be closed/reopened.** Balances "don't make the user hunt for what they asked for" against "don't force screen real estate on someone who wants to keep chatting."
- **No animation beyond a small loading pulse.** The assignment explicitly says not to spend time on excessive animation; every design hour went into states and information architecture instead.

## Manual UI test plan

Run against a live stack (`docker compose up`, transcripts ingested):

1. **Empty state:** open the app fresh — sidebar says "No chats yet," conversation area invites a first message, artifact panel says "Artifacts you generate will appear here."
2. **New chat + provider badge:** click "New chat," confirm the provider badge shows the correct Local/Cloud label and model name matching `.env`.
3. **Grounded Q&A:** ask a question clearly covered by an ingested transcript — confirm an answer appears with >=1 source card, each showing title/episode/excerpt/relevance/link.
4. **Abstention:** ask something obviously outside the knowledge base (e.g. "what's today's weather?") — confirm the amber abstention bubble, not a fabricated answer.
5. **Follow-up context:** ask a vague follow-up ("what about for a smaller team?") right after a grounded answer — confirm the response stays topically consistent with the prior turn.
6. **Session isolation:** create a second chat, ask something — confirm the first session's history is untouched when you switch back.
7. **Ship 30 essay:** ask for one — confirm the artifact panel opens, word count looks close to ~1,250 words, headings/bullets/bold are present, and the essay's claims trace back to visible sources.
8. **Markdown artifact:** ask for a markdown summary — confirm it renders with headings/lists/bold, and the Source toggle shows raw markdown text (not HTML).
9. **HTML artifact:** ask for an HTML page — confirm it renders inside the panel; open browser devtools and confirm the artifact lives inside an `<iframe>` with `sandbox=""` and no `allow-scripts`/`allow-same-origin`.
10. **Artifact controls:** copy (clipboard has the raw content), download (file saves with a sane filename/extension), close (panel disappears, reopenable via the header toggle).
11. **Resilience:** stop Ollama (`docker compose stop ollama`), ask a question — confirm a clear, categorized error banner appears (not a blank screen or a raw stack trace), then restart Ollama and confirm the app recovers without a page reload.
12. **Responsive:** resize to a mobile width — confirm the sidebar becomes a drawer (hamburger opens/closes it) and the artifact panel becomes a full-screen overlay.
13. **Keyboard-only pass:** tab through the entire chat flow (new chat, session list, composer, send, artifact toggle, close button) without a mouse — confirm every control is reachable and shows a visible focus ring.
