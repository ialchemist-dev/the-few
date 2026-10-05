# Script conventions

Every episode is a single-host script. These rules keep scripts
parseable by any TTS backend and pleasant to hear.

## Format

- One speaker. Turn labels are ASCII: `Host: ` (letters, colon, space).
  No full-width punctuation, no missing space — some TTS chunk parsers
  silently drop malformed turns.
- The spoken host name (e.g. 小北) may appear inside dialogue; the
  label itself stays ASCII.
- Complete sentences. No markdown, no emoji, no raw URLs, no citation
  numbers, no stage directions (`[pause]`, `*laughs*`).
- Numbers in natural language ("three", "三家"), not digits, where the
  language reads them aloud awkwardly.

## Structure (per episode)

1. One-sentence open: what today covers, no throat-clearing.
2. One section per source item, newest first. Each section: what
   happened, then the key facts exactly as the source states them.
3. One-sentence close. No recap of the whole episode, no "thanks for
   listening" filler.

## Content rules

- **Content only.** Never mention how the episode was generated, the
  selection logic, or the pipeline's philosophy.
- **Report and summarize — nothing more.** The host is a reporter and
  summarizer of the given updates. No interpretation, no analysis, no
  editorial framing, no "why it matters" — the item speaks for itself.
- **No connections.** Never connect one item to another, never relate
  an item to past coverage or earlier episodes, never synthesize a
  through-line. Each section stands alone.
- **Source-grounded.** Every claim traces to a unit in the digest.
  The composer may compress and restate faithfully, but not invent.
- **No cross-contamination.** A channel's episode uses only that
  channel's units.
- Target length comes from the channel's `max_minutes`; prefer cutting
  a weak item over rushing all of them.

## File layout

```
data/episodes/YYYY-MM-DD/
  <channel>.mp3
  <channel>-script.txt
  <channel>-units.json   # the digest snapshot this episode was built from
```

The `-units.json` snapshot is what makes an episode auditable: given
the script and the snapshot, anyone can check grounding.
