"""v0 pipeline: a title-first attention gate with triage.

By design, `brief` shows only *titles* (source · title · link) — no LLM summary.
Fetching the page to get a clean title is cheap; the expensive part (an LLM
summary) is deferred to `open`, and only ever runs on items you chose to keep.
That's the whole point: the gate is cheap, and your attention is the scarce thing.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Callable

from .config import Source
from .db import DISMISSED, INTERESTED, NEW, Store
from .fetch import discover, fetch_article

# Max new items to ingest per source per run. Set high enough to pull a source's
# whole recent listing (fetching is cheap now — no LLM at ingest); the *display*
# cap (--show) then surfaces the newest N, date-sorted. Lower it for sources with
# very large listing pages.
DEFAULT_MAX_NEW = 40
DEFAULT_SHOW = 25  # max items shown in a single brief (the daily cap)

Logger = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def ingest_new(
    store: Store,
    sources: list[Source],
    *,
    max_new_per_source: int = DEFAULT_MAX_NEW,
    log: Logger = _noop,
) -> int:
    """Discover and store new items (titles + cached body) for each source.

    No summarization happens here. Returns the number of newly stored items.
    """
    total = 0
    for source in sources:
        log(f"[{source.slug}] discovering…")
        try:
            candidates = discover(source)
        except Exception as exc:  # network / parse failure shouldn't kill the run
            log(f"[{source.slug}] discover failed: {exc}")
            continue

        new_count = 0
        for cand in candidates:
            if new_count >= max_new_per_source:
                break
            if store.has_link(cand.link):
                continue

            log(f"[{source.slug}] fetching {cand.link}")
            try:
                article = fetch_article(cand.link, fallback_title=cand.title)
            except Exception as exc:
                log(f"[{source.slug}] fetch failed: {exc}")
                continue

            item_id = store.add_item(
                source_slug=source.slug,
                title=article.title,
                link=article.link,
                full_text=article.text,
                # Prefer the date on the page; fall back to the sitemap lastmod.
                published=article.date or cand.date or None,
            )
            if item_id is not None:  # None == raced/duplicate
                new_count += 1
        total += new_count
        log(f"[{source.slug}] {new_count} new item(s)")
    return total


def render_items(
    heading: str,
    rows: list[sqlite3.Row],
    name_by_slug: dict[str, str],
    *,
    footer: str = "",
) -> str:
    """Render a numbered, scannable list of items (source · title · date · link)."""
    lines: list[str] = []
    lines.append(f"📡  {heading}")
    lines.append("─" * 52)
    if not rows:
        lines.append("")
        lines.append("Nothing here. Enjoy the quiet.")
        lines.append("")
        return "\n".join(lines)

    for i, row in enumerate(rows, start=1):
        source = name_by_slug.get(row["source_slug"], row["source_slug"])
        lines.append(f"{i:2}. [{source}] {row['title']}")
        meta = row["published"] + " · " if row["published"] else ""
        lines.append(f"      {meta}{row['link']}")

    if footer:
        lines.append("")
        lines.append("─" * 52)
        lines.append(footer)
    lines.append("")
    return "\n".join(lines)


def keep(store: Store, positions: list[int]) -> tuple[list[str], list[str]]:
    """Finalize the current brief: keep the chosen items, dismiss the rest.

    Returns (kept_titles, dismissed_titles). Only items currently `new` are
    auto-dismissed, so running `keep` after `list` won't archive your reading list.
    """
    kept_ids: set[int] = set()
    kept_titles: list[str] = []
    for pos in positions:
        item = store.view_item(pos)
        if item is None:
            continue
        store.set_status(item["id"], INTERESTED)
        kept_ids.add(item["id"])
        kept_titles.append(item["title"])

    dismissed_titles: list[str] = []
    for item_id in store.view_item_ids():
        if item_id in kept_ids:
            continue
        item = store.get_item(item_id)
        if item is not None and item["status"] == NEW:
            store.set_status(item_id, DISMISSED)
            dismissed_titles.append(item["title"])

    return kept_titles, dismissed_titles


def todays_heading(count: int, label: str) -> str:
    return f"THE FEW · {date.today().isoformat()} · {count} {label}"


def render_digest(
    rows: list[sqlite3.Row], name_by_slug: dict[str, str], *, heading: str | None = None
) -> str:
    """A chat-ready message. Every item puts its raw original URL on its own line so
    it is directly clickable in any chat client — the link must never be dropped."""
    title = heading or f"{len(rows)} item{'' if len(rows) == 1 else 's'}"
    lines = [f"📡  The Few — {title}"]
    if not rows:
        lines += ["", "Nothing to report."]
        return "\n".join(lines)
    for i, row in enumerate(rows, start=1):
        source = name_by_slug.get(row["source_slug"], row["source_slug"])
        meta = " · ".join(x for x in (source, row["published"]) if x)
        lines += ["", f"{i}. {row['title']}", f"   {meta}", f"   {row['link']}"]
    return "\n".join(lines)
