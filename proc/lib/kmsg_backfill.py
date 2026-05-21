"""
kmsg daily backfill orchestrator.

For each chat (excluding openchats/UI artifacts):
- `kmsg read <title> --limit 500 --json`
- bucket messages by date (today as default, hour-rollover heuristic for midnight crossing)
- write/merge `data/kmsg/<chat_id>__<slug>/YYYY-MM-DD.md`
- state SQLite for msg-hash dedup

Run:
    python proc/lib/kmsg_backfill.py snapshot          # 441 chats, today bucket
    python proc/lib/kmsg_backfill.py snapshot --chat "쥬쥬월드"   # 1 chat test
    python proc/lib/kmsg_backfill.py chats             # refresh chat list only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KMSG_DIR = ROOT / "data" / "kmsg"
INDEX_DIR = KMSG_DIR / "_index"
STATE_DB = KMSG_DIR / "_state.sqlite"
EXCLUDES_PATH = INDEX_DIR / "excludes.json"

# UI artifacts kmsg sometimes returns when --limit is small.
DEFAULT_EXCLUDE_TITLES = {
    "My Default Profile",
    "Updated Profiles",
    "Favorites",
    "Friends",
    "Friends with Birthdays",
    "Channel",
    ".",
}
EXCLUDE_TITLE_PATTERNS = [
    re.compile(r"^View more birthdays.*$"),
    re.compile(r"^Channel \d+$"),
]


def slugify(title: str, maxlen: int = 40) -> str:
    s = unicodedata.normalize("NFC", title)
    s = re.sub(r"[\\/:\*\?\"<>\|\r\n\t]+", "_", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:maxlen] or "_"


def init_state(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            chat_id TEXT NOT NULL,
            date TEXT NOT NULL,
            msg_hash TEXT NOT NULL,
            time_raw TEXT,
            author TEXT,
            body TEXT,
            seen_at TEXT NOT NULL,
            PRIMARY KEY (chat_id, msg_hash)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chats_meta (
            chat_id TEXT PRIMARY KEY,
            title TEXT,
            last_fetch_at TEXT,
            last_count INTEGER,
            error TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_chat_date ON messages(chat_id, date)")
    conn.commit()
    return conn


def load_excludes() -> dict:
    """Returns {"titles": set, "patterns": [re], "chat_ids": set}."""
    titles = set(DEFAULT_EXCLUDE_TITLES)
    patterns = list(EXCLUDE_TITLE_PATTERNS)
    chat_ids: set[str] = set()
    if EXCLUDES_PATH.exists():
        data = json.loads(EXCLUDES_PATH.read_text())
        titles |= set(data.get("titles", []))
        patterns.extend(re.compile(p) for p in data.get("title_patterns", []))
        chat_ids |= set(data.get("chat_ids", []))
    return {"titles": titles, "patterns": patterns, "chat_ids": chat_ids}


def is_excluded(chat: dict, excludes: dict) -> bool:
    title = chat.get("title", "")
    if chat.get("chat_id") in excludes["chat_ids"]:
        return True
    if title in excludes["titles"]:
        return True
    for pat in excludes["patterns"]:
        if pat.match(title):
            return True
    return False


def refresh_chats(limit: int = 2000) -> Path:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = INDEX_DIR / f"chats-{ts}.json"
    err = INDEX_DIR / f"chats-{ts}.stderr"
    print(f"[chats] fetching... → {out.name}", flush=True)
    with out.open("wb") as fo, err.open("wb") as fe:
        subprocess.run(
            ["kmsg", "chats", "--limit", str(limit), "--json"],
            check=True, stdout=fo, stderr=fe,
        )
    data = json.loads(out.read_text())
    print(f"[chats] {len(data.get('chats', []))} chats", flush=True)
    return out


def latest_chats_file() -> Path | None:
    files = sorted(INDEX_DIR.glob("chats-*.json"))
    return files[-1] if files else None


def read_chat(title: str, limit: int = 500, deep: bool = False, timeout: int = 15) -> dict | None:
    cmd = ["kmsg", "read", title, "--limit", str(limit), "--json"]
    if deep:
        cmd.append("--deep-recovery")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Kill any lingering kmsg/KakaoTalk child so the next chat starts clean
        return {"error": "timeout"}
    if r.returncode != 0:
        return {"error": f"exit={r.returncode} stderr={(r.stderr or '').strip()[:200]}"}
    if not r.stdout.strip():
        return {"error": "empty-stdout"}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"json: {e}"}


def msg_hash(m: dict) -> str:
    key = f"{m.get('time_raw','')}|{m.get('author','')}|{m.get('body','')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def bucket_date(messages: list[dict], today: date) -> list[tuple[date, dict]]:
    """
    Assign a date to each message.
    Default: today.
    Heuristic: if hour decreases significantly between consecutive messages (e.g.,
    23:xx → 00:xx → 0x:xx), it crossed midnight — push the later half to today,
    earlier half to yesterday. With kmsg's 12h format this is brittle, so
    we conservatively just assign 'today' to all unless we see a clear backwards jump.
    """
    if not messages:
        return []
    # Parse all hours; messages with un-parseable time → today
    parsed = []
    for m in messages:
        raw = (m.get("time_raw") or "").strip()
        h = -1
        mm = -1
        try:
            parts = raw.split(":")
            h = int(parts[0])
            mm = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            pass
        parsed.append((h, mm, m))

    # Detect rollover points (hour goes backwards by >6 hours, i.e., real day crossing)
    # If any rollover found, messages BEFORE the last rollover get 'yesterday'.
    last_rollover_idx = None
    for i in range(1, len(parsed)):
        ph, pm, _ = parsed[i - 1]
        ch, cm, _ = parsed[i]
        if ph >= 0 and ch >= 0:
            prev_min = ph * 60 + pm
            cur_min = ch * 60 + cm
            # Backward jump > 6h likely crossed midnight (12h or 24h ambiguous tolerant)
            if prev_min - cur_min > 6 * 60:
                last_rollover_idx = i
    out: list[tuple[date, dict]] = []
    yesterday = today - timedelta(days=1)
    for i, (_, _, m) in enumerate(parsed):
        d = yesterday if (last_rollover_idx is not None and i < last_rollover_idx) else today
        out.append((d, m))
    return out


def md_path(chat_id: str, slug: str, d: date) -> Path:
    return KMSG_DIR / f"{chat_id}__{slug}" / f"{d.isoformat()}.md"


def existing_hashes(p: Path) -> set[str]:
    if not p.exists():
        return set()
    hashes = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"<!-- h=([0-9a-f]{12}) -->", line)
        if m:
            hashes.add(m.group(1))
    return hashes


def append_md(p: Path, chat_title: str, d: date, msgs: list[dict]) -> int:
    """Append new messages (de-duped by hash). Returns count of new messages written."""
    p.parent.mkdir(parents=True, exist_ok=True)
    seen = existing_hashes(p)
    new = [(msg_hash(m), m) for m in msgs if msg_hash(m) not in seen]
    if not new:
        return 0
    header_needed = not p.exists()
    fetch_ts = datetime.now().isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        if header_needed:
            f.write(f"# {chat_title} — {d.isoformat()}\n\n")
        f.write(f"<!-- fetched_at={fetch_ts} count={len(new)} -->\n")
        for h, m in new:
            time_raw = m.get("time_raw", "??:??")
            author = m.get("author", "?")
            body = (m.get("body", "") or "").rstrip()
            f.write(f"<!-- h={h} -->\n")
            f.write(f"**{time_raw}** `{author}`\n\n")
            for line in body.splitlines() or [""]:
                f.write(f"> {line}\n")
            f.write("\n")
    return len(new)


def write_state(conn: sqlite3.Connection, chat_id: str, d: date, m: dict, seen_at: str):
    conn.execute(
        "INSERT OR IGNORE INTO messages (chat_id, date, msg_hash, time_raw, author, body, seen_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (chat_id, d.isoformat(), msg_hash(m), m.get("time_raw"), m.get("author"), m.get("body"), seen_at),
    )


def update_chat_meta(conn: sqlite3.Connection, chat_id: str, title: str, count: int, error: str | None):
    conn.execute(
        "INSERT INTO chats_meta (chat_id, title, last_fetch_at, last_count, error) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, last_fetch_at=excluded.last_fetch_at, "
        "last_count=excluded.last_count, error=excluded.error",
        (chat_id, title, datetime.now().isoformat(timespec="seconds"), count, error),
    )


def snapshot(only_title: str | None = None, limit: int = 500, refresh: bool = True,
             timeout: int = 15, abort_after_consecutive_timeouts: int = 8):
    conn = init_state(STATE_DB)
    excludes = load_excludes()

    if refresh or latest_chats_file() is None:
        chats_file = refresh_chats()
    else:
        chats_file = latest_chats_file()
    chats = json.loads(chats_file.read_text())["chats"]

    if only_title:
        chats = [c for c in chats if only_title in c["title"]]
        print(f"[filter] matched {len(chats)} chats containing '{only_title}'", flush=True)

    skipped = []
    todo = []
    for c in chats:
        if is_excluded(c, excludes):
            skipped.append(c["title"])
            continue
        todo.append(c)
    print(f"[plan] {len(todo)} to process, {len(skipped)} excluded (timeout={timeout}s)", flush=True)

    today = date.today()
    fetch_ts = datetime.now().isoformat(timespec="seconds")
    stats = {"ok": 0, "empty": 0, "error": 0, "new_messages": 0}
    failed_candidates: list[dict] = []
    consecutive_timeouts = 0

    for i, c in enumerate(todo, 1):
        title = c["title"]
        chat_id = c["chat_id"]
        slug = slugify(title)
        print(f"[{i}/{len(todo)}] {chat_id} {title[:40]}", flush=True)

        res = read_chat(title, limit=limit, timeout=timeout)
        if res is None or "error" in (res or {}):
            err = (res or {}).get("error", "unknown")
            print(f"   ✗ {err}", flush=True)
            update_chat_meta(conn, chat_id, title, 0, err)
            failed_candidates.append({"chat_id": chat_id, "title": title, "error": err})
            stats["error"] += 1
            conn.commit()
            if err == "timeout":
                consecutive_timeouts += 1
                if consecutive_timeouts >= abort_after_consecutive_timeouts:
                    print(f"\n!!! {consecutive_timeouts} consecutive timeouts — KakaoTalk likely stuck. Aborting. !!!", flush=True)
                    break
            else:
                consecutive_timeouts = 0
            continue

        consecutive_timeouts = 0
        msgs = res.get("messages", [])
        if not msgs:
            update_chat_meta(conn, chat_id, title, 0, None)
            stats["empty"] += 1
            conn.commit()
            continue

        bucketed = bucket_date(msgs, today)
        by_date: dict[date, list[dict]] = {}
        for d, m in bucketed:
            by_date.setdefault(d, []).append(m)

        new_total = 0
        for d, ms in by_date.items():
            n = append_md(md_path(chat_id, slug, d), title, d, ms)
            new_total += n
            for m in ms:
                write_state(conn, chat_id, d, m, fetch_ts)

        update_chat_meta(conn, chat_id, title, len(msgs), None)
        conn.commit()
        stats["ok"] += 1
        stats["new_messages"] += new_total
        print(f"   ✓ {len(msgs)} msgs, +{new_total} new", flush=True)

    # Persist failed candidates for review/auto-exclude
    if failed_candidates:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        fc_path = INDEX_DIR / f"failed-{ts}.json"
        fc_path.write_text(json.dumps(failed_candidates, ensure_ascii=False, indent=2))
        print(f"[failed] {len(failed_candidates)} candidates written to {fc_path.name}", flush=True)

    print(f"\n=== DONE === ok={stats['ok']} empty={stats['empty']} error={stats['error']} new_msgs={stats['new_messages']}", flush=True)


def auto_exclude_repeat_failures(min_failures: int = 2):
    """Read all failed-*.json under _index and add chats that failed in >=min_failures runs to excludes."""
    fc_files = sorted(INDEX_DIR.glob("failed-*.json"))
    if not fc_files:
        print("no failed-*.json found", flush=True)
        return
    counts: dict[str, dict] = {}
    for f in fc_files:
        for entry in json.loads(f.read_text()):
            cid = entry["chat_id"]
            rec = counts.setdefault(cid, {"chat_id": cid, "title": entry["title"], "errors": [], "runs": 0})
            rec["runs"] += 1
            rec["errors"].append(entry["error"])
    repeat = [r for r in counts.values() if r["runs"] >= min_failures]
    if not repeat:
        print(f"no chats failed in >={min_failures} runs", flush=True)
        return
    excludes = json.loads(EXCLUDES_PATH.read_text()) if EXCLUDES_PATH.exists() else {
        "_comment": "auto-curated", "titles": [], "title_patterns": [], "chat_ids": []
    }
    added = 0
    for r in repeat:
        if r["chat_id"] not in excludes["chat_ids"]:
            excludes["chat_ids"].append(r["chat_id"])
            added += 1
            print(f"  + {r['chat_id']} {r['title']} (failed {r['runs']}x: {set(r['errors'])})", flush=True)
    EXCLUDES_PATH.write_text(json.dumps(excludes, ensure_ascii=False, indent=2))
    print(f"[auto-exclude] added {added} chat_ids to excludes.json", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_chats = sub.add_parser("chats", help="Refresh chat list only")
    sp_chats.add_argument("--limit", type=int, default=2000)

    sp_snap = sub.add_parser("snapshot", help="Read each chat and write daily MDs")
    sp_snap.add_argument("--chat", help="Only chats whose title contains this substring")
    sp_snap.add_argument("--limit", type=int, default=500, help="Per-chat read limit")
    sp_snap.add_argument("--no-refresh", action="store_true", help="Reuse latest chat list")
    sp_snap.add_argument("--timeout", type=int, default=15, help="Per-chat read timeout (seconds)")
    sp_snap.add_argument("--abort-after", type=int, default=8,
                         help="Abort run after N consecutive timeouts (KakaoTalk stuck)")

    sp_ax = sub.add_parser("auto-exclude", help="Add chat_ids that failed in N+ runs to excludes.json")
    sp_ax.add_argument("--min-failures", type=int, default=2)

    args = ap.parse_args()

    if args.cmd == "chats":
        refresh_chats(limit=args.limit)
    elif args.cmd == "snapshot":
        snapshot(only_title=args.chat, limit=args.limit, refresh=not args.no_refresh,
                 timeout=args.timeout, abort_after_consecutive_timeouts=args.abort_after)
    elif args.cmd == "auto-exclude":
        auto_exclude_repeat_failures(min_failures=args.min_failures)


if __name__ == "__main__":
    main()
