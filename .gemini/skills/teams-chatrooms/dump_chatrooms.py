#!/usr/bin/env python3
"""Dump all Teams chatrooms (DM / group / meeting) the current user belongs to.

Output: a markdown summary at data/teams/chatrooms_list.md (path overridable).
Source: MS Graph `/me/chats` with `$expand=members,lastMessagePreview`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "proc" / "lib"))

from msgraph import GraphClient  # noqa: E402
from teams_graph import _kst, _strip_html  # noqa: E402


def fetch_chats(g: GraphClient) -> tuple[dict, list[dict]]:
    me = g.get("/me")
    me_id = me.get("id") or ""
    me_email = me.get("mail") or me.get("userPrincipalName") or ""

    items: list[dict] = []
    for c in g.paged(
        "/me/chats",
        params={
            "$top": 50,
            "$expand": "members,lastMessagePreview",
            "$orderby": "lastMessagePreview/createdDateTime desc",
        },
    ):
        last = c.get("lastMessagePreview") or {}
        body = last.get("body") or {}
        text = body.get("content") or ""
        if body.get("contentType") == "html":
            text = _strip_html(text)
        sender_user = ((last.get("from") or {}).get("user") or {})
        last_who = sender_user.get("displayName") or ""
        last_by_me = (sender_user.get("id") or "") == me_id
        last_ts = _kst(last.get("createdDateTime")) if last.get("createdDateTime") else None
        members = [
            {
                "name": m.get("displayName") or "",
                "email": m.get("email") or "",
                "user_id": m.get("userId") or "",
                "roles": m.get("roles") or [],
            }
            for m in (c.get("members") or [])
        ]
        items.append({
            "chat_id": c.get("id"),
            "kind": c.get("chatType") or "",
            "name": c.get("topic") or "",
            "created": c.get("createdDateTime"),
            "web_url": c.get("webUrl"),
            "members": members,
            "last_msg_preview": text[:200],
            "last_who": last_who,
            "last_ts": last_ts.isoformat() if last_ts else None,
            "last_by_me": last_by_me,
        })

    return {"me_id": me_id, "me_email": me_email}, items


def fmt_ts(ts: str | None) -> str:
    return ts[:16].replace("T", " ") if ts else "-"


def partner(c: dict, me_id: str, me_email: str) -> dict | None:
    for m in c["members"]:
        if m["user_id"] != me_id and m["email"] != me_email:
            return m
    return None


def members_inline(c: dict, me_id: str, limit: int | None = None) -> str:
    names = []
    for m in c["members"]:
        nm = m["name"] or m["email"] or m["user_id"] or "?"
        if m["user_id"] == me_id:
            nm += " (나)"
        names.append(nm)
    if limit and len(names) > limit:
        return ", ".join(names[:limit]) + f" … (+{len(names) - limit})"
    return ", ".join(names)


def render_markdown(meta: dict, chats: list[dict]) -> str:
    me_id = meta["me_id"]
    me_email = meta["me_email"]
    dms = [c for c in chats if c["kind"] == "oneOnOne"]
    groups = [c for c in chats if c["kind"] == "group"]
    meetings = [c for c in chats if c["kind"] == "meeting"]
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    out: list[str] = []
    out.append("# Microsoft Teams 채팅방 목록")
    out.append("")
    out.append(f"- 추출일: {today} (KST)")
    out.append(f"- 본인: {me_email} (`{me_id}`)")
    out.append("- 데이터 소스: MS Graph `/me/chats` (`$expand=members,lastMessagePreview`)")
    out.append(
        f"- 총 채팅방: **{len(chats)}** (DM {len(dms)} / 그룹 {len(groups)} / 회의 {len(meetings)})"
    )
    out.append("")
    out.append("정렬: 최근 메시지 시각 내림차순. `last_by_me`는 마지막 메시지를 내가 보냈는지 여부.")
    out.append("")

    out.append(f"## 1) DM (1:1) — {len(dms)}개")
    out.append("")
    out.append("| # | 상대 | 이메일 | 마지막 발신자 | 마지막 시각 | by me |")
    out.append("|---|------|--------|--------------|-------------|-------|")
    for i, c in enumerate(dms, 1):
        p = partner(c, me_id, me_email) or {}
        nm = p.get("name", "") or "(unknown)"
        em = p.get("email", "") or ""
        out.append(
            f"| {i} | {nm} | {em} | {c['last_who']} | {fmt_ts(c['last_ts'])} | "
            f"{'✅' if c['last_by_me'] else ''} |"
        )
    out.append("")

    out.append(f"## 2) 그룹 채팅 — {len(groups)}개")
    out.append("")
    for i, c in enumerate(groups, 1):
        name = c["name"] or "(이름 없음)"
        out.append(f"### G{i:02d}. {name}")
        out.append("")
        out.append(f"- 멤버 수: {len(c['members'])}명")
        out.append(
            f"- 마지막 메시지: {fmt_ts(c['last_ts'])} — **{c['last_who']}**"
            + (" (나)" if c["last_by_me"] else "")
        )
        if c["last_msg_preview"]:
            prev = c["last_msg_preview"].replace("\n", " ")[:120]
            out.append(f"  - > {prev}")
        out.append(f"- 멤버: {members_inline(c, me_id)}")
        out.append(f"- chat_id: `{c['chat_id']}`")
        out.append("")

    out.append(f"## 3) 회의 채팅 (Teams 회의에서 생성됨) — {len(meetings)}개")
    out.append("")
    for i, c in enumerate(meetings, 1):
        name = c["name"] or "(이름 없음)"
        out.append(f"### M{i:02d}. {name}")
        out.append("")
        out.append(f"- 멤버 수: {len(c['members'])}명")
        out.append(
            f"- 마지막 메시지: {fmt_ts(c['last_ts'])} — **{c['last_who']}**"
            + (" (나)" if c["last_by_me"] else "")
        )
        if c["last_msg_preview"]:
            prev = c["last_msg_preview"].replace("\n", " ")[:120]
            out.append(f"  - > {prev}")
        out.append(f"- 멤버: {members_inline(c, me_id, limit=15)}")
        out.append(f"- chat_id: `{c['chat_id']}`")
        out.append("")

    out.append("---")
    out.append("")
    out.append("## 부록: chat_id 빠른 참조")
    out.append("")
    out.append("| 종류 | 이름/상대 | chat_id |")
    out.append("|------|-----------|---------|")
    for c in dms:
        p = partner(c, me_id, me_email) or {}
        out.append(f"| DM | {p.get('name', '') or '(unknown)'} | `{c['chat_id']}` |")
    for c in groups:
        out.append(f"| 그룹 | {c['name'] or '(이름 없음)'} | `{c['chat_id']}` |")
    for c in meetings:
        out.append(f"| 회의 | {c['name'] or '(이름 없음)'} | `{c['chat_id']}` |")

    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        default="data/teams/chatrooms_list.md",
        help="output markdown path (default: data/teams/chatrooms_list.md)",
    )
    ap.add_argument(
        "--json",
        default=None,
        help="optional raw JSON dump path (e.g. data/teams/chatrooms_list.json)",
    )
    args = ap.parse_args()

    g = GraphClient()
    meta, chats = fetch_chats(g)
    md = render_markdown(meta, chats)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")

    print(
        f"[teams-chatrooms] wrote {out_path} — {len(chats)} chats "
        f"(DM {sum(1 for c in chats if c['kind'] == 'oneOnOne')} / "
        f"group {sum(1 for c in chats if c['kind'] == 'group')} / "
        f"meeting {sum(1 for c in chats if c['kind'] == 'meeting')})"
    )

    if args.json:
        jp = Path(args.json)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(
            json.dumps({"meta": meta, "chats": chats}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"[teams-chatrooms] wrote {jp}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
