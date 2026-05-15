#!/usr/bin/env python3
"""Dump Microsoft Teams conversations to raw JSON and Markdown.

Creates:
- output/teams/conversations/dm/
- output/teams/conversations/groupchat/
- output/teams/conversations/teams/

Source is Microsoft Graph using the existing MSAL token cache.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "proc" / "lib"))

from msgraph import GraphClient, GraphClientError  # noqa: E402
from teams_graph import KST, _channel_msg_to_dict, _kst, _msg_to_dict  # noqa: E402


OUT_ROOT = ROOT / "output" / "teams" / "conversations"


class StateStore:
    """SQLite state for incremental Teams archive runs."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
              scope TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              title TEXT,
              raw_path TEXT,
              md_path TEXT,
              last_seen_at TEXT,
              PRIMARY KEY (scope, conversation_id)
            );
            CREATE TABLE IF NOT EXISTS messages (
              scope TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              message_id TEXT NOT NULL,
              parent_id TEXT,
              seen_at TEXT NOT NULL,
              PRIMARY KEY (scope, conversation_id, message_id)
            );
            """
        )
        self.db.commit()

    def seen_ids(self, scope: str, conversation_id: str) -> set[str]:
        rows = self.db.execute(
            "SELECT message_id FROM messages WHERE scope=? AND conversation_id=?",
            (scope, conversation_id),
        )
        return {r[0] for r in rows}

    def upsert_conversation(self, scope: str, conversation_id: str, title: str,
                            raw_path: Path, md_path: Path) -> None:
        self.db.execute(
            """
            INSERT INTO conversations(scope, conversation_id, title, raw_path, md_path, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope, conversation_id) DO UPDATE SET
              title=excluded.title,
              raw_path=excluded.raw_path,
              md_path=excluded.md_path,
              last_seen_at=excluded.last_seen_at
            """,
            (scope, conversation_id, title, str(raw_path), str(md_path), now_stamp()),
        )

    def mark_messages(self, scope: str, conversation_id: str, messages: list[dict],
                      parent_id: str | None = None) -> None:
        rows = [
            (scope, conversation_id, str(m.get("id")), parent_id, now_stamp())
            for m in messages
            if m.get("id")
        ]
        if rows:
            self.db.executemany(
                """
                INSERT OR IGNORE INTO messages(scope, conversation_id, message_id, parent_id, seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def commit(self) -> None:
        self.db.commit()

    def close(self) -> None:
        self.db.commit()
        self.db.close()


def graph_items(g: GraphClient, path_or_url: str, params: dict | None = None) -> Iterator[dict]:
    """Yield every item from a Graph collection, following @odata.nextLink."""
    url = g._url(path_or_url)
    first = True
    while url:
        for attempt in range(6):
            r = requests.get(
                url,
                params=params if first else None,
                headers=g._headers(),
                timeout=60,
            )
            if r.status_code in (429, 503, 504):
                wait = int(r.headers.get("Retry-After") or min(60, 2 ** attempt))
                print(f"[wait] Graph {r.status_code}; sleeping {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if not r.ok:
                raise GraphClientError(f"GET {url} failed [{r.status_code}]: {r.text[:500]}")
            break
        else:
            raise GraphClientError(f"GET {url} failed after retries")

        data = r.json()
        for item in data.get("value", []):
            yield item
        url = data.get("@odata.nextLink")
        first = False


def now_stamp() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %z")


def safe_name(text: str, fallback: str = "untitled", limit: int = 90) -> str:
    text = (text or "").strip() or fallback
    text = re.sub(r"[\\/:*?\"<>|\n\r\t]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text[:limit].strip(" .") or fallback)


def id_suffix(value: str, limit: int = 18) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", value or "")
    return (cleaned[:limit] or "id")


def read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def merge_messages(existing: list[dict], new_items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    no_id: list[dict] = []
    for item in existing + new_items:
        mid = item.get("id")
        if mid:
            merged[str(mid)] = item
        else:
            no_id.append(item)
    rows = list(merged.values()) + no_id
    rows.sort(key=lambda m: m.get("createdDateTime") or m.get("lastModifiedDateTime") or "", reverse=True)
    return rows


def merge_posts(existing: list[dict], new_items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    no_id: list[dict] = []
    for item in existing + new_items:
        mid = item.get("id")
        if not mid:
            no_id.append(item)
            continue
        current = merged.get(str(mid), {})
        replies = merge_messages(current.get("allReplies") or [], item.get("allReplies") or [])
        combined = {**current, **item}
        if replies:
            combined["allReplies"] = replies
        merged[str(mid)] = combined
    rows = list(merged.values()) + no_id
    rows.sort(key=lambda m: m.get("createdDateTime") or m.get("lastModifiedDateTime") or "", reverse=True)
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def member_name(member: dict) -> str:
    return member.get("displayName") or member.get("email") or member.get("userId") or "unknown"


def chat_title(chat: dict, me_id: str) -> str:
    topic = chat.get("topic") or ""
    if topic:
        return topic
    members = chat.get("members") or []
    others = [m for m in members if m.get("userId") != me_id]
    names = [member_name(m) for m in others] or [member_name(m) for m in members]
    return ", ".join(names[:8]) or chat.get("id") or "chat"


def format_ts(ts: Any) -> str:
    if not ts:
        return "-"
    if isinstance(ts, datetime):
        return ts.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    parsed = _kst(str(ts))
    return parsed.strftime("%Y-%m-%d %H:%M") if parsed else str(ts)


def render_chat_md(chat: dict, messages: list[dict], me_id: str) -> list[str]:
    title = chat_title(chat, me_id)
    kind = chat.get("chatType") or "chat"
    normalized = []
    for raw in messages:
        msg = _msg_to_dict(raw)
        if msg:
            normalized.append(msg)
    normalized.sort(key=lambda m: m.get("ts") or datetime.min.replace(tzinfo=timezone.utc))

    lines = [
        f"# Teams {kind}: {title}",
        "",
        f"- 추출일: {now_stamp()}",
        f"- chat_id: `{chat.get('id')}`",
        f"- 원본 메시지 수: {len(messages)}",
        f"- Markdown 표시 메시지 수: {len(normalized)}",
        f"- 멤버: {', '.join(member_name(m) for m in chat.get('members') or [])}",
        "",
    ]
    current_day = None
    for msg in normalized:
        ts = msg.get("ts")
        day = ts.date().isoformat() if ts else "unknown-date"
        if day != current_day:
            current_day = day
            lines.extend([f"## {day}", ""])
        lines.append(f"**[{format_ts(ts)[11:16]}] {msg.get('who') or 'unknown'}**")
        quote = msg.get("quote")
        if quote:
            lines.append(f"> {quote.get('sender') or ''}: {quote.get('body') or ''}")
        text = msg.get("text") or ""
        lines.extend(text.splitlines() or [""])
        lines.append("")
    return lines


def render_channel_md(team: dict, channel: dict, posts: list[dict]) -> list[str]:
    normalized_threads = []
    for item in posts:
        parent_raw = item.get("message") or item
        parent = _channel_msg_to_dict(parent_raw)
        if not parent:
            continue
        replies = []
        for raw in item.get("allReplies") or []:
            reply = _channel_msg_to_dict(raw)
            if reply:
                replies.append(reply)
        replies.sort(key=lambda m: m.get("ts") or datetime.min.replace(tzinfo=timezone.utc))
        normalized_threads.append({"parent": parent, "replies": replies})
    normalized_threads.sort(key=lambda t: t["parent"].get("ts") or datetime.min.replace(tzinfo=timezone.utc))

    lines = [
        f"# Teams Channel: {team.get('displayName')} / {channel.get('displayName')}",
        "",
        f"- 추출일: {now_stamp()}",
        f"- team_id: `{team.get('id')}`",
        f"- channel_id: `{channel.get('id')}`",
        f"- 원본 thread 수: {len(posts)}",
        f"- Markdown 표시 thread 수: {len(normalized_threads)}",
        "",
    ]
    current_day = None
    for thread in normalized_threads:
        parent = thread["parent"]
        ts = parent.get("ts")
        day = ts.date().isoformat() if ts else "unknown-date"
        if day != current_day:
            current_day = day
            lines.extend([f"## {day}", ""])
        lines.append(f"**[{format_ts(ts)[11:16]}] {parent.get('who') or 'unknown'}**")
        if parent.get("quote"):
            q = parent["quote"]
            lines.append(f"> {q.get('sender') or ''}: {q.get('body') or ''}")
        lines.extend((parent.get("text") or "").splitlines() or [""])
        lines.append("")
        for reply in thread["replies"]:
            rts = reply.get("ts")
            lines.append(f"- **[{format_ts(rts)[11:16]}] {reply.get('who') or 'unknown'}**")
            for line in (reply.get("text") or "").splitlines() or [""]:
                lines.append(f"  {line}")
            lines.append("")
    return lines


def fetch_chats(g: GraphClient) -> list[dict]:
    return list(graph_items(g, "/me/chats", {
        "$top": 50,
        "$expand": "members,lastMessagePreview",
        "$orderby": "lastMessagePreview/createdDateTime desc",
    }))


def fetch_chat_messages(g: GraphClient, chat_id: str, stop_ids: set[str] | None = None,
                        rescan: bool = False) -> list[dict]:
    out = []
    stop_ids = stop_ids or set()
    for item in graph_items(g, f"/me/chats/{chat_id}/messages", {"$top": 50}):
        mid = str(item.get("id") or "")
        if mid and mid in stop_ids and not rescan:
            break
        out.append(item)
    return out


def fetch_joined_teams(g: GraphClient) -> list[dict]:
    return list(graph_items(g, "/me/joinedTeams"))


def fetch_channels(g: GraphClient, team_id: str) -> list[dict]:
    return list(graph_items(g, f"/teams/{team_id}/channels"))


def fetch_channel_replies(g: GraphClient, team_id: str, channel_id: str, message_id: str) -> list[dict]:
    path = f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies"
    return list(graph_items(g, path, {"$top": 50}))


def fetch_channel_posts(g: GraphClient, team_id: str, channel_id: str, include_replies: bool,
                        stop_ids: set[str] | None = None, rescan: bool = False,
                        reply_refresh_threads: int = 100,
                        retry_post_ids: set[str] | None = None) -> list[dict]:
    path = f"/teams/{team_id}/channels/{channel_id}/messages"
    posts = []
    stop_ids = stop_ids or set()
    retry_post_ids = set(retry_post_ids or set())
    for item in graph_items(g, path, {"$top": 50}):
        mid = str(item.get("id") or "")
        seen = bool(mid and mid in stop_ids)
        retry_needed = bool(mid and mid in retry_post_ids)
        if seen and not rescan and len(posts) >= reply_refresh_threads and not retry_needed:
            if retry_post_ids:
                continue
            break
        item["_archiveSeenBefore"] = seen
        posts.append(item)
        retry_post_ids.discard(mid)
        if seen and not rescan and len(posts) >= reply_refresh_threads and not retry_post_ids:
            break
    if not include_replies:
        return posts
    for idx, post in enumerate(posts):
        mid = post.get("id")
        if not mid:
            post["allReplies"] = []
            continue
        if rescan or not post.get("_archiveSeenBefore") or idx < reply_refresh_threads:
            try:
                post["allReplies"] = fetch_channel_replies(g, team_id, channel_id, mid)
                post.pop("_replyFetchError", None)
            except Exception as exc:
                post["allReplies"] = []
                post["_replyFetchError"] = str(exc)
                print(f"[error] replies {team_id}/{channel_id}/{mid}: {exc}", file=sys.stderr)
    return posts


def dump_chats(g: GraphClient, me: dict, out_root: Path, max_chats: int | None,
               state: StateStore, rescan: bool) -> dict:
    me_id = me.get("id") or ""
    chats = fetch_chats(g)
    if max_chats is not None:
        chats = chats[:max_chats]

    summary = {
        "dm": 0,
        "groupchat": 0,
        "chat_messages_total": 0,
        "chat_messages_new": 0,
        "chat_errors": [],
    }
    write_json(out_root / "chatrooms.raw.json", {"me": me, "chats": chats})

    for index, chat in enumerate(chats, 1):
        chat_id = chat.get("id") or ""
        kind = chat.get("chatType") or "chat"
        bucket = "dm" if kind == "oneOnOne" else "groupchat"
        title = chat_title(chat, me_id)
        stem = f"{safe_name(title)}-{id_suffix(chat_id)}"
        raw_path = out_root / bucket / f"{stem}.raw.json"
        md_path = out_root / bucket / f"{stem}.md"
        error_path = out_root / bucket / f"{stem}.error.json"
        print(f"[chat] {index}/{len(chats)} {bucket} {title}")
        try:
            existing_payload = read_json(raw_path) or {}
            existing_messages = existing_payload.get("messages") or []
            known_ids = state.seen_ids("chat", chat_id) | {
                str(m.get("id")) for m in existing_messages if m.get("id")
            }
            must_rescan = rescan or not raw_path.exists()
            new_messages = fetch_chat_messages(g, chat_id, stop_ids=known_ids, rescan=must_rescan)
            messages = merge_messages(existing_messages, new_messages)
            payload = {"chat": chat, "messages": messages}
            if new_messages or must_rescan:
                write_json(raw_path, payload)
                write_md(md_path, render_chat_md(chat, messages, me_id))
            state.upsert_conversation("chat", chat_id, title, raw_path, md_path)
            state.mark_messages("chat", chat_id, messages)
            state.commit()
            if error_path.exists():
                error_path.unlink()
            summary[bucket] += 1
            summary["chat_messages_total"] += len(messages)
            summary["chat_messages_new"] += len(new_messages)
        except Exception as exc:  # keep dumping other rooms
            summary["chat_errors"].append({"chat_id": chat_id, "title": title, "error": str(exc)})
            write_json(error_path, {"chat": chat, "error": str(exc)})
            print(f"[error] chat {title}: {exc}", file=sys.stderr)
    return summary


def dump_teams(g: GraphClient, out_root: Path, max_teams: int | None, max_channels: int | None,
               include_replies: bool, state: StateStore, rescan: bool,
               reply_refresh_threads: int) -> dict:
    teams = fetch_joined_teams(g)
    if max_teams is not None:
        teams = teams[:max_teams]

    summary = {
        "teams": len(teams),
        "channels": 0,
        "channel_threads_total": 0,
        "channel_threads_new_or_refreshed": 0,
        "channel_replies_total": 0,
        "team_errors": [],
    }
    write_json(out_root / "teams" / "teams.raw.json", {"teams": teams})

    for team_index, team in enumerate(teams, 1):
        team_name = team.get("displayName") or team.get("id") or "team"
        try:
            channels = fetch_channels(g, team.get("id"))
            if max_channels is not None:
                channels = channels[:max_channels]
            team_dir = out_root / "teams" / f"{safe_name(team_name)}-{id_suffix(team.get('id') or '')}"
            write_json(team_dir / "_channels.raw.json", {"team": team, "channels": channels})
            for channel_index, channel in enumerate(channels, 1):
                channel_name = channel.get("displayName") or channel.get("id") or "channel"
                conversation_id = f"{team.get('id')}/{channel.get('id')}"
                stem = f"{safe_name(channel_name)}-{id_suffix(channel.get('id') or '')}"
                raw_path = team_dir / f"{stem}.raw.json"
                md_path = team_dir / f"{stem}.md"
                error_path = team_dir / f"{stem}.error.json"
                print(f"[channel] {team_index}/{len(teams)} {team_name} / {channel_name}")
                try:
                    existing_payload = read_json(raw_path) or {}
                    existing_posts = existing_payload.get("posts") or []
                    retry_post_ids = {
                        str(p.get("id"))
                        for p in existing_posts
                        if p.get("id") and p.get("_replyFetchError")
                    }
                    known_ids = state.seen_ids("channel", conversation_id) | {
                        str(p.get("id"))
                        for p in existing_posts
                        if p.get("id") and not p.get("_replyFetchError")
                    }
                    must_rescan = rescan or not raw_path.exists()
                    new_posts = fetch_channel_posts(
                        g,
                        team.get("id"),
                        channel.get("id"),
                        include_replies,
                        stop_ids=known_ids,
                        rescan=must_rescan,
                        reply_refresh_threads=reply_refresh_threads,
                        retry_post_ids=retry_post_ids,
                    )
                    posts = merge_posts(existing_posts, new_posts)
                    if new_posts or must_rescan:
                        write_json(raw_path, {
                            "team": team,
                            "channel": channel,
                            "posts": posts,
                        })
                        write_md(md_path, render_channel_md(team, channel, posts))
                    state.upsert_conversation("channel", conversation_id, f"{team_name} / {channel_name}", raw_path, md_path)
                    state.mark_messages(
                        "channel",
                        conversation_id,
                        [p for p in posts if not p.get("_replyFetchError")],
                    )
                    for post in posts:
                        state.mark_messages("channel", conversation_id, post.get("allReplies") or [], parent_id=post.get("id"))
                    state.commit()
                    if error_path.exists():
                        error_path.unlink()
                    summary["channels"] += 1
                    summary["channel_threads_total"] += len(posts)
                    summary["channel_threads_new_or_refreshed"] += len(new_posts)
                    summary["channel_replies_total"] += sum(len(p.get("allReplies") or []) for p in posts)
                except Exception as exc:
                    summary["team_errors"].append({
                        "team_id": team.get("id"),
                        "team": team_name,
                        "channel_id": channel.get("id"),
                        "channel": channel_name,
                        "error": str(exc),
                    })
                    write_json(error_path, {
                        "team": team,
                        "channel": channel,
                        "error": str(exc),
                    })
                    print(f"[error] channel {team_name}/{channel_name}: {exc}", file=sys.stderr)
        except Exception as exc:
            summary["team_errors"].append({"team_id": team.get("id"), "team": team_name, "error": str(exc)})
            print(f"[error] team {team_name}: {exc}", file=sys.stderr)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT_ROOT), help="output directory")
    ap.add_argument("--max-chats", type=int, default=None, help="debug cap for chat rooms")
    ap.add_argument("--max-teams", type=int, default=None, help="debug cap for teams")
    ap.add_argument("--max-channels", type=int, default=None, help="debug cap per team")
    ap.add_argument("--skip-chats", action="store_true")
    ap.add_argument("--skip-teams", action="store_true")
    ap.add_argument("--skip-replies", action="store_true", help="skip channel replies")
    ap.add_argument("--rescan", action="store_true", help="ignore SQLite/file state and fetch full history")
    ap.add_argument(
        "--state-db",
        default=None,
        help="SQLite state path (default: <out>/_state.sqlite3)",
    )
    ap.add_argument(
        "--reply-refresh-threads",
        type=int,
        default=25,
        help="for incremental channel runs, refresh replies for this many newest threads",
    )
    args = ap.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    state = StateStore(Path(args.state_db) if args.state_db else out_root / "_state.sqlite3")

    try:
        g = GraphClient()
        me = g.get("/me")
        summary: dict[str, Any] = {
            "extracted_at": now_stamp(),
            "me": {
                "id": me.get("id"),
                "displayName": me.get("displayName"),
                "mail": me.get("mail") or me.get("userPrincipalName"),
            },
            "out": str(out_root),
            "state_db": str(state.path),
            "incremental": not args.rescan,
            "reply_refresh_threads": args.reply_refresh_threads,
        }

        if not args.skip_chats:
            summary["chats"] = dump_chats(g, me, out_root, args.max_chats, state, args.rescan)
        if not args.skip_teams:
            summary["teams"] = dump_teams(
                g,
                out_root,
                args.max_teams,
                args.max_channels,
                not args.skip_replies,
                state,
                args.rescan,
                args.reply_refresh_threads,
            )

        write_json(out_root / "_summary.json", summary)
        lines = [
            "# Teams Conversations Dump",
            "",
            f"- 추출일: {summary['extracted_at']}",
            f"- 본인: {summary['me']['displayName']} <{summary['me']['mail']}>",
            f"- 출력 경로: `{summary['out']}`",
            f"- SQLite 상태 DB: `{summary['state_db']}`",
            f"- 증분 모드: `{summary['incremental']}`",
            "",
            "## Counts",
            "",
            "```json",
            json.dumps({k: v for k, v in summary.items() if k not in ("me", "out", "extracted_at")},
                       ensure_ascii=False, indent=2),
            "```",
        ]
        write_md(out_root / "_summary.md", lines)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        state.close()


if __name__ == "__main__":
    raise SystemExit(main())
