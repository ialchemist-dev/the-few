"""Turn a fetched HTML page into clean-ish plain text.

Deliberately dependency-free: strip scripts/styles/tags and collapse whitespace.
It isn't a full readability extractor — but server-rendered article pages carry
their body text inline, and Claude is robust to a bit of surrounding nav cruft.
Keeping this simple avoids a headless browser or a readability library for v1.
"""

from __future__ import annotations

import html as _html
import re
from datetime import datetime

_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\f\v]+")
_BLANKLINES = re.compile(r"\n\s*\n\s*")


def html_to_text(raw: str) -> str:
    """Strip tags and entities from an HTML document, preserving rough line breaks."""
    text = _SCRIPT_STYLE.sub(" ", raw)
    # Convert common block boundaries into newlines before dropping tags so the
    # output keeps some structure for the summarizer.
    text = re.sub(r"</(p|div|li|h[1-6]|section|article|br)\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = _TAG.sub(" ", text)
    text = _html.unescape(text)
    text = _WS.sub(" ", text)
    text = _BLANKLINES.sub("\n\n", text)
    return text.strip()


_DATE = re.compile(
    r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},\s+\d{4})\b"
)


def extract_date(raw: str) -> str:
    """Best-effort publish date as a sortable ISO string (YYYY-MM-DD), or "".

    Finds the first "Month D, YYYY" in the page text and normalizes it so dates
    sort correctly across the whole list.
    """
    text = _SCRIPT_STYLE.sub(" ", raw)
    text = _TAG.sub(" ", text)
    m = _DATE.search(text)
    if not m:
        return ""
    return human_date_to_iso(m.group(1))


def human_date_to_iso(s: str) -> str:
    """'June 3, 2026' / 'Jun 3, 2026' -> '2026-06-03'. Returns "" if unparseable."""
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def extract_title(raw: str) -> str:
    """Best-effort page title from <title> or the first <h1>."""
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    if m:
        title = _html.unescape(_TAG.sub("", m.group(1))).strip()
        # Trim trailing site suffixes like " \ Anthropic" or " | Site".
        title = re.split(r"\s[\\|]\s", title)[0].strip()
        if title:
            return title
    m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.IGNORECASE | re.DOTALL)
    if m:
        return _html.unescape(_TAG.sub("", m.group(1))).strip()
    return ""
