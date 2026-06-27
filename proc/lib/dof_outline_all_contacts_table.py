#!/usr/bin/env python3
"""Create one all-company contact/category table and publish it to Outline."""

from __future__ import annotations

import csv
import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dof_partial_distributor_candidate_expansion as partial
import dof_prospect_outline_publish as pub


pub.REQUEST_TIMEOUT = 300

ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
OUT_DIR = OUT_ROOT / "all_contacts_table"
MD_PATH = OUT_DIR / "all_company_contacts_table.md"
COMPACT_MD_PATH = OUT_DIR / "all_company_contacts_table_outline_compact.md"
CSV_PATH = OUT_DIR / "all_company_contacts_table.csv"
RESULT_PATH = OUT_DIR / "all_company_contacts_table_publish_result.json"
DOC_TITLE = "전체 업체 연락처 테이블 (자동생성)"
CACHE_KEY = "report:all-company-contacts-table"
ROOT_DOC_ID = "89c2b595-26e3-43fd-b4d2-23d514515e2d"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def md_cell(value: object) -> str:
    text = clean(value)
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    text = text.replace("\n", " ").replace("\r", " ")
    return text


def contact_completeness(row: dict[str, Any]) -> str:
    tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
    return clean(tags.get("contact_completeness")) or partial.contact_completeness(row)


def source_trust(row: dict[str, Any]) -> str:
    tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
    trust = clean(tags.get("source_trust"))
    if trust:
        return trust
    if clean(row.get("validation_status")) == "valid":
        return "valid-direct-source"
    return ""


def table_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("_region")),
        clean(pub.customer_status(row)),
        clean(row.get("_country_label") or row.get("_country")),
        clean(row.get("name")).lower(),
    )


def row_for_output(row: dict[str, Any]) -> dict[str, str]:
    return {
        "대분류": clean(row.get("_region")),
        "중분류": clean(pub.customer_status(row)),
        "소분류": clean(row.get("_country_label") or pub.country_label(row.get("_country"))),
        "세그먼트": clean(row.get("_segment_ko") or row.get("segment")),
        "업체명": clean(row.get("name")),
        "이메일": clean(row.get("email")),
        "전화": clean(row.get("phone")),
        "주소": clean(row.get("address")),
        "웹사이트": clean(row.get("website")),
        "신뢰도": source_trust(row),
        "연락처완성도": contact_completeness(row),
        "출처유형": clean(row.get("source_type")),
        "출처URL": clean(row.get("source_url")),
    }


def build_markdown(rows: list[dict[str, Any]]) -> str:
    generated = datetime.now().replace(microsecond=0).isoformat()
    status_counts = Counter(pub.customer_status(row) for row in rows)
    region_counts = Counter(clean(row.get("_region")) for row in rows)
    trust_counts = Counter(source_trust(row) or "미상" for row in rows)
    contact_counts = Counter(contact_completeness(row) or "미상" for row in rows)

    lines: list[str] = [
        f"# {DOC_TITLE}",
        "",
        f"- 생성시각: {generated}",
        f"- 총 업체 수: {len(rows):,}",
        "- 분류 기준: 대분류=지역, 중분류=고객군/상태, 소분류=국가",
        "- 이 문서는 한 개의 Markdown table로 전체 업체 연락처를 모은 자동 생성 문서이다.",
        "",
        "## 요약",
        "",
        "### 지역별",
        "",
    ]
    for label, count in region_counts.most_common():
        lines.append(f"- {label or '미상'}: {count:,}")
    lines += ["", "### 고객군별", ""]
    for label, count in status_counts.most_common():
        lines.append(f"- {label or '미상'}: {count:,}")
    lines += ["", "### 신뢰도별", ""]
    for label, count in trust_counts.most_common():
        lines.append(f"- {label}: {count:,}")
    lines += ["", "### 연락처 완성도별", ""]
    for label, count in contact_counts.most_common():
        lines.append(f"- {label}: {count:,}")

    columns = ["대분류", "중분류", "소분류", "세그먼트", "업체명", "이메일", "전화", "주소", "웹사이트", "신뢰도", "연락처완성도"]
    lines += ["", "## 전체 업체 연락처 테이블", "", "|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        output = row_for_output(row)
        lines.append("|" + "|".join(md_cell(output[column]) for column in columns) + "|")
    return "\n".join(lines) + "\n"


def build_compact_markdown(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = [
        f"# {DOC_TITLE}",
        "",
        f"- 총 업체 수: {len(rows):,}",
        "- 분류 기준: 대분류=지역, 중분류=고객군/상태, 소분류=국가",
        "- Outline 본문 크기 제한 때문에 연락처는 한 칸에 합쳤다. 전체 상세 CSV/MD는 로컬 산출물에 저장되어 있다.",
        "",
        "|대분류|중분류|소분류|업체명|연락처|",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        contact_parts = []
        if clean(row.get("email")):
            contact_parts.append(f"E:{clean(row.get('email'))}")
        elif clean(row.get("phone")):
            contact_parts.append(f"T:{clean(row.get('phone'))}")
        elif clean(row.get("website")):
            contact_parts.append(f"W:{clean(row.get('website'))}")
        elif clean(row.get("address")):
            contact_parts.append(f"A:{clean(row.get('address'))}")
        values = [
            row.get("_region"),
            pub.customer_status(row),
            row.get("_country_label") or pub.country_label(row.get("_country")),
            row.get("name"),
            "; ".join(contact_parts),
        ]
        lines.append("|" + "|".join(md_cell(value) for value in values) + "|")
    return "\n".join(lines) + "\n"


def write_csv(rows: list[dict[str, Any]]) -> None:
    columns = ["대분류", "중분류", "소분류", "세그먼트", "업체명", "이메일", "전화", "주소", "웹사이트", "신뢰도", "연락처완성도", "출처유형", "출처URL"]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row_for_output(row))


def publish_to_outline(markdown: str) -> dict[str, Any]:
    client = pub.OutlineClient(pub.read_env_key("DOF_OUTLINE_KEY"))
    root = {"id": ROOT_DOC_ID}
    cache = pub.load_json(pub.DOC_CACHE, {"docs": {}})
    cached = (cache.get("docs") or {}).get(CACHE_KEY)
    try:
        if isinstance(cached, dict) and cached.get("id"):
            data = client.update_document(cached["id"], DOC_TITLE, markdown)
        else:
            existing = {
                doc["title"]: doc
                for doc in client.documents_list(parentDocumentId=root["id"])
                if doc.get("title")
            }.get(DOC_TITLE)
            if existing:
                data = client.update_document(existing["id"], DOC_TITLE, markdown)
            else:
                data = client.create_document(DOC_TITLE, root["id"], markdown)
        doc = pub.OutlineDoc(data["id"], data["urlId"], data["title"], pub.doc_url(data), data.get("parentDocumentId", root["id"]))
        cache.setdefault("docs", {})[CACHE_KEY] = {
            "id": doc.id,
            "url_id": doc.url_id,
            "title": doc.title,
            "url": doc.url,
            "parent_document_id": doc.parent_document_id,
        }
        pub.save_json(pub.DOC_CACHE, cache)
        return {"published": True, "document": cache["docs"][CACHE_KEY]}
    except Exception as error:
        fallback = (
            f"# {DOC_TITLE}\n\n"
            "전체 테이블 본문이 너무 커서 Outline API 전체 발행에 실패했다.\n\n"
            f"- 로컬 Markdown: `{MD_PATH}`\n"
            f"- 로컬 CSV: `{CSV_PATH}`\n"
            f"- 오류: `{str(error)[:500]}`\n"
        )
        try:
            data = client.create_document(f"{DOC_TITLE} - 산출물 링크", root["id"], fallback)
            return {"published": False, "fallbackDocument": {"id": data["id"], "url": pub.doc_url(data), "title": data["title"]}, "error": str(error)}
        except Exception as fallback_error:
            return {"published": False, "error": str(error), "fallbackError": str(fallback_error)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-outline", action="store_true", help="Write local MD/CSV/result files without publishing to Outline.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = pub.enrich_rows(pub.read_jsonl(pub.COMPLETE_JSONL))
    rows = sorted(rows, key=table_sort_key)
    markdown = build_markdown(rows)
    compact_markdown = build_compact_markdown(rows)
    MD_PATH.write_text(markdown, encoding="utf-8")
    COMPACT_MD_PATH.write_text(compact_markdown, encoding="utf-8")
    write_csv(rows)
    result = {
        "generatedAt": datetime.now().replace(microsecond=0).isoformat(),
        "rowCount": len(rows),
        "markdown": str(MD_PATH),
        "markdownBytes": MD_PATH.stat().st_size,
        "outlineMarkdown": str(COMPACT_MD_PATH),
        "outlineMarkdownBytes": COMPACT_MD_PATH.stat().st_size,
        "csv": str(CSV_PATH),
        "csvBytes": CSV_PATH.stat().st_size,
        "outline": {"published": False, "skipped": True} if args.skip_outline else publish_to_outline(compact_markdown),
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
