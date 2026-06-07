"""Fetch strategies: discover item links from a source, and pull article bodies.

`html_list` scrapes a listing page for links matching a pattern (e.g. "/news/").
Each source's fetch strategy is dispatched by name so adding "rss" later is just
another function — no change to the rest of the pipeline.
"""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from .config import Source
from .extract import extract_date, extract_title, html_to_text

USER_AGENT = "the-few/0.1 (+https://github.com/junjieyu/the-few)"
_TIMEOUT = 30

# Last-path-segment words that signal an index/listing page, not an article.
_INDEX_SLUGS = {"category", "categories", "tag", "tags", "page", "author", "archive"}


@dataclass
class Discovered:
    """A candidate item found on a listing page/sitemap, before its body is fetched."""

    title: str
    link: str
    date: str = ""  # ISO date if known (sitemap lastmod), else ""


@dataclass
class Article:
    """A fetched item: title, body text, and a display date."""

    title: str
    link: str
    text: str
    date: str = ""


def http_get(url: str) -> str:
    """GET a URL as text with a polite User-Agent."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _discover_html_list(source: Source, listing_html: str) -> list[Discovered]:
    """Extract de-duplicated article links from a listing page."""
    pattern = source.link_pattern or "/"
    # Capture href targets; tolerate single or double quotes.
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', listing_html)
    seen: set[str] = set()
    found: list[Discovered] = []
    for href in hrefs:
        if pattern not in href:
            continue
        link = urljoin(source.origin + "/", href)
        # Skip the listing page itself and anchors/fragments.
        if link.rstrip("/") == source.url.rstrip("/"):
            continue
        link = link.split("#")[0]
        if link in seen:
            continue
        # Skip listing/index pages (e.g. /blog/category, /blog/category/agents):
        # reject if any path segment is an index word, not just the last.
        segments = {s.lower() for s in urlsplit(link).path.split("/") if s}
        if segments & _INDEX_SLUGS:
            continue
        seen.add(link)
        # Derive a placeholder title from the slug; the real one comes from the article.
        slug = link.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").strip()
        found.append(Discovered(title=slug.title(), link=link))
    return found


def _discover_sitemap(source: Source, sitemap_xml: str) -> list[Discovered]:
    """Extract article URLs (with lastmod dates) from a sitemap, newest first.

    `link_pattern` is treated as a path prefix (e.g. "/blog/"), so locale variants
    like /ko/blog/... are excluded. Index pages are skipped as in html_list.
    """
    prefix = source.link_pattern or "/"
    blocks = re.findall(r"<url>(.*?)</url>", sitemap_xml, re.IGNORECASE | re.DOTALL)
    found: list[Discovered] = []
    seen: set[str] = set()
    for block in blocks:
        loc = re.search(r"<loc>(.*?)</loc>", block, re.IGNORECASE | re.DOTALL)
        if not loc:
            continue
        link = loc.group(1).strip().split("#")[0]
        path = urlsplit(link).path
        if not path.startswith(prefix):  # path prefix → drops /ko/blog/, etc.
            continue
        segments = {s.lower() for s in path.split("/") if s}
        if segments & _INDEX_SLUGS:
            continue
        if link.rstrip("/") == source.url.rstrip("/") or link in seen:
            continue
        seen.add(link)
        mod = re.search(r"<lastmod>(.*?)</lastmod>", block, re.IGNORECASE | re.DOTALL)
        date = mod.group(1).strip()[:10] if mod else ""
        slug = path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").strip()
        found.append(Discovered(title=slug.title(), link=link, date=date))
    # Newest first; entries without a date sort to the end.
    found.sort(key=lambda d: d.date or "", reverse=True)
    return found


def discover(source: Source) -> list[Discovered]:
    """Find candidate items for a source using its declared fetch strategy."""
    if source.fetch == "html_list":
        return _discover_html_list(source, http_get(source.url))
    if source.fetch == "sitemap":
        sitemap_url = source.sitemap_url or (source.origin + "/sitemap.xml")
        return _discover_sitemap(source, http_get(sitemap_url))
    raise NotImplementedError(
        f"Fetch strategy {source.fetch!r} is not implemented yet "
        f"(source: {source.slug})."
    )


def fetch_article(link: str, fallback_title: str = "") -> Article:
    """Pull an article page and extract its title, body text, and display date."""
    raw = http_get(link)
    title = extract_title(raw) or fallback_title
    text = html_to_text(raw)
    date = extract_date(raw)
    return Article(title=title, link=link, text=text, date=date)
