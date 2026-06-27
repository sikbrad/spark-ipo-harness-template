#!/usr/bin/env python3
"""Update Outline middle-document status sections from the local Outline cache."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
BASE = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
OUT_DIR = BASE / "outline_publish/middle_docs_update"
DOC_CACHE = BASE / "outline_publish/outline_docs.json"
OUTLINE_BASE = "https://outline.doflab.com"
ROOT_DOC_ID = "89c2b595-26e3-43fd-b4d2-23d514515e2d"
ROOT_URL_ID = "7jib7jef7lky7zue67o0-c0ae88mpyc"
ROOT_URL = f"{OUTLINE_BASE}/doc/{ROOT_URL_ID}"
SECTION_TITLE_TEXT = "현재 하위 현황 (자동 갱신)"
SECTION_TITLE = f"## {SECTION_TITLE_TEXT}"
APPEND_SECTION_TITLE_TEXT = "현재 하위 현황 추가 갱신 (2026-06-04)"
APPEND_SECTION_TITLE = f"## {APPEND_SECTION_TITLE_TEXT}"
KST_DATE = "2026-06-04"
STATUS_LABELS = ["기존고객", "잠재고객-치과", "잠재고객-교정치과", "잠재고객-치기공", "잠재고객-유통사"]


@dataclass
class Doc:
    id: str
    title: str
    url_id: str = ""
    parent_id: str = ""
    archived_at: str | None = None
    deleted_at: str | None = None


@dataclass
class Stats:
    id: str
    title: str
    url_id: str
    parent_id: str
    path_parts: list[str]
    direct_children: list[dict[str, str]] = field(default_factory=list)
    direct_folder_count: int = 0
    direct_company_count: int = 0
    descendant_folder_count: int = 0
    descendant_company_count: int = 0
    statuses: Counter[str] = field(default_factory=Counter)
    regions: Counter[str] = field(default_factory=Counter)
    countries: Counter[str] = field(default_factory=Counter)

    @property
    def path(self) -> str:
        return " / ".join(self.path_parts)

    @property
    def depth(self) -> int:
        return max(0, len(self.path_parts) - 1)

    @property
    def url(self) -> str:
        return f"{OUTLINE_BASE}/doc/{self.url_id}"


class OutlineClient:
    def __init__(self, key: str, timeout: int):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {key}"})

    def api(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                response = self.session.post(f"{OUTLINE_BASE}/api/{endpoint}", json=body, timeout=self.timeout)
                payload = response.json()
                if response.status_code < 400 and payload.get("success") is not False:
                    return payload
                if response.status_code not in {429, 500, 502, 503, 504}:
                    raise RuntimeError(f"{endpoint} failed {response.status_code}: {response.text[:600]}")
            except Exception as error:  # requests wraps timeout/connectivity in multiple concrete classes.
                last_error = error
            time.sleep(min(20, attempt * 2))
        raise RuntimeError(f"{endpoint} failed after retries: {last_error}")

    def document_info(self, doc_id: str) -> dict[str, Any]:
        return self.api("documents.info", {"id": doc_id})["data"]

    def document_update(self, doc_id: str, title: str, text: str) -> dict[str, Any]:
        return self.api("documents.update", {"id": doc_id, "title": title, "text": text, "publish": True, "fullWidth": True})[
            "data"
        ]

    def document_append(self, doc_id: str, text: str) -> dict[str, Any]:
        return self.api("documents.update", {"id": doc_id, "text": text, "append": True, "publish": True, "fullWidth": True})["data"]


def read_env_key(name: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError(f"{name} not found")


def md_escape(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|])", r"\\\1", text)


def md_link(label: str, url: str) -> str:
    return f"[{md_escape(label or url)}]({url})"


def load_cache_docs() -> list[Doc]:
    cache = json.loads(DOC_CACHE.read_text(encoding="utf-8"))
    docs = [
        Doc(id=ROOT_DOC_ID, title="영업처후보", url_id=ROOT_URL_ID, parent_id=""),
    ]
    for raw in (cache.get("docs") or {}).values():
        if not isinstance(raw, dict) or not raw.get("id") or raw.get("id") == ROOT_DOC_ID:
            continue
        docs.append(
            Doc(
                id=str(raw.get("id")),
                title=str(raw.get("title") or ""),
                url_id=str(raw.get("url_id") or ""),
                parent_id=str(raw.get("parent_document_id") or ""),
                archived_at=raw.get("archived_at"),
                deleted_at=raw.get("deleted_at"),
            )
        )
    return docs


def build_tree(docs: list[Doc]) -> tuple[dict[str, Doc], dict[str, list[Doc]]]:
    by_id = {doc.id: doc for doc in docs}
    children_by_parent: dict[str, list[Doc]] = defaultdict(list)
    for doc in docs:
        if doc.archived_at or doc.deleted_at:
            continue
        children_by_parent[doc.parent_id].append(doc)
    for children in children_by_parent.values():
        children.sort(key=lambda doc: doc.title)
    return by_id, children_by_parent


def collect_reachable(children_by_parent: dict[str, list[Doc]]) -> set[str]:
    reachable: set[str] = set()
    stack = [ROOT_DOC_ID]
    while stack:
        doc_id = stack.pop()
        if doc_id in reachable:
            continue
        reachable.add(doc_id)
        stack.extend(child.id for child in children_by_parent.get(doc_id, []))
    return reachable


def path_of(doc: Doc, by_id: dict[str, Doc]) -> list[str]:
    parts: list[str] = []
    seen: set[str] = set()
    cur: Doc | None = doc
    while cur and cur.id not in seen:
        seen.add(cur.id)
        parts.append(cur.title)
        cur = by_id.get(cur.parent_id)
    return list(reversed(parts))


def infer_status(path_parts: list[str]) -> str:
    return next((part for part in path_parts if part in STATUS_LABELS), "미분류")


def infer_region(path_parts: list[str]) -> str:
    return path_parts[1] if len(path_parts) >= 2 else ""


def infer_country(path_parts: list[str], status: str) -> str:
    try:
        index = path_parts.index(status)
    except ValueError:
        return ""
    return path_parts[index + 1] if index + 1 < len(path_parts) else ""


def compute_stats(by_id: dict[str, Doc], children_by_parent: dict[str, list[Doc]]) -> tuple[set[str], set[str], dict[str, Stats]]:
    reachable = collect_reachable(children_by_parent)
    internal_ids = {
        doc_id
        for doc_id in reachable
        if any(child.id in reachable for child in children_by_parent.get(doc_id, []))
    }
    company_ids = {doc_id for doc_id in reachable if doc_id != ROOT_DOC_ID and doc_id not in internal_ids}
    memo: dict[str, Stats] = {}

    def visit(doc: Doc) -> Stats:
        if doc.id in memo:
            return memo[doc.id]
        path_parts = path_of(doc, by_id)
        children = [child for child in children_by_parent.get(doc.id, []) if child.id in reachable and not child.archived_at and not child.deleted_at]
        stats = Stats(id=doc.id, title=doc.title, url_id=doc.url_id, parent_id=doc.parent_id, path_parts=path_parts)
        stats.direct_folder_count = sum(1 for child in children if child.id in internal_ids)
        stats.direct_company_count = sum(1 for child in children if child.id in company_ids)
        stats.direct_children = [
            {
                "id": child.id,
                "title": child.title,
                "url": f"{OUTLINE_BASE}/doc/{child.url_id}",
                "kind": "중간 문서" if child.id in internal_ids else "업체 문서",
            }
            for child in children
        ]
        if doc.id in company_ids:
            stats.descendant_company_count = 1
            status = infer_status(path_parts)
            region = infer_region(path_parts)
            country = infer_country(path_parts, status)
            stats.statuses[status] += 1
            if region:
                stats.regions[region] += 1
            if country:
                stats.countries[country] += 1
        for child in children:
            child_stats = visit(child)
            if child.id in internal_ids:
                stats.descendant_folder_count += 1 + child_stats.descendant_folder_count
            stats.descendant_company_count += child_stats.descendant_company_count
            stats.statuses.update(child_stats.statuses)
            stats.regions.update(child_stats.regions)
            stats.countries.update(child_stats.countries)
        memo[doc.id] = stats
        return stats

    visit(by_id[ROOT_DOC_ID])
    return internal_ids, company_ids, memo


def top_entries(counter: Counter[str], limit: int = 8) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def list_line(label: str, entries: list[tuple[str, int]]) -> str:
    if not entries:
        return f"- {label}: 없음"
    return f"- {label}: " + ", ".join(f"{md_escape(key)} {value:,}건" for key, value in entries)


def build_section(stats: Stats, root_stats: Stats) -> str:
    folder_label = "전체 루트" if stats.depth == 0 else "지역 문서" if stats.depth == 1 else "상태 문서" if stats.depth == 2 else "국가/세부 분류 문서"
    child_folders = [child for child in stats.direct_children if child["kind"] == "중간 문서"][:12]
    direct_companies = [child for child in stats.direct_children if child["kind"] == "업체 문서"][:8]
    lines = [
        SECTION_TITLE,
        "",
        f"- 기준: {KST_DATE} KST live Outline tree/cache. 이 문서는 **{md_escape(folder_label)}**이며 업체 카드가 아니라 하위 업체/분류를 찾기 위한 중간 문서다.",
        f"- 경로: {md_escape(stats.path)}.",
        f"- 하위 업체 문서: {stats.descendant_company_count:,}건. 하위 중간 문서: {stats.descendant_folder_count:,}건.",
        f"- 직속 하위: 중간 문서 {stats.direct_folder_count:,}개, 업체 문서 {stats.direct_company_count:,}개.",
        list_line("상태 분포", top_entries(stats.statuses, 8)),
    ]
    if stats.depth <= 1:
        lines.append(list_line("주요 국가/분류", top_entries(stats.countries, 10)))
    elif len(stats.countries) > 1:
        lines.append(list_line("국가/분류", top_entries(stats.countries, 10)))
    if stats.id == ROOT_DOC_ID:
        lines.append(f"- 전체 루트 기준 하위 업체 총계: {root_stats.descendant_company_count:,}건, 중간 문서 총계: {root_stats.descendant_folder_count:,}건.")
        lines.append(f"- 루트 링크: {md_link('영업처후보', ROOT_URL)}")
    if child_folders:
        lines.extend(["", "### 바로 아래 중간 문서", ""])
        lines.extend(f"- {md_link(child['title'], child['url'])}" for child in child_folders)
    if direct_companies:
        lines.extend(["", "### 바로 아래 업체 예시", ""])
        lines.extend(f"- {md_link(child['title'], child['url'])}" for child in direct_companies)
    lines.extend(
        [
            "",
            "### 해석",
            "",
            "- 이 섹션은 현재 Outline 계층을 기준으로 한 자동 현황이다. 업체별 영업정보, 치과 관련 활동, 언론/행사 노출 및 신뢰도 판단은 각 업체 문서의 `공개 웹검색 보강` 섹션에서 확인한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def replace_section(text: str, section: str) -> str:
    pattern = re.compile(r"\n?## 현재 하위 현황 \(자동 갱신\)\n[\s\S]*?(?=\n## |\s*$)")
    source = str(text or "")
    if pattern.search(source):
        return pattern.sub(f"\n{section.rstrip()}\n", source)
    insert = re.search(r"\n## (?:하위|전체|지역|국가|업체|분류|영업|메모|목록)", source)
    if insert and insert.start() > 0:
        return f"{source[:insert.start()].rstrip()}\n\n{section.rstrip()}\n{source[insert.start():]}"
    return f"{source.rstrip()}\n\n{section}"


def update_one(client: OutlineClient, doc: Doc, stats: Stats, root_stats: Stats, args: argparse.Namespace) -> dict[str, Any]:
    if args.append_only:
        section = build_section(stats, root_stats).replace(SECTION_TITLE, APPEND_SECTION_TITLE, 1)
        updated = client.document_append(doc.id, f"\n\n{section}")
        return {
            "id": doc.id,
            "title": doc.title,
            "path": stats.path,
            "url": f"{OUTLINE_BASE}/doc/{updated.get('urlId') or doc.url_id}",
            "changed": True,
            "updated": True,
            "append_only": True,
        }

    info = client.document_info(doc.id)
    before = str(info.get("text") or "")
    section = build_section(stats, root_stats)
    next_text = replace_section(before, section)
    row = {"id": doc.id, "title": doc.title, "path": stats.path, "url": stats.url, "changed": before != next_text}
    if args.verify_only:
        row["verified"] = SECTION_TITLE_TEXT in before
        return row
    if args.dry_run:
        row["dry_run"] = True
        return row
    updated = client.document_update(doc.id, info.get("title") or doc.title, next_text)
    row["updated"] = True
    row["url"] = f"{OUTLINE_BASE}/doc/{updated.get('urlId') or doc.url_id}"
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--skip-root", action="store_true")
    parser.add_argument("--append-only", action="store_true")
    parser.add_argument("--max-targets", type=int, default=0)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docs = load_cache_docs()
    by_id, children_by_parent = build_tree(docs)
    internal_ids, company_ids, stats_by_id = compute_stats(by_id, children_by_parent)
    root_stats = stats_by_id[ROOT_DOC_ID]
    targets = [by_id[doc_id] for doc_id in internal_ids if doc_id in by_id]
    if args.skip_root:
        targets = [doc for doc in targets if doc.id != ROOT_DOC_ID]
    targets.sort(key=lambda doc: stats_by_id[doc.id].path)
    if args.max_targets > 0:
        targets = targets[: args.max_targets]

    scan = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tree_source": str(DOC_CACHE),
        "middle_doc_count": len(targets),
        "company_doc_count": len(company_ids),
        "root_stats": {
            "descendant_company_count": root_stats.descendant_company_count,
            "descendant_folder_count": root_stats.descendant_folder_count,
        },
        "targets": [
            {
                "id": doc.id,
                "title": doc.title,
                "path": stats_by_id[doc.id].path,
                "descendant_company_count": stats_by_id[doc.id].descendant_company_count,
                "descendant_folder_count": stats_by_id[doc.id].descendant_folder_count,
                "url": stats_by_id[doc.id].url,
            }
            for doc in targets
        ],
    }
    (OUT_DIR / "middle_docs_scan_cache_2026-06-04.json").write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding="utf-8")

    client = OutlineClient(read_env_key("DOF_OUTLINE_KEY"), args.timeout)
    if args.verify_only:
        result_name = "middle_docs_verify_cache_2026-06-04.jsonl"
    elif args.append_only:
        result_name = "middle_docs_append_cache_2026-06-04.jsonl"
    else:
        result_name = "middle_docs_update_cache_2026-06-04.jsonl"
    result_path = OUT_DIR / result_name
    result_path.write_text("", encoding="utf-8")
    processed = ok = failed = 0

    def run(doc: Doc) -> dict[str, Any]:
        try:
            return update_one(client, doc, stats_by_id[doc.id], root_stats, args)
        except Exception as error:
            return {
                "id": doc.id,
                "title": doc.title,
                "path": stats_by_id[doc.id].path,
                "url": stats_by_id[doc.id].url,
                "failed": True,
                "error": str(error)[:600],
            }

    with ThreadPoolExecutor(max_workers=max(1, min(args.concurrency, len(targets)))) as executor:
        futures = [executor.submit(run, doc) for doc in targets]
        for future in as_completed(futures):
            row = future.result()
            with result_path.open("a", encoding="utf-8") as file_obj:
                file_obj.write(json.dumps(row, ensure_ascii=False) + "\n")
            processed += 1
            if row.get("failed") or (args.verify_only and not row.get("verified")):
                failed += 1
            else:
                ok += 1
            if processed % 25 == 0 or processed == len(targets):
                print(json.dumps({"processed": processed, "target": len(targets), "ok": ok, "failed": failed}, ensure_ascii=False), flush=True)

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dry_run": args.dry_run,
        "verify_only": args.verify_only,
        "append_only": args.append_only,
        "skip_root": args.skip_root,
        "target_count": len(targets),
        "ok": ok,
        "failed": failed,
        "result_jsonl": str(result_path),
        "scan_json": str(OUT_DIR / "middle_docs_scan_cache_2026-06-04.json"),
    }
    if args.verify_only:
        summary_name = "middle_docs_verify_cache_summary_2026-06-04.json"
    elif args.append_only:
        summary_name = "middle_docs_append_cache_summary_2026-06-04.json"
    else:
        summary_name = "middle_docs_update_cache_summary_2026-06-04.json"
    (OUT_DIR / summary_name).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
