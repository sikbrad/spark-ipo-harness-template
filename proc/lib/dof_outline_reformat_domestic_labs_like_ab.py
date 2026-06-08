#!/usr/bin/env python3
"""Reformat domestic dental lab Outline docs to match the domestic clinic hierarchy."""

from __future__ import annotations

import base64
import json
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
ENRICHED_DATA_JSON = ROOT / "output/domestic-dental-labs-260607/domestic_dental_labs_selected_enriched_260608.json"
OUT_DIR = ROOT / "output/domestic-dental-labs-260607/format_fix"
RESULT_JSON = OUT_DIR / "format_fix_result.json"

OUTLINE_BASE = "https://outline.doflab.com"
DETAIL_PARENT_ID = "d2f90e91-0cf0-4c3d-9e5a-1c719fa45097"
REPORT_DOC_ID = "1fcdc2e0-fdf6-4efd-a0b7-1680b2777441"
COLLECTION_ID = "ccc57505-9f9d-411f-b3c3-12d30aac65cc"

REGION_ORDER = ["수도권", "영남", "호남", "강원", "충청", "제주"]
REGION_PROVINCES = {
    "수도권": ["서울특별시", "경기도", "인천광역시"],
    "영남": ["부산광역시", "대구광역시", "울산광역시", "경상북도", "경상남도"],
    "호남": ["광주광역시", "전북특별자치도", "전라남도"],
    "강원": ["강원특별자치도"],
    "충청": ["대전광역시", "세종특별자치시", "충청북도", "충청남도"],
    "제주": ["제주특별자치도"],
}
PROVINCE_TO_REGION = {province: region for region, provinces in REGION_PROVINCES.items() for province in provinces}
PROVINCE_SHORT = {
    "서울특별시": "서울",
    "경기도": "경기",
    "인천광역시": "인천",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "울산광역시": "울산",
    "경상북도": "경북",
    "경상남도": "경남",
    "광주광역시": "광주",
    "전북특별자치도": "전북",
    "전라남도": "전남",
    "강원특별자치도": "강원",
    "대전광역시": "대전",
    "세종특별자치시": "세종",
    "충청북도": "충북",
    "충청남도": "충남",
    "제주특별자치도": "제주",
}
PROVINCE_ORDER = [province for region in REGION_ORDER for province in REGION_PROVINCES[region]]
TITLE_OVERRIDES = {
    "PHMB320143740032062300003": "덴탈랩동행치과기공소 (수원 2014)",
    "PHMB320085020055062300002": "스마일치과기공소 (포항 2008)",
}


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def md(value: Any, limit: int = 200) -> str:
    return compact(value, limit).replace("|", "\\|").replace("\n", "<br>")


def canonical_url(doc: dict[str, Any]) -> str:
    path = doc.get("url") or f"/doc/{doc.get('urlId')}"
    return f"{OUTLINE_BASE}{path}"


def current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class Outline:
    def __init__(self, key: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {key}"})

    def api(self, endpoint: str, body: dict[str, Any], timeout: int = 90) -> Any:
        last = None
        for attempt in range(1, 7):
            try:
                response = self.session.post(f"{OUTLINE_BASE}/api/{endpoint}", json=body, timeout=timeout)
                if response.status_code < 400:
                    return response.json()["data"]
                last = RuntimeError(f"{endpoint} failed {response.status_code}: {response.text[:700]}")
            except requests.RequestException as error:
                last = error
            if attempt < 6:
                time.sleep(min(20, 1.5 * attempt))
        raise RuntimeError(f"{endpoint} failed after retries: {last}")

    def info(self, doc_id: str) -> dict[str, Any]:
        return self.api("documents.info", {"id": doc_id}, timeout=60)

    def list_children(self, parent_id: str) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = self.api("documents.list", {"parentDocumentId": parent_id, "limit": 100, "offset": offset}, timeout=60)
            batch = data if isinstance(data, list) else data.get("data", [])
            docs.extend(batch)
            if len(batch) < 100:
                return docs
            offset += len(batch)

    def update(self, doc_id: str, title: str, text: str) -> dict[str, Any]:
        return self.api(
            "documents.update",
            {"id": doc_id, "title": title, "text": text, "publish": True, "fullWidth": True},
            timeout=120,
        )

    def create(self, parent_id: str, title: str, text: str) -> dict[str, Any]:
        return self.api(
            "documents.create",
            {"parentDocumentId": parent_id, "title": title, "text": text, "publish": True, "fullWidth": True},
            timeout=120,
        )

    def move(self, doc_id: str, parent_id: str) -> dict[str, Any]:
        data = self.api("documents.move", {"id": doc_id, "parentDocumentId": parent_id}, timeout=90)
        docs = data.get("documents") if isinstance(data, dict) else None
        return docs[0] if docs else self.info(doc_id)


def upsert_child(client: Outline, parent_id: str, title: str, text: str, existing: dict[str, dict[str, Any]]) -> dict[str, Any]:
    doc = existing.get(title)
    if doc:
        updated = client.update(doc["id"], title, text)
    else:
        updated = client.create(parent_id, title, text)
        existing[title] = updated
        time.sleep(0.04)
    return client.info(updated["id"])


def lab_priority(row: dict[str, Any]) -> str:
    portal = row.get("portal_match_status") or row.get("portal_status") or ""
    if portal in {"포털 주문 발생", "포털 주문 가능성 높음", "포털 등록 확인", "포털 등록 가능성 높음"}:
        return "C-포털/주문"
    if portal and portal != "포털 미발견" and portal != "포털/주문 직접 매칭 없음":
        return "B-포털유사명 검증"
    if int(row.get("equipment_total") or 0) >= 20 and row.get("phone"):
        return "A-우선접촉"
    return "B-검증후접촉"


def lab_fit(row: dict[str, Any]) -> str:
    total = int(row.get("equipment_total") or 0)
    if total >= 60:
        return "대형 장비 보유 신호가 강해 기공물 접수, 스캔 데이터 수급, 밀링/프린팅 장비 교체 제안까지 연결하기 좋은 후보"
    if total >= 30:
        return "공개 장비 항목이 충분해 보철 제작 workflow가 확인되는 후보"
    if total >= 10:
        return "기본 기공 장비가 공개되어 있어 지역 기공 네트워크 접촉 후보로 분류"
    return "인허가상 영업중인 기공소로, 장비 상세와 디지털 workflow는 별도 확인이 필요한 후보"


def detected_items(row: dict[str, Any]) -> str:
    return f"치과기공소, 보철 제작 장비 공개값 {row.get('equipment_summary') or '상세 미공개'}"


def portal_status(row: dict[str, Any]) -> str:
    return row.get("portal_match_status") or row.get("portal_status") or "포털 확인 전"


def portal_detail(row: dict[str, Any]) -> str:
    return row.get("portal_match_summary") or portal_status(row)


def web_status(row: dict[str, Any]) -> str:
    return row.get("web_summary") or "웹 검색 전"


def web_detail(row: dict[str, Any]) -> str:
    return row.get("web_evidence") or "웹 검색 전"


def web_confidence(row: dict[str, Any]) -> str:
    return row.get("web_confidence") or "미확인"


def card_text(row: dict[str, Any], district_url: str, province_url: str) -> str:
    total = int(row.get("equipment_total") or 0)
    priority = lab_priority(row)
    source = "공공데이터포털 전국치과기공소표준데이터 / 지방행정 인허가 CSV"
    card_rows = "\n".join(
        [
            "| 항목 | 내용 |",
            "| --- | --- |",
            f"| 지역 | {md(row.get('province'))} {md(row.get('city'))} |",
            "| 고객군 | 치과기공소 (기공/스캔/밀링 workflow 타겟) |",
            f"| 업체 성격 | {md(row.get('detail_status'))} 상태로 공개 인허가에 등재된 치과기공소 |",
            f"| 포털 존재 여부 | {md(portal_status(row), 120)} |",
            f"| 포털 확인 근거 | {md(portal_detail(row), 260)} |",
            f"| 규모/장비 신호 | 공개 장비 합계 {total} / {md(row.get('equipment_summary') or '장비 세부 항목 미공개', 180)} |",
            f"| 등급 | {priority} |",
            f"| DOF 적합성 | {md(lab_fit(row), 180)} |",
            "| 선정 이유 | 인허가 데이터상 영업중이고 전화/주소/장비 항목이 함께 잡혀 있어, 치과 보철 제작 흐름을 가진 실제 접촉 후보로 다룰 수 있다. |",
        ]
    )
    contact_rows = "\n".join(
        [
            "| 항목 | 내용 |",
            "| --- | --- |",
            f"| 전화 | {md(row.get('phone') or '공개 전화 없음')} |",
            f"| 주소 | {md(row.get('address') or '주소 미공개', 220)} |",
            f"| 웹사이트/검색 흔적 | {md(web_status(row), 260)} |",
            f"| 웹/뉴스/행사 근거 | {md(web_detail(row), 500)} |",
            f"| 링크/부가정보 신뢰도 | {md(web_confidence(row), 60)} |",
        ]
    )
    signal_rows = "\n".join(
        [
            "| 항목 | 내용 |",
            "| --- | --- |",
            f"| 상태 | {md(row.get('status'))} / {md(row.get('detail_status'))} (신뢰도 {md(row.get('trust'))}) |",
            f"| 장비 | {md(row.get('equipment_summary') or '상세 미공개', 180)} |",
            f"| 포털 주문/제품 힌트 | {md(', '.join(row.get('portal_product_names') or []) or '포털 제품명 없음', 220)} |",
            f"| 인허가일자 | {md(row.get('license_date') or '미공개')} |",
            f"| 관리번호 | {md(row.get('management_no'))} |",
        ]
    )
    basis_rows = "\n".join(
        [
            "| 항목 | 내용 |",
            "| --- | --- |",
            f"| 데이터 | {source} |",
            f"| 포털 조회 | 포털 Company/Order DB를 회사명, 전화, 주소 기준으로 대조. {md(row.get('portal_match_confidence') or '미확인')} 신뢰도. |",
            f"| 웹 조회 | 네이버/DuckDuckGo 검색 결과에서 상호·지역이 맞는 웹사이트, 업체목록, 기업정보, 뉴스/세미나 흔적을 선별. {md(web_confidence(row), 40)} 신뢰도. |",
            f"| 추천 판단 | {md(lab_fit(row), 180)} |",
            "| 주의 | 포털 유사명은 동일 업체일 수 있으므로 영업 전 포털 row와 전화/주소를 대조해야 한다. 검색 엔진 403/timeout 항목은 추가 브라우저 확인 여지를 남겼다. |",
        ]
    )
    return "\n".join(
        [
            "# 영업처 카드",
            "",
            card_rows,
            "",
            "# 연락처",
            "",
            contact_rows,
            "",
            "# 기공/장비 신호",
            "",
            signal_rows,
            "",
            "# 판단 근거",
            "",
            basis_rows,
            "",
            "# 검색/출처",
            "",
            f"* 원천: {row.get('source_url')}",
            f"* 검색: {row.get('search_url')}",
            "",
            "# 영업 메모",
            "",
            "(영업사원 작성칸 - 비워둠)",
            "",
            "백링크",
            "",
            f"* [{row.get('city')}]({district_url})",
            f"* [{PROVINCE_SHORT[row.get('province')]}]({province_url})",
            "",
        ]
    )


def district_table(rows: list[dict[str, Any]], links: dict[str, str]) -> str:
    lines = [
        "| 등급 | 기공소명 | 어떤 곳인지 | 포털 존재 여부 | 웹/뉴스/행사 흔적 | 장비/기공 신호 | 전화 | 주소 | 신뢰도 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        key = row["management_no"]
        name = f"[{md(row['name'], 80)}]({links[key]})" if key in links else md(row["name"], 80)
        lines.append(
            "| "
            + " | ".join(
                [
                    md(lab_priority(row), 40),
                    name,
                    "영업중 인허가 치과기공소",
                    md(portal_status(row), 90),
                    md(web_status(row), 120),
                    md(row.get("equipment_summary") or "장비 공개값 없음", 130),
                    md(row.get("phone") or "-", 40),
                    md(row.get("address") or "-", 160),
                    md(row.get("trust") or "높음", 30),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def district_text(province: str, city: str, rows: list[dict[str, Any]], links: dict[str, str]) -> str:
    a_count = sum(1 for row in rows if lab_priority(row).startswith("A-"))
    similar = sum(1 for row in rows if portal_status(row) not in {"포털 미발견", "포털/주문 직접 매칭 없음"})
    web_found = sum(1 for row in rows if (row.get("web_result_count") or 0) > 0)
    return "\n".join(
        [
            f"# {city} ({len(rows)}곳)",
            "",
            (
                f"{province} {city}의 국내 치과기공소 후보입니다. 업체명을 누르면 개별 영업처 카드로 이동합니다. "
                f"A-우선접촉 {a_count}곳, 포털/주문 확인 또는 유사명 검증 필요 {similar}곳, 웹 흔적 확인 {web_found}곳입니다."
            ),
            "",
            district_table(rows, links),
            "",
        ]
    )


def province_text(province: str, city_rows: dict[str, list[dict[str, Any]]], district_docs: dict[str, dict[str, Any]], links: dict[str, str]) -> str:
    short = PROVINCE_SHORT[province]
    total = sum(len(rows) for rows in city_rows.values())
    lines = [
        f"# {short} ({total}곳)",
        "",
        f"{short}의 치과기공소 영업 후보를 시군구별로 정리했습니다. 기공소명을 누르면 상세 카드로 이동합니다.",
        "",
    ]
    for city, rows in sorted(city_rows.items(), key=lambda item: (-len(item[1]), item[0])):
        city_url = canonical_url(district_docs[city])
        lines.extend(
            [
                f"# {city} ({len(rows)}곳)",
                "",
                f"[{city} 상세 문서]({city_url})",
                "",
                district_table(rows, links),
                "",
            ]
        )
    return "\n".join(lines)


def region_text(region: str, province_docs: list[dict[str, Any]], counts: dict[str, int]) -> str:
    total = sum(counts.get(doc["province"], 0) for doc in province_docs)
    lines = [
        f"# {region}",
        "",
        f"{region} 권역의 국내 치과기공소 영업 후보 {total:,}곳을 시도·시군구별로 묶었습니다.",
        "",
        "문서",
        "",
    ]
    for doc in province_docs:
        lines.append(f"* [{doc['title']}]({canonical_url(doc)}) - {counts.get(doc['province'], 0):,}곳")
    return "\n".join(lines) + "\n"


def root_text(region_docs: list[dict[str, Any]], total: int) -> str:
    lines = [
        "# 국내 치과기공소",
        "",
        (
            "공공 인허가 데이터를 바탕으로 발굴한 국내 치과기공소 영업처 후보입니다. "
            "치과기공소 한 곳이 카드 한 장이며, 권역 -> 시도 -> 시군구 순으로 묶었습니다."
        ),
        "",
        (
            "각 시군구 페이지의 표에서 등급, 포털 존재 여부, 장비/기공 신호, 전화, 주소를 확인할 수 있습니다. "
            "업체명을 누르면 상세 영업처 카드로 이동합니다."
        ),
        "",
        f"전체 반영: {total:,}곳",
        f"정리 시각: {current_time()} KST",
        "",
        "문서",
        "",
    ]
    for doc in region_docs:
        lines.append(f"* [{doc['title']}]({canonical_url(doc)})")
    return "\n".join(lines) + "\n"


def report_table(rows: list[dict[str, Any]], links: dict[str, str]) -> str:
    lines = [
        "| 우선순위 | 포탈/주문 상태 | 권역/시도 | 업체 | 어떤 회사인지 | 확인된 취급품목 | 왜 추천하는지 | 연락/웹 | 확인 출처 | 신뢰도 | 추가 확인 취급/브랜드 | 최근 온라인 흔적 | 링크/부가정보 신뢰도 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        key = row["management_no"]
        name = f"[{md(row['name'], 80)}]({links.get(key, row.get('search_url'))})"
        source = f"[공공데이터]({row.get('source_url')})<br>[검색]({row.get('search_url')})"
        lines.append(
            "| "
            + " | ".join(
                [
                    md(lab_priority(row), 50),
                    md(portal_status(row), 90),
                    md(f"{PROVINCE_TO_REGION[row['province']]} / {row['province']} {row['city']}", 80),
                    name,
                    "영업중 인허가 치과기공소",
                    md(detected_items(row), 130),
                    md(lab_fit(row), 150),
                    md((row.get("phone") or "공개 전화 없음") + "<br>" + (row.get("address") or "주소 미공개"), 170),
                    source,
                    md(row.get("trust") or "높음", 30),
                    "DOF 스캐너, CAD/CAM, 기공물 접수, 밀링/프린팅 workflow",
                    md(web_status(row), 140),
                    md(f"{web_confidence(row)}<br>{web_detail(row)}", 220),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def report_text(rows: list[dict[str, Any]], links: dict[str, str]) -> str:
    portal_counts = Counter(portal_status(row) for row in rows)
    web_found = sum(1 for row in rows if (row.get("web_result_count") or 0) > 0)
    media_found = sum(1 for row in rows if row.get("web_has_news_or_conference"))
    candidates = [row for row in rows if portal_status(row) in {"포털 미발견", "포털/주문 직접 매칭 없음"}]
    selected = sorted(
        candidates,
        key=lambda row: (
            -int(row.get("equipment_total") or 0),
            0 if row.get("web_result_count") else 1,
            row.get("province") or "",
            row.get("city") or "",
            row.get("name") or "",
        ),
    )[:300]
    priority_counts = Counter(lab_priority(row) for row in selected)
    return "\n".join(
        [
            "# 260607 국내 치과기공소 추천 요약",
            "",
            "## 작성 기준",
            "",
            "* 대상: 국내 치과기공소 중 인허가상 영업중이며 전화, 주소, 장비 항목이 공개된 영업 후보.",
            "* 포털 제외/주의 기준: 포털 Company/Order DB를 상호, 전화, 주소로 대조했다. 추천 표는 `포털 미발견` 업체만 우선 노출하고, 주문 발생/등록 확인 업체는 상세 카드에서 기존 고객으로 표시했다.",
            "* 추천 기준: 공개 장비 합계, 전화 공개 여부, 지역 기공 네트워크성, 포털 직접 매칭 없음, 웹/업체정보 검색 흔적을 함께 보았다.",
            "* 웹 조사 기준: 네이버/DuckDuckGo 검색에서 상호와 지역이 같이 맞는 웹사이트, 업체목록, 기업정보/채용, 뉴스/컨퍼런스 흔적만 채택했다. 검색엔진 403/timeout은 낮은 신뢰도 또는 미확인으로 남겼다.",
            "* 출처 신뢰도: 업체 존재와 영업상태는 정부 표준 인허가 데이터 기반이라 높다. 포털 매칭은 전화/주소/주문번호가 붙으면 높고, 상호만 유사하면 낮다. 웹/미디어 정보는 검색 결과 기반이라 개별 링크 재확인이 필요하다.",
            "* 상세 업체 카드는 [국내 치과기공소](https://outline.doflab.com/doc/6rwt64k0ioy5moqzvoq4soqzteygja-QcheOAYy0a) 하위 권역 -> 시도 -> 시군구 문서에 배치했다.",
            "",
            "## 추천 요약",
            "",
            f"* 추천 업체 수: {len(selected):,}개",
            f"* 전체 상세 카드: {len(rows):,}개",
            f"* A-우선접촉: {priority_counts.get('A-우선접촉', 0):,}개",
            f"* B-포털유사명 검증: {priority_counts.get('B-포털유사명 검증', 0):,}개",
            f"* B-검증후접촉: {priority_counts.get('B-검증후접촉', 0):,}개",
            "* 포털 전수 매칭 분포: " + ", ".join(f"{key} {value:,}" for key, value in portal_counts.most_common()),
            f"* 웹/업체정보 흔적 확인: {web_found:,}개, 뉴스/컨퍼런스/세미나 흔적: {media_found:,}개",
            "* 핵심 출처: 공공데이터포털 전국치과기공소표준데이터, 지방행정 인허가 CSV.",
            "* 이번 리포트 표는 해외 리포트와 같은 방식으로 추천 사유, 취급품목, 연락/웹, 출처, 신뢰도를 한 줄에서 비교할 수 있게 작성했다.",
            "",
            "## 추천 업체 테이블",
            "",
            report_table(selected, links),
            "",
        ]
    )


def fetch_collection_structure() -> list[dict[str, Any]]:
    sql = (
        "SELECT encode(convert_to(\"documentStructure\"::text, 'UTF8'), 'base64') "
        f"FROM collections WHERE id = '{COLLECTION_ID}';"
    )
    cmd = "docker exec -i outline-postgres psql -U outline -d outline -At -c " + shlex.quote(sql)
    encoded = subprocess.check_output(["ssh", "-o", "BatchMode=yes", "DOF-AX01", cmd], text=True)
    return json.loads(base64.b64decode("".join(encoded.split())).decode("utf-8"))


def write_collection_structure(structure: list[dict[str, Any]]) -> None:
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


def restart_outline() -> str:
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "DOF-AX01", "docker", "restart", "outline"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def backup_collection_structure() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    structure = fetch_collection_structure()
    path = OUT_DIR / f"collection_structure_before_format_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def replace_qche_tree(
    region_docs: dict[str, dict[str, Any]],
    province_docs: dict[str, dict[str, Any]],
    district_docs: dict[tuple[str, str], dict[str, Any]],
    company_docs: dict[str, dict[str, Any]],
    grouped: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    structure = fetch_collection_structure()
    all_new_ids = {doc["id"] for doc in region_docs.values()} | {doc["id"] for doc in province_docs.values()} | {
        doc["id"] for doc in district_docs.values()
    } | {doc["id"] for doc in company_docs.values()}
    removed = 0

    def prune(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        out: list[dict[str, Any]] = []
        for node in nodes:
            if node.get("id") in all_new_ids:
                removed += 1
                continue
            copied = dict(node)
            copied["children"] = prune(list(copied.get("children") or []))
            out.append(copied)
        return out

    def node(doc: dict[str, Any], children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"id": doc["id"], "url": doc.get("url") or f"/doc/{doc.get('urlId')}", "title": doc["title"], "children": children or []}

    region_nodes = []
    for region in REGION_ORDER:
        province_nodes = []
        for province in REGION_PROVINCES[region]:
            if province not in province_docs:
                continue
            district_nodes = []
            for city, rows in sorted(grouped[province].items(), key=lambda item: (-len(item[1]), item[0])):
                city_doc = district_docs[(province, city)]
                company_nodes = [node(company_docs[row["management_no"]]) for row in rows if row["management_no"] in company_docs]
                district_nodes.append(node(city_doc, company_nodes))
            province_nodes.append(node(province_docs[province], district_nodes))
        region_nodes.append(node(region_docs[region], province_nodes))

    structure = prune(structure)
    inserted = False

    def set_root(nodes: list[dict[str, Any]]) -> None:
        nonlocal inserted
        for item in nodes:
            if item.get("id") == DETAIL_PARENT_ID:
                item["children"] = region_nodes
                inserted = True
                return
            set_root(list(item.get("children") or []))

    set_root(structure)
    write_collection_structure(structure)
    return {"inserted": inserted, "region_nodes": len(region_nodes), "removed_existing_nodes": removed}


def unique_titles(rows: list[dict[str, Any]]) -> dict[str, str]:
    by_parent_name: dict[tuple[str, str, str], int] = defaultdict(int)
    titles = {}
    for row in rows:
        if row["management_no"] in TITLE_OVERRIDES:
            titles[row["management_no"]] = TITLE_OVERRIDES[row["management_no"]]
            continue
        key = (row["province"], row["city"], row["name"])
        by_parent_name[key] += 1
    seen: dict[tuple[str, str, str], int] = defaultdict(int)
    for row in rows:
        key = (row["province"], row["city"], row["name"])
        seen[key] += 1
        if by_parent_name[key] == 1:
            titles[row["management_no"]] = row["name"]
        else:
            titles[row["management_no"]] = f"{row['name']} ({row['management_no'][-6:]})"
    return titles


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data_path = ENRICHED_DATA_JSON if ENRICHED_DATA_JSON.exists() else DATA_JSON
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    rows.sort(key=lambda row: (-int(row.get("equipment_total") or 0), row.get("province") or "", row.get("city") or "", row.get("name") or ""))
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["province"]][row["city"]].append(row)

    backup_path = backup_collection_structure()
    key = outline_publish.read_env_key("DOF_OUTLINE_KEY")
    client = Outline(key)
    title_by_id = unique_titles(rows)

    root_existing = {doc["title"]: doc for doc in client.list_children(DETAIL_PARENT_ID)}
    region_docs: dict[str, dict[str, Any]] = {}
    for region in REGION_ORDER:
        text = f"# {region}\n\n{region} 권역의 국내 치과기공소 후보를 시도·시군구별로 묶는 문서입니다.\n"
        region_docs[region] = upsert_child(client, DETAIL_PARENT_ID, region, text, root_existing)

    root_existing = {doc["title"]: doc for doc in client.list_children(DETAIL_PARENT_ID)}
    province_docs: dict[str, dict[str, Any]] = {}
    for province in PROVINCE_ORDER:
        short = PROVINCE_SHORT[province]
        region_doc = region_docs[PROVINCE_TO_REGION[province]]
        existing = {doc["title"]: doc for doc in client.list_children(region_doc["id"])}
        root_old = root_existing.get(province)
        if not root_old and short not in REGION_ORDER:
            root_old = root_existing.get(short)
        if root_old and root_old.get("id") == region_doc["id"]:
            root_old = None
        old = root_old or existing.get(province) or existing.get(short)
        if old:
            if old.get("parentDocumentId") != region_doc["id"]:
                client.move(old["id"], region_doc["id"])
            updated = client.update(old["id"], short, f"# {short}\n\n{short}의 치과기공소 후보를 시군구별로 정리합니다.\n")
            province_docs[province] = client.info(updated["id"])
        else:
            province_docs[province] = upsert_child(client, region_doc["id"], short, f"# {short}\n\n{short}의 치과기공소 후보를 시군구별로 정리합니다.\n", existing)

    district_docs: dict[tuple[str, str], dict[str, Any]] = {}
    for province in PROVINCE_ORDER:
        province_doc = province_docs[province]
        existing = {doc["title"]: doc for doc in client.list_children(province_doc["id"])}
        for city, city_rows in sorted(grouped[province].items(), key=lambda item: (-len(item[1]), item[0])):
            district_docs[(province, city)] = upsert_child(
                client,
                province_doc["id"],
                city,
                f"# {city} ({len(city_rows)}곳)\n\n{province} {city}의 치과기공소 후보입니다.\n",
                existing,
            )

    company_docs: dict[str, dict[str, Any]] = {}
    links: dict[str, str] = {}
    created_or_updated = 0
    for province in PROVINCE_ORDER:
        province_doc = province_docs[province]
        province_url = canonical_url(province_doc)
        for city, city_rows in sorted(grouped[province].items(), key=lambda item: (-len(item[1]), item[0])):
            district_doc = district_docs[(province, city)]
            district_url = canonical_url(district_doc)
            existing = {doc["title"]: doc for doc in client.list_children(district_doc["id"])}
            for row in city_rows:
                title = title_by_id[row["management_no"]]
                text = card_text(row, district_url, province_url)
                doc = upsert_child(client, district_doc["id"], title, text, existing)
                company_docs[row["management_no"]] = doc
                links[row["management_no"]] = canonical_url(doc)
                created_or_updated += 1
                if created_or_updated % 100 == 0:
                    print(f"company_cards {created_or_updated}/{len(rows)}", flush=True)

    for province in PROVINCE_ORDER:
        province_doc = province_docs[province]
        for city, city_rows in grouped[province].items():
            city_doc = district_docs[(province, city)]
            client.update(city_doc["id"], city, district_text(province, city, city_rows, links))
        client.update(province_doc["id"], PROVINCE_SHORT[province], province_text(province, grouped[province], {city: district_docs[(province, city)] for city in grouped[province]}, links))

    province_counts = {province: sum(len(rows_) for rows_ in grouped[province].values()) for province in PROVINCE_ORDER}
    for region in REGION_ORDER:
        docs = [{**province_docs[province], "province": province} for province in REGION_PROVINCES[region] if province in province_docs]
        client.update(region_docs[region]["id"], region, region_text(region, docs, province_counts))

    region_doc_list = [region_docs[region] for region in REGION_ORDER]
    client.update(DETAIL_PARENT_ID, "국내 치과기공소", root_text(region_doc_list, len(rows)))
    report = client.update(REPORT_DOC_ID, "리포트260607-국내-기공소", report_text(rows, links))

    tree_result = replace_qche_tree(region_docs, province_docs, district_docs, company_docs, grouped)
    restarted = restart_outline()

    result = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "backup": str(backup_path),
        "total_rows": len(rows),
        "data_path": str(data_path),
        "region_docs": {k: {"id": v["id"], "url": canonical_url(v)} for k, v in region_docs.items()},
        "province_docs": {k: {"id": v["id"], "title": v["title"], "url": canonical_url(v)} for k, v in province_docs.items()},
        "district_docs": len(district_docs),
        "company_docs": len(company_docs),
        "report_doc": {"id": report["id"], "url": canonical_url(report), "title": report["title"]},
        "tree_result": tree_result,
        "outline_restart": restarted,
    }
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
