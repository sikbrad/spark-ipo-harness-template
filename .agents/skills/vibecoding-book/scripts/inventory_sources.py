#!/usr/bin/env python3
"""Inventory local source material for the vibecoding book workflow."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


KEYWORDS = [
    "바이브",
    "vibe",
    "vibecoding",
    "vivecoding",
    "책",
    "출간",
    "목차",
    "강의",
    "실습",
    "말라카",
    "AX",
    "자동화",
    "사내교육",
    "클리닉",
    "카카오모빌리티",
    "카모",
    "MVP",
    "CRM",
    "ERP",
    "거래원장",
    "ChatGPT",
    "Claude",
    "Cursor",
    "Lovable",
]

SCAN_DIRS = [
    "data/daily",
    "data/notion/md",
    "data/vibecoding-book",
    "proc/plan",
    "output/teams/conversations",
]

SCAN_SUFFIXES = {".md", ".txt", ".json"}
MAX_SCAN_BYTES = 1_000_000


def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def safe_text(path: Path, limit: int = MAX_SCAN_BYTES) -> str:
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return ""
    return data.decode("utf-8", errors="ignore")


def keyword_score(text: str) -> tuple[int, dict[str, int]]:
    lower = text.lower()
    counts = {kw: lower.count(kw.lower()) for kw in KEYWORDS}
    return sum(counts.values()), {k: v for k, v in counts.items() if v}


def excerpt_for(text: str) -> str:
    chunks = [clean_ws(chunk) for chunk in re.split(r"[\n.!?。！？]+", text) if clean_ws(chunk)]
    for keyword in KEYWORDS:
        for chunk in chunks:
            if keyword.lower() in chunk.lower():
                return chunk[:360]
    return (chunks[0] if chunks else "")[:360]


def count_glob(root: Path, pattern: str) -> int:
    return sum(1 for _ in root.glob(pattern))


def chatgpt_summary(root: Path) -> dict[str, Any]:
    db = root / "data/db/chatgpt.sqlite"
    summary: dict[str, Any] = {"path": str(db), "exists": db.exists()}
    if not db.exists():
        return summary
    query = """
        SELECT title, create_time, update_time
        FROM conversations
        WHERE lower(title) LIKE lower(?)
        ORDER BY update_time DESC
        LIMIT 30
    """
    like_patterns = [
        "%바이브%",
        "%vibe%",
        "%책%",
        "%출간%",
        "%AX%",
        "%자동화%",
        "%강의%",
        "%MVP%",
        "%ChatGPT%",
    ]
    try:
        with sqlite3.connect(db) as conn:
            total, min_create, max_update = conn.execute(
                "SELECT COUNT(*), MIN(create_time), MAX(update_time) FROM conversations"
            ).fetchone()
            hits: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            for pattern in like_patterns:
                for title, create_time, update_time in conn.execute(query, (pattern,)):
                    key = (title or "", update_time or "")
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append(
                        {
                            "title": title or "",
                            "create_time": create_time or "",
                            "update_time": update_time or "",
                        }
                    )
            summary.update(
                {
                    "total_conversations": total,
                    "min_create_time": min_create,
                    "max_update_time": max_update,
                    "keyword_title_hits": hits[:30],
                }
            )
    except sqlite3.Error as exc:
        summary["error"] = str(exc)
    return summary


def ppt_summary(root: Path) -> dict[str, Any]:
    base = root / "data/vibecoding-book/extracts"
    all_slides = base / "all-slides.json"
    decks = base / "decks.json"
    summary: dict[str, Any] = {
        "extract_dir": str(base),
        "extract_dir_exists": base.exists(),
        "deck_dirs": count_glob(base, "*/slides.json") if base.exists() else 0,
        "all_slides_json": str(all_slides),
        "decks_json": str(decks),
    }
    if all_slides.exists():
        try:
            payload = json.loads(all_slides.read_text(encoding="utf-8"))
            slides = payload if isinstance(payload, list) else payload.get("slides", [])
            summary["all_slides_count"] = len(slides) if isinstance(slides, list) else 0
        except Exception as exc:
            summary["all_slides_error"] = str(exc)
    return summary


def daily_summary(root: Path) -> dict[str, Any]:
    daily = root / "data/daily"
    raw_names = Counter(path.name for path in daily.glob("*/raw/*")) if daily.exists() else Counter()
    voice_files = sorted(daily.glob("*/raw/voice-*.txt")) if daily.exists() else []
    voice_keyword_counts = Counter()
    for path in voice_files:
        name = path.name.lower()
        for keyword in ["ax", "강의", "회사", "거래원장", "일기", "kubit", "ai"]:
            if keyword.lower() in name:
                voice_keyword_counts[keyword] += 1
    return {
        "daily_dir": str(daily),
        "daily_dir_exists": daily.exists(),
        "summary_md_count": count_glob(daily, "*/summary.md") if daily.exists() else 0,
        "notion_jot_count": raw_names.get("notion-jot.json", 0),
        "notion_edited_count": raw_names.get("notion-edited.json", 0),
        "teams_chats_count": raw_names.get("teams-chats.json", 0),
        "outlook_count": raw_names.get("outlook.json", 0),
        "voice_transcript_count": len(voice_files),
        "voice_filename_keyword_counts": dict(voice_keyword_counts),
        "recent_voice_transcripts": [str(path) for path in voice_files[-30:]],
    }


def notion_summary(root: Path) -> dict[str, Any]:
    md = root / "data/notion/md"
    hydrated = root / "data/notion/hydrated/pages"
    dump_pages = root / "data/notion/dump/pages"
    return {
        "md_dir": str(md),
        "md_count": count_glob(md, "**/*.md") if md.exists() else 0,
        "hydrated_pages_dir": str(hydrated),
        "hydrated_pages_count": count_glob(hydrated, "*.json") if hydrated.exists() else 0,
        "dump_pages_dir": str(dump_pages),
        "dump_pages_count": count_glob(dump_pages, "*.json") if dump_pages.exists() else 0,
    }


def scan_candidates(root: Path, limit: int = 80) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for rel in SCAN_DIRS:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            if ".git" in path.parts or "node_modules" in path.parts:
                continue
            text = safe_text(path)
            score, counts = keyword_score(text)
            if score <= 0:
                continue
            candidates.append(
                {
                    "path": str(path),
                    "score": score,
                    "keyword_counts": counts,
                    "size": path.stat().st_size,
                    "excerpt": excerpt_for(text),
                }
            )
    candidates.sort(key=lambda item: (item["score"], item["size"]), reverse=True)
    return candidates[:limit]


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Vibecoding Book Source Inventory",
        "",
        f"- Created at: {payload['created_at']}",
        f"- Root: `{payload['root']}`",
        "",
        "## Counts",
        "",
        f"- PPT extract deck dirs: {payload['ppt']['deck_dirs']}",
        f"- PPT extracted slides: {payload['ppt'].get('all_slides_count', 0)}",
        f"- Daily summaries: {payload['daily']['summary_md_count']}",
        f"- Daily Notion Jot raw files: {payload['daily']['notion_jot_count']}",
        f"- Voice transcripts: {payload['daily']['voice_transcript_count']}",
        f"- Notion markdown files: {payload['notion']['md_count']}",
        f"- Notion hydrated pages: {payload['notion']['hydrated_pages_count']}",
        f"- ChatGPT conversations: {payload['chatgpt'].get('total_conversations', 0)}",
        "",
        "## Voice Transcript Filename Signals",
        "",
    ]
    voice_counts = payload["daily"].get("voice_filename_keyword_counts", {})
    if voice_counts:
        for key, count in sorted(voice_counts.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- No voice filename keyword signals found.")

    lines.extend(["", "## ChatGPT Title Hits", ""])
    for item in payload["chatgpt"].get("keyword_title_hits", [])[:20]:
        lines.append(f"- {item['update_time']} — {item['title']}")

    lines.extend(["", "## Top Local Candidate Files", ""])
    for item in payload["candidates"][:40]:
        counts = ", ".join(f"{k}:{v}" for k, v in sorted(item["keyword_counts"].items(), key=lambda kv: kv[1], reverse=True)[:6])
        lines.append(f"### {item['path']}")
        lines.append(f"- score: {item['score']} ({counts})")
        lines.append(f"- excerpt: {item['excerpt']}")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository/workspace root to scan")
    parser.add_argument("--out", default=None, help="Output directory for source-inventory files")
    parser.add_argument("--candidate-limit", type=int, default=80)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.out).resolve() if args.out else root / "data/vibecoding-book/source-inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "keywords": KEYWORDS,
        "ppt": ppt_summary(root),
        "daily": daily_summary(root),
        "notion": notion_summary(root),
        "chatgpt": chatgpt_summary(root),
        "candidates": scan_candidates(root, args.candidate_limit),
    }
    (out_dir / "source-inventory.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload, out_dir / "source-inventory.md")
    print(json.dumps({"out": str(out_dir), "candidates": len(payload["candidates"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
