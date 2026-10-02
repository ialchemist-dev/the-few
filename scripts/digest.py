#!/home/hatch/workspace/.venv/bin/python
"""digest.py — dedupe, filter, rank ingested units, group by channel.

Reads data/units/YYYY-MM-DD.json, writes data/digested/YYYY-MM-DD.json:
{channel_id: [units...]}. Pure function of its input — re-runnable.

Usage: python3 scripts/digest.py [--date YYYY-MM-DD]
"""
import argparse, json, os
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = ap.parse_args()

    in_path = os.path.join(REPO, "data", "units", f"{args.date}.json")
    if not os.path.exists(in_path):
        print(f"no units file: {in_path} — run ingest first")
        raise SystemExit(1)
    with open(in_path) as f:
        units = json.load(f)

    seen_urls, seen_titles = set(), set()
    grouped = {}
    for u in units:
        if not (u.get("title") or u.get("body")):
            continue  # empty stub
        url = u.get("url", "")
        title = (u.get("title") or "").strip().lower()
        if url and url in seen_urls:
            continue
        if title and title in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)
        grouped.setdefault(u.get("channel", "main"), []).append(u)

    # newest first where timestamps exist; otherwise keep ingest order
    for ch in grouped:
        grouped[ch].sort(key=lambda u: u.get("published_at", ""), reverse=True)

    out_path = os.path.join(REPO, "data", "digested", f"{args.date}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(grouped, f, indent=2, ensure_ascii=False)
    total = sum(len(v) for v in grouped.values())
    print(f"digested {total} unit(s) into {len(grouped)} channel(s) → {out_path}")

if __name__ == "__main__":
    main()
