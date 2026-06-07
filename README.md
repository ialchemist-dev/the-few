# The Few

> "Never in the field of human conflict was so much owed by so many to so few." — Churchill

A gate between you and the firehose. Instead of streaming endless low-signal
candidates (LinkedIn, YouTube, TikTok), you curate a few sources that publish
valuable content publicly, get a short **title-only** list of what's new, keep the
handful worth your attention, and dismiss the rest forever. Detail loads only when
you ask for it. The scarce thing is your attention — so the gate is cheap by design.

The atom is a **source**, not a person. (Following people for their best thinking
fails — perspective increasingly hides behind paywalls. Publications and orgs, by
contrast, publish high-signal content publicly, at a steady cadence.)

## How it works

```
brief (titles only) → keep / dismiss → list (your kept items) → open (detail on demand)
```

The triage state machine is the whole point:

```
new ──(you keep it)──▶ interested   (reading list; persists)
    ──(you don't)────▶ dismissed     (archived; never shown again)
```

Default flow touches **no LLM** — `brief` shows titles, dates, and links. The only
paid step is `open --summary`, and it runs only on an item you chose to keep.

## Setup

```bash
pip install -e .       # or: pipx install the-few
the-few setup          # creates ~/.the-few/ with a starter source list + database
```

Your data and source list live in `~/.the-few/` (override with `THE_FEW_HOME`), not
in the repo — so nothing personal is ever committed. Edit `~/.the-few/sources.toml`
to curate your sources. No API key is needed for the core flow; a key is only
required for `open --summary`.

## Usage

```bash
the-few brief          # fetch new items; show today's numbered title list
the-few keep 1 3 5     # keep those (→ reading list); dismiss the rest of the brief
the-few list           # show your reading list (kept items)
the-few open 2         # read item 2 in full
the-few open 2 --summary   # ...or get an LLM summary (needs a key)
the-few say            # read the current titles aloud (macOS `say`)
the-few done 2         # archive item 2 from the reading list
the-few sources        # list your curated sources
```

`brief` prints to stdout, progress to stderr. Numbers refer to the last
`brief`/`list` you ran, so `keep 1 3` / `open 2` always mean "from what I just saw".

### Options

- `--max-new N` — cap new items ingested per source per run (default 5).
- `--show N` — daily cap on items shown in a brief (default 30).
- `--db PATH`, `--config PATH` — override the SQLite store / source list locations.

### Summaries (optional, `open --summary`)

Uses **DeepSeek** by default (cheap, OpenAI-compatible). Configure via env:

- `DEEPSEEK_API_KEY` (or `THE_FEW_API_KEY`) — your key.
- `THE_FEW_MODEL` — default `deepseek-chat` (try `deepseek-reasoner` for R1).
- `THE_FEW_BASE_URL` — default `https://api.deepseek.com`. Since it's just an
  OpenAI-compatible endpoint, you can point this (and `THE_FEW_MODEL`) at any
  compatible provider — OpenAI, a local Ollama, etc.

## Status

v0: the **title-first attention gate** — `brief → keep → list → open` — works end to
end over one source, with on-demand detail and summaries. Next: voice briefing (read
the titles aloud, triage by reply) and more sources (RSS / sitemap discovery). See
`THE_FEW_PLAN.md` for the broader vision.
