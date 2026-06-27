#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "proc/lib/msgraph.py").exists():
            return parent
    raise RuntimeError("repo root with proc/lib/msgraph.py not found")


ROOT = find_repo_root()
sys.path.insert(0, str(ROOT / "proc/lib"))

from msgraph import GraphClient  # noqa: E402
from teams_graph import KST, channel_map, channel_posts, find_channel_graph  # noqa: E402


def day_range(day: str) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(f"{day}T00:00:00").replace(tzinfo=KST)
    return start, start + timedelta(days=1)


def date_iter(start: str, end: str):
    cur = datetime.fromisoformat(start).date()
    last = datetime.fromisoformat(end).date()
    while cur <= last:
        yield cur.isoformat()
        cur += timedelta(days=1)


def serialise_thread(thread: dict) -> dict:
    def msg(m: dict) -> dict:
        return {
            "ts": m["ts"].isoformat() if m.get("ts") else "",
            "who": m.get("who", ""),
            "text": m.get("text", ""),
            "quote": m.get("quote"),
            "id": m.get("id", ""),
            "type": m.get("type", ""),
        }

    return {
        "parent": msg(thread["parent"]),
        "parent_in_window": thread.get("parent_in_window", False),
        "replies": [msg(r) for r in thread.get("replies", [])],
        "reply_total": thread.get("reply_total", 0),
    }


def collect_day(g: GraphClient, channel: dict, day: str, force: bool) -> tuple[Path, bool]:
    out = ROOT / f"data/daily/{day}/raw/teams-standup.json"
    if out.exists() and not force:
        return out, False
    since, until = day_range(day)
    threads = channel_posts(
        g,
        channel["team_id"],
        channel["channel_id"],
        since=since,
        until=until,
        page_size=50,
        max_pages=5,
        include_replies=True,
    )
    payload = {
        "source": "msgraph.channel_posts",
        "channel_query": "standup-daily-ax",
        "team_id": channel["team_id"],
        "team_name": channel.get("team_name", ""),
        "channel_id": channel["channel_id"],
        "channel_name": channel.get("channel_name", ""),
        "day": day,
        "threads": [serialise_thread(t) for t in threads],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, True


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect Teams standup-daily-ax raw by day.")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--channel", default="standup-daily-ax")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    g = GraphClient()
    cache = ROOT / "output/teams-channel-map.json"
    cmap = channel_map(g, cache_path=str(cache))
    hits = find_channel_graph(g, args.channel, cache=cmap)
    if not hits:
        raise SystemExit(f"channel not found: {args.channel}")
    channel = hits[0]

    for day in date_iter(args.start, args.end):
        out, changed = collect_day(g, channel, day, args.force)
        action = "wrote" if changed else "exists"
        print(f"{day}: {action} {out.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from None
