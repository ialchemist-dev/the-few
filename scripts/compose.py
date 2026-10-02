#!/home/hatch/workspace/.venv/bin/python
"""compose.py — build one single-host script per channel from the digest.

Reads data/digested/YYYY-MM-DD.json + prompt template in
references/prompts.md, writes data/episodes/YYYY-MM-DD/<channel>-script.txt
and <channel>-units.json (the audit snapshot).

This v0.1 renders a deterministic script skeleton from the template
variables. Swap in an LLM call against references/prompts.md "Compose"
template when you want natural voice — the I/O contract stays the same.

Usage: python3 scripts/compose.py [--date YYYY-MM-DD] [--config sources.yaml]
"""
import argparse, json, os, re
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_yaml(path):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def render_skeleton(channel_cfg, units):
    """Deterministic v0.1 composer: one Host: paragraph per unit."""
    lang = channel_cfg.get("language", "en")
    lines = []
    if lang == "zh":
        lines.append(f"Host: 今天的{channel_cfg.get('name', channel_cfg['id'])}，一共 {len(units)} 条更新。")
    else:
        lines.append(f"Host: Today's {channel_cfg.get('name', channel_cfg['id'])}: {len(units)} updates.")
    for u in units:
        src, title = u.get("source", ""), u.get("title", "")
        body = (u.get("body") or "")[:600]
        if lang == "zh":
            lines.append(f"Host: 先看{src}：{title}。{body}")
        else:
            lines.append(f"Host: From {src}: {title}. {body}")
    if lang == "zh":
        lines.append("Host: 以上就是今天的全部内容。")
    else:
        lines.append("Host: That's everything for today.")
    # enforce ASCII "Host: " labels
    out = []
    for ln in lines:
        ln = re.sub(r"^[^:]*:\s*", "Host: ", ln)
        out.append(ln if ln.startswith("Host: ") else "Host: " + ln)
    return "\n\n".join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--config", default=os.path.join(REPO, "sources.yaml"))
    args = ap.parse_args()

    dig_path = os.path.join(REPO, "data", "digested", f"{args.date}.json")
    if not os.path.exists(dig_path):
        print(f"no digested file: {dig_path} — run digest first")
        raise SystemExit(1)
    with open(dig_path) as f:
        grouped = json.load(f)

    channels = {c["id"]: c for c in load_yaml(args.config).get("channels", [])}
    ep_dir = os.path.join(REPO, "data", "episodes", args.date)
    os.makedirs(ep_dir, exist_ok=True)

    for ch_id, units in grouped.items():
        cfg = channels.get(ch_id, {"id": ch_id, "name": ch_id, "language": "en"})
        script = render_skeleton(cfg, units)
        with open(os.path.join(ep_dir, f"{ch_id}-script.txt"), "w") as f:
            f.write(script + "\n")
        with open(os.path.join(ep_dir, f"{ch_id}-units.json"), "w") as f:
            json.dump(units, f, indent=2, ensure_ascii=False)
        print(f"[{ch_id}] script: {len(units)} unit(s) → {ep_dir}/{ch_id}-script.txt")

if __name__ == "__main__":
    main()
