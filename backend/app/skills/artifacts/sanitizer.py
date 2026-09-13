"""Defense-in-depth for LLM-generated HTML artifacts.

Generated HTML is untrusted input, full stop -- even though it comes from
"our own" model, the model is instructable by upstream conversation content
(including retrieved transcript text) and must be treated the same as any
other user-supplied HTML. This module is layer 1 of 2:

  1. Sanitize server-side (this file): strip scripts, event handlers,
     javascript: URLs, forms, iframes/objects/embeds, and any externally
     loaded resource that isn't a small allow-listed set of things.
  2. Render client-side inside a sandboxed <iframe> with a strict `sandbox`
     attribute and no `allow-same-origin`, so even if something slipped
     through layer 1 it cannot read cookies/localStorage/parent DOM or
     navigate the top-level page. See design.md "Artifact viewer" and
     frontend/components/ArtifactViewer.tsx.

What's allowed: standard structural/text tags, inline <style>, safe
attributes (class, id, style, href for http(s)/mailto links, src for http(s)
images), and a small set of common ARIA/data attributes.

What's blocked: <script>, <iframe>, <object>, <embed>, <form>, <link>,
<meta>, on* event handlers, javascript:/data:text/html URLs, and any
attribute not on the allow-list.
"""
from __future__ import annotations

import re

import bleach
from bleach.css_sanitizer import CSSSanitizer

from app.core.errors import ArtifactSanitizationError

ALLOWED_TAGS = [
    "a", "abbr", "b", "blockquote", "br", "caption", "code", "div", "em",
    "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i",
    "img", "li", "ol", "p", "pre", "small", "span", "strong", "style",
    "sub", "sup", "table", "tbody", "td", "th", "thead", "tr", "u", "ul",
    "section", "article", "header", "footer", "main", "nav", "mark",
]

ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "style", "title", "aria-label", "aria-hidden", "role"],
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_DANGEROUS_TAG_PATTERN = re.compile(
    r"<\s*(script|iframe|object|embed|form|link|meta|base|frame|frameset|applet)\b",
    re.IGNORECASE,
)
_EVENT_HANDLER_ATTR = re.compile(r"on\w+\s*=", re.IGNORECASE)
_JS_URL = re.compile(r"javascript\s*:", re.IGNORECASE)


def _css_sanitizer() -> CSSSanitizer:
    # Keep CSS conservative: no @import (fetches external stylesheets) and
    # no url() pointing anywhere but data:image (fonts/remote CSS are a
    # common exfiltration/tracking vector in "harmless" generated CSS).
    allowed_css_properties = [
        "color", "background", "background-color", "font", "font-size", "font-family",
        "font-weight", "font-style", "text-align", "text-decoration", "line-height",
        "margin", "margin-top", "margin-bottom", "margin-left", "margin-right",
        "padding", "padding-top", "padding-bottom", "padding-left", "padding-right",
        "border", "border-radius", "border-color", "border-width", "border-style",
        "display", "flex", "flex-direction", "justify-content", "align-items", "gap",
        "grid-template-columns", "width", "max-width", "min-width", "height", "max-height",
        "box-shadow", "opacity", "overflow", "list-style", "letter-spacing", "white-space",
    ]
    return CSSSanitizer(allowed_css_properties=allowed_css_properties)


# bleach.clean() strips a disallowed tag's markup but keeps its inner text --
# fine for most tags, but leaves raw JS source visible as inert text for
# <script> (and similarly for iframe/object/embed/form payloads). We remove
# these element-and-content pairs outright before bleach ever sees them.
_STRIP_WITH_CONTENT_RE = re.compile(
    r"<\s*(script|iframe|object|embed|form)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
# Self-closing or unclosed variants (e.g. a lone <embed src="...">).
_STRIP_TAG_ONLY_RE = re.compile(
    r"<\s*(script|iframe|object|embed|form)\b[^>]*/?>",
    re.IGNORECASE,
)


def sanitize_html(raw_html: str, *, max_bytes: int = 200_000) -> str:
    if len(raw_html.encode("utf-8")) > max_bytes:
        raise ArtifactSanitizationError(
            "Generated HTML exceeds the maximum allowed size.",
            detail=f"limit={max_bytes} bytes",
        )

    pre_stripped = _STRIP_WITH_CONTENT_RE.sub("", raw_html)
    pre_stripped = _STRIP_TAG_ONLY_RE.sub("", pre_stripped)

    cleaned = bleach.clean(
        pre_stripped,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=_css_sanitizer(),
        strip=True,
        strip_comments=True,
    )

    # Belt-and-suspenders: bleach.clean should already remove these, but we
    # fail loudly (rather than silently trust) if any of these signatures
    # somehow survive -- e.g. via a bleach config regression.
    if _DANGEROUS_TAG_PATTERN.search(cleaned) or _EVENT_HANDLER_ATTR.search(cleaned) or _JS_URL.search(cleaned):
        raise ArtifactSanitizationError(
            "Generated HTML failed post-sanitization safety check.",
            detail="dangerous pattern detected after cleaning",
        )

    return cleaned


def wrap_fragment_as_document(fragment: str, title: str) -> str:
    """Wrap a sanitized fragment in a minimal HTML document for the iframe srcdoc."""
    escaped_title = bleach.clean(title, tags=[], strip=True)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{escaped_title}</title>"
        "<meta name=\"referrer\" content=\"no-referrer\">"
        "<style>body{font-family:system-ui,-apple-system,sans-serif;margin:16px;color:#1a1a1a;}"
        "img{max-width:100%;}</style></head><body>" + fragment + "</body></html>"
    )
