#!/usr/bin/env python3
"""Move domestic dental-lab detail rows into child Outline docs and fix the tree."""

from __future__ import annotations

import json
import base64
import re
import shlex
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dof_prospect_outline_publish as outline_publish  # noqa: E402


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
DATA_JSON = ROOT / "output/domestic-dental-labs-260607/domestic_dental_labs_selected.json"
OUT_DIR = ROOT / "output/domestic-dental-labs-260607/tree_fix"
RESULT_JSON = OUT_DIR / "tree_fix_result.json"

OUTLINE_BASE = "https://outline.doflab.com"
REPORT_PARENT_ID = "07b08eec-2ecb-42aa-b043-8e89f5ac6fb9"
REPORT_DOC_ID = "1fcdc2e0-fdf6-4efd-a0b7-1680b2777441"
DETAIL_PARENT_ID = "d2f90e91-0cf0-4c3d-9e5a-1c719fa45097"
COLLECTION_ID = "ccc57505-9f9d-411f-b3c3-12d30aac65cc"

SOFT_DELETED_DUPLICATE_IDS = {
    "67241aef-14e2-4048-a0af-efd4e4d26c1d",
    "ccd4374b-072b-4534-b48f-238a57c349b2",
}

PROVINCE_ORDER = [
    "서울특별시",
    "경기도",
    "인천광역시",
    "부산광역시",
    "대구광역시",
    "울산광역시",
    "경상북도",
    "경상남도",
    "대전광역시",
    "세종특별자치시",
    "충청북도",
    "충청남도",
    "광주광역시",
    "전북특별자치도",
    "전라남도",
    "강원특별자치도",
    "제주특별자치도",
]


def compact(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def md_escape(value: Any, limit: int = 220) -> str:
    return compact(value, limit).replace("|", "\\|").replace("\n", "<br>")


def outline_api(session: requests.Session, endpoint: str, body: dict[str, Any], timeout: int = 90) -> dict[str, Any]:
    response = session.post(f"{OUTLINE_BASE}/api/{endpoint}", json=body, timeout=timeout)
    response.raise_for_status()
    return response.json()["data"]


def table_header() -> str:
    return (
        "| 우선순위 | 대분류 | 중분류 | 소분류 | 업체명 | 어떤 곳인지 | 포털 존재 여부 | 인허가/인증 근거 | "
        "영업상태 | 인허가일자 | 주소 | 전화 | 장비 공개값 | 검색/출처 | 신뢰도 | 추천 이유 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )


def row_markdown(row: dict[str, Any]) -> str:
    priority = "A-영업중 인허가"
    values = [
        priority,
        "국내",
        "치과기공소",
        f"{row.get('province')}/{row.get('city')}",
        row.get("name"),
        "전국 표준 인허가 데이터에 등재된 치과기공소",
        row.get("portal_status"),
        "의료기사 등에 관한 법률 기반 치과기공소 인허가 표준데이터",
        f"{row.get('status')}/{row.get('detail_status')}",
        row.get("license_date") or "-",
        row.get("address") or "주소 미공개",
        row.get("phone") or "전화 미공개",
        row.get("equipment_summary"),
        f"공공데이터 / 검색어: {row.get('name')} {row.get('province')} {row.get('city')} 치과기공소",
        row.get("trust"),
        row.get("recommendation"),
    ]
    return "| " + " | ".join(md_escape(value, 220) for value in values) + " |\n"


def absolute_doc_url(doc: dict[str, Any]) -> str:
    path = doc.get("url") or f"/doc/{doc['urlId']}"
    return f"{OUTLINE_BASE}{path}"


def child_markdown(province: str, rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    counts = Counter(row.get("portal_status") for row in rows)
    head = [
        f"# 국내 치과기공소 - {province}",
        "",
        "## 요약",
        f"- 상위 문서: [국내 치과기공소]({OUTLINE_BASE}/doc/6rwt64k0ioy5moqzvoq4soqzteygja-QcheOAYy0a/edit)",
        "- 원천: 공공데이터포털 `전국치과기공소표준데이터` 및 지방행정 인허가 CSV.",
        f"- 표 반영: {len(rows):,}곳.",
        "- 포털 매칭 분포: " + ", ".join(f"{k or '미확인'} {v:,}" for k, v in counts.most_common()),
        "- 신뢰도: 업체 존재/영업상태는 정부 표준 인허가 데이터 기반. 담당자/실장비 현황은 개별 확인 필요.",
        "",
        "## 업체 테이블",
        table_header().rstrip(),
    ]
    row_lines = [row_markdown(row).rstrip() for row in rows]
    chunks: list[str] = []
    for start in range(0, len(row_lines), 100):
        chunks.append("\n".join(row_lines[start : start + 100]) + "\n")
    return "\n".join(head) + "\n", chunks


def parent_summary(child_docs: list[dict[str, Any]], total_rows: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 국내 치과기공소",
        "",
        "## 정리",
        "- 이 문서는 국내 치과기공소 업체별 상세 데이터의 상위 문서다.",
        "- 상세 업체 표는 아래 시도별 하위 문서로 분리했다.",
        "- 원천: 공공데이터포털 `전국치과기공소표준데이터` 및 지방행정 인허가 CSV.",
        f"- 전체 반영: {total_rows:,}곳.",
        "- 업체 존재/영업상태 신뢰도는 정부 표준 인허가 데이터 기반이라 높다. 담당자/홈페이지/실장비 현황은 개별 확인 필요.",
        f"- 정리 시각: {now} KST.",
        "",
        "## 하위 문서",
    ]
    for doc in child_docs:
        lines.append(f"- [{doc['title']}]({absolute_doc_url(doc)}) - {doc['rows']:,}곳")
    return "\n".join(lines) + "\n"


def report_summary(child_docs: list[dict[str, Any]], total_rows: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 리포트260607-국내-기공소",
        "",
        "## 정리",
        "- `리포트` 하위 중복 문서는 DB와 컬렉션 트리에서 정리했고, 이 요약 문서 하나만 남긴다.",
        f"- 업체별 상세 데이터 {total_rows:,}행은 [국내 치과기공소](https://outline.doflab.com/doc/6rwt64k0ioy5moqzvoq4soqzteygja-QcheOAYy0a/edit) 하위 시도별 문서로 분리했다.",
        "- 원천: 공공데이터포털 `전국치과기공소표준데이터` 및 지방행정 인허가 CSV.",
        "- 신뢰도: 업체 존재/영업상태는 정부 표준 인허가 데이터라 높다. 담당자/홈페이지/실장비 현황은 개별 확인 필요.",
        f"- 정리 시각: {now} KST.",
        "",
        "## 상세 데이터 위치",
        "- [국내 치과기공소](https://outline.doflab.com/doc/6rwt64k0ioy5moqzvoq4soqzteygja-QcheOAYy0a/edit)",
    ]
    for doc in child_docs:
        lines.append(f"- [{doc['title']}]({absolute_doc_url(doc)}) - {doc['rows']:,}곳")
    return "\n".join(lines) + "\n"


def replace_collection_tree(child_docs: list[dict[str, Any]]) -> dict[str, Any]:
    get_sql = (
        "SELECT encode(convert_to(\"documentStructure\"::text, 'UTF8'), 'base64') "
        f"FROM collections WHERE id = '{COLLECTION_ID}';"
    )
    get_cmd = (
        "docker exec -i outline-postgres psql -U outline -d outline -At -c "
        + shlex.quote(get_sql)
    )
    encoded = subprocess.check_output(
        ["ssh", "-o", "BatchMode=yes", "DOF-AX01", get_cmd],
        text=True,
    )
    current = base64.b64decode("".join(encoded.split())).decode("utf-8")
    structure = json.loads(current)

    removed = 0

    def clean(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        out: list[dict[str, Any]] = []
        for node in nodes:
            if node.get("id") in SOFT_DELETED_DUPLICATE_IDS:
                removed += 1
                continue
            copied = dict(node)
            copied["children"] = clean(list(copied.get("children") or []))
            out.append(copied)
        return out

    structure = clean(structure)
    child_nodes = [{"id": doc["id"], "url": doc.get("url") or f"/doc/{doc['urlId']}", "title": doc["title"], "children": []} for doc in child_docs]
    inserted_parent = False

    def set_children(nodes: list[dict[str, Any]]) -> None:
        nonlocal inserted_parent
        for node in nodes:
            if node.get("id") == DETAIL_PARENT_ID:
                node["children"] = child_nodes
                inserted_parent = True
            else:
                set_children(list(node.get("children") or []))

    set_children(structure)
    payload = json.dumps(structure, ensure_ascii=False)
    sql = (
        "UPDATE collections "
        f"SET \"documentStructure\" = $json${payload}$json$::jsonb, \"updatedAt\" = now() "
        f"WHERE id = '{COLLECTION_ID}';"
    )
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "DOF-AX01", "docker", "exec", "-i", "outline-postgres", "psql", "-U", "outline", "-d", "outline", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        text=True,
        check=True,
    )
    return {"removed_duplicate_tree_nodes": removed, "inserted_detail_children": inserted_parent, "child_nodes": len(child_nodes)}


def restart_outline() -> str:
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "DOF-AX01", "docker", "restart", "outline"],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("province") or "지역확인필요"].append(row)

    key = outline_publish.read_env_key("DOF_OUTLINE_KEY")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}"})

    existing_children = {}
    try:
        listed = outline_api(session, "documents.list", {"parentDocumentId": DETAIL_PARENT_ID, "limit": 100, "offset": 0}, timeout=30)
        for doc in listed:
            existing_children[doc.get("title")] = doc
    except Exception:
        existing_children = {}

    child_docs: list[dict[str, Any]] = []
    for province in PROVINCE_ORDER:
        province_rows = grouped.get(province, [])
        if not province_rows:
            continue
        title = f"{province}"
        base, chunks = child_markdown(province, province_rows)
        existing = existing_children.get(title)
        if existing:
            data = outline_api(session, "documents.update", {"id": existing["id"], "title": title, "text": base, "publish": True, "fullWidth": True}, timeout=90)
            action = "updated"
        else:
            data = outline_api(
                session,
                "documents.create",
                {"parentDocumentId": DETAIL_PARENT_ID, "title": title, "text": base, "publish": True, "fullWidth": True},
                timeout=90,
            )
            action = "created"
        doc_id = data["id"]
        for chunk in chunks:
            outline_api(session, "documents.update", {"id": doc_id, "text": chunk, "append": True, "publish": True, "fullWidth": True}, timeout=120)
            time.sleep(0.05)
        info = outline_api(session, "documents.info", {"id": doc_id}, timeout=90)
        text = info.get("text") or ""
        child_docs.append(
            {
                "id": doc_id,
                "urlId": info.get("urlId"),
                "url": info.get("url"),
                "title": info.get("title"),
                "rows": len(province_rows),
                "table_rows_readback": text.count("| A-영업중 인허가 |"),
                "text_length": len(text),
                "action": action,
            }
        )

    child_docs.sort(key=lambda doc: PROVINCE_ORDER.index(doc["title"]) if doc["title"] in PROVINCE_ORDER else 999)
    parent_text = parent_summary(child_docs, len(rows))
    report_text = report_summary(child_docs, len(rows))
    detail_parent = outline_api(session, "documents.update", {"id": DETAIL_PARENT_ID, "title": "국내 치과기공소", "text": parent_text, "publish": True, "fullWidth": True}, timeout=90)
    report = outline_api(session, "documents.update", {"id": REPORT_DOC_ID, "title": "리포트260607-국내-기공소", "text": report_text, "publish": True, "fullWidth": True}, timeout=90)

    tree_result = replace_collection_tree(child_docs)
    restarted = restart_outline()

    result = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "total_rows": len(rows),
        "child_docs": child_docs,
        "detail_parent": {"id": detail_parent.get("id"), "urlId": detail_parent.get("urlId"), "title": detail_parent.get("title")},
        "report_doc": {"id": report.get("id"), "urlId": report.get("urlId"), "title": report.get("title")},
        "tree_result": tree_result,
        "outline_restart": restarted,
    }
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
