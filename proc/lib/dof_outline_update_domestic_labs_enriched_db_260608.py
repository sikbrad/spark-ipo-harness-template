#!/usr/bin/env python3
"""Fast DB-backed Outline text update for enriched domestic dental-lab docs."""

from __future__ import annotations

import base64
import json
import re
import shlex
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dof_outline_reformat_domestic_labs_like_ab as fmt  # noqa: E402


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_DIR = ROOT / "output/domestic-dental-labs-260607/web_enrich_260608"
DATA_JSON = ROOT / "output/domestic-dental-labs-260607/domestic_dental_labs_selected_enriched_260608.json"
RESULT_JSON = OUT_DIR / "outline_enriched_db_update_result.json"

MGMT_RE = re.compile(r"\| 관리번호 \| ([^|]+?) \|")


def run_ssh_psql(sql: str) -> str:
    return subprocess.check_output(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "DOF-AX01",
            "docker",
            "exec",
            "-i",
            "outline-postgres",
            "psql",
            "-U",
            "outline",
            "-d",
            "outline",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
        ],
        input=sql,
        text=True,
    )


def fetch_subtree_docs() -> list[dict[str, Any]]:
    sql = f"""
WITH RECURSIVE tree AS (
  SELECT id, title, "parentDocumentId", "urlId", text
  FROM documents
  WHERE id = '{fmt.DETAIL_PARENT_ID}'::uuid AND "deletedAt" IS NULL
  UNION ALL
  SELECT d.id, d.title, d."parentDocumentId", d."urlId", d.text
  FROM documents d
  JOIN tree t ON d."parentDocumentId" = t.id
  WHERE d."deletedAt" IS NULL
),
payload AS (
  SELECT coalesce(jsonb_agg(jsonb_build_object(
    'id', id::text,
    'title', title,
    'parentDocumentId', "parentDocumentId"::text,
    'urlId', "urlId",
    'text', text
  )), '[]'::jsonb) AS data
  FROM tree
)
SELECT encode(convert_to(data::text, 'UTF8'), 'base64') FROM payload;
"""
    encoded = "".join(run_ssh_psql(sql).split())
    return json.loads(base64.b64decode(encoded).decode("utf-8"))


def node_maps(structure: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_id: dict[str, dict[str, Any]] = {}
    full_url_by_id: dict[str, str] = {}

    def visit(node: dict[str, Any]) -> None:
        if node.get("id"):
            by_id[node["id"]] = node
            if node.get("url"):
                full_url_by_id[node["id"]] = f"{fmt.OUTLINE_BASE}{node['url']}"
        for child in node.get("children") or []:
            visit(child)

    for item in structure:
        visit(item)
    return by_id, full_url_by_id


def find_node(structure: list[dict[str, Any]], doc_id: str) -> dict[str, Any]:
    stack = list(structure)
    while stack:
        node = stack.pop()
        if node.get("id") == doc_id:
            return node
        stack.extend(node.get("children") or [])
    raise RuntimeError(f"documentStructure node not found: {doc_id}")


def md_doc(node: dict[str, Any]) -> dict[str, Any]:
    return {"id": node["id"], "title": node.get("title"), "url": node.get("url")}


def build_updates(rows: list[dict[str, Any]], docs: list[dict[str, Any]], structure: list[dict[str, Any]]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    docs_by_id = {doc["id"]: doc for doc in docs}
    _, full_url_by_id = node_maps(structure)
    root_node = find_node(structure, fmt.DETAIL_PARENT_ID)

    region_nodes = {child["title"]: child for child in root_node.get("children") or []}
    province_nodes: dict[str, dict[str, Any]] = {}
    district_nodes: dict[tuple[str, str], dict[str, Any]] = {}
    for region, provinces in fmt.REGION_PROVINCES.items():
        region_node = region_nodes[region]
        by_title = {child["title"]: child for child in region_node.get("children") or []}
        for province in provinces:
            short = fmt.PROVINCE_SHORT[province]
            province_node = by_title[short]
            province_nodes[province] = province_node
            for city_node in province_node.get("children") or []:
                district_nodes[(province, city_node["title"])] = city_node

    card_by_mgmt: dict[str, str] = {}
    for doc in docs:
        text = doc.get("text") or ""
        match = MGMT_RE.search(text)
        if match:
            card_by_mgmt[match.group(1).strip()] = doc["id"]

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["province"]][row["city"]].append(row)

    links: dict[str, str] = {}
    updates: list[dict[str, str]] = []
    missing_cards: list[str] = []
    for row in rows:
        doc_id = card_by_mgmt.get(row["management_no"])
        if not doc_id:
            missing_cards.append(row["management_no"])
            continue
        district_node = district_nodes[(row["province"], row["city"])]
        province_node = province_nodes[row["province"]]
        links[row["management_no"]] = full_url_by_id.get(doc_id, f"{fmt.OUTLINE_BASE}/doc/{docs_by_id[doc_id].get('urlId')}")
        updates.append(
            {
                "id": doc_id,
                "title": docs_by_id[doc_id]["title"],
                "text": fmt.card_text(
                    row,
                    full_url_by_id.get(district_node["id"], f"{fmt.OUTLINE_BASE}{district_node.get('url', '')}"),
                    full_url_by_id.get(province_node["id"], f"{fmt.OUTLINE_BASE}{province_node.get('url', '')}"),
                ),
            }
        )

    for province in fmt.PROVINCE_ORDER:
        province_node = province_nodes[province]
        for city, city_rows in grouped[province].items():
            city_node = district_nodes[(province, city)]
            updates.append({"id": city_node["id"], "title": city, "text": fmt.district_text(province, city, city_rows, links)})
        district_docs = {city: md_doc(district_nodes[(province, city)]) for city in grouped[province]}
        updates.append(
            {
                "id": province_node["id"],
                "title": fmt.PROVINCE_SHORT[province],
                "text": fmt.province_text(province, grouped[province], district_docs, links),
            }
        )

    province_counts = {province: sum(len(city_rows) for city_rows in grouped[province].values()) for province in fmt.PROVINCE_ORDER}
    for region in fmt.REGION_ORDER:
        docs_for_region = [
            {**md_doc(province_nodes[province]), "province": province}
            for province in fmt.REGION_PROVINCES[region]
            if province in province_nodes
        ]
        updates.append({"id": region_nodes[region]["id"], "title": region, "text": fmt.region_text(region, docs_for_region, province_counts)})

    region_doc_list = [md_doc(region_nodes[region]) for region in fmt.REGION_ORDER]
    updates.append({"id": fmt.DETAIL_PARENT_ID, "title": "국내 치과기공소", "text": fmt.root_text(region_doc_list, len(rows))})
    updates.append({"id": fmt.REPORT_DOC_ID, "title": "리포트260607-국내-기공소", "text": fmt.report_text(rows, links)})
    meta = {
        "missing_cards": missing_cards,
        "card_updates": len(rows) - len(missing_cards),
        "district_updates": len(district_nodes),
        "province_updates": len(province_nodes),
        "total_updates": len(updates),
    }
    return updates, meta


def backup_docs(docs: list[dict[str, Any]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"outline_docs_before_enriched_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def apply_updates(updates: list[dict[str, str]]) -> int:
    payload = base64.b64encode(json.dumps(updates, ensure_ascii=False).encode("utf-8")).decode("ascii")
    sql = f"""
WITH payload AS (
  SELECT convert_from(decode('{payload}', 'base64'), 'UTF8')::jsonb AS data
),
items AS (
  SELECT
    item->>'id' AS id,
    item->>'title' AS title,
    item->>'text' AS text
  FROM payload, jsonb_array_elements(data) AS item
),
updated AS (
  UPDATE documents d
  SET title = items.title,
      text = items.text,
      "updatedAt" = now()
  FROM items
  WHERE d.id = items.id::uuid
    AND d."deletedAt" IS NULL
  RETURNING d.id
)
SELECT count(*) FROM updated;
"""
    return int(run_ssh_psql(sql).strip())


def verify_db() -> dict[str, Any]:
    sql = f"""
WITH RECURSIVE tree AS (
  SELECT id, title, "parentDocumentId", text
  FROM documents
  WHERE id = '{fmt.DETAIL_PARENT_ID}'::uuid AND "deletedAt" IS NULL
  UNION ALL
  SELECT d.id, d.title, d."parentDocumentId", d.text
  FROM documents d
  JOIN tree t ON d."parentDocumentId" = t.id
  WHERE d."deletedAt" IS NULL
)
SELECT jsonb_build_object(
  'subtree_docs', count(*),
  'company_cards_with_mgmt', count(*) FILTER (WHERE text LIKE '%| 관리번호 | PHMB%'),
  'company_cards_with_portal_basis', count(*) FILTER (WHERE text LIKE '%| 포털 확인 근거 |%'),
  'company_cards_with_web_basis', count(*) FILTER (WHERE text LIKE '%| 웹/뉴스/행사 근거 |%'),
  'district_pages_with_web_column', count(*) FILTER (WHERE text LIKE '%| 웹/뉴스/행사 흔적 |%'),
  'report_has_portal_counts', bool_or(id = '{fmt.REPORT_DOC_ID}'::uuid AND text LIKE '%포털 전수 매칭 분포%'),
  'report_has_web_summary', bool_or(id = '{fmt.REPORT_DOC_ID}'::uuid AND text LIKE '%웹/업체정보 흔적 확인%')
)::text
FROM tree;
"""
    return json.loads(run_ssh_psql(sql))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    docs = fetch_subtree_docs()
    backup_path = backup_docs(docs)
    structure_backup_path = fmt.backup_collection_structure()
    structure = fmt.fetch_collection_structure()
    updates, meta = build_updates(rows, docs, structure)
    updated_count = apply_updates(updates)
    restarted = fmt.restart_outline()
    verification = verify_db()
    result = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "data_path": str(DATA_JSON),
        "backup_docs": str(backup_path),
        "backup_structure": str(structure_backup_path),
        "requested_updates": len(updates),
        "updated_count": updated_count,
        "meta": meta,
        "outline_restart": restarted,
        "verification": verification,
    }
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if updated_count == len(updates) and not meta["missing_cards"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
