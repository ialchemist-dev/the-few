#!/home/hatch/workspace/.venv/bin/python
"""ingest.py — fetch new items from each source in sources.yaml.

Reads sources.yaml, fetches items newer than the per-source watermark in
data/state.json, writes data/units/YYYY-MM-DD.json, advances watermarks.

Usage: python3 scripts/ingest.py [--date YYYY-MM-DD] [--config sources.yaml]
"""
import argparse, json, sys, os
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts", "lib"))

def load_yaml(path):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def load_state(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"sources": {}}

def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

FETCHERS = {}

def register(typ):
    def deco(fn):
        FETCHERS[typ] = fn
        return fn
    return deco

@register("rss")
def fetch_rss(source, since_id, log):
    import feedparser
    feed = feedparser.parse(source["feed_url"])
    items = []
    for e in feed.entries:
        uid = e.get("id") or e.get("link")
        if since_id and uid == since_id:
            break
        items.append({
            "id": f"rss:{uid}",
            "source": source["name"],
            "channel": source["channel"],
            "title": e.get("title", ""),
            "url": e.get("link", ""),
            "published_at": e.get("published", ""),
            "body": (e.get("summary", "") or "")[:4000],
            "kind": "article",
        })
    return items

@register("youtube")
def fetch_youtube(source, since_id, log):
    """Transcripts via youtube-transcript-api; yt-dlp fallback on 429/IP-block."""
    from youtube_transcript_api import YouTubeTranscriptApi
    import yt_dlp
    handle = source["handle"]
    items = []
    # Resolve latest videos via yt-dlp (flat playlist, no download)
    url = f"https://www.youtube.com/@{handle}/videos"
    ydl_opts = {"extract_flat": True, "quiet": True, "playlistend": 10,
                "extractor_args": {"youtube": {"player_client": ["android"]}}}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as ex:
        log(f"[youtube:{handle}] listing failed: {ex}")
        return items
    for v in (info.get("entries") or []):
        vid = v.get("id")
        if not vid or (since_id and f"yt:{vid}" == since_id):
            break
        transcript = ""
        try:
            fetched = YouTubeTranscriptApi().fetch(vid, languages=["en", "zh-Hans", "zh-Hant"])
            transcript = " ".join(s.text for s in fetched)
        except Exception as ex:
            log(f"[youtube:{handle}] transcript failed for {vid}: {ex}")
        items.append({
            "id": f"yt:{vid}",
            "source": source["name"],
            "channel": source["channel"],
            "title": v.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "published_at": "",
            "body": transcript[:12000],
            "kind": "video",
        })
    return items

@register("blog")
def fetch_blog(source, since_id, log):
    if source.get("feed_url"):
        return fetch_rss({**source, "feed_url": source["feed_url"]}, since_id, log)
    log(f"[blog:{source['name']}] no feed_url; HTML extraction not implemented in v0.1")
    return []

@register("x")
def fetch_x(source, since_id, log):
    log(f"[x:{source['name']}] auth-gated in v0.1 — skipped (see references/auth.md)")
    return []

@register("linkedin")
def fetch_linkedin(source, since_id, log):
    log(f"[linkedin:{source['name']}] auth-gated in v0.1 — skipped (see references/auth.md)")
    return []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--config", default=os.path.join(REPO, "sources.yaml"))
    args = ap.parse_args()

    def log(msg):
        print(msg, flush=True)

    if not os.path.exists(args.config):
        log(f"missing {args.config} — copy examples/sources.yaml first")
        sys.exit(1)

    cfg = load_yaml(args.config)
    state_path = os.path.join(REPO, "data", "state.json")
    state = load_state(state_path)

    known_types = {"rss", "youtube", "blog", "x", "linkedin"}
    all_items = []
    for src in cfg.get("sources", []):
        if not src.get("enabled", True):
            continue
        if src["type"] not in known_types:
            log(f"unknown source type '{src['type']}' for {src['name']} — fix sources.yaml")
            sys.exit(2)
        wm = state["sources"].get(src["name"], {})
        since_id = wm.get("last_item_id")
        try:
            items = FETCHERS[src["type"]](src, since_id, log)
        except Exception as ex:
            log(f"[{src['type']}:{src['name']}] fetcher crashed: {ex} — skipped")
            items = []
        # cap per source
        items = items[:src.get("max_items_per_day", 5)]
        if items:
            state["sources"][src["name"]] = {
                "last_item_id": items[0]["id"],
                "last_run": datetime.now(timezone.utc).isoformat(),
            }
        all_items.extend(items)
        log(f"[{src['name']}] {len(items)} new item(s)")

    out_path = os.path.join(REPO, "data", "units", f"{args.date}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_items, f, indent=2, ensure_ascii=False)
    save_state(state_path, state)
    log(f"wrote {len(all_items)} unit(s) → {out_path}")

if __name__ == "__main__":
    main()
