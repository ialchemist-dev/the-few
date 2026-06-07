"""Load the hand-picked source list from TOML.

A *source* is the atom of The Few. Each source declares how to discover new items
(a fetch strategy) and where it lives. The list is meant to stay small and curated
by hand — that editorial taste is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import paths

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]

# Repo-relative fallbacks (dev convenience) checked after the data home.
DEFAULT_CONFIG_NAMES = ("config/sources.toml", "sources.toml")

# Written to the data home by `the-few setup` when no source list exists yet.
DEFAULT_SOURCES_TOML = """\
# The Few — your curated source list.
#
# The atom is a *source*: a publication or org blog that shares high-signal content
# publicly, at a steady cadence. Keep this list SMALL and hand-picked — the editorial
# taste is the whole point. Quantity is the enemy; a finite briefing is the feature.
#
# fetch strategies:
#   html_list  — scrape a listing page for links containing `link_pattern`
#   sitemap    — pull URLs from a sitemap (best when it carries <lastmod> dates)

[[sources]]
name = "Claude Blog"
slug = "claude-blog"
url = "https://claude.com/blog"
fetch = "html_list"
link_pattern = "/blog/"
base = "https://claude.com"
tags = ["ai", "engineering"]
"""


@dataclass
class Source:
    """One curated publication/feed."""

    name: str
    slug: str
    url: str
    # How to discover items: "html_list" scrapes a listing page for article links;
    # "rss" parses a feed (reserved for future sources).
    fetch: str = "html_list"
    # For html_list: the substring an <a href> must contain to count as an article.
    # For sitemap: the path prefix a URL's path must start with (e.g. "/blog/").
    link_pattern: str = ""
    base: str = ""
    # For sitemap: the sitemap URL (defaults to <origin>/sitemap.xml).
    sitemap_url: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def origin(self) -> str:
        """Origin used to resolve relative links (falls back to the source URL)."""
        if self.base:
            return self.base.rstrip("/")
        # Derive scheme://host from the listing URL.
        from urllib.parse import urlsplit

        parts = urlsplit(self.url)
        return f"{parts.scheme}://{parts.netloc}"


def find_config(explicit: str | Path | None = None) -> Path:
    """Locate the sources TOML, raising a helpful error if it's missing.

    Resolution order: explicit path → ``~/.the-few/sources.toml`` → repo-relative
    fallbacks (dev convenience).
    """
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"Source list not found: {path}")
        return path
    candidates = [paths.sources_path(), *(Path(n) for n in DEFAULT_CONFIG_NAMES)]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No source list found. Run `the-few setup` to create one at "
        f"{paths.sources_path()}."
    )


def load_sources(path: str | Path | None = None) -> list[Source]:
    """Parse the TOML source list into Source objects."""
    config_path = find_config(path)
    with config_path.open("rb") as fh:
        data = tomllib.load(fh)

    sources: list[Source] = []
    for raw in data.get("sources", []):
        sources.append(
            Source(
                name=raw["name"],
                slug=raw["slug"],
                url=raw["url"],
                fetch=raw.get("fetch", "html_list"),
                link_pattern=raw.get("link_pattern", ""),
                base=raw.get("base", ""),
                sitemap_url=raw.get("sitemap_url", ""),
                tags=raw.get("tags", []),
            )
        )
    if not sources:
        raise ValueError(f"{config_path} contains no [[sources]] entries.")
    return sources
