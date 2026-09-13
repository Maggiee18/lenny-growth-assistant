# 006 — Artifact security (HTML sanitization + sandboxed viewer)

**Goal:** treat all LLM-generated HTML as untrusted; implement defense-in-depth sanitization + isolated rendering per assignment's explicit "Security expectation."

## Design

Two independent layers, deliberately redundant:
1. **Server-side** (`backend/app/skills/artifacts/sanitizer.py`): `bleach.clean()` with an explicit tag/attribute/protocol allow-list (no `script`, `iframe`, `object`, `embed`, `form`, `link`, `meta`; no `on*` handlers; only `http(s)`/`mailto` URLs).
2. **Client-side** (`frontend/components/ArtifactViewer.tsx`): sanitized HTML is rendered inside an `<iframe sandbox="">` with an **empty** sandbox value — the most restrictive setting, disabling script execution, form submission, top navigation, popups, and same-origin access unconditionally, regardless of whether layer 1 has a bug.

Markdown artifacts get a parallel guarantee for a different reason: `react-markdown` is used **without** the `rehype-raw` plugin, so any raw HTML embedded in markdown text (from the model or from retrieved transcript content) is rendered as literal escaped text, never parsed as markup — no `dangerouslySetInnerHTML` anywhere in the frontend.

## Failure found by test: bleach removes tags but not their inner text

**Attempted:** wrote `tests/test_artifacts.py::test_sanitize_html_strips_script_tags` — `sanitize_html("<div>Hello</div><script>alert('xss')</script>")` should contain neither `<script` nor `alert`.

**Failed because:** `bleach.clean(strip=True)` removes a disallowed tag's *markup* but keeps its *text content* by default — the output was `<div>Hello</div>alert('xss')`. Not executable (it's inert text once the `<script>` wrapper is gone), but it directly contradicts the documented promise ("What's blocked: script...") and would visibly leak raw JS source into a rendered artifact, which is confusing and looks like a security bug even though it isn't an XSS vector.

**Fix:** added a pre-processing regex pass (`_STRIP_WITH_CONTENT_RE`, `_STRIP_TAG_ONLY_RE`) that removes `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>` **and their content** before bleach ever sees the string, handling both matched-pair and self-closing/unclosed forms. `<style>` is deliberately excluded from this list since inline CSS is an intentionally allowed artifact feature.

**Verified:** the failing test now passes, plus additional tests for event-handler stripping (`onerror=`), `javascript:` URL stripping, `iframe`/`object`/`embed`/`form` removal, safe-tag preservation (`<h1>`, `<strong>`, inline `<style>`), and an oversized-payload rejection. Frontend: `tests/ArtifactViewer.test.tsx` asserts the iframe's `sandbox` attribute is literally `""` and that embedded `<img onerror=...>` inside markdown never becomes a real DOM `<img>` element.
