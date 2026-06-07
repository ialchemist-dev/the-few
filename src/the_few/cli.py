"""Command-line entry point — a title-first attention gate with triage.

    the-few brief         Fetch new items; show today's numbered title list
    the-few keep 1 3 5    Keep those (→ reading list); dismiss the rest of the brief
    the-few list          Show your reading list (kept items)
    the-few open 2        Read item 2 in full (--summary for an LLM summary)
    the-few done 2        Archive item 2 from the reading list
    the-few sources       List your curated sources

Default flow is cheap (titles only). An LLM is touched only by `open --summary`,
and only for an item you chose to keep.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .brief import (
    DEFAULT_MAX_NEW,
    DEFAULT_SHOW,
    ingest_new,
    keep,
    render_items,
    todays_heading,
)
from . import paths
from .config import DEFAULT_SOURCES_TOML, Source, load_sources
from .db import DISMISSED, INTERESTED, NEW, Store


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _names(sources: list[Source]) -> dict[str, str]:
    return {s.slug: s.name for s in sources}


def _item_dict(row, name_by_slug: dict[str, str]) -> dict:
    """Stable, machine-readable shape of an item — the skill/agent contract."""
    return {
        "id": row["id"],
        "source": row["source_slug"],
        "source_name": name_by_slug.get(row["source_slug"], row["source_slug"]),
        "title": row["title"],
        "link": row["link"],
        "published": row["published"],
        "status": row["status"],
        "read": row["read_at"] is not None,
    }


def cmd_brief(args: argparse.Namespace) -> int:
    sources = load_sources(args.config)
    log = _noop if args.quiet else _log
    with Store(args.db) as store:
        ingest_new(store, sources, max_new_per_source=args.max_new, log=log)
        rows = store.items_by_status(NEW, limit=args.show)
        store.record_view([r["id"] for r in rows])
        footer = (
            "keep what's worth your attention:   the-few keep 1 4\n"
            "read one in full:                   the-few open 2\n"
            "(items you don't keep are dismissed and won't return)"
        )
        print(render_items(todays_heading(len(rows), "new"), rows, _names(sources), footer=footer))
    return 0


def cmd_keep(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        kept, dismissed = keep(store, args.positions)
    if kept:
        print(f"kept {len(kept)}:")
        for t in kept:
            print(f"  ✓ {t}")
    if dismissed:
        print(f"dismissed {len(dismissed)} from this brief.")
    if not kept:
        print("nothing kept (check the numbers against your last brief).")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    sources = load_sources(args.config)
    with Store(args.db) as store:
        rows = store.items_by_status(INTERESTED)
        store.record_view([r["id"] for r in rows])
        footer = "read one in full:  the-few open 2\narchive one:       the-few done 2"
        print(
            render_items(
                todays_heading(len(rows), "kept"), rows, _names(sources), footer=footer
            )
        )
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    sources = load_sources(args.config)
    if args.id is None and args.position is None:
        print("give an item: `the-few open 2` (view position) or `--id 12`.", file=sys.stderr)
        return 2
    with Store(args.db) as store:
        item = store.get_item(args.id) if args.id is not None else store.view_item(args.position)
        if item is None:
            ref = f"id {args.id}" if args.id is not None else f"position {args.position}"
            print(
                f"no item at {ref}. Run `the-few brief`/`list`, or check the id.",
                file=sys.stderr,
            )
            return 1

        text = item["full_text"] or ""
        if not text:  # cache miss (e.g. future RSS-only source) — fetch on demand
            from .fetch import fetch_article

            article = fetch_article(item["link"], fallback_title=item["title"])
            text = article.text
            store.set_full_text(item["id"], text)

        source = _names(sources).get(item["source_slug"], item["source_slug"])
        print(f"# {item['title']}")
        print(f"[{source}] {item['published'] or ''}  {item['link']}")
        print("─" * 52)

        if args.summary:
            print(_summarize_item(store, item, source))
        else:
            print(text)

        store.set_read(item["id"], True)  # opening an item marks it read
    return 0


def _summarize_item(store, item, source_name: str) -> str:
    """Return a cached or freshly generated LLM summary for an item."""
    if item["summary"]:
        return item["summary"]
    from .summarize import is_auth_error, summarize_article

    try:
        summary = summarize_article(
            source_name=source_name,
            title=item["title"] or "",
            text=item["full_text"] or "",
        )
    except Exception as exc:
        if is_auth_error(exc):
            return (
                "(summary unavailable — set DEEPSEEK_API_KEY to enable summaries)"
            )
        return f"(summary failed: {exc})"
    store.set_summary(item["id"], summary)
    return summary


def cmd_say(args: argparse.Namespace) -> int:
    from .voice import build_spoken, have_say, speak

    sources = load_sources(args.config)
    with Store(args.db) as store:
        rows = store.view_items()
    if not rows:
        print("nothing to read — run `the-few brief` or `the-few list` first.", file=sys.stderr)
        return 1

    script = build_spoken(rows, _names(sources))
    if args.text or (not have_say() and not args.out):
        print(script)
        if not have_say():
            print("(macOS `say` not found — printed the script instead.)", file=sys.stderr)
        return 0
    speak(script, voice=args.voice, rate=args.rate, out_file=args.out)
    if args.out:
        print(f"saved audio to {args.out}")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    from .db import DISMISSED

    with Store(args.db) as store:
        archived = 0
        for pos in args.positions:
            item = store.view_item(pos)
            if item is not None:
                store.set_status(item["id"], DISMISSED)
                archived += 1
    print(f"archived {archived}.")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Read interface: filter items, output JSON (for agents) or a readable list."""
    sources = load_sources(args.config)
    names = _names(sources)
    with Store(args.db) as store:
        rows = store.query_items(
            status=args.status,
            unread=(True if args.unread else None),
            source=args.source,
            contains=args.contains,
            since=args.since,
            limit=args.limit,
        )
    if args.json:
        print(json.dumps([_item_dict(r, names) for r in rows], ensure_ascii=False, indent=2))
        return 0
    # Human output keys on the stable item id (so `mark <id>` works without a view).
    print(f"📡  THE FEW · {len(rows)} match" + ("es" if len(rows) != 1 else ""))
    print("─" * 52)
    for row in rows:
        src = names.get(row["source_slug"], row["source_slug"])
        flags = row["status"] + ("" if row["read_at"] else ", unread")
        print(f"#{row['id']:<4} [{src}] {row['title']}")
        print(f"      {row['published'] or ''} · {row['link']}  ({flags})")
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    """Write interface: change item state by stable id (agent-friendly)."""
    if not any([args.interested, args.dismissed, args.read, args.unread]):
        print("specify an action: --interested / --dismissed / --read / --unread",
              file=sys.stderr)
        return 2
    with Store(args.db) as store:
        updated = 0
        for item_id in args.ids:
            if store.get_item(item_id) is None:
                continue
            if args.interested:
                store.set_status(item_id, INTERESTED)
            if args.dismissed:
                store.set_status(item_id, DISMISSED)
            if args.read:
                store.set_read(item_id, True)
            if args.unread:
                store.set_read(item_id, False)
            updated += 1
    print(f"updated {updated} item(s).")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    """Create the data home, seed a source list, and initialize the database."""
    home = paths.ensure_home()
    print(f"data home: {home}")

    sources_file = paths.sources_path()
    if sources_file.exists():
        print(f"sources:   {sources_file} (exists, left as-is)")
    else:
        sources_file.write_text(DEFAULT_SOURCES_TOML)
        print(f"sources:   {sources_file} (created — edit to add your own)")

    with Store(args.db) as store:
        db_file = store.path
    print(f"database:  {db_file} (ready)")
    print("\nNext: `the-few brief` to fetch your first headlines.")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    sources = load_sources(args.config)
    for s in sources:
        tags = f"  [{', '.join(s.tags)}]" if s.tags else ""
        print(f"{s.slug:16} {s.name}{tags}")
        print(f"{'':16} {s.url}  (fetch: {s.fetch})")
    return 0


def _noop(_: str) -> None:
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="the-few",
        description="A finite, title-first attention gate over a few curated sources.",
    )
    parser.add_argument("--version", action="version", version=f"the-few {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config", default=None, help="Path to the source list (default: config/sources.toml)."
    )
    common.add_argument(
        "--db", default=None, help=f"SQLite store path (default: {paths.db_path()})."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_brief = sub.add_parser("brief", parents=[common], help="Fetch new items; show titles.")
    p_brief.add_argument("--max-new", type=int, default=DEFAULT_MAX_NEW,
                         help=f"Max new items per source per run (default: {DEFAULT_MAX_NEW}).")
    p_brief.add_argument("--show", type=int, default=DEFAULT_SHOW,
                         help=f"Max items shown (daily cap, default: {DEFAULT_SHOW}).")
    p_brief.add_argument("--quiet", action="store_true", help="Suppress progress on stderr.")
    p_brief.set_defaults(func=cmd_brief)

    p_keep = sub.add_parser("keep", parents=[common],
                            help="Keep items from the last brief; dismiss the rest.")
    p_keep.add_argument("positions", nargs="+", type=int, help="Item numbers, e.g. 1 3 5.")
    p_keep.set_defaults(func=cmd_keep)

    p_list = sub.add_parser("list", parents=[common], help="Show your reading list (kept items).")
    p_list.set_defaults(func=cmd_list)

    p_open = sub.add_parser("open", parents=[common], help="Read an item in full (marks it read).")
    p_open.add_argument("position", type=int, nargs="?", help="Item number from the last brief/list.")
    p_open.add_argument("--id", type=int, default=None, help="Open by stable item id instead.")
    p_open.add_argument("--summary", action="store_true", help="LLM summary instead of full text.")
    p_open.set_defaults(func=cmd_open)

    p_query = sub.add_parser("query", parents=[common],
                             help="Query items (JSON for agents, or a readable list).")
    p_query.add_argument("--status", choices=[NEW, INTERESTED, DISMISSED], default=None)
    p_query.add_argument("--unread", action="store_true", help="Only items not yet opened.")
    p_query.add_argument("--source", default=None, help="Filter by source slug.")
    p_query.add_argument("--contains", default=None, help="Title substring match.")
    p_query.add_argument("--since", default=None, help="Published on/after YYYY-MM-DD.")
    p_query.add_argument("--limit", type=int, default=None, help="Max results.")
    p_query.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    p_query.set_defaults(func=cmd_query)

    p_mark = sub.add_parser("mark", parents=[common], help="Change item state by id (for agents).")
    p_mark.add_argument("ids", nargs="+", type=int, help="Item ids, e.g. 12 15.")
    p_mark.add_argument("--interested", action="store_true", help="Add to reading list.")
    p_mark.add_argument("--dismissed", action="store_true", help="Archive.")
    p_mark.add_argument("--read", action="store_true", help="Mark read.")
    p_mark.add_argument("--unread", action="store_true", help="Mark unread.")
    p_mark.set_defaults(func=cmd_mark)

    p_say = sub.add_parser("say", parents=[common], help="Read the current titles aloud (macOS `say`).")
    p_say.add_argument("--text", action="store_true", help="Print the spoken script instead of playing it.")
    p_say.add_argument("--voice", default=None, help="macOS voice name (e.g. Samantha).")
    p_say.add_argument("--rate", type=int, default=None, help="Words per minute (e.g. 180).")
    p_say.add_argument("--out", default=None, help="Save audio to a file instead of playing.")
    p_say.set_defaults(func=cmd_say)

    p_done = sub.add_parser("done", parents=[common], help="Archive items from the reading list.")
    p_done.add_argument("positions", nargs="+", type=int, help="Item numbers, e.g. 2 4.")
    p_done.set_defaults(func=cmd_done)

    p_setup = sub.add_parser("setup", parents=[common],
                             help="Create the data home (~/.the-few), seed sources, init the DB.")
    p_setup.set_defaults(func=cmd_setup)

    p_sources = sub.add_parser("sources", parents=[common], help="List the curated sources.")
    p_sources.set_defaults(func=cmd_sources)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
