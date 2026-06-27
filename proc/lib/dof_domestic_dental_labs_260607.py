#!/usr/bin/env python3
"""Build and publish the domestic dental-lab licensing report for 260607."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dof_domestic_report_260607 as domestic_base  # noqa: E402
import dof_prospect_outline_publish as outline_publish  # noqa: E402


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_DIR = ROOT / "output/domestic-dental-labs-260607"
RAW_CSV = OUT_DIR / "health_dental_labs_localdata.csv"
ALL_JSON = OUT_DIR / "domestic_dental_labs_all.json"
SELECTED_JSON = OUT_DIR / "domestic_dental_labs_selected.json"
REPORT_MD = OUT_DIR / "report_260607_domestic_dental_labs.md"
RESULT_JSON = OUT_DIR / "report_260607_domestic_dental_labs_result.json"
HEALTH_JSON = OUT_DIR / "outline_health_260607_domestic_dental_labs.json"

OUTLINE_BASE = "https://outline.doflab.com"
REPORT_PARENT_ID = "07b08eec-2ecb-42aa-b043-8e89f5ac6fb9"
REPORT_TITLE = "리포트260607-국내-기공소"

DATA_GO_KR_URL = "https://www.data.go.kr/data/15114134/standard.do?recommendDataYn=Y"
LOCALDATA_INFO_URL = "https://file.localdata.go.kr/file/dental_labs/info"
LOCALDATA_VALIDATE_URL = "https://file.localdata.go.kr/file/validate/download-count"
LOCALDATA_DOWNLOAD_URL = "https://file.localdata.go.kr/file/download/dental_labs/info"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

REGION_GROUPS = {
    "수도권": {"서울특별시", "인천광역시", "경기도"},
    "영남": {"부산광역시", "대구광역시", "울산광역시", "경상북도", "경상남도"},
    "충청": {"대전광역시", "세종특별자치시", "충청북도", "충청남도"},
    "호남": {"광주광역시", "전북특별자치도", "전라북도", "전라남도"},
    "강원": {"강원특별자치도", "강원도"},
    "제주": {"제주특별자치도"},
}

EQUIPMENT_COLUMNS = [
    ("기공용레스수", "레스"),
    ("기공용모터수", "모터"),
    ("기공용컴프레서수", "컴프레서"),
    ("샌드기수", "샌드기"),
    ("서베이어수", "서베이어"),
    ("아세틸렌수", "아세틸렌"),
    ("원심주조기수", "원심주조기"),
    ("전기로수", "전기로"),
    ("진공매몰기수", "진공매몰기"),
    ("진동기수", "진동기"),
    ("초음파청소기수", "초음파청소기"),
    ("치과용프레스수", "치과용프레스"),
    ("트리머수", "트리머"),
    ("포셀린로수", "포셀린로"),
    ("핀덱스수", "핀덱스"),
]


@dataclass
class LabRow:
    name: str
    status: str
    detail_status: str
    license_date: str
    closed_date: str
    province: str
    city: str
    address: str
    zip_code: str
    phone: str
    portal_status: str
    equipment_total: int
    equipment_summary: str
    management_no: str
    updated_at: str
    source_url: str
    search_url: str
    trust: str
    recommendation: str


def compact(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def md_escape(value: Any, limit: int = 220) -> str:
    return compact(value, limit).replace("|", "\\|").replace("\n", "<br>")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def normalize_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value or "").lower()


def parse_int(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def derive_region(address: str) -> tuple[str, str, str]:
    parts = (address or "").split()
    province = parts[0] if parts else "지역확인필요"
    city = parts[1] if len(parts) > 1 else "시군구확인필요"
    group = "기타"
    for label, provinces in REGION_GROUPS.items():
        if province in provinces:
            group = label
            break
    return group, province, city


def clean_phone(value: str, address: str = "") -> str:
    text = re.sub(r"\s+", "", value or "")
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 8 and address.startswith("서울"):
        digits = "02" + digits
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    if digits.startswith("02") and len(digits) in {9, 10}:
        return f"02-{digits[2:-4]}-{digits[-4:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return text.replace(".", "-")


def download_localdata_csv(timeout: int) -> tuple[str, dict[str, Any]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Referer": DATA_GO_KR_URL,
        }
    )
    page = session.get(LOCALDATA_INFO_URL, timeout=timeout)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")
    csrf = ""
    meta = soup.find("meta", {"name": "_csrf"})
    if meta:
        csrf = str(meta.get("content") or "")
    headers = {"Referer": LOCALDATA_INFO_URL}
    if csrf:
        headers["X-XSRF-TOKEN"] = csrf
    validate = session.get(LOCALDATA_VALIDATE_URL, headers=headers, timeout=timeout)
    validate.raise_for_status()
    response = session.get(LOCALDATA_DOWNLOAD_URL, headers=headers, timeout=max(timeout, 120))
    response.raise_for_status()
    raw = response.content
    text = raw.decode("cp949")
    RAW_CSV.write_text(text, encoding="utf-8")
    meta_info = {
        "downloaded_at": datetime.now().isoformat(timespec="seconds"),
        "source_data_go_kr": DATA_GO_KR_URL,
        "source_localdata_info": LOCALDATA_INFO_URL,
        "source_localdata_download": LOCALDATA_DOWNLOAD_URL,
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "content_disposition": response.headers.get("content-disposition"),
        "byte_length": len(raw),
        "saved_csv": str(RAW_CSV),
    }
    return text, meta_info


def row_to_lab(row: dict[str, str], existing_keys: set[str]) -> LabRow:
    name = compact(row.get("사업장명"), 80)
    address = compact(row.get("도로명주소") or row.get("지번주소"), 180)
    group, province, city = derive_region(address)
    phone = clean_phone(row.get("전화번호", ""), address)
    norm = normalize_key(name)
    portal_status = "포털/주문 직접 매칭 없음"
    if norm in existing_keys or any(norm and norm in key for key in existing_keys):
        portal_status = "기존 포털/주문 유사명"
    equipment_parts: list[str] = []
    equipment_total = 0
    for key, label in EQUIPMENT_COLUMNS:
        count = parse_int(row.get(key))
        if count > 0:
            equipment_total += count
            if len(equipment_parts) < 5:
                equipment_parts.append(f"{label} {count}")
    equipment_summary = ", ".join(equipment_parts) if equipment_parts else "장비수 공개값 없음"
    status = compact(row.get("영업상태명"), 40)
    detail_status = compact(row.get("상세영업상태명"), 40)
    trust = "높음" if status == "영업/정상" and detail_status == "영업중" and address else "중간"
    if not phone:
        trust = "중간"
    recommendation = (
        "행정안전부 표준 인허가 데이터에 영업중 치과기공소로 등재되어 있고 "
        "보철 제작 장비 항목이 공개되어 기공/스캔/밀링 workflow 영업 타깃으로 분류 가능"
    )
    if equipment_total == 0:
        recommendation = (
            "행정안전부 표준 인허가 데이터에 영업중 치과기공소로 등재되어 있어 "
            "주소 기반 1차 콜드아웃 후보로 활용 가능"
        )
    search_url = "https://search.naver.com/search.naver?query=" + quote_plus(f"{name} {province} {city} 치과기공소")
    return LabRow(
        name=name,
        status=status,
        detail_status=detail_status,
        license_date=compact(row.get("인허가일자"), 20),
        closed_date=compact(row.get("폐업일자"), 20),
        province=province,
        city=city,
        address=address,
        zip_code=compact(row.get("도로명우편번호") or row.get("소재지우편번호"), 20),
        phone=phone,
        portal_status=portal_status,
        equipment_total=equipment_total,
        equipment_summary=equipment_summary,
        management_no=compact(row.get("관리번호"), 60),
        updated_at=compact(row.get("최종수정시점") or row.get("데이터갱신시점"), 40),
        source_url=DATA_GO_KR_URL,
        search_url=search_url,
        trust=trust,
        recommendation=recommendation,
    )


def load_rows(csv_text: str, existing_keys: set[str]) -> list[LabRow]:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = [row_to_lab(row, existing_keys) for row in reader if compact(row.get("사업장명"))]
    return rows


def select_rows(rows: list[LabRow], target_count: int) -> list[LabRow]:
    active = [row for row in rows if row.status == "영업/정상" and row.detail_status == "영업중"]
    ranked = sorted(
        active,
        key=lambda row: (
            0 if row.phone else 1,
            0 if row.address else 1,
            -row.equipment_total,
            row.province,
            row.city,
            row.name,
        ),
    )
    if target_count <= 0:
        return ranked
    return ranked[: min(target_count, len(ranked))]


def make_report(
    selected: list[LabRow],
    all_rows: list[LabRow],
    source_meta: dict[str, Any],
    outline_status: dict[str, Any] | None = None,
) -> str:
    active_count = sum(1 for row in all_rows if row.status == "영업/정상" and row.detail_status == "영업중")
    status_counts = Counter(row.detail_status or row.status for row in all_rows)
    province_counts = Counter(row.province for row in selected)
    portal_counts = Counter(row.portal_status for row in selected)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    outline_text = compact((outline_status or {}).get("status") or "publish 전 생성", 180)
    lines = [
        "# 260607 국내 치과기공소 인허가 기반 영업후보",
        "",
        "## 작성 기준",
        "- 목적: 국내 치과 영업후보 중 치과기공소 비중이 낮았던 문제를 보완하기 위해, 전국 치과기공소 인허가/영업상태 데이터를 별도 리포트로 정리했다.",
        f"- 원천: [공공데이터포털 전국치과기공소표준데이터]({DATA_GO_KR_URL}) 및 해당 페이지의 지방행정 인허가 CSV 다운로드.",
        "- 데이터 의미: 의료기사 등에 관한 법률에 따라 운영되는 치과기공소의 인허가일자, 영업상태, 사업장명, 소재지주소, 전화번호, 일부 장비 수량이 포함된다.",
        "- 추천 기준: `영업/정상` + `영업중` 상태인 업체를 우선했고, 전화번호/주소/장비 수량이 있는 업체를 상단 배치했다.",
        "- 포털 여부: 로컬 portal/contact/order 산출물의 기존 고객·주문명과 이름 유사 매칭되는 경우 `기존 포털/주문 유사명`으로 표시했다. 직접 매칭이 없다는 표시는 공공데이터에 포털 미등록을 증명하는 것이 아니라 로컬 매칭 결과다.",
        "- 신뢰도: 정부 표준 인허가 데이터 기반이므로 업체 존재/영업상태 신뢰도는 높다. 단, 웹사이트·담당자·실장비 현황은 개별 콜/웹검색으로 최신 확인이 필요하다.",
        f"- 작성 시각: {now} KST. Outline API 상태: {outline_text}",
        "",
        "## 수집 요약",
        f"- 원천 전체 행: {len(all_rows):,}개",
        f"- 영업중 치과기공소: {active_count:,}개",
        f"- 이 문서 표 반영: {len(selected):,}개",
        "- 전체 상태 분포: " + ", ".join(f"{k} {v:,}" for k, v in status_counts.most_common(8)),
        "- 표 반영 지역 상위: " + ", ".join(f"{k} {v:,}" for k, v in province_counts.most_common(12)),
        "- 포털 매칭 분포: " + ", ".join(f"{k} {v:,}" for k, v in portal_counts.most_common()),
        f"- 원천 CSV 저장: `{source_meta.get('saved_csv')}`",
        "",
        "## 업체 테이블",
        "| 우선순위 | 대분류 | 중분류 | 소분류 | 업체명 | 어떤 곳인지 | 포털 존재 여부 | 인허가/인증 근거 | 영업상태 | 인허가일자 | 주소 | 전화 | 장비 공개값 | 검색/출처 | 신뢰도 | 추천 이유 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in selected:
        priority = "A-영업중 인허가"
        category = "국내"
        middle = "치과기공소"
        sub = f"{row.province}/{row.city}"
        what = "전국 표준 인허가 데이터에 등재된 치과기공소"
        evidence = "의료기사 등에 관한 법률 기반 치과기공소 인허가 표준데이터"
        status = f"{row.status}/{row.detail_status}"
        address = row.address or "주소 미공개"
        phone = row.phone or "전화 미공개"
        source = f"공공데이터 / 검색어: {row.name} {row.province} {row.city} 치과기공소"
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(priority, 80),
                    md_escape(category, 40),
                    md_escape(middle, 40),
                    md_escape(sub, 80),
                    md_escape(row.name, 100),
                    md_escape(what, 120),
                    md_escape(row.portal_status, 100),
                    md_escape(evidence, 160),
                    md_escape(status, 80),
                    md_escape(row.license_date or "-", 40),
                    md_escape(address, 180),
                    md_escape(phone, 60),
                    md_escape(row.equipment_summary, 160),
                    source,
                    md_escape(row.trust, 40),
                    md_escape(row.recommendation, 220),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 후속 사용 메모",
            "- 전화번호가 있는 곳은 바로 콜드아웃 후보로 쓰고, 전화 미공개 업체는 네이버/카카오 지도 또는 지자체 보건소 페이지로 연락처를 보강한다.",
            "- `기존 포털/주문 유사명`은 후보에서 제외하거나 기존 고객 확장 영업으로 따로 다룬다.",
            "- 장비 수량은 인허가 표준 항목의 공개값이다. CAD/CAM, 구강스캐너, 밀링기 보유 여부는 이 표만으로 확정하지 말고 홈페이지/전화로 재확인한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def outline_api(session: requests.Session, endpoint: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = session.post(f"{OUTLINE_BASE}/api/{endpoint}", json=body, timeout=timeout)
    response.raise_for_status()
    return response.json()


def split_markdown_for_append(markdown: str, chunk_rows: int) -> tuple[str, list[str]]:
    lines = markdown.splitlines()
    row_indexes = [idx for idx, line in enumerate(lines) if line.startswith("| A-영업중 인허가 |")]
    if not row_indexes:
        return markdown, []
    first_row = row_indexes[0]
    last_row = row_indexes[-1]
    base_text = "\n".join(lines[:first_row]) + "\n"
    row_lines = lines[first_row : last_row + 1]
    suffix_lines = lines[last_row + 1 :]
    chunks: list[str] = []
    for start in range(0, len(row_lines), chunk_rows):
        chunks.append("\n".join(row_lines[start : start + chunk_rows]) + "\n")
    if suffix_lines:
        chunks.append("\n".join(suffix_lines) + "\n")
    return base_text, chunks


def outline_health_check(timeout: int) -> dict[str, Any]:
    key = outline_publish.read_env_key("DOF_OUTLINE_KEY")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}"})
    health: dict[str, Any] = {"checked_at": datetime.now().isoformat(timespec="seconds"), "status": "starting"}
    try:
        parent = outline_api(session, "documents.info", {"id": REPORT_PARENT_ID}, timeout)
        health.update(
            {
                "status": "healthy",
                "parent_title": (parent.get("data") or {}).get("title"),
            }
        )
        try:
            listed = outline_api(session, "documents.list", {"parentDocumentId": REPORT_PARENT_ID, "limit": 100, "offset": 0}, min(timeout, 30))
            health["listed_children"] = len(listed.get("data") or [])
        except Exception as list_error:
            health["list_status"] = f"documents.list skipped: {type(list_error).__name__}: {list_error}"
    except Exception as error:
        health.update({"status": f"outline health failed: {type(error).__name__}: {error}"})
    save_json(HEALTH_JSON, health)
    return health


def publish_to_outline(markdown: str, timeout: int) -> dict[str, Any]:
    key = outline_publish.read_env_key("DOF_OUTLINE_KEY")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}"})
    health: dict[str, Any] = {"checked_at": datetime.now().isoformat(timespec="seconds"), "status": "starting"}
    listed: dict[str, Any] = {"data": []}
    try:
        parent = outline_api(session, "documents.info", {"id": REPORT_PARENT_ID}, timeout)
        health.update(
            {
                "status": "healthy",
                "parent_title": (parent.get("data") or {}).get("title"),
            }
        )
        try:
            listed = outline_api(session, "documents.list", {"parentDocumentId": REPORT_PARENT_ID, "limit": 100, "offset": 0}, min(timeout, 30))
            health["listed_children"] = len(listed.get("data") or [])
        except Exception as list_error:
            health["list_status"] = f"documents.list skipped: {type(list_error).__name__}: {list_error}"
    except Exception as error:
        health.update({"status": f"outline health failed: {type(error).__name__}: {error}"})
        save_json(HEALTH_JSON, health)
        return {"published": False, "health": health, "error": health["status"]}

    try:
        existing_id = ""
        existing_url = ""
        for doc in listed.get("data") or []:
            if doc.get("title") == REPORT_TITLE:
                existing_id = doc.get("id") or ""
                existing_url = f"{OUTLINE_BASE}/doc/{doc.get('urlId')}"
                break
        base_text, append_chunks = split_markdown_for_append(markdown, chunk_rows=250)
        if existing_id:
            data = outline_api(
                session,
                "documents.update",
                {"id": existing_id, "title": REPORT_TITLE, "text": base_text, "publish": True, "fullWidth": True},
                timeout,
            )["data"]
            action = "updated"
        else:
            data = outline_api(
                session,
                "documents.create",
                {
                    "title": REPORT_TITLE,
                    "parentDocumentId": REPORT_PARENT_ID,
                    "text": base_text,
                    "publish": True,
                    "fullWidth": True,
                },
                timeout,
            )["data"]
            action = "created"
        doc_id = data.get("id") or existing_id
        appended_chunks = 0
        for chunk in append_chunks:
            outline_api(
                session,
                "documents.update",
                {"id": doc_id, "text": chunk, "append": True, "publish": True, "fullWidth": True},
                timeout,
            )
            appended_chunks += 1
        readback = outline_api(session, "documents.info", {"id": doc_id}, timeout)["data"]
        text = readback.get("text") or ""
        result = {
            "published": True,
            "action": action,
            "append_chunks": appended_chunks,
            "doc_id": doc_id,
            "url": f"{OUTLINE_BASE}/doc/{readback.get('urlId')}" if readback.get("urlId") else existing_url,
            "title": readback.get("title"),
            "text_length": len(text),
            "table_rows": text.count("| A-영업중 인허가 |"),
            "has_portal_column": "포털 존재 여부" in text,
            "has_source_note": "전국치과기공소표준데이터" in text,
            "health": health,
        }
        save_json(HEALTH_JSON, health)
        return result
    except Exception as error:
        health.update({"status": f"outline publish failed: {type(error).__name__}: {error}"})
        save_json(HEALTH_JSON, health)
        return {"published": False, "health": health, "error": health["status"]}


def build_report(target_count: int, publish: bool, timeout: int) -> dict[str, Any]:
    csv_text, source_meta = download_localdata_csv(timeout)
    existing_keys = domestic_base.load_existing_customer_keys()
    rows = load_rows(csv_text, existing_keys)
    selected = select_rows(rows, target_count)
    source_meta["parsed_rows"] = len(rows)
    source_meta["selected_rows"] = len(selected)
    source_meta["active_rows"] = sum(1 for row in rows if row.status == "영업/정상" and row.detail_status == "영업중")
    save_json(ALL_JSON, [asdict(row) for row in rows])
    save_json(SELECTED_JSON, [asdict(row) for row in selected])
    outline_status: dict[str, Any] = outline_health_check(timeout) if publish else {"status": "publish skipped"}
    outline_result: dict[str, Any] = {"published": False, "skipped": not publish, "health": outline_status}
    markdown = make_report(selected, rows, source_meta, outline_status)
    REPORT_MD.write_text(markdown, encoding="utf-8")
    if publish:
        outline_result = publish_to_outline(markdown, timeout)
    result = {
        "target_count": target_count,
        "all_rows": len(rows),
        "active_rows": source_meta["active_rows"],
        "selected_rows": len(selected),
        "source": source_meta,
        "outputs": {
            "raw_csv": str(RAW_CSV),
            "all_json": str(ALL_JSON),
            "selected_json": str(SELECTED_JSON),
            "report_md": str(REPORT_MD),
            "health_json": str(HEALTH_JSON),
        },
        "outline": outline_result,
    }
    save_json(RESULT_JSON, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-count", type=int, default=3000, help="Rows to include in the Outline table. 0 means all active rows.")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    result = build_report(args.target_count, args.publish, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if (not args.publish or result.get("outline", {}).get("published")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
