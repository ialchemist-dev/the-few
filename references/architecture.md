# Architecture

## Pipeline

```
┌─────────────┐
│ sources.yaml │  user-owned, the only input that matters
└──────┬──────┘
       │ daily trigger (cron)
       ▼
┌─────────────┐
│    ingest    │  per-source fetchers → raw items
└──────┬──────┘
       │ data/units/YYYY-MM-DD.json
       ▼
┌─────────────┐
│    digest    │  dedupe, filter, rank, group by channel
└──────┬──────┘
       │ data/digested/YYYY-MM-DD.json
       ▼
┌─────────────┐
│   compose    │  prompt template → single-host script
└──────┬──────┘
       │ data/episodes/YYYY-MM-DD/<channel>-script.txt
       ▼
┌─────────────┐
│  synthesize  │  TTS backend → MP3
└─────────────┘
  data/episodes/YYYY-MM-DD/<channel>.mp3
```

Every stage reads the previous stage's output file and writes its own.
Stages are independently re-runnable: `compose` never re-fetches, `ingest`
never re-renders.

## State

`data/state.json` tracks per-source watermarks:

```json
{
  "sources": {
    "3blue1brown": {"last_item_id": "abc123", "last_run": "2026-09-28T07:14:00-06:00"},
    "openai-blog": {"last_item_id": "https://openai.com/...", "last_run": "..."}
  }
}
```

Ingest only fetches items newer than the watermark, then advances it.
A source that fails does not block others; failures are logged to
`data/logs/ingest-YYYY-MM-DD.log` and the run continues.

## Channels

A channel is one episode per day. Sources declare which channel they feed:

```yaml
channels:
  - id: research
    name: "Research Digest"
    language: zh
    voice: default
  - id: personal
    name: "Personal Briefing"
    language: zh
    voice: default
```

Keep channels few. Two is the tested shape (personal vs. research);
one is fine. More than three is a smell — the user's attention is the
scarce resource.

## Source types

| type     | how it fetches                              | auth needed |
|----------|---------------------------------------------|-------------|
| rss      | feedparser on `feed_url`                    | no          |
| youtube  | transcript API, yt-dlp fallback             | no          |
| blog     | RSS if available, else HTML extract         | no          |
| x        | API or login session                        | yes         |
| linkedin | login session                               | yes         |

Auth-gated types degrade gracefully: no credentials → warning in the
log, source skipped, run continues. The pipeline must never fail closed
because one source is unreachable.

## Units

The digest's atomic item. Every ingested item becomes a unit:

```json
{
  "id": "yt:abc123",
  "source": "3Blue1Brown",
  "channel": "research",
  "title": "...",
  "url": "https://...",
  "published_at": "2026-09-27T...",
  "body": "transcript or article text, truncated to N chars",
  "kind": "video|post|article"
}
```

## Design principles

- **Files over services.** State is JSON on disk. Any agent with a
  shell can inspect and repair a run.
- **Prompts over code.** Episode voice lives in
  `references/prompts.md`, not in Python string literals. Changing the
  show's voice never requires a code change.
- **Append-only episodes.** Published episodes are never rewritten.
  A bad episode is superseded by the next day's, not patched.
- **Boring technology.** feedparser, yt-dlp, cron, ffmpeg. The novelty
  is the curation contract, not the stack.
