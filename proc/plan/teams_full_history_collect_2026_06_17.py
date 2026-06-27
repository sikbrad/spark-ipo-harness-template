#!/usr/bin/env python3
"""Collect full Microsoft Teams chat + channel history for ins@doflab.com.

The script uses delegated MS Graph access through proc/lib/msgraph.py and writes
date-scoped raw artifacts. It is resumable: existing per-chat/per-channel JSON
files are reused unless --force is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, "proc/lib")
from msgraph import GraphClient, GraphClientError  # noqa: E402


KST = timezone(timedelta(hours=9))
RUN_DATE = "2026-06-17"
ROOT = Path("data/teams/full-history") / RUN_DATE
CHAT_DIR = ROOT / "chats"
CHANNEL_DIR = ROOT / "channels"


def now_iso() -> str:
    return datetime.now(KST).isoformat()


def safe_name(value: str, fallback: str = "untitled") -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        value = fallback
    value = re.sub(r"[^\w가-힣 .@()+,#&=-]+", "_", value)
    value = value.strip(" ._")
    return value[:120] or fallback


def short_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def strip_html(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value).replace("\xa0", " ")
    return re.sub(r"\n{2,}", "\n", value).strip()


def parse_dt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(KST).isoformat()
    except ValueError:
        return value


def message_text(message: dict) -> str:
    body = message.get("body") or {}
    content = body.get("content") or ""
    if body.get("contentType") == "html":
        content = strip_html(content)
    return content.strip()


def message_who(message: dict) -> str:
    sender = message.get("from") or {}
    return (
        ((sender.get("user") or {}).get("displayName"))
        or ((sender.get("application") or {}).get("displayName"))
        or ((sender.get("device") or {}).get("displayName"))
        or ""
    )


def normalize_message(message: dict) -> dict | None:
    if not isinstance(message, dict):
        return None
    if message.get("deletedDateTime"):
        return None
    if (message.get("messageType") or "").startswith("systemEventMessage"):
        return None
    text = message_text(message)
    attachments = message.get("attachments") or []
    if not text and not attachments:
        return None
    return {
        "id": message.get("id"),
        "ts": parse_dt(message.get("createdDateTime") or message.get("lastModifiedDateTime")),
        "last_modified": parse_dt(message.get("lastModifiedDateTime")),
        "who": message_who(message),
        "text": text,
        "importance": message.get("importance"),
        "subject": message.get("subject"),
        "summary": message.get("summary"),
        "web_url": message.get("webUrl"),
        "mentions": message.get("mentions") or [],
        "attachments": attachments,
        "raw": message,
    }


def graph_get(g: GraphClient, path_or_url: str, params: dict | None = None) -> dict:
    url = path_or_url if path_or_url.startswith("http") else g._url(path_or_url)
    for attempt in range(8):
        response = requests.get(url, params=params, headers=g._headers(), timeout=60)
        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 2 ** attempt)
            print(
                f"    Graph retry {response.status_code} attempt={attempt + 1} delay={delay}s",
                flush=True,
            )
            time.sleep(delay)
            continue
        if not response.ok:
            raise GraphClientError(f"GET {path_or_url} failed [{response.status_code}]: {response.text[:1000]}")
        return response.json() if response.content else {}
    raise GraphClientError(f"GET {path_or_url} failed after retries")


def graph_post(g: GraphClient, path: str, payload: dict) -> dict:
    url = g._url(path)
    for attempt in range(8):
        response = requests.post(
            url,
            json=payload,
            headers=g._headers({"Content-Type": "application/json"}),
            timeout=90,
        )
        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 2 ** attempt)
            time.sleep(delay)
            continue
        if not response.ok:
            raise GraphClientError(f"POST {path} failed [{response.status_code}]: {response.text[:1000]}")
        return response.json() if response.content else {}
    raise GraphClientError(f"POST {path} failed after retries")


def paged(
    g: GraphClient,
    path: str,
    params: dict | None = None,
    *,
    progress_label: str | None = None,
    progress_every: int = 50,
) -> list[dict]:
    out: list[dict] = []
    next_url: str | None = None
    page_count = 0
    seen_next_links: set[str] = set()
    while True:
        data = graph_get(g, next_url or path, params=None if next_url else params)
        page_count += 1
        out.extend(data.get("value") or [])
        next_url = data.get("@odata.nextLink")
        if progress_label and (page_count == 1 or len(out) % progress_every < len(data.get("value") or [])):
            print(f"    {progress_label}: pages={page_count} rows={len(out)}", flush=True)
        if not next_url:
            break
        if next_url in seen_next_links:
            raise GraphClientError(f"Repeated nextLink while paging {path}")
        seen_next_links.add(next_url)
    return out


def chat_display_name(chat: dict, me_id: str, me_mail: str) -> str:
    if chat.get("topic"):
        return chat["topic"]
    members = chat.get("members") or []
    names = []
    for member in members:
        if member.get("userId") == me_id:
            continue
        if (member.get("email") or "").lower() == me_mail.lower():
            continue
        names.append(member.get("displayName") or member.get("email") or member.get("userId") or "?")
    return ", ".join(names[:8]) or "(unknown)"


def list_chats(g: GraphClient, me: dict) -> list[dict]:
    me_id = me.get("id") or ""
    me_mail = me.get("mail") or me.get("userPrincipalName") or ""
    rows = paged(
        g,
        "/me/chats",
        {
            "$top": 50,
            "$expand": "members,lastMessagePreview",
            "$orderby": "lastMessagePreview/createdDateTime desc",
        },
    )
    out = []
    for chat in rows:
        last = chat.get("lastMessagePreview") or {}
        body = last.get("body") or {}
        preview = body.get("content") or ""
        if body.get("contentType") == "html":
            preview = strip_html(preview)
        out.append({
            "chat_id": chat.get("id"),
            "kind": chat.get("chatType") or "",
            "name": chat_display_name(chat, me_id, me_mail),
            "topic": chat.get("topic") or "",
            "created": parse_dt(chat.get("createdDateTime")),
            "web_url": chat.get("webUrl"),
            "members": [
                {
                    "name": m.get("displayName") or "",
                    "email": m.get("email") or "",
                    "user_id": m.get("userId") or "",
                    "roles": m.get("roles") or [],
                }
                for m in (chat.get("members") or [])
            ],
            "last_ts": parse_dt(last.get("createdDateTime")),
            "last_who": (((last.get("from") or {}).get("user") or {}).get("displayName") or ""),
            "last_preview": preview[:500],
        })
    return out


def collect_chat(g: GraphClient, chat: dict, *, force: bool) -> dict:
    chat_id = chat["chat_id"]
    filename = f"{safe_name(chat.get('name') or chat_id)}__{short_id(chat_id)}.json"
    out_path = CHAT_DIR / filename
    if out_path.exists() and not force:
        data = json.loads(out_path.read_text(encoding="utf-8"))
        return {
            "chat_id": chat_id,
            "name": chat.get("name"),
            "status": "skipped_existing",
            "message_count": len(data.get("messages") or []),
            "path": str(out_path),
        }
    raw_messages = paged(g, f"/me/chats/{chat_id}/messages", {"$top": 50})
    messages = [m for m in (normalize_message(m) for m in raw_messages) if m]
    messages.sort(key=lambda m: m.get("ts") or "")
    payload = {
        "collected_at": now_iso(),
        "chat": chat,
        "message_count": len(messages),
        "messages": messages,
    }
    write_json(out_path, payload)
    return {
        "chat_id": chat_id,
        "name": chat.get("name"),
        "status": "ok",
        "message_count": len(messages),
        "path": str(out_path),
    }


def list_channels(g: GraphClient) -> list[dict]:
    rows = []
    teams = paged(g, "/me/joinedTeams")
    for team in teams:
        team_id = team.get("id")
        team_name = team.get("displayName") or ""
        try:
            channels = paged(g, f"/teams/{team_id}/channels")
        except Exception as exc:
            rows.append({
                "team_id": team_id,
                "team_name": team_name,
                "status": "channels_failed",
                "error": repr(exc),
            })
            continue
        for channel in channels:
            rows.append({
                "team_id": team_id,
                "team_name": team_name,
                "channel_id": channel.get("id"),
                "channel_name": channel.get("displayName") or "",
                "membership_type": channel.get("membershipType"),
                "email": channel.get("email"),
                "web_url": channel.get("webUrl"),
                "created": parse_dt(channel.get("createdDateTime")),
                "description": channel.get("description"),
                "status": "listed",
            })
    return rows


def collect_replies_batch(
    g: GraphClient,
    team_id: str,
    channel_id: str,
    parent_ids: list[str],
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    """Fetch replies for many channel parent messages using Graph $batch.

    Graph batch accepts up to 20 requests. Each reply collection is still fully
    paged if the first page exposes @odata.nextLink.
    """
    reply_map: dict[str, list[dict]] = {pid: [] for pid in parent_ids}
    errors: dict[str, str] = {}
    id_map: dict[str, str] = {}
    retry_parent_ids: list[str] = []

    for start in range(0, len(parent_ids), 20):
        chunk = parent_ids[start : start + 20]
        requests_payload = []
        id_map.clear()
        for idx, parent_id in enumerate(chunk):
            req_id = str(idx + 1)
            id_map[req_id] = parent_id
            requests_payload.append({
                "id": req_id,
                "method": "GET",
                "url": f"/teams/{team_id}/channels/{channel_id}/messages/{parent_id}/replies?$top=50",
            })
        batch = graph_post(g, "/$batch", {"requests": requests_payload})
        for response in batch.get("responses") or []:
            parent_id = id_map.get(str(response.get("id")))
            if not parent_id:
                continue
            status = int(response.get("status") or 0)
            if status < 200 or status >= 300:
                if status in {429, 500, 502, 503, 504}:
                    retry_parent_ids.append(parent_id)
                else:
                    errors[parent_id] = json.dumps(response.get("body") or response, ensure_ascii=False)[:1000]
                continue
            body = response.get("body") or {}
            raw_replies = body.get("value") or []
            next_link = body.get("@odata.nextLink")
            while next_link:
                next_body = graph_get(g, next_link)
                raw_replies.extend(next_body.get("value") or [])
                next_link = next_body.get("@odata.nextLink")
            replies = [m for m in (normalize_message(m) for m in raw_replies) if m]
            replies.sort(key=lambda m: m.get("ts") or "")
            reply_map[parent_id] = replies

    if retry_parent_ids:
        print(f"    retry replies individually={len(retry_parent_ids)}", flush=True)
    for idx, parent_id in enumerate(retry_parent_ids, 1):
        try:
            raw_replies = paged(
                g,
                f"/teams/{team_id}/channels/{channel_id}/messages/{parent_id}/replies",
                {"$top": 20},
            )
            replies = [m for m in (normalize_message(m) for m in raw_replies) if m]
            replies.sort(key=lambda m: m.get("ts") or "")
            reply_map[parent_id] = replies
            if idx % 10 == 0:
                print(f"    retried replies {idx}/{len(retry_parent_ids)}", flush=True)
        except Exception as exc:
            errors[parent_id] = repr(exc)[:1000]
    return reply_map, errors


def collect_channel_delta(g: GraphClient, channel: dict, out_path: Path) -> dict:
    """Fallback for channels whose regular /messages skiptoken repeatedly 504s."""
    team_id = channel["team_id"]
    channel_id = channel.get("channel_id")
    raw_messages = paged(
        g,
        f"/teams/{team_id}/channels/{channel_id}/messages/delta",
        {"$top": 10},
        progress_label=f"delta {channel.get('team_name')} / {channel.get('channel_name')}",
        progress_every=500,
    )
    parent_raw_by_id: dict[str, dict] = {}
    replies_raw_by_parent: dict[str, list[dict]] = {}
    for raw in raw_messages:
        if raw.get("deletedDateTime"):
            continue
        reply_to = raw.get("replyToId")
        if reply_to:
            replies_raw_by_parent.setdefault(str(reply_to), []).append(raw)
        else:
            mid = raw.get("id")
            if mid:
                parent_raw_by_id[str(mid)] = raw

    parents = [m for m in (normalize_message(m) for m in parent_raw_by_id.values()) if m]
    parents.sort(key=lambda m: m.get("ts") or "")
    reply_map, reply_errors = collect_replies_batch(g, team_id, channel_id, [p["id"] for p in parents])
    threads = []
    message_count = 0
    for idx, parent in enumerate(parents, 1):
        replies = reply_map.get(str(parent["id"])) or [
            m
            for m in (normalize_message(m) for m in replies_raw_by_parent.get(str(parent["id"]), []))
            if m
        ]
        replies.sort(key=lambda m: m.get("ts") or "")
        thread = {"parent": parent, "replies": replies, "reply_count": len(replies)}
        if parent["id"] in reply_errors:
            thread["reply_error"] = reply_errors[parent["id"]]
        threads.append(thread)
        message_count += 1 + len(replies)
        if idx % 500 == 0:
            print(f"    delta assembled {idx}/{len(parents)} threads", flush=True)

    payload = {
        "collected_at": now_iso(),
        "collection_mode": "delta",
        "channel": channel,
        "thread_count": len(threads),
        "message_count": message_count,
        "reply_error_count": len(reply_errors),
        "raw_delta_message_count": len(raw_messages),
        "orphan_reply_count": sum(
            len(v) for parent_id, v in replies_raw_by_parent.items() if parent_id not in parent_raw_by_id
        ),
        "threads": threads,
    }
    write_json(out_path, payload)
    return {
        "team_id": team_id,
        "channel_id": channel_id,
        "team_name": channel.get("team_name"),
        "channel_name": channel.get("channel_name"),
        "status": "ok_delta",
        "thread_count": len(threads),
        "message_count": message_count,
        "reply_error_count": len(reply_errors),
        "path": str(out_path),
    }


def collect_channel(g: GraphClient, channel: dict, *, force: bool) -> dict:
    team_id = channel["team_id"]
    channel_id = channel.get("channel_id")
    name = f"{channel.get('team_name')}__{channel.get('channel_name')}"
    filename = f"{safe_name(name)}__{short_id(team_id + ':' + channel_id)}.json"
    out_path = CHANNEL_DIR / filename
    if out_path.exists() and not force:
        data = json.loads(out_path.read_text(encoding="utf-8"))
        return {
            "team_id": team_id,
            "channel_id": channel_id,
            "team_name": channel.get("team_name"),
            "channel_name": channel.get("channel_name"),
            "status": "skipped_existing",
            "thread_count": len(data.get("threads") or []),
            "message_count": data.get("message_count") or 0,
            "path": str(out_path),
        }

    try:
        raw_parents = paged(
            g,
            f"/teams/{team_id}/channels/{channel_id}/messages",
            {"$top": 10, "$expand": "replies"},
            progress_label=f"parents {channel.get('team_name')} / {channel.get('channel_name')}",
            progress_every=100,
        )
    except GraphClientError as exc:
        if "failed after retries" in str(exc):
            print("    regular paging failed; trying delta fallback", flush=True)
            return collect_channel_delta(g, channel, out_path)
        raise
    parents = [m for m in (normalize_message(m) for m in raw_parents) if m]
    parents.sort(key=lambda m: m.get("ts") or "")
    print(f"    parent threads={len(parents)}", flush=True)

    raw_parent_by_id = {raw.get("id"): raw for raw in raw_parents if raw.get("id")}
    reply_map: dict[str, list[dict]] = {}
    fallback_parent_ids: list[str] = []
    for parent in parents:
        raw_parent = raw_parent_by_id.get(parent["id"]) or {}
        if "replies" not in raw_parent:
            fallback_parent_ids.append(parent["id"])
            reply_map[parent["id"]] = []
            continue
        raw_replies = raw_parent.get("replies") or []
        replies = [m for m in (normalize_message(m) for m in raw_replies) if m]
        replies.sort(key=lambda m: m.get("ts") or "")
        reply_map[parent["id"]] = replies
        reply_count = raw_parent.get("replies@odata.count")
        if isinstance(reply_count, int) and reply_count > len(raw_replies):
            fallback_parent_ids.append(parent["id"])

    reply_errors: dict[str, str] = {}
    if fallback_parent_ids:
        print(f"    fallback reply fetch={len(fallback_parent_ids)}", flush=True)
        fallback_map, reply_errors = collect_replies_batch(g, team_id, channel_id, fallback_parent_ids)
        reply_map.update(fallback_map)
    threads = []
    message_count = 0
    for idx, parent in enumerate(parents, 1):
        replies = reply_map.get(parent["id"], [])
        thread = {"parent": parent, "replies": replies, "reply_count": len(replies)}
        if parent["id"] in reply_errors:
            thread["reply_error"] = reply_errors[parent["id"]]
        threads.append(thread)
        message_count += 1 + len(replies)
        if idx % 250 == 0:
            print(f"    assembled {idx}/{len(parents)} threads", flush=True)
    payload = {
        "collected_at": now_iso(),
        "channel": channel,
        "thread_count": len(threads),
        "message_count": message_count,
        "reply_error_count": len(reply_errors),
        "threads": threads,
    }
    write_json(out_path, payload)
    return {
        "team_id": team_id,
        "channel_id": channel_id,
        "team_name": channel.get("team_name"),
        "channel_name": channel.get("channel_name"),
        "status": "ok",
        "thread_count": len(threads),
        "message_count": message_count,
        "reply_error_count": len(reply_errors),
        "path": str(out_path),
    }


def render_inventory_md(me: dict, chats: list[dict], channels: list[dict]) -> str:
    lines = [
        "# Teams Inventory",
        "",
        f"- collected_at: {now_iso()}",
        f"- user: {me.get('displayName')} <{me.get('mail') or me.get('userPrincipalName')}>",
        f"- chats: {len(chats)}",
        f"- channels: {len([c for c in channels if c.get('channel_id')])}",
        "",
        "## Chatrooms",
        "",
        "| kind | name | members | last_ts | chat_id |",
        "|---|---|---:|---|---|",
    ]
    for chat in chats:
        lines.append(
            f"| {chat.get('kind')} | {chat.get('name')} | {len(chat.get('members') or [])} | "
            f"{chat.get('last_ts') or ''} | `{chat.get('chat_id')}` |"
        )
    lines.extend(["", "## Channels", "", "| team | channel | type | channel_id |", "|---|---|---|---|"])
    for channel in channels:
        if not channel.get("channel_id"):
            lines.append(f"| {channel.get('team_name')} | (channel-list failed) | error | {channel.get('error')} |")
            continue
        lines.append(
            f"| {channel.get('team_name')} | {channel.get('channel_name')} | "
            f"{channel.get('membership_type') or ''} | `{channel.get('channel_id')}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-chats", action="store_true")
    ap.add_argument("--skip-channels", action="store_true")
    args = ap.parse_args()

    ROOT.mkdir(parents=True, exist_ok=True)
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    CHANNEL_DIR.mkdir(parents=True, exist_ok=True)

    g = GraphClient()
    me = g.get("/me")
    write_json(ROOT / "me.json", me)
    if (me.get("mail") or me.get("userPrincipalName") or "").lower() != "ins@doflab.com":
        raise SystemExit(f"Unexpected Graph user: {me.get('mail') or me.get('userPrincipalName')}")

    chats = list_chats(g, me)
    channels = list_channels(g)
    write_json(ROOT / "chatrooms.json", {"collected_at": now_iso(), "me": me, "chats": chats})
    write_json(ROOT / "channels.json", {"collected_at": now_iso(), "me": me, "channels": channels})
    (ROOT / "inventory.md").write_text(render_inventory_md(me, chats, channels), encoding="utf-8")

    status = {
        "collected_at": now_iso(),
        "me": {"displayName": me.get("displayName"), "mail": me.get("mail"), "userPrincipalName": me.get("userPrincipalName")},
        "chatrooms_total": len(chats),
        "channels_total": len([c for c in channels if c.get("channel_id")]),
        "chats": [],
        "channels": [],
        "errors": [],
    }

    if not args.skip_chats:
        for idx, chat in enumerate(chats, 1):
            print(f"[chat {idx}/{len(chats)}] {chat.get('kind')} {chat.get('name')}", flush=True)
            try:
                status["chats"].append(collect_chat(g, chat, force=args.force))
            except Exception as exc:
                status["errors"].append({"kind": "chat", "chat": chat, "error": repr(exc)})
                print(f"  FAIL {exc!r}", flush=True)
            write_json(ROOT / "collect-status.json", status)

    readable_channels = [c for c in channels if c.get("channel_id")]
    if not args.skip_channels:
        for idx, channel in enumerate(readable_channels, 1):
            print(
                f"[channel {idx}/{len(readable_channels)}] {channel.get('team_name')} / {channel.get('channel_name')}",
                flush=True,
            )
            try:
                status["channels"].append(collect_channel(g, channel, force=args.force))
            except Exception as exc:
                status["errors"].append({"kind": "channel", "channel": channel, "error": repr(exc)})
                print(f"  FAIL {exc!r}", flush=True)
            write_json(ROOT / "collect-status.json", status)

    status["finished_at"] = now_iso()
    status["chat_messages_total"] = sum((row.get("message_count") or 0) for row in status["chats"])
    status["channel_messages_total"] = sum((row.get("message_count") or 0) for row in status["channels"])
    status["error_count"] = len(status["errors"])
    write_json(ROOT / "collect-status.json", status)
    print(json.dumps({
        "root": str(ROOT),
        "chatrooms": status["chatrooms_total"],
        "channels": status["channels_total"],
        "chat_messages": status["chat_messages_total"],
        "channel_messages": status["channel_messages_total"],
        "errors": status["error_count"],
    }, ensure_ascii=False, indent=2))
    return 0 if not status["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
