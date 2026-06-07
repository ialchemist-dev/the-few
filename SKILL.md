---
name: the-few
description: >
  A finite, title-first attention gate over a few curated sources. Use when the user
  asks "what's new in my feeds / blogs", "what am I interested in", "anything I
  haven't read", "read me my headlines", wants to keep/dismiss/read an item, add a
  source, or set up a scheduled briefing. Default flow shows titles only; full text
  and LLM summaries load on demand.
version: 0.1.0
metadata:
  openclaw:
    emoji: "📡"
    requires:
      bins: [python3]
    anyBins: [pipx, pip3, pip]
    os: [macos, linux]
    envVars:
      - name: THE_FEW_HOME
        required: false
        description: Data directory (default ~/.the-few)
      - name: DEEPSEEK_API_KEY
        required: false
        description: Enables LLM summaries (`open --summary`); the core flow needs no key
---

## What The Few is

A gate between the user and the firehose. They curate a few high-signal sources;
The Few shows a short list of **what's new** (source · title · link), lets them
**keep** the few worth their attention and **dismiss** the rest, and loads full
text or an LLM summary only **on demand**. The scarce thing is their attention.

State machine per item: `new → interested (kept) / dismissed`. Opening an item
marks it `read`. "Interested but unread" is the user's live reading list.

Data lives in `~/.the-few/` (the database + their `sources.toml`), never in the repo.

## Routing user intent

| User says | Action |
|-----------|--------|
| "what's new", "anything new in my blogs/feeds" | `the-few brief` to fetch, then `the-few query --status new --json` to read the result |
| "what am I interested in", "my reading list" | `the-few query --status interested --json` |
| "what haven't I read", "anything unread" | `the-few query --status interested --unread --json` |
| "I'm interested in / keep #ID" | `the-few mark <id> --interested` |
| "dismiss / not interested #ID" | `the-few mark <id> --dismissed` |
| "read me / open / summarize #ID" | `the-few open --id <id> --summary` (or without `--summary` for full text) |
| "mark #ID read" | `the-few mark <id> --read` |
| "read the headlines aloud" | `the-few say` (after a `brief` or `list`) |
| "what sources do I follow" | `the-few sources` |
| "add a source" | Edit `~/.the-few/sources.toml` (see Adding a source below), then `the-few brief` |
| "my daily briefing" | See Digest below |

**Always pass `--json` for programmatic reads** and act on items by their stable
`id` (from the JSON), not by list position. The JSON shape per item is:
`{id, source, source_name, title, link, published, status, read}`.

## Digest (what to send the user)

A good briefing = new items + things they kept but haven't read:

```bash
the-few brief --quiet                              # fetch the latest
the-few query --status new --json                  # newly surfaced
the-few query --status interested --unread --json  # kept, not yet read
```

Render these as a short chat message (source · title · link). Offer to `open`
anything they want in full or summarized. For a scheduled briefing, run this on a
cron and post the result to the user's chat.

## Adding a source

Append a `[[sources]]` block to `~/.the-few/sources.toml`:

```toml
[[sources]]
name = "Example Blog"
slug = "example"
url = "https://example.com/blog"
fetch = "html_list"      # or "sitemap" if the sitemap has <lastmod> dates
link_pattern = "/blog/"
base = "https://example.com"
tags = ["topic"]
```

Then `the-few brief` picks it up. Keep the list small — curation is the point.

## Setup

If the `the-few` command is missing or `~/.the-few/` doesn't exist:

1. Install the CLI: `pipx install the-few` (preferred on macOS), or `pip3 install
   the-few` / `pip install the-few`.
2. Run `the-few setup` (creates `~/.the-few/` with a starter source list + database).
3. Optional: export `DEEPSEEK_API_KEY` to enable `open --summary`.

## Command reference

- `the-few brief [--show N] [--quiet]` — fetch new items; print the numbered title list
- `the-few query [--status new|interested|dismissed] [--unread] [--source SLUG] [--contains TEXT] [--since YYYY-MM-DD] [--limit N] [--json]` — read interface
- `the-few mark <id...> [--interested|--dismissed|--read|--unread]` — change state by id
- `the-few open (<pos> | --id <id>) [--summary]` — read full text or LLM summary (marks read)
- `the-few keep <pos...>` / `the-few done <pos...>` — interactive triage by list position
- `the-few list` — the reading list (kept items)
- `the-few say [--voice NAME] [--rate WPM] [--out FILE]` — read current titles aloud
- `the-few sources` — list curated sources
