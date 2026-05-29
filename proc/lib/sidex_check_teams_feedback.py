#!/usr/bin/env python3
"""Check Teams replies after the SIDEX PDF delivery message."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
sys.path.insert(0, str(ROOT / "proc/lib"))

from msgraph import GraphClient  # noqa: E402
from onedrive import KST  # noqa: E402


STATE_PATH = ROOT / "output/sidex-2026/pdf_report/teams_send_result.json"
FEEDBACK_OUT = ROOT / "output/sidex-2026/pdf_report/teams_feedback_latest.json"


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def load_state() -> dict[str, Any]:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def parse_graph_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(KST)


def strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"</p>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value).replace("\xa0", " ")
    return re.sub(r"\n{2,}", "\n", value).strip()


def message_text(message: dict[str, Any]) -> str:
    body = message.get("body") or {}
    content = body.get("content") or ""
    return strip_html(content) if body.get("contentType") == "html" else content.strip()


def fetch_messages_after(g: GraphClient, chat_id: str, sent_at: datetime, max_pages: int = 4) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    params = {"$top": 50}
    next_link = None
    pages = 0
    while True:
        data = g.get(next_link or f"/me/chats/{chat_id}/messages", params=None if next_link else params)
        pages += 1
        for raw in data.get("value") or []:
            created_raw = raw.get("createdDateTime") or raw.get("lastModifiedDateTime")
            if not created_raw:
                continue
            created = parse_graph_time(created_raw)
            if created <= sent_at:
                next_link = None
                break
            if raw.get("deletedDateTime"):
                continue
            if ((raw.get("from") or {}).get("application") or {}).get("id"):
                continue
            text = message_text(raw)
            if not text:
                continue
            sender = ((raw.get("from") or {}).get("user") or {}).get("displayName") or ""
            sender_id = ((raw.get("from") or {}).get("user") or {}).get("id") or ""
            out.append(
                {
                    "id": raw.get("id"),
                    "created": created.isoformat(),
                    "sender": sender,
                    "sender_id": sender_id,
                    "text": text,
                }
            )
        if not next_link:
            break
        next_link = data.get("@odata.nextLink")
        if not next_link or pages >= max_pages:
            break
    out.sort(key=lambda row: row["created"])
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mark-checked", action="store_true")
    args = parser.parse_args()

    state = load_state()
    sent_at_raw = state.get("message_createdDateTime") or state.get("sent_at")
    sent_at = parse_graph_time(sent_at_raw)
    g = GraphClient()
    rows = fetch_messages_after(g, state["chat_id"], sent_at - timedelta(seconds=1))
    sent_id = state.get("message_id")
    checked = set(state.get("feedback_checked_message_ids") or [])
    feedback = [row for row in rows if row.get("id") != sent_id]
    new_feedback = [row for row in feedback if row.get("id") not in checked]
    result = {
        "checked_at": datetime.now(KST).isoformat(),
        "chat_id": state["chat_id"],
        "sent_message_id": sent_id,
        "feedback_count": len(feedback),
        "new_feedback_count": len(new_feedback),
        "feedback": feedback,
        "new_feedback": new_feedback,
    }
    save_json(FEEDBACK_OUT, result)
    state["last_feedback_check_at"] = result["checked_at"]
    if args.mark_checked and new_feedback:
        state["feedback_checked_message_ids"] = sorted(checked | {row["id"] for row in new_feedback if row.get("id")})
    save_json(STATE_PATH, state)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
