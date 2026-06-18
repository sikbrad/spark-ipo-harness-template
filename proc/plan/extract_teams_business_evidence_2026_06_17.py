#!/usr/bin/env python3
"""Extract person-centered business-rule evidence from full Teams history."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


RUN_DATE = "2026-06-17"
ROOT = Path("data/teams/full-history") / RUN_DATE
OUT = Path("output/teams-business-rules") / RUN_DATE
EVIDENCE_DIR = OUT / "person_evidence"

TARGETS = {
    "김규탁": {
        "display": ["김규탁", "김규탁 Jake"],
        "email": "jakekim@doflab.com",
    },
    "조소연": {
        "display": ["조소연", "조소연 Anna"],
        "email": "jsy@doflab.com",
    },
    "정재회": {
        "display": ["정재회"],
        "email": "ndsp13@doflab.com",
    },
    "김채원": {
        "display": ["김채원"],
        "email": "cwkim@doflab.com",
    },
    "이미연": {
        "display": ["이미연"],
        "email": "mylee@doflab.com",
    },
}

CATEGORIES = {
    "주문/매출/영업관리": [
        "주문", "매출", "견적", "계약", "세일즈포스", "salesforce", "sf", "핑거세일즈",
        "쇼핑몰", "dof shop", "dofshop", "국내 주문", "주문방", "영업관리", "판매",
        "리포트", "report", "라인아이템", "opportunity", "quote",
    ],
    "출고/물류/재고": [
        "출고", "물류", "배송", "송장", "운송장", "택배", "통관", "선적", "packing",
        "패킹", "invoice", "인보이스", "재고", "입고", "납기", "퀵", "화물", "dhl",
        "ups", "fedex", "픽업", "출하", "창고",
    ],
    "정산/세금/회계": [
        "세금계산서", "계산서", "입금", "미수", "정산", "결제", "청구", "거래명세서",
        "전자세금", "영수증", "매입", "카드", "계좌", "마감", "회계",
    ],
    "고객/지원/이슈대응": [
        "고객", "문의", "요청", "지원요청", "대응", "확인요청", "cs", "이슈", "장애",
        "답변", "안내", "클레임", "문의사항", "처리", "해결", "확인 부탁",
    ],
    "수출관리/컴플라이언스": [
        "수출", "전략물자", "hs", "승인", "자율준수", "통제", "수출관리", "관세",
        "원산지", "통관서류", "license", "compliance", "자율수출",
    ],
    "내부프로세스/인수인계": [
        "공유", "전달", "확인", "담당", "양식", "리스트", "프로세스", "회의", "인수인계",
        "업데이트", "정리", "취합", "등록", "변경", "누락", "체크", "요청드립니다",
    ],
    "개발/시스템요청": [
        "개발", "배포", "api", "코드", "github", "서버", "버그", "ax", "crm", "포탈",
        "앱", "자동화", "python", "시스템", "수정", "noti-post-dev", "migration",
        "스마트 코딩", "리뉴얼", "프론트", "백엔드", "db",
    ],
}

ROUTINE_CATEGORY_ORDER = [
    "주문/매출/영업관리",
    "출고/물류/재고",
    "정산/세금/회계",
    "고객/지원/이슈대응",
    "수출관리/컴플라이언스",
    "내부프로세스/인수인계",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def text_of(item: dict) -> str:
    return re.sub(r"\s+", " ", item.get("text") or "").strip()


def category_hits(source_name: str, text: str) -> list[str]:
    haystack = f"{source_name}\n{text}".lower()
    hits = []
    for category, keywords in CATEGORIES.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            hits.append(category)
    return hits


def person_tokens(person: str) -> list[str]:
    info = TARGETS[person]
    tokens = list(info["display"])
    if info.get("email"):
        tokens.append(info["email"])
    return [t for t in tokens if t]


def is_target_author(person: str, who: str) -> bool:
    return any(token in (who or "") for token in TARGETS[person]["display"])


def members_include(person: str, members: list[dict]) -> bool:
    email = (TARGETS[person].get("email") or "").lower()
    displays = TARGETS[person]["display"]
    for member in members or []:
        if email and (member.get("email") or "").lower() == email:
            return True
        if any(token in (member.get("name") or member.get("displayName") or "") for token in displays):
            return True
    return False


def mentions_include(person: str, message: dict) -> bool:
    tokens = person_tokens(person)
    for mention in message.get("mentions") or []:
        mentioned = mention.get("mentioned") or {}
        blob = json.dumps(mentioned, ensure_ascii=False)
        if any(token in blob for token in tokens):
            return True
    return False


def text_mentions(person: str, text: str) -> bool:
    tokens = person_tokens(person)
    return any(token in text for token in tokens)


def collect_chat_items() -> list[dict]:
    items = []
    for path in sorted((ROOT / "chats").glob("*.json")):
        payload = load_json(path)
        chat = payload.get("chat") or {}
        source = chat.get("name") or path.stem
        messages = payload.get("messages") or []
        members = chat.get("members") or []
        for idx, message in enumerate(messages):
            items.append({
                "kind": "chat",
                "source": source,
                "source_path": str(path),
                "source_id": chat.get("chat_id"),
                "source_kind": chat.get("kind"),
                "members": members,
                "idx": idx,
                "ts": message.get("ts"),
                "who": message.get("who") or "",
                "text": text_of(message),
                "web_url": message.get("web_url"),
                "mentions": message.get("mentions") or [],
            })
    return items


def collect_channel_items() -> list[dict]:
    items = []
    channel_dir = ROOT / "channels"
    if not channel_dir.exists():
        return items
    for path in sorted(channel_dir.glob("*.json")):
        payload = load_json(path)
        channel = payload.get("channel") or {}
        source = f"{channel.get('team_name') or ''} / {channel.get('channel_name') or ''}".strip()
        for thread_idx, thread in enumerate(payload.get("threads") or []):
            parent = thread.get("parent") or {}
            messages = [("parent", parent)] + [(f"reply:{i}", reply) for i, reply in enumerate(thread.get("replies") or [])]
            for idx, (role, message) in enumerate(messages):
                items.append({
                    "kind": "channel",
                    "source": source,
                    "source_path": str(path),
                    "source_id": channel.get("channel_id"),
                    "team_id": channel.get("team_id"),
                    "thread_idx": thread_idx,
                    "message_role": role,
                    "idx": idx,
                    "ts": message.get("ts"),
                    "who": message.get("who") or "",
                    "text": text_of(message),
                    "web_url": message.get("web_url"),
                    "mentions": message.get("mentions") or [],
                })
    return items


def interesting_for_person(person: str, item: dict) -> tuple[bool, list[str]]:
    reasons = []
    if is_target_author(person, item.get("who") or ""):
        reasons.append("author")
    if item.get("kind") == "chat" and members_include(person, item.get("members") or []):
        reasons.append("chat_member")
    if text_mentions(person, item.get("text") or ""):
        reasons.append("text_mention")
    if mentions_include(person, item):
        reasons.append("graph_mention")
    return bool(reasons), reasons


def compact_item(item: dict, reasons: list[str]) -> dict:
    categories = category_hits(item.get("source") or "", item.get("text") or "")
    return {
        "ts": item.get("ts"),
        "who": item.get("who"),
        "source": item.get("source"),
        "kind": item.get("kind"),
        "source_kind": item.get("source_kind"),
        "text": item.get("text"),
        "categories": categories,
        "is_dev_system": "개발/시스템요청" in categories,
        "routine_categories": [c for c in categories if c in ROUTINE_CATEGORY_ORDER],
        "reasons": reasons,
        "web_url": item.get("web_url"),
        "source_path": item.get("source_path"),
    }


def first_last(items: list[dict]) -> tuple[str | None, str | None]:
    dates = sorted(i.get("ts") for i in items if i.get("ts"))
    return (dates[0], dates[-1]) if dates else (None, None)


def build_person_summary(person: str, all_items: list[dict]) -> dict:
    evidence = []
    for item in all_items:
        ok, reasons = interesting_for_person(person, item)
        if not ok:
            continue
        compact = compact_item(item, reasons)
        if not compact["text"] and not compact["categories"]:
            continue
        evidence.append(compact)

    evidence.sort(key=lambda i: i.get("ts") or "")
    routine = [i for i in evidence if i["routine_categories"]]
    routine_non_dev = [i for i in routine if not i["is_dev_system"] or len(i["routine_categories"]) >= 2]

    category_counter = Counter()
    source_counter = Counter()
    author_counter = Counter()
    reason_counter = Counter()
    for item in evidence:
        source_counter[item["source"]] += 1
        author_counter[item["who"]] += 1
        for reason in item["reasons"]:
            reason_counter[reason] += 1
        for category in item["categories"]:
            category_counter[category] += 1

    samples_by_category: dict[str, list[dict]] = defaultdict(list)
    for category in ROUTINE_CATEGORY_ORDER:
        seen = set()
        for item in routine_non_dev:
            if category not in item["routine_categories"]:
                continue
            key = (item["source"], item["who"], item["text"][:80])
            if key in seen:
                continue
            seen.add(key)
            samples_by_category[category].append(item)
            if len(samples_by_category[category]) >= 18:
                break

    return {
        "person": person,
        "aliases": TARGETS[person],
        "evidence_count": len(evidence),
        "routine_evidence_count": len(routine),
        "routine_non_dev_count": len(routine_non_dev),
        "date_range": first_last(evidence),
        "category_counts": dict(category_counter.most_common()),
        "top_sources": dict(source_counter.most_common(30)),
        "top_authors": dict(author_counter.most_common(20)),
        "reason_counts": dict(reason_counter.most_common()),
        "samples_by_category": samples_by_category,
        "recent_routine_non_dev": routine_non_dev[-120:],
        "all_evidence_path": str(EVIDENCE_DIR / f"{person}_all_evidence.json"),
    }


def render_markdown(summaries: dict[str, dict]) -> str:
    lines = [
        "# Teams 업무규칙 분석 후보 근거",
        "",
        f"- source_root: `{ROOT}`",
        f"- generated_from: Teams full-history {RUN_DATE}",
        "",
    ]
    for person, summary in summaries.items():
        lines.extend([
            f"## {person}",
            "",
            f"- evidence_count: {summary['evidence_count']}",
            f"- routine_non_dev_count: {summary['routine_non_dev_count']}",
            f"- date_range: {summary['date_range'][0]} ~ {summary['date_range'][1]}",
            f"- top_sources: {', '.join(f'{k}({v})' for k, v in list(summary['top_sources'].items())[:8])}",
            f"- category_counts: {', '.join(f'{k}({v})' for k, v in summary['category_counts'].items())}",
            "",
        ])
        for category in ROUTINE_CATEGORY_ORDER:
            samples = summary["samples_by_category"].get(category) or []
            if not samples:
                continue
            lines.extend([f"### {category}", ""])
            for sample in samples[:10]:
                text = sample["text"]
                if len(text) > 240:
                    text = text[:237] + "..."
                lines.append(
                    f"- {sample['ts']} | {sample['source']} | {sample['who']}: {text}"
                )
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    all_items = collect_chat_items() + collect_channel_items()
    all_items.sort(key=lambda i: i.get("ts") or "")

    summaries = {}
    for person in TARGETS:
        summary = build_person_summary(person, all_items)
        summaries[person] = summary
        all_evidence = []
        for item in all_items:
            ok, reasons = interesting_for_person(person, item)
            if ok:
                all_evidence.append(compact_item(item, reasons))
        write_path = EVIDENCE_DIR / f"{person}_all_evidence.json"
        write_path.write_text(json.dumps(all_evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT / "evidence_summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "evidence_digest.md").write_text(render_markdown(summaries), encoding="utf-8")
    print(json.dumps({
        "items": len(all_items),
        "persons": {person: summaries[person]["routine_non_dev_count"] for person in summaries},
        "output": str(OUT),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
