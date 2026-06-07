"""Summarize an article into a briefing-sized blurb via an LLM.

Aggressive summarization is the product: the briefing should let you *finish*, and
only drill into the source when something fires your interest. Each item becomes a
one-line takeaway plus a 2-3 sentence "what it says + why it matters".

Uses DeepSeek by default (cheap, OpenAI-compatible). Configure via env vars:
    DEEPSEEK_API_KEY   your key (required)   — or THE_FEW_API_KEY
    THE_FEW_MODEL      default "deepseek-chat" (try "deepseek-reasoner" for R1)
    THE_FEW_BASE_URL   default "https://api.deepseek.com"

Because it's just an OpenAI-compatible endpoint, you can point THE_FEW_BASE_URL /
THE_FEW_MODEL at any compatible provider (OpenAI, a local Ollama, etc.).
"""

from __future__ import annotations

import os

import openai
from openai import OpenAI

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com"
# Cap the text handed to the model so one long page can't blow up token cost.
# The body is the lede + first sections, which is plenty for a briefing summary.
_MAX_CHARS = 16000

SYSTEM = (
    "You write a daily briefing for a reader who wants maximum signal in minimum "
    "time. For each article you are given, produce a tight, factual summary that "
    "lets the reader decide whether to read the original. No hype, no preamble, no "
    "marketing voice. Respond with ONLY the formatted summary — no meta-commentary."
)

PROMPT_TEMPLATE = """\
Summarize the following article for a daily briefing.

Format your answer EXACTLY as:
**<one-line takeaway, under 15 words>**
<2-3 sentences: what it says and why it matters>

Source: {source_name}
Title: {title}

Article text:
---
{text}
---"""


class MissingAPIKey(RuntimeError):
    """Raised when no LLM API key is configured."""


def _model() -> str:
    return os.environ.get("THE_FEW_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def make_client() -> OpenAI:
    """Build an OpenAI-compatible client pointed at DeepSeek (or an override).

    Raises MissingAPIKey if no key is set, so the run fails fast with a clear message
    instead of fetching articles it can't summarize.
    """
    api_key = (
        os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("THE_FEW_API_KEY") or ""
    ).strip()
    if not api_key:
        raise MissingAPIKey(
            "No API key found. Set DEEPSEEK_API_KEY (get one at platform.deepseek.com)."
        )
    base_url = os.environ.get("THE_FEW_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    return OpenAI(api_key=api_key, base_url=base_url)


def is_auth_error(exc: Exception) -> bool:
    """True if the exception is a credentials/auth problem (fatal for the whole run)."""
    if isinstance(exc, (MissingAPIKey, openai.AuthenticationError)):
        return True
    msg = str(exc).lower()
    return "api_key" in msg or "authentication" in msg or "invalid api key" in msg


def summarize_article(
    *,
    source_name: str,
    title: str,
    text: str,
    client: OpenAI | None = None,
) -> str:
    """Return a briefing blurb for one article."""
    client = client or make_client()
    body = text[:_MAX_CHARS]
    prompt = PROMPT_TEMPLATE.format(source_name=source_name, title=title, text=body)

    response = client.chat.completions.create(
        model=_model(),
        max_tokens=600,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()
