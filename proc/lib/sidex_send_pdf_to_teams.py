#!/usr/bin/env python3
"""Upload the SIDEX PDF report and send its link to a Teams chat."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
sys.path.insert(0, str(ROOT / "proc/lib"))

from msgraph import GraphClient, GraphClientError  # noqa: E402
from onedrive import KST, OneDriveClient  # noqa: E402
from teams_graph import chat_list, send_chat_message  # noqa: E402


PDF_PATH = ROOT / "output/sidex-2026/pdf_report/SIDEX_2026_visit_report.pdf"
STATE_PATH = ROOT / "output/sidex-2026/pdf_report/teams_send_result.json"
TARGET_EMAIL = "ins@doflab.com"
REMOTE_FOLDER = "Reports/SIDEX 2026"
REMOTE_NAME = "SIDEX_2026_visit_report.pdf"


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def member_rows(g: GraphClient, chat_id: str) -> list[dict[str, Any]]:
    data = g.get(f"/me/chats/{chat_id}/members")
    return data.get("value") or []


def pick_chat(g: GraphClient, target_email: str) -> dict[str, Any]:
    me = g.get("/me")
    me_id = me.get("id")
    target = g.get(f"/users/{target_email}", params={"$select": "id,displayName,mail,userPrincipalName"})
    target_id = target.get("id")

    one_on_one = [row for row in chat_list(g, top=50) if row.get("kind") == "oneOnOne"]
    exact_hits: list[dict[str, Any]] = []
    self_hits: list[dict[str, Any]] = []
    for row in one_on_one:
        members = member_rows(g, row["chat_id"])
        member_ids = {m.get("userId") for m in members}
        member_emails = {(m.get("email") or "").lower() for m in members}
        row = {**row, "members": members}
        if target_id == me_id and len(member_ids) == 1 and me_id in member_ids:
            self_hits.append(row)
        elif target_id and target_id in member_ids and target_id != me_id:
            exact_hits.append(row)
        elif target_email.lower() in member_emails and target_id != me_id:
            exact_hits.append(row)

    if target_id == me_id and self_hits:
        return {"chat": self_hits[0], "target": target, "mode": "existing_self_chat"}
    if exact_hits:
        return {"chat": exact_hits[0], "target": target, "mode": "existing_one_on_one"}

    if target_id == me_id:
        raise RuntimeError("No existing self Teams chat was found for the current account.")

    body = {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{me_id}')",
            },
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{target_id}')",
            },
        ],
    }
    chat = g.post("/chats", json_body=body)
    return {"chat": {"chat_id": chat["id"], "members": []}, "target": target, "mode": "created_one_on_one"}


def ensure_remote_folder(od: OneDriveClient) -> None:
    current = ""
    for part in REMOTE_FOLDER.split("/"):
        parent = current or "/"
        current = f"{current}/{part}".strip("/")
        try:
            od.get_item(current)
        except Exception:
            od.create_folder(parent, part, conflict="fail")


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)
    g = GraphClient()
    od = OneDriveClient(g)
    ensure_remote_folder(od)
    remote_path = f"{REMOTE_FOLDER}/{REMOTE_NAME}"
    item = od.upload(str(PDF_PATH), remote_path, conflict="replace")
    link = od.share(remote_path, scope="view", link_type="organization")
    link_url = (link.get("link") or {}).get("webUrl") or item.get("web_url")
    if not link_url:
        raise RuntimeError("OneDrive upload succeeded but no share URL was returned.")

    picked = pick_chat(g, TARGET_EMAIL)
    chat_id = picked["chat"]["chat_id"]
    message = (
        "SIDEX 2026 방문 인사이트 PDF를 만들었습니다.\n\n"
        "- 업체 66개\n"
        "- 사진/자료 148장\n"
        "- 백인식 현장 메모 16건 반영\n"
        "- 분야별 통계와 업체별 요약 포함\n\n"
        f"PDF: {link_url}\n\n"
        "피드백 주시면 3시간 안에 확인해서 수정본까지 반영하겠습니다."
    )
    sent = send_chat_message(g, chat_id, message)
    now = datetime.now(KST).isoformat()
    result = {
        "sent_at": now,
        "target_email": TARGET_EMAIL,
        "target": picked["target"],
        "chat_id": chat_id,
        "chat_pick_mode": picked["mode"],
        "message_id": sent.get("id"),
        "message_createdDateTime": sent.get("createdDateTime"),
        "pdf_path": str(PDF_PATH),
        "onedrive_remote_path": remote_path,
        "onedrive_item": item,
        "share_url": link_url,
        "feedback_checked_message_ids": [],
    }
    save_json(STATE_PATH, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    except GraphClientError as exc:
        raise SystemExit(f"Graph error: {exc}") from exc
