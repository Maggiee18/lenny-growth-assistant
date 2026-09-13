from __future__ import annotations

import re

TARGET_WORDS = 1250
WORD_TOLERANCE = 0.25  # +/- 25% => acceptable band per assignment's "approximately"


def word_count(markdown_text: str) -> int:
    stripped = re.sub(r"[#*_`>-]", " ", markdown_text)
    return len(stripped.split())


def validate_structure(markdown_text: str) -> list[str]:
    """Return a list of warnings (empty = fully compliant). Never raises --
    a Ship 30 draft that's slightly off-spec should still reach the user
    with a visible warning rather than be silently blocked."""
    warnings: list[str] = []

    wc = word_count(markdown_text)
    low, high = TARGET_WORDS * (1 - WORD_TOLERANCE), TARGET_WORDS * (1 + WORD_TOLERANCE)
    if not (low <= wc <= high):
        warnings.append(f"Word count {wc} is outside the target band ({int(low)}-{int(high)}).")

    headings = re.findall(r"^#{1,3}\s+.+$", markdown_text, re.MULTILINE)
    if len(headings) < 2:
        warnings.append("Fewer than 2 headings found; essay may not be skimmable.")

    bullets = re.findall(r"^\s*[-*]\s+.+$", markdown_text, re.MULTILINE)
    if len(bullets) < 2:
        warnings.append("Fewer than 2 bullet points found.")

    bold = re.findall(r"\*\*[^*]+\*\*", markdown_text)
    if len(bold) < 2:
        warnings.append("Fewer than 2 bold emphasis spans found.")

    first_para = next((p for p in markdown_text.split("\n\n") if p.strip() and not p.strip().startswith("#")), "")
    if len(first_para.split()) > 80:
        warnings.append("Opening hook paragraph looks long; aim for a tight, punchy hook.")

    return warnings
