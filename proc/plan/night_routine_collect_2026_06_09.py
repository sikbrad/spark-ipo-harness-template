#!/usr/bin/env python3
"""Collect raw sources for the 2026-06-09 night routine.

This is intentionally a date-scoped operations script. It reads existing
workspace API helpers, writes only daily raw artifacts, and records per-source
failures without stopping the whole routine.
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, "proc/lib")

DAY = "2026-06-09"
NEXT_DAY = "2026-06-10"
RAW = Path(f"data/daily/{DAY}/raw")
RAW.mkdir(parents=True, exist_ok=True)

TASK_DS = "312bfde5-d1da-4f7d-94a6-b73c912eb042"


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    return value


def write_json(name: str, payload: Any) -> None:
    (RAW / name).write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def rt_to_text(rt: list[dict]) -> str:
    return "".join((r.get("plain_text") or "") for r in (rt or []))


def title_of(page: dict) -> str:
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return rt_to_text(prop.get("title") or [])
    return ""


def text_of_block(block: dict) -> str:
    btype = block.get("type")
    payload = block.get(btype) or {}
    return rt_to_text(payload.get("rich_text") or [])


def simple_block_tree(client: Any, block_id: str, depth: int = 0) -> list[dict]:
    if depth > 3:
        return []
    out = []
    for block in client.blocks_children_iter(block_id):
        row = {
            "id": block.get("id"),
            "type": block.get("type"),
            "text": text_of_block(block),
            "has_children": bool(block.get("has_children")),
        }
        if block.get("has_children"):
            row["children"] = simple_block_tree(client, block["id"], depth + 1)
        out.append(row)
    return out


def to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_cmd(name: str, cmd: list[str], timeout: int = 120) -> bool:
    try:
        proc = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        (RAW / f"{name}.log").write_text(to_text(exc.stdout), encoding="utf-8")
        (RAW / f"{name}.err").write_text(to_text(exc.stderr), encoding="utf-8")
        ERRORS.append({
            "source": name,
            "status": "partial_timeout",
            "detail": f"Timed out after {timeout}s.",
        })
        return False
    (RAW / f"{name}.log").write_text(proc.stdout or "", encoding="utf-8")
    (RAW / f"{name}.err").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:500]
        ERRORS.append({"source": name, "status": "failed", "detail": detail})
        return False
    return True


def collect_notion_live() -> None:
    from notion_api import NotionClient

    client = NotionClient.from_cache()
    search = client.request(
        "POST",
        "/search",
        json={
            "query": f"DailyJot {DAY}",
            "page_size": 10,
            "filter": {"property": "object", "value": "page"},
        },
    )
    jot_pages = []
    for page in search.get("results", []):
        title = title_of(page)
        if DAY not in title:
            continue
        full = client.pages_retrieve(page["id"])
        jot_pages.append({
            "id": full.get("id"),
            "url": full.get("url"),
            "title": title_of(full),
            "properties": full.get("properties") or {},
            "blocks": simple_block_tree(client, full["id"]),
        })
    write_json("notion-jot-live.json", jot_pages)
    write_json("notion-jot.json", jot_pages)

    tasks = []
    for page in client.data_sources_query_iter(TASK_DS):
        props = page.get("properties") or {}
        status = ((props.get("Status") or {}).get("status") or {}).get("name") or ""
        act = (props.get("ActDate") or {}).get("date")
        due = (props.get("DueDate") or {}).get("date")
        last_edited = page.get("last_edited_time") or ""
        include = False
        for date_obj in (act, due):
            if not date_obj:
                continue
            start = date_obj.get("start") or ""
            if start.startswith(DAY):
                include = True
            if date_obj is due and start and start[:10] <= DAY and status not in {"Done", "Close", "Someday"}:
                include = True
        if status in {"Ready", "Todo", "Doing", "Wait", "Schedule"}:
            include = True
        if status == "Done" and last_edited.startswith(DAY):
            include = True
        if not include:
            continue
        tasks.append({
            "id": page.get("id"),
            "url": page.get("url"),
            "title": title_of(page),
            "status": status,
            "act_date": act,
            "due_date": due,
            "last_edited_time": last_edited,
            "created_time": page.get("created_time"),
            "areas": (props.get("Areas") or {}).get("relation") or [],
            "properties": props,
        })
    write_json("notion-tasks-live.json", tasks)
    write_json("notion-tasks.json", tasks)


def collect_notion_edited_from_state() -> None:
    db = Path("data/db/notion_state.sqlite")
    if not db.exists():
        write_json("notion-edited.json", [])
        return
    out = []
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT kind,id,title,last_edited_time FROM notion_object "
            "WHERE last_edited_time LIKE ? AND (kind='page' OR kind='database') "
            "ORDER BY last_edited_time DESC",
            (f"{DAY}T%",),
        ).fetchall()
    for kind, oid, title, last_edited_time in rows:
        out.append({
            "kind": kind,
            "id": oid,
            "title": title,
            "last_edited_time": last_edited_time,
            "page_json": f"data/notion/dump/pages/{oid}.json" if kind == "page" else None,
            "blocks_json": f"data/notion/dump/blocks/{oid}.json" if kind == "page" else None,
        })
    write_json("notion-edited.json", out)


def collect_raindrop_day() -> None:
    out = []
    for p in sorted(Path("data/raindrop/dump/raindrops").glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        dates = [data.get("created") or "", data.get("lastUpdate") or ""]
        if any(str(v).startswith(DAY) for v in dates):
            out.append(data)
    out.sort(key=lambda d: d.get("lastUpdate") or d.get("created") or "", reverse=True)
    write_json("raindrop.json", out)


def collect_outlook() -> None:
    from outlook import KST, MailClient

    since = datetime.fromisoformat(f"{DAY}T00:00:00+09:00")
    until = since + timedelta(days=1)
    client = MailClient()
    errors = []
    payload = {"day": DAY, "timezone": "Asia/Seoul", "inbox": [], "sent": [], "errors": errors}
    for folder, key in [("inbox", "inbox"), ("sentitems", "sent")]:
        try:
            rows = client.list_messages(folder=folder, since=since, until=until, top=80)
            payload[key] = rows
        except Exception as exc:
            errors.append({"folder": folder, "error": repr(exc)})
    write_json("outlook.json", payload)
    write_json("outlook-errors.json", errors)


def collect_teams() -> None:
    from msgraph import GraphClient
    from teams_graph import KST, channel_map, channel_posts, chat_list, chat_messages, find_channel_graph

    since = datetime.fromisoformat(f"{DAY}T00:00:00+09:00")
    until = since + timedelta(days=1)
    graph = GraphClient()

    chat_rows = []
    chat_errors = []
    for chat in chat_list(graph, top=50):
        last_ts = chat.get("last_ts")
        if last_ts and last_ts < since:
            break
        cid = chat.get("chat_id")
        if not cid:
            continue
        try:
            messages = chat_messages(graph, cid, since=since, until=until, max_pages=10)
            if messages:
                chat_rows.append({"chat": chat, "messages": messages})
        except Exception as exc:
            chat_errors.append({"chat": chat, "error": repr(exc)})
    write_json("teams-chats.json", chat_rows)

    cmap = channel_map(graph, cache_path=str(RAW / "teams-channel-map.json"))
    standup_matches = find_channel_graph(graph, "standup-daily-ax", cache=cmap)
    if standup_matches:
        ch = standup_matches[0]
        try:
            threads = channel_posts(
                graph,
                ch["team_id"],
                ch["channel_id"],
                since=since,
                until=until,
                include_replies=True,
                max_pages=3,
            )
            write_json("teams-standup.json", {
                "source": "msgraph.channel_posts",
                "channel_query": "standup-daily-ax",
                "day": DAY,
                **ch,
                "threads": threads,
            })
        except Exception as exc:
            write_json("teams-standup.json", {
                "source": "msgraph.channel_posts",
                "channel_query": "standup-daily-ax",
                "day": DAY,
                **ch,
                "error": repr(exc),
                "threads": [],
            })
            chat_errors.append({"source": "teams_standup", "error": repr(exc), "channel": ch})
    else:
        write_json("teams-standup.json", {"day": DAY, "channel_query": "standup-daily-ax", "threads": [], "error": "channel not found"})

    channel_rows = []
    channel_errors = []
    mention_re = re.compile(r"백인식|Brad|인식")
    for ch in cmap:
        try:
            threads = channel_posts(
                graph,
                ch["team_id"],
                ch["channel_id"],
                since=since,
                until=until,
                include_replies=True,
                max_pages=2,
            )
            kept = []
            for thread in threads:
                items = [thread.get("parent") or {}, *(thread.get("replies") or [])]
                if any((m.get("who") or "").startswith("백인식") or mention_re.search(m.get("text") or "") for m in items):
                    kept.append(thread)
            if kept:
                channel_rows.append({"channel": ch, "threads": kept})
        except Exception as exc:
            channel_errors.append({"channel": ch, "error": repr(exc)})
            channel_rows.append({"channel": ch, "error": repr(exc), "threads": []})
    write_json("teams-channels.json", channel_rows)
    write_json("teams-errors.json", {"chats": chat_errors, "channels": channel_errors})
    if channel_errors:
        ERRORS.append({
            "source": "teams_channels",
            "status": "partial",
            "detail": f"{len(channel_errors)} channel reads failed; standup/chat collection still completed.",
            "items": channel_errors[:10],
        })


def collect_local_audio_candidates() -> None:
    suffixes = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg"}
    compact = DAY[2:4] + DAY[5:7] + DAY[8:10]
    rows = []
    for path in Path(".").rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        s = str(path)
        if "/proc/archive/" in s:
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
        except Exception:
            mtime = ""
        if compact in path.name or DAY in path.name or mtime == DAY:
            rows.append(s)
    (RAW / "local-audio-candidates.txt").write_text("\n".join(rows), encoding="utf-8")


ERRORS: list[dict] = []


def main() -> int:
    collect_local_audio_candidates()

    if "--skip-notion-dump" in sys.argv:
        ERRORS.append({
            "source": "notion-dump",
            "status": "partial_timeout",
            "detail": "Skipped on resume after the first 300s Notion dump timeout; live Notion snapshots and current local state were used.",
        })
    else:
        run_cmd(
            "notion-dump",
            [
                "python3",
                "proc/lib/notion_dump.py",
                "dump",
                "--root",
                "e0a658bf0f8d4e6384c6903940c7e7a9",
                "--root",
                "bd198b22ef9f44618c2382ce45bbf7b0",
                "--out",
                "data/notion/dump",
            ],
            timeout=300,
        )
    try:
        collect_notion_live()
    except Exception as exc:
        ERRORS.append({"source": "notion_live", "status": "failed", "detail": repr(exc)})
        write_json("notion-jot.json", [])
        write_json("notion-tasks.json", [])
    collect_notion_edited_from_state()

    run_cmd("raindrop-dump", ["python3", "proc/lib/raindrop_dump.py", "dump"], timeout=240)
    collect_raindrop_day()

    for account in ["bispro89", "sikbrad"]:
        run_cmd(
            f"gcal-{account}",
            [
                "python3",
                "proc/lib/gcal_api.py",
                "events",
                "--account",
                account,
                "--since",
                DAY,
                "--until",
                DAY,
                "--out",
                str(RAW / f"gcal-{account}.json"),
            ],
            timeout=120,
        )
        run_cmd(
            f"gmail-{account}",
            [
                "python3",
                "proc/lib/gmail_api.py",
                "search",
                "--account",
                account,
                "--q",
                f"after:{DAY.replace('-', '/')} before:{NEXT_DAY.replace('-', '/')} -category:promotions -category:social",
                "--max",
                "80",
                "--out",
                str(RAW / f"gmail-{account}.json"),
            ],
            timeout=180,
        )
        run_cmd(
            f"gdrive-{account}",
            [
                "python3",
                "proc/lib/gdrive_api.py",
                "search",
                "--account",
                account,
                "--q",
                f"modifiedTime > '{DAY}T00:00:00+09:00' and modifiedTime < '{NEXT_DAY}T00:00:00+09:00' and trashed = false",
                "--max",
                "80",
                "--out",
                str(RAW / f"gdrive-{account}.json"),
            ],
            timeout=180,
        )

    try:
        collect_outlook()
    except Exception as exc:
        ERRORS.append({"source": "outlook", "status": "failed", "detail": repr(exc)})
        write_json("outlook.json", [])
        write_json("outlook-errors.json", [{"error": repr(exc)}])

    try:
        collect_teams()
    except Exception as exc:
        ERRORS.append({"source": "teams", "status": "failed", "detail": repr(exc)})
        write_json("teams-chats.json", [])
        write_json("teams-channels.json", [])
        write_json("teams-standup.json", {"day": DAY, "threads": [], "error": repr(exc)})
        write_json("teams-errors.json", [{"error": repr(exc)}])

    run_cmd("atlassian", ["python3", "proc/lib/daily_atlassian.py", DAY], timeout=180)

    write_json("source-errors.json", ERRORS)
    print(json.dumps({"day": DAY, "errors": len(ERRORS), "raw": str(RAW)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
