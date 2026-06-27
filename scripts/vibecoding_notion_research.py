#!/usr/bin/env python3
"""Extract Notion evidence for Malaka's author profile and book direction."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path("data/vibecoding-book")
NOTION_DIR = Path("data/notion/hydrated")
OUT_DIR = ROOT / "research"

TOPICS = {
    "identity": ["말라카", "malaka", "백인식", "강연자", "발표자", "나의", "내가"],
    "ai_vibecoding": ["AI", "ai", "GPT", "ChatGPT", "Claude", "Codex", "Cursor", "Lovable", "바이브코딩", "프롬프트", "에이전트"],
    "automation": ["자동화", "브라우저", "Playwright", "API", "스크래핑", "크롤", "워크플로", "업무"],
    "startup_product": ["창업", "스타트업", "MVP", "고객", "사업", "제품", "기획", "서비스", "검증"],
    "teaching_writing": ["강의", "교육", "책", "출판", "글쓰기", "발표", "워크숍", "커리큘럼"],
    "operations": ["ERP", "포탈", "Salesforce", "Slack", "Teams", "노션", "캘린더", "메일", "데이터"],
    "life_philosophy": ["회고", "생각", "일상", "가족", "건강", "삶", "습관", "시간", "감정"],
}


@dataclass
class PageRecord:
    path: Path
    page_id: str
    title: str
    created_time: str
    last_edited_time: str
    data_source_id: str
    data_source_title: str
    text: str
    score: int
    topic_scores: dict[str, int]


def rich_text_to_plain(value: Any) -> str:
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(item.get("plain_text") or item.get("text", {}).get("content", ""))
        return "".join(parts)
    return ""


def collect_plain_values(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, dict):
        if "plain_text" in value and isinstance(value["plain_text"], str):
            texts.append(value["plain_text"])
        if value.get("type") in {"title", "rich_text"}:
            texts.append(rich_text_to_plain(value.get(value["type"], [])))
        for key, child in value.items():
            if key in {"id", "object", "created_by", "last_edited_by", "parent", "annotations"}:
                continue
            texts.extend(collect_plain_values(child))
    elif isinstance(value, list):
        for child in value:
            texts.extend(collect_plain_values(child))
    elif isinstance(value, str):
        if len(value) > 1 and not re.fullmatch(r"[a-f0-9-]{16,}", value):
            texts.append(value)
    return texts


def page_title(page: dict[str, Any]) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            title = rich_text_to_plain(prop.get("title", []))
            if title:
                return title
    url = page.get("url") or ""
    return url.rsplit("/", 1)[-1] or page.get("id", "")


def block_text(block: dict[str, Any]) -> list[str]:
    typ = block.get("type")
    texts: list[str] = []
    if typ and isinstance(block.get(typ), dict):
        payload = block[typ]
        for key in ("rich_text", "caption"):
            plain = rich_text_to_plain(payload.get(key, []))
            if plain:
                texts.append(plain)
        if typ in {"child_page", "child_database"} and payload.get("title"):
            texts.append(str(payload["title"]))
    for child in block.get("children", []) or []:
        texts.extend(block_text(child))
    return texts


def load_data_source_titles() -> dict[str, str]:
    titles = {}
    for path in (NOTION_DIR / "data_sources").glob("*.json"):
        obj = json.loads(path.read_text(encoding="utf-8"))
        title = rich_text_to_plain(obj.get("title", [])) or path.stem
        titles[obj["id"]] = title
    return titles


def keyword_count(text: str, keywords: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(keyword.lower()) for keyword in keywords)


def summarize_excerpt(text: str, keywords: list[str], limit: int = 280) -> str:
    chunks = [clean_ws(item) for item in re.split(r"[\n。.!?！？]+", text) if clean_ws(item)]
    for keyword in keywords:
        for chunk in chunks:
            if keyword.lower() in chunk.lower() and len(chunk) > 8:
                return chunk[:limit]
    return (chunks[0] if chunks else "")[:limit]


def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def load_pages() -> list[PageRecord]:
    data_sources = load_data_source_titles()
    records: list[PageRecord] = []
    all_keywords = sorted({keyword for values in TOPICS.values() for keyword in values}, key=len, reverse=True)
    for path in (NOTION_DIR / "pages").glob("*.json"):
        page = json.loads(path.read_text(encoding="utf-8"))
        parent = page.get("parent", {})
        data_source_id = parent.get("data_source_id") or parent.get("database_id") or ""
        title = page_title(page)
        prop_text = "\n".join(clean_ws(item) for item in collect_plain_values(page.get("properties", {})) if clean_ws(item))
        body_text = "\n".join(clean_ws(item) for block in page.get("blocks", []) for item in block_text(block) if clean_ws(item))
        text = clean_ws("\n".join([title, prop_text, body_text]))
        topic_scores = {name: keyword_count(text, keywords) for name, keywords in TOPICS.items()}
        score = keyword_count(text, all_keywords)
        if score <= 0:
            continue
        records.append(
            PageRecord(
                path=path,
                page_id=page.get("id", ""),
                title=title,
                created_time=page.get("created_time", ""),
                last_edited_time=page.get("last_edited_time", ""),
                data_source_id=data_source_id,
                data_source_title=data_sources.get(data_source_id, ""),
                text=text,
                score=score,
                topic_scores=topic_scores,
            )
        )
    return records


def write_outputs(records: list[PageRecord]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    topic_ranked: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        for topic, score in record.topic_scores.items():
            if score:
                topic_ranked[topic].append(
                    {
                        "title": record.title,
                        "path": str(record.path),
                        "data_source": record.data_source_title,
                        "created_time": record.created_time,
                        "last_edited_time": record.last_edited_time,
                        "score": score,
                        "excerpt": summarize_excerpt(record.text, TOPICS[topic]),
                    }
                )

    for items in topic_ranked.values():
        items.sort(key=lambda item: (item["score"], item["last_edited_time"]), reverse=True)

    corpus = [
        {
            "title": record.title,
            "path": str(record.path),
            "data_source": record.data_source_title,
            "created_time": record.created_time,
            "last_edited_time": record.last_edited_time,
            "score": record.score,
            "topic_scores": record.topic_scores,
            "excerpt": summarize_excerpt(record.text, sorted({k for v in TOPICS.values() for k in v}, key=len, reverse=True), 420),
        }
        for record in sorted(records, key=lambda item: item.score, reverse=True)
    ]
    (OUT_DIR / "notion-author-corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "notion-topic-evidence.json").write_text(json.dumps(topic_ranked, ensure_ascii=False, indent=2), encoding="utf-8")

    data_source_counts = Counter(record.data_source_title or "(unknown)" for record in records)
    lines = [
        "# Notion author profile evidence",
        "",
        f"- Relevant pages scanned: {len(records)}",
        f"- Topic buckets: {', '.join(TOPICS)}",
        "",
        "## Data sources with relevant signals",
        "",
    ]
    for name, count in data_source_counts.most_common(20):
        lines.append(f"- {name}: {count}")

    for topic, label in [
        ("identity", "Identity / self presentation"),
        ("ai_vibecoding", "AI and vibecoding"),
        ("automation", "Automation and workflows"),
        ("startup_product", "Startup, MVP, and product"),
        ("teaching_writing", "Teaching and publishing"),
        ("operations", "Operational systems"),
        ("life_philosophy", "Life and working philosophy"),
    ]:
        lines.extend(["", f"## {label}", ""])
        for item in topic_ranked.get(topic, [])[:12]:
            lines.append(f"### {item['title']}")
            lines.append(f"- Source: `{item['path']}`")
            lines.append(f"- Data source: {item['data_source'] or '(unknown)'}")
            lines.append(f"- Score: {item['score']}")
            lines.append(f"- Excerpt: {item['excerpt']}")
            lines.append("")

    lines.extend(
        [
            "## Synthesis for this book",
            "",
            "- 말라카는 개발/자동화/운영을 추상 담론이 아니라 실제 업무 산출물로 바꾸는 쪽에 관심이 강하다.",
            "- Notion에는 AI 도구, 검색/리서치, 프로젝트/태스크 운영, 출판 보드, 업무 자동화 신호가 함께 나타난다.",
            "- 따라서 책의 저자 목소리는 기술 소개자가 아니라 '문제와 도구 사이에서 반복 가능한 실행법을 설계하는 실무자'에 가깝게 잡는다.",
            "- 강의 PPT의 핵심 소재는 바이브코딩/MVP/웹앱/AI 에이전트이고, Notion의 핵심 맥락은 기록, 운영, 자동화, 출판/교육으로 보강한다.",
        ]
    )
    (OUT_DIR / "notion-author-profile-evidence.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    records = load_pages()
    write_outputs(records)
    print(f"records={len(records)}")
    print((OUT_DIR / "notion-author-profile-evidence.md").resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
