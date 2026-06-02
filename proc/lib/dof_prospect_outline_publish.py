#!/usr/bin/env python3
"""Publish DOF overseas customer prospects as an Outline document tree."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from dof_customer_prospect_map_points import COUNTRY_NAMES


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
BASE = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA = BASE / "data"
COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
PUBLISH_ROOT = BASE / "outline_publish"
DOC_CACHE = PUBLISH_ROOT / "outline_docs.json"
PUBLISH_DATASET = PUBLISH_ROOT / "outline_publish_dataset.json"
PUBLISH_RESULT = PUBLISH_ROOT / "outline_publish_result.json"

OUTLINE_BASE = "https://outline.doflab.com"
TARGET_URL_ID = "7jib7jef7lky7zue67o0-c0ae88mpyc"
REQUEST_TIMEOUT = 60
PAUSE_SECONDS = 0.03


WEST_EUROPE = {
    "Austria",
    "Belgium",
    "Denmark",
    "Finland",
    "France",
    "Germany",
    "Iceland",
    "Ireland",
    "Italy",
    "Luxembourg",
    "Malta",
    "Monaco",
    "Netherlands",
    "Norway",
    "Portugal",
    "Spain",
    "Sweden",
    "Switzerland",
    "United Kingdom",
}
EAST_EUROPE = {
    "Albania",
    "Armenia",
    "Belarus",
    "Bosnia and Herzegovina",
    "Bulgaria",
    "Croatia",
    "Czechia",
    "Estonia",
    "Georgia",
    "Hungary",
    "Kosovo",
    "Latvia",
    "Lithuania",
    "Moldova",
    "North Macedonia",
    "Poland",
    "Romania",
    "Russia",
    "Serbia",
    "Slovakia",
    "Slovenia",
    "Ukraine",
}
EAST_ASIA = {"China", "Hong Kong", "Japan", "South Korea", "Taiwan"}
SOUTHEAST_ASIA = {
    "Brunei",
    "Cambodia",
    "Indonesia",
    "Laos",
    "Malaysia",
    "Myanmar",
    "Philippines",
    "Singapore",
    "Thailand",
    "Timor-Leste",
    "Vietnam",
}
MIDDLE_EAST = {
    "Bahrain",
    "Cyprus",
    "Iran",
    "Iraq",
    "Israel",
    "Jordan",
    "Kuwait",
    "Lebanon",
    "Oman",
    "Qatar",
    "Saudi Arabia",
    "Syria",
    "Turkey",
    "United Arab Emirates",
    "Yemen",
}
SOUTH_ASIA = {"Bangladesh", "India", "Nepal", "Pakistan", "Sri Lanka"}
OCEANIA = {"Australia", "New Zealand"}
NORTH_AMERICA = {"Canada", "Mexico", "United States"}
LATIN_AMERICA = {
    "Argentina",
    "Bolivia",
    "Brazil",
    "Chile",
    "Colombia",
    "Costa Rica",
    "Dominican Republic",
    "Ecuador",
    "El Salvador",
    "Guatemala",
    "Honduras",
    "Nicaragua",
    "Panama",
    "Paraguay",
    "Peru",
    "Uruguay",
    "Venezuela",
}
AFRICA = {
    "Algeria",
    "Botswana",
    "Cote d'Ivoire",
    "Egypt",
    "Ethiopia",
    "Ghana",
    "Kenya",
    "Libya",
    "Mauritius",
    "Morocco",
    "Namibia",
    "Nigeria",
    "Senegal",
    "South Africa",
    "Tanzania",
    "Tunisia",
    "Uganda",
    "Zambia",
    "Zimbabwe",
}
NORTHEAST_ASIA = {"China", "Hong Kong", "Japan", "Mongolia", "South Korea", "Taiwan"}
INDONESIA = {"Indonesia"}
SEA_EX_INDONESIA = SOUTHEAST_ASIA - INDONESIA
CENTRAL_EUROPE = {"Austria", "Czechia", "Germany", "Hungary", "Liechtenstein", "Poland", "Slovakia", "Slovenia", "Switzerland"}
SOUTHERN_EUROPE = {"Greece", "Montenegro"}
WESTERN_EUROPE = {
    "Belgium",
    "Denmark",
    "Finland",
    "France",
    "Iceland",
    "Ireland",
    "Italy",
    "Luxembourg",
    "Malta",
    "Monaco",
    "Netherlands",
    "Norway",
    "Portugal",
    "Spain",
    "Sweden",
    "United Kingdom",
}
CIS = {"Armenia", "Azerbaijan", "Belarus", "Kazakhstan", "Kyrgyzstan", "Moldova", "Russia", "Tajikistan", "Uzbekistan"}
EASTERN_EUROPE = EAST_EUROPE - CENTRAL_EUROPE - CIS
REGION_ORDER = [
    "북미",
    "남미",
    "동북아",
    "동남아",
    "인니",
    "중유럽",
    "서유럽",
    "남유럽",
    "동유럽",
    "CIS",
    "중동",
    "남아시아",
    "오세아니아",
    "아프리카",
    "기타",
]
REGION_LABEL_KO = {region: region for region in REGION_ORDER}
COUNTRY_LABEL_KO = {
    "Albania": "알바니아",
    "Algeria": "알제리",
    "Argentina": "아르헨",
    "Armenia": "아르메니아",
    "Australia": "호주",
    "Austria": "오스트리아",
    "Azerbaijan": "아제르",
    "Bangladesh": "방글라데시",
    "Belarus": "벨라루스",
    "Belgium": "벨기에",
    "Bolivia": "볼리비아",
    "Bosnia and Herzegovina": "보스니아",
    "Botswana": "보츠와나",
    "Brazil": "브라질",
    "Bulgaria": "불가리아",
    "Cambodia": "캄보디아",
    "Canada": "캐나다",
    "Chile": "칠레",
    "China": "중국",
    "Colombia": "콜롬비아",
    "Costa Rica": "코스타리카",
    "Cote d'Ivoire": "코트디부아르",
    "Croatia": "크로아티아",
    "Cyprus": "키프로스",
    "Czechia": "체코",
    "Denmark": "덴마크",
    "Dominican Republic": "도미니카",
    "Ecuador": "에콰도르",
    "Egypt": "이집트",
    "El Salvador": "엘살바도르",
    "Estonia": "에스토니아",
    "Ethiopia": "에티오피아",
    "Finland": "핀란드",
    "France": "프랑스",
    "Germany": "독일",
    "Georgia": "조지아",
    "Ghana": "가나",
    "Greece": "그리스",
    "Guatemala": "과테말라",
    "Honduras": "온두라스",
    "Hong Kong": "홍콩",
    "Hungary": "헝가리",
    "Iceland": "아이슬란드",
    "India": "인도",
    "Indonesia": "인니",
    "Iran": "이란",
    "Iraq": "이라크",
    "Ireland": "아일랜드",
    "Israel": "이스라엘",
    "Italy": "이탈리아",
    "Japan": "일본",
    "Jordan": "요르단",
    "Kazakhstan": "카자흐",
    "Kenya": "케냐",
    "Kosovo": "코소보",
    "Kuwait": "쿠웨이트",
    "Kyrgyzstan": "키르기스",
    "Lebanon": "레바논",
    "Liechtenstein": "리히텐슈타인",
    "Libya": "리비아",
    "Lithuania": "리투아니아",
    "Malta": "몰타",
    "Malaysia": "말레이",
    "Mauritius": "모리셔스",
    "Mexico": "멕시코",
    "Moldova": "몰도바",
    "Monaco": "모나코",
    "Mongolia": "몽골",
    "Montenegro": "몬테네그로",
    "Morocco": "모로코",
    "Myanmar": "미얀마",
    "Namibia": "나미비아",
    "Netherlands": "네덜란드",
    "New Zealand": "뉴질랜드",
    "Nicaragua": "니카라과",
    "Nigeria": "나이지리아",
    "North Macedonia": "북마케도니아",
    "Norway": "노르웨이",
    "Oman": "오만",
    "Panama": "파나마",
    "Paraguay": "파라과이",
    "Peru": "페루",
    "Philippines": "필리핀",
    "Poland": "폴란드",
    "Portugal": "포르투갈",
    "Qatar": "카타르",
    "Romania": "루마니아",
    "Russia": "러시아",
    "Saudi Arabia": "사우디",
    "Senegal": "세네갈",
    "Serbia": "세르비아",
    "Singapore": "싱가포르",
    "Slovakia": "슬로바키아",
    "South Africa": "남아공",
    "Spain": "스페인",
    "Sweden": "스웨덴",
    "Switzerland": "스위스",
    "Syria": "시리아",
    "Taiwan": "대만",
    "Tajikistan": "타지키스탄",
    "Tanzania": "탄자니아",
    "Thailand": "태국",
    "Tunisia": "튀니지",
    "Turkey": "튀르키예",
    "Ukraine": "우크라이나",
    "Uganda": "우간다",
    "United Arab Emirates": "UAE",
    "United Kingdom": "영국",
    "United States": "미국",
    "Uruguay": "우루과이",
    "Uzbekistan": "우즈벡",
    "Venezuela": "베네수엘라",
    "Vietnam": "베트남",
    "Zambia": "잠비아",
    "Yemen": "예멘",
    "Zimbabwe": "짐바브웨",
}

SEGMENT_KO = {
    "Dental clinic / practice": "치과 병·의원",
    "Dental clinic / orthodontics": "교정 치과",
    "Dental clinic / implant and surgery": "임플란트·구강외과 치과",
    "Dental laboratory / dental technician": "치과기공소·치과기공사",
    "Dental distributor / product supplier": "치과 유통사·장비 공급사",
    "Portal customer / dental business": "기존 포탈 고객 / 치과 사업자",
    "Portal customer / dealer or channel": "기존 포탈 고객 / 딜러·채널",
    "Portal customer / overseas account": "기존 포탈 고객 / 해외 계정",
    "Portal customer / dental lab or milling": "기존 포탈 고객 / 기공소·밀링",
}
DOF_FIT_KO = {
    "Intraoral scanner, digital impression, clinic-to-lab workflow": "구강스캐너, 디지털 인상, 치과-기공소 연계 워크플로우",
    "Intraoral scanner, digital impression, case communication workflow": "구강스캐너, 디지털 인상, 교정 케이스 커뮤니케이션 워크플로우",
    "Intraoral scanner, implant planning workflow, lab communication": "구강스캐너, 임플란트 플래닝, 기공소 협업 워크플로우",
    "Lab scanner, CAD/CAM workflow, production digitization": "랩 스캐너, CAD/CAM, 기공 생산 디지털화",
    "Channel sales, scanner resale, equipment distribution, local service partnership": "채널 영업, 스캐너 리셀, 장비 유통, 현지 서비스 파트너십",
    "Existing DOF account: prioritize account expansion, scanner replacement, service renewal, or channel follow-up depending on account type.": "기존 DOF 계정: 계정 확대, 스캐너 교체, 서비스 갱신, 채널 후속 영업을 우선 검토",
}
SOURCE_TYPE_KO = {
    "OpenStreetMap public business tag": "공개 OSM 사업자 태그",
    "OpenStreetMap dental distributor/import-export public business tag": "공개 OSM 치과 유통·수출입 사업자 태그",
    "OSM public tag + official website contact extraction": "공개 OSM 태그 + 공식 웹사이트 연락처 확인",
    "DOF portal Company": "DOF 포탈 등록 고객사",
    "Bredent global distributor locator": "Bredent 공식 글로벌 유통사 locator",
    "Henry Schein international distributor locator": "Henry Schein 공식 국제 유통사 locator",
    "Denovo Dental official distributor page": "Denovo Dental 공식 유통사 페이지",
    "Modern Dentistry Media dental directory PDF 2024": "Modern Dentistry Media 치과 공급사 PDF 2024",
    "Dentsply Sirona MENA local distributors PDF": "Dentsply Sirona MENA 현지 딜러 PDF",
    "German Pavilion dental trade fair exhibitor directory": "German Pavilion 치과 전시 참가사 디렉터리",
    "Italian Trade Agency AEEDC 2026 Italian Pavilion PDF": "ITA AEEDC 2026 이탈리아관 PDF",
    "Dental World Budapest exhibitor directory": "Dental World Budapest 참가사 디렉터리",
    "vhf dental reseller directory": "vhf 치과 CAD/CAM reseller 디렉터리",
    "imes-icore USA partner directory": "imes-icore USA CAD/CAM 파트너 디렉터리",
    "LMTmag dental laboratory and supplier company directory": "LMTmag 치기공·재료·장비 회사 디렉터리",
    "USA Dental Products regional supplier directory": "USA Dental Products 주별 공급사 디렉터리",
    "Greater New York Dental Meeting 2025 official exhibitor directory": "GNYDM 2025 공식 참가사 디렉터리",
    "SmallWorldLabs official dental exhibition exhibitor directory": "SmallWorldLabs 공식 치과 전시회 참가사 디렉터리",
    "IDS Cologne 2025 official exhibitor search": "IDS Cologne 2025 공식 참가사 검색",
    "IDS Cologne 2025 preliminary exhibitor list PDF and official website contact": "IDS Cologne 2025 예비 참가사 PDF + 공식 웹사이트 연락처",
}
SELECTION_REASON_KO = {
    "Publicly listed dental practice with direct email, phone, and address; dental clinics are prospective buyers of intraoral scanners and digital impression workflows.": "공개 사업자 정보에서 이메일, 전화번호, 주소가 확인된 치과 병·의원이다. 치과 병·의원은 구강스캐너와 디지털 인상 워크플로우의 직접 구매 또는 도입 검토 대상이다.",
    "Publicly listed orthodontic or dental clinic with direct email, phone, and address; likely buyer or evaluator of intraoral scanning and digital treatment workflows.": "공개 사업자 정보에서 이메일, 전화번호, 주소가 확인된 교정 또는 치과 병·의원이다. 구강스캐닝과 디지털 치료 워크플로우를 구매하거나 평가할 가능성이 높다.",
    "Publicly listed implant/surgical dental provider with direct email, phone, and address; implant workflows often require accurate scans and lab collaboration.": "공개 사업자 정보에서 이메일, 전화번호, 주소가 확인된 임플란트·수술 중심 치과 사업자다. 임플란트 워크플로우는 정밀 스캔과 기공소 협업 수요가 커서 DOF 제품과 연결 가능성이 높다.",
    "Publicly listed dental lab or dental technician with direct email, phone, and address; likely buyer of lab scanners, model scanning workflow, and CAD/CAM production tools.": "공개 사업자 정보에서 이메일, 전화번호, 주소가 확인된 치과기공소 또는 치과기공사다. 랩 스캐너, 모델 스캔 워크플로우, CAD/CAM 생산 장비의 구매 후보가 될 수 있다.",
    "Publicly listed dental distributor, supply, equipment, or trading company with direct email, phone, and address; likely channel partner or resale prospect for DOF scanners and digital dentistry products.": "공개 사업자 정보에서 이메일, 전화번호, 주소가 확인된 치과 유통사·장비 공급사·무역사다. DOF 스캐너와 디지털 치과 제품의 현지 채널 또는 리셀 파트너 후보가 될 수 있다.",
}


@dataclass
class OutlineDoc:
    id: str
    url_id: str
    title: str
    url: str
    parent_document_id: str | None = None


def read_env_key(name: str) -> str:
    env_path = ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError(f"{name} not found")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def md_escape(text: Any) -> str:
    value = "" if text is None else str(text)
    return value.replace("|", "\\|").replace("\n", "<br>").strip()


def md_link(label: str, url: str) -> str:
    if not url:
        return md_escape(label)
    return f"[{md_escape(label)}]({url})"


def compact(text: Any, limit: int = 260) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def country_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Unknown"
    upper = raw.upper()
    if upper in COUNTRY_NAMES:
        return COUNTRY_NAMES[upper]
    by_name = {name.lower(): name for name in COUNTRY_NAMES.values()}
    aliases = {
        "usa": "United States",
        "u.s.a.": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
        "uae": "United Arab Emirates",
        "viet nam": "Vietnam",
        "türkiye": "Turkey",
        "türkİye": "Turkey",
        "turkiye": "Turkey",
    }
    lowered = raw.lower()
    normalized_lowered = lowered.replace("i\u0307", "i")
    return aliases.get(lowered, aliases.get(normalized_lowered, by_name.get(lowered, raw)))


def region_for_country(country: str) -> str:
    if country in NORTH_AMERICA:
        return "북미"
    if country in LATIN_AMERICA:
        return "남미"
    if country in NORTHEAST_ASIA:
        return "동북아"
    if country in INDONESIA:
        return "인니"
    if country in SEA_EX_INDONESIA:
        return "동남아"
    if country in CENTRAL_EUROPE:
        return "중유럽"
    if country in WESTERN_EUROPE:
        return "서유럽"
    if country in SOUTHERN_EUROPE:
        return "남유럽"
    if country in CIS:
        return "CIS"
    if country in EASTERN_EUROPE:
        return "동유럽"
    if country in MIDDLE_EAST:
        return "중동"
    if country in SOUTH_ASIA:
        return "남아시아"
    if country in OCEANIA:
        return "오세아니아"
    if country in AFRICA:
        return "아프리카"
    return "기타"


def region_label(region: str) -> str:
    return REGION_LABEL_KO.get(region, region)


def country_label(country: Any) -> str:
    value = str(country or "").strip()
    return COUNTRY_LABEL_KO.get(value, value or "미상")


def country_display_counts(rows: list[dict[str, Any]], limit: int = 8) -> str:
    counts = Counter(country_label(row.get("_country")) for row in rows)
    return ", ".join(f"{country} {count:,}건" for country, count in counts.most_common(limit))


def ko_segment(value: Any) -> str:
    return SEGMENT_KO.get(str(value or ""), str(value or "미분류"))


def ko_dof_fit(value: Any) -> str:
    return DOF_FIT_KO.get(str(value or ""), str(value or "미분류"))


def ko_source_type(value: Any) -> str:
    return SOURCE_TYPE_KO.get(str(value or ""), str(value or "미분류"))


def ko_selection_reason(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return SELECTION_REASON_KO.get(text, text)


def ko_evidence(value: Any) -> str:
    text = compact(value, 220)
    if not text:
        return ""
    text = re.sub(r"OSM tags: ([^;]+)", r"OSM 업종 태그: \1", text)
    text = text.replace("Required contact fields found:", "필수 연락처 확인:")
    text = text.replace("email=", "이메일=")
    text = text.replace("phone=", "전화=")
    text = text.replace("address=", "주소=")
    return text


def tag_value(row: dict[str, Any], key: str) -> str:
    tags = row.get("tags") or {}
    if not isinstance(tags, dict):
        return ""
    return compact(tags.get(key), 520)


def acquisition_path(row: dict[str, Any]) -> str:
    explicit = tag_value(row, "acquisition_path")
    if explicit:
        return explicit
    source = str(row.get("source_type") or "")
    if source == "DOF portal Company" or row.get("portal_company_id"):
        return "DOF 포탈 등록 고객사 데이터를 기준으로 해외 고객 여부와 연락처를 확인"
    if "website contact extraction" in source:
        return "OSM 공개 사업장 태그로 후보를 찾고 공식 웹사이트 연락처 페이지에서 이메일·전화·주소를 보강"
    if "OpenStreetMap" in source:
        return "공개 OSM 사업장 태그에서 업종, 이메일, 전화, 주소를 확인"
    if "PDF" in source:
        return "공개 PDF 디렉터리에서 업체명, 연락처, 주소를 추출"
    if "directory" in source.lower() or "locator" in source.lower():
        return "공개 사업자 디렉터리 또는 공식 distributor locator에서 연락처를 확인"
    return "공개 웹 출처에서 업체명, 이메일, 전화, 주소, 업종 근거를 확인"


def site_business_summary(row: dict[str, Any]) -> str:
    explicit = tag_value(row, "site_business_summary")
    if explicit:
        return explicit
    segment = str(row.get("segment") or "")
    source = str(row.get("source_type") or "")
    evidence = " ".join(str(item) for item in (row.get("evidence") or []) if item)
    tags = row.get("tags") or {}
    tag_blob = " ".join(str(value) for value in tags.values()) if isinstance(tags, dict) else ""
    blob = f"{segment} {source} {evidence} {tag_blob}".lower()
    if "distribut" in blob or "supply" in blob or "depot" in blob or "trading" in blob or "import" in blob or "export" in blob:
        return "치과 장비·재료 공급, 유통, 수입·수출 또는 현지 리셀/서비스 채널 후보로 판단"
    if "lab" in segment.lower() or "technician" in segment.lower() or "zahntechnik" in blob or "laborator" in blob:
        return "치과기공·보철 제작·CAD/CAM 또는 랩 스캐너 워크플로우 수요가 있는 후보로 판단"
    if "orthodont" in blob:
        return "교정 진료와 디지털 인상/모델 워크플로우 수요가 있는 치과 후보로 판단"
    if "implant" in blob or "surgery" in blob:
        return "임플란트·수술 진료와 정밀 스캔/기공소 협업 수요가 있는 치과 후보로 판단"
    if source == "DOF portal Company" or row.get("portal_company_id"):
        return "DOF 포탈에 등록된 기존 해외 고객사로 계정 확대, 장비 교체, 서비스 갱신 또는 채널 후속 영업 대상"
    return "치과 병·의원 또는 치과 관련 사업자로 구강스캐너와 디지털 치과 워크플로우 제안 대상"


def summarize_counter(rows: list[dict[str, Any]], key: str, limit: int = 6) -> str:
    counter = Counter(str(row.get(key) or "미분류") for row in rows)
    return ", ".join(f"{name} {count:,}건" for name, count in counter.most_common(limit))


def prospect_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
    source = str(row.get("source_type") or "")
    portal_rank = 0 if "portal" in source.lower() else 1
    return (portal_rank, str(row.get("segment") or ""), str(row.get("name") or "").lower())


def enrich_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        country = country_name(row.get("country"))
        region = region_for_country(country)
        enriched.append(
            {
                **row,
                "_index": index,
                "_country": country,
                "_country_label": country_label(country),
                "_region": region,
                "_segment_ko": ko_segment(row.get("segment")),
                "_dof_fit_ko": ko_dof_fit(row.get("dof_fit")),
                "_source_type_ko": ko_source_type(row.get("source_type")),
                "_selection_reason_ko": ko_selection_reason(row.get("selection_reason")),
                "_acquisition_path_ko": acquisition_path(row),
                "_site_business_summary_ko": site_business_summary(row),
            }
        )
    return enriched


class OutlineClient:
    def __init__(self, key: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {key}"})

    def api(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(1, 6):
            response = self.session.post(f"{OUTLINE_BASE}/api/{endpoint}", json=body, timeout=REQUEST_TIMEOUT)
            if response.status_code < 400:
                return response.json()
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 5:
                time.sleep(min(30, attempt * 2))
                continue
            raise RuntimeError(f"{endpoint} failed {response.status_code}: {response.text[:1000]}")
        raise RuntimeError(f"{endpoint} failed after retries")

    def document_info(self, doc_id: str) -> dict[str, Any]:
        return self.api("documents.info", {"id": doc_id})["data"]

    def documents_list(self, **params: Any) -> list[dict[str, Any]]:
        offset = 0
        docs: list[dict[str, Any]] = []
        while True:
            data = self.api("documents.list", {"limit": 100, "offset": offset, **params})
            batch = data.get("data") or []
            docs.extend(batch)
            pagination = data.get("pagination") or {}
            total = int(pagination.get("total") or len(docs))
            offset += len(batch)
            if not batch or offset >= total:
                return docs

    def create_document(self, title: str, parent_document_id: str, text: str) -> dict[str, Any]:
        return self.api(
            "documents.create",
            {"title": title, "parentDocumentId": parent_document_id, "text": text, "publish": True, "fullWidth": True},
        )["data"]

    def update_document(self, doc_id: str, title: str, text: str) -> dict[str, Any]:
        return self.api("documents.update", {"id": doc_id, "title": title, "text": text, "publish": True, "fullWidth": True})[
            "data"
        ]

    def rename_document(self, doc_id: str, title: str) -> dict[str, Any]:
        return self.api("documents.update", {"id": doc_id, "title": title})["data"]

    def move_document(self, doc_id: str, parent_document_id: str) -> dict[str, Any]:
        data = self.api("documents.move", {"id": doc_id, "parentDocumentId": parent_document_id})["data"]
        documents = data.get("documents") or []
        if not documents:
            raise RuntimeError(f"documents.move returned no document for {doc_id}")
        return documents[0]

    def archive_document(self, doc_id: str) -> dict[str, Any]:
        return self.api("documents.archive", {"id": doc_id})["data"]


def doc_url(doc: dict[str, Any]) -> str:
    return f"{OUTLINE_BASE}/doc/{doc['urlId']}"


class OutlinePublisher:
    def __init__(self, client: OutlineClient, cache: dict[str, Any], dry_run: bool = False):
        self.client = client
        self.cache = cache
        self.dry_run = dry_run
        self.child_title_maps: dict[str, dict[str, dict[str, Any]]] = {}
        self.published: dict[str, OutlineDoc] = {}

    def existing_children_by_title(self, parent_document_id: str) -> dict[str, dict[str, Any]]:
        if parent_document_id not in self.child_title_maps:
            self.child_title_maps[parent_document_id] = {
                doc["title"]: doc for doc in self.client.documents_list(parentDocumentId=parent_document_id) if doc.get("title")
            }
        return self.child_title_maps[parent_document_id]

    def ensure_document(
        self,
        key: str,
        title: str,
        parent_document_id: str,
        text: str,
        update_cached: bool = True,
    ) -> OutlineDoc:
        cached = (self.cache.get("docs") or {}).get(key)
        candidate_id = cached.get("id") if isinstance(cached, dict) else None

        if self.dry_run:
            doc = OutlineDoc(
                id=candidate_id or f"dry-run-{key}",
                url_id=(cached or {}).get("url_id", ""),
                title=title,
                url=(cached or {}).get("url", ""),
                parent_document_id=parent_document_id,
            )
            self.published[key] = doc
            return doc

        if candidate_id:
            if not update_cached:
                doc = OutlineDoc(
                    id=cached["id"],
                    url_id=cached.get("url_id", ""),
                    title=cached.get("title", title),
                    url=cached.get("url", ""),
                    parent_document_id=cached.get("parent_document_id", parent_document_id),
                )
                self.published[key] = doc
                return doc
            try:
                updated = self.client.update_document(candidate_id, title, text)
                doc = OutlineDoc(updated["id"], updated["urlId"], updated["title"], doc_url(updated), parent_document_id)
                self._remember(key, doc)
                return doc
            except RuntimeError:
                pass

        existing = self.existing_children_by_title(parent_document_id).get(title)
        if existing:
            updated = self.client.update_document(existing["id"], title, text)
        else:
            updated = self.client.create_document(title, parent_document_id, text)
            self.child_title_maps.setdefault(parent_document_id, {})[title] = updated
            time.sleep(PAUSE_SECONDS)

        doc = OutlineDoc(updated["id"], updated["urlId"], updated["title"], doc_url(updated), parent_document_id)
        self._remember(key, doc)
        return doc

    def update_root(self, key: str, doc_id: str, title: str, text: str) -> OutlineDoc:
        if self.dry_run:
            doc = OutlineDoc(id=doc_id, url_id="", title=title, url="")
            self.published[key] = doc
            return doc
        updated = self.client.update_document(doc_id, title, text)
        doc = OutlineDoc(updated["id"], updated["urlId"], updated["title"], doc_url(updated), updated.get("parentDocumentId"))
        self._remember(key, doc)
        return doc

    def _remember(self, key: str, doc: OutlineDoc) -> None:
        self.cache.setdefault("docs", {})[key] = {
            "id": doc.id,
            "url_id": doc.url_id,
            "title": doc.title,
            "url": doc.url,
            "parent_document_id": doc.parent_document_id,
        }
        self.published[key] = doc
        save_json(DOC_CACHE, self.cache)

    def remove_cached_doc(self, key: str) -> None:
        if key in self.cache.get("docs", {}):
            del self.cache["docs"][key]
            save_json(DOC_CACHE, self.cache)

    def resolve_company_key(self, key: str) -> str:
        docs = self.cache.setdefault("docs", {})
        if key in docs or not key.startswith("company:"):
            return key
        stable_id = key.removeprefix("company:")
        suffix = f":{stable_id}"
        matches = sorted(k for k in docs if k.startswith("company:") and k.endswith(suffix))
        if not matches:
            return key
        docs[key] = docs.pop(matches[0])
        save_json(DOC_CACHE, self.cache)
        return key

    def ensure_company_document(self, key: str, title: str, parent_document_id: str, text: str) -> OutlineDoc:
        key = self.resolve_company_key(key)
        cached = (self.cache.get("docs") or {}).get(key)
        if self.dry_run:
            doc = OutlineDoc(
                id=(cached or {}).get("id", f"dry-run-{key}"),
                url_id=(cached or {}).get("url_id", ""),
                title=title,
                url=(cached or {}).get("url", ""),
                parent_document_id=parent_document_id,
            )
            self.published[key] = doc
            return doc

        if isinstance(cached, dict) and cached.get("id"):
            doc = OutlineDoc(
                id=cached["id"],
                url_id=cached.get("url_id", ""),
                title=cached.get("title", title),
                url=cached.get("url", ""),
                parent_document_id=cached.get("parent_document_id"),
            )
            if doc.parent_document_id != parent_document_id:
                moved = self.client.move_document(doc.id, parent_document_id)
                doc = OutlineDoc(moved["id"], moved["urlId"], moved["title"], doc_url(moved), parent_document_id)
                self._remember(key, doc)
            if doc.title != title:
                renamed = self.client.rename_document(doc.id, title)
                doc = OutlineDoc(renamed["id"], renamed["urlId"], renamed["title"], doc_url(renamed), parent_document_id)
                self._remember(key, doc)
            self.published[key] = doc
            return doc

        return self.ensure_document(key, title, parent_document_id, text)


def segment_bucket(row: dict[str, Any]) -> str:
    segment = str(row.get("segment") or "")
    text = " ".join(
        [
            str(row.get("name") or ""),
            segment,
            str(row.get("dof_fit") or ""),
            " ".join(str(value) for value in (row.get("tags") or {}).values()),
        ]
    ).lower()
    if "dealer" in segment.lower() or "channel" in segment.lower():
        return "유통사"
    if re.search(r"\b(distribut|dealer|trading|supply|supplies|depot|equipment|import|export|retail|wholesale)\b", text):
        return "유통사"
    if "orthodont" in text or "교정" in text:
        return "교정치과"
    if "lab" in segment.lower() or "milling" in segment.lower():
        return "치기공"
    if re.search(
        r"(dental\s*(lab|laborator|design|studio|milling|cad|cam|technician)|dentallabor|zahntechnik|laboratoire|laboratorio|odontotecn|prothes|技工|技工所|lab[oó]?\s*nha|laboratorium\s*gigi)",
        text,
    ):
        return "치기공"
    return "치과"


def customer_status(row: dict[str, Any]) -> str:
    if row.get("source_type") == "DOF portal Company" or row.get("portal_company_id"):
        return "기존고객"
    return f"잠재고객-{segment_bucket(row)}"


def build_hierarchy(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, list[dict[str, Any]]]]]:
    tree: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in rows:
        tree[row["_region"]][customer_status(row)][row["_country"]].append(row)
    for statuses in tree.values():
        for countries in statuses.values():
            for country, country_rows in list(countries.items()):
                countries[country] = sorted(country_rows, key=prospect_sort_key)
    return tree


def region_sort_key(item: tuple[str, dict[str, dict[str, list[dict[str, Any]]]]]) -> tuple[int, str]:
    region = item[0]
    try:
        return (REGION_ORDER.index(region), region)
    except ValueError:
        return (len(REGION_ORDER), region)


def country_sort_key(item: tuple[str, int] | tuple[str, list[dict[str, Any]]]) -> tuple[int, str]:
    value = item[1]
    count = value if isinstance(value, int) else len(value)
    return (-count, item[0])


def status_sort_key(item: tuple[str, Any]) -> tuple[int, str]:
    order = {
        "기존고객": 0,
        "잠재고객-치과": 10,
        "잠재고객-교정치과": 11,
        "잠재고객-치기공": 12,
        "잠재고객-유통사": 13,
    }
    return (order.get(item[0], 9), item[0])


def status_key(region: str, status: str) -> str:
    return f"status:{region}:{status}"


def country_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(row["_country"] for row in rows)


def country_count_summary(rows: list[dict[str, Any]], limit: int = 8) -> str:
    return country_display_counts(rows, limit)


def flatten_status(countries: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for country_rows in countries.values() for row in country_rows]


def flatten_region(statuses: dict[str, dict[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    return [row for countries in statuses.values() for row in flatten_status(countries)]


def status_count_summary(rows: list[dict[str, Any]]) -> str:
    counts = Counter(customer_status(row) for row in rows)
    return ", ".join(f"{status} {count:,}건" for status, count in sorted(counts.items(), key=lambda item: status_sort_key((item[0], [None] * item[1]))))


def country_key(region: str, status: str, country: str) -> str:
    return f"country:{region}:{status}:{country}"


def legacy_country_key(region: str, country: str) -> str:
    return f"country:{region}:{country}"


def country_title(country: str, count: int) -> str:
    return country_label(country)


def legacy_country_sort_key(item: tuple[str, list[dict[str, Any]]]) -> tuple[int, str]:
    return (-len(item[1]), item[0])


def stable_company_id(row: dict[str, Any]) -> str:
    if row.get("portal_company_id"):
        return f"portal:{row['portal_company_id']}"
    if row.get("osm_type") and row.get("osm_id"):
        return f"osm:{row['osm_type']}:{row['osm_id']}"
    if row.get("email"):
        return "email:" + re.sub(r"[^a-z0-9@._+-]+", "-", str(row["email"]).lower())
    return f"row:{row.get('_index')}"


def company_key(region: str, country: str, row: dict[str, Any]) -> str:
    return f"company:{stable_company_id(row)}"


def company_title(row: dict[str, Any], number: int) -> str:
    country = compact(row.get("_country_label") or country_label(row.get("_country")), 12) or "미상"
    prefix = f"{number:04d}. "
    suffix = f" ({country})"
    name_limit = max(20, 100 - len(prefix) - len(suffix))
    name = compact(row.get("name"), name_limit) or "이름 없음"
    return f"{prefix}{name}{suffix}"


def prospect_block(row: dict[str, Any], number: int) -> list[str]:
    name = compact(row.get("name"), 120) or "이름 없음"
    source_url = str(row.get("source_url") or "")
    website = str(row.get("website") or "")
    evidence = row.get("evidence") or []
    if isinstance(evidence, list):
        evidence_text = "; ".join(ko_evidence(item) for item in evidence[:3])
    else:
        evidence_text = ko_evidence(evidence)
    lines = [f"### {number:03d}. {md_escape(name)}", ""]
    lines += [
        f"- 고객군: {md_escape(row.get('_segment_ko'))}",
        f"- DOF 적합성: {md_escape(row.get('_dof_fit_ko'))}",
        f"- 선정 이유: {md_escape(compact(row.get('_selection_reason_ko'), 420))}",
        f"- 연락처: {md_escape(row.get('email'))} / {md_escape(row.get('phone'))}",
        f"- 주소: {md_escape(row.get('address'))}",
        f"- 웹사이트: {md_link(website, website) if website else ''}",
        f"- 출처: {md_link(row.get('_source_type_ko') or source_url or 'source', source_url)}",
        f"- 데이터 취득 경로: {md_escape(compact(row.get('_acquisition_path_ko'), 220))}",
        f"- 취급품목/사이트 요약: {md_escape(compact(row.get('_site_business_summary_ko'), 220))}",
    ]
    if evidence_text:
        lines.append(f"- 근거: {md_escape(evidence_text)}")
    if row.get("portal_orders_count") is not None:
        lines.append(f"- 포탈 주문 수: {md_escape(row.get('portal_orders_count'))}")
    lines.append("")
    return lines


def build_company_markdown(region: str, country: str, row: dict[str, Any], number: int) -> str:
    name = compact(row.get("name"), 140) or "이름 없음"
    lines = [
        f"# {md_escape(name)}",
        "",
        "## 영업처 카드",
        "",
        f"- 지역: {region_label(region)}",
        f"- 국가: {country_label(country)}",
        f"- 고객군: {md_escape(row.get('_segment_ko'))}",
        f"- DOF 적합성: {md_escape(row.get('_dof_fit_ko'))}",
        f"- 선정 이유: {md_escape(compact(row.get('_selection_reason_ko'), 520))}",
        "",
        "## 연락처",
        "",
        f"- 이메일: {md_escape(row.get('email'))}",
        f"- 전화: {md_escape(row.get('phone'))}",
        f"- 주소: {md_escape(row.get('address'))}",
    ]
    website = str(row.get("website") or "")
    source_url = str(row.get("source_url") or "")
    if website:
        lines.append(f"- 웹사이트: {md_link(website, website)}")
    if source_url:
        lines.append(f"- 출처: {md_link(row.get('_source_type_ko') or '출처 열기', source_url)}")
    lines += [
        "",
        "## 데이터 취득 및 취급품목",
        "",
        f"- 데이터 취득 경로: {md_escape(row.get('_acquisition_path_ko'))}",
        f"- 취급품목/사이트 요약: {md_escape(row.get('_site_business_summary_ko'))}",
    ]
    product_keywords = tag_value(row, "product_keywords")
    if product_keywords:
        lines.append(f"- 제품/영업 키워드: {md_escape(product_keywords)}")
    lines += ["", "## 판단 근거", ""]
    evidence = row.get("evidence") or []
    if isinstance(evidence, list):
        for item in evidence[:5]:
            lines.append(f"- {md_escape(ko_evidence(item))}")
    elif evidence:
        lines.append(f"- {md_escape(ko_evidence(evidence))}")
    else:
        lines.append("- 별도 근거 텍스트 없음.")
    if row.get("portal_orders_count") is not None:
        lines += ["", "## 포탈 정보", "", f"- 포탈 주문 수: {md_escape(row.get('portal_orders_count'))}"]
    lines += ["", "## 영업 메모", "", ""]
    return "\n".join(lines).strip() + "\n"


def build_status_markdown(
    region: str,
    status: str,
    countries: dict[str, list[dict[str, Any]]],
    country_docs: dict[str, OutlineDoc],
) -> str:
    rows = flatten_status(countries)
    lines = [
        f"# {region_label(region)} / {status}",
        "",
        "## 그룹 요약",
        "",
        f"- 지역: {region_label(region)}",
        f"- 구분: {status}",
        f"- 업체 수: {len(rows):,}건",
        f"- 국가 수: {len(country_counts(rows)):,}개",
        f"- 주요 국가: {country_count_summary(rows, 10)}",
        f"- 고객군: {summarize_counter(rows, '_segment_ko', 8)}",
        f"- DOF 적합성: {summarize_counter(rows, '_dof_fit_ko', 5)}",
        f"- 출처: {summarize_counter(rows, '_source_type_ko', 5)}",
        "",
        "## 국가별 문서",
        "",
        "| 국가 | 업체 수 | 주요 고객군 | 문서 |",
        "| --- | ---: | --- | --- |",
    ]
    for country, country_rows in sorted(countries.items(), key=country_sort_key):
        doc = country_docs.get(country)
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(country_label(country)),
                    f"{len(country_rows):,}",
                    md_escape(summarize_counter(country_rows, "_segment_ko", 3)),
                    md_link("열기", doc.url) if doc else "",
                ]
            )
            + " |"
        )
    lines += [
        "",
        "## 대표 업체",
        "",
        "| 업체 | 국가 | 고객군 | 이메일 | 전화 | 선정 이유 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows[:20]:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(row.get("name")),
                    md_escape(row.get("_country_label")),
                    md_escape(row.get("_segment_ko")),
                    md_escape(row.get("email")),
                    md_escape(row.get("phone")),
                    md_escape(compact(row.get("_selection_reason_ko"), 180)),
                ]
            )
            + " |"
        )
    return "\n".join(lines).strip() + "\n"


def build_country_markdown(
    region: str,
    status: str,
    country: str,
    rows: list[dict[str, Any]],
    company_docs: list[tuple[dict[str, Any], OutlineDoc]],
) -> str:
    lines = [
        f"# {country_label(country)} / {status}",
        "",
        "## 국가 요약",
        "",
        f"- 지역: {region_label(region)}",
        f"- 구분: {status}",
        f"- 국가: {country_label(country)}",
        f"- 업체 수: {len(rows):,}건",
        f"- 고객군: {summarize_counter(rows, '_segment_ko', 8)}",
        f"- DOF 적합성: {summarize_counter(rows, '_dof_fit_ko', 5)}",
        f"- 출처: {summarize_counter(rows, '_source_type_ko', 5)}",
        "",
        "## 대표 업체",
        "",
        "| 업체 | 고객군 | 이메일 | 전화 | 선정 이유 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows[:20]:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(row.get("name")),
                    md_escape(row.get("_segment_ko")),
                    md_escape(row.get("email")),
                    md_escape(row.get("phone")),
                    md_escape(compact(row.get("_selection_reason_ko"), 180)),
                ]
            )
            + " |"
        )
    display_docs = company_docs if len(company_docs) <= 50 else company_docs[:50]
    if len(company_docs) > len(display_docs):
        lines += [
            "",
            "## 업체별 문서",
            "",
            f"- 전체 {len(company_docs):,}개 업체 문서는 이 `{country_label(country)}` 문서의 하위 문서로 업체 단위 생성되어 있다.",
            "- 본문에는 Outline 문서 크기 제한을 피하기 위해 대표 50개만 표시한다.",
            "",
        ]
    else:
        lines += ["", "## 업체별 문서", ""]
    lines += [
        "| 순번 | 업체 | 국가 | 고객군 | 이메일 | 전화 | 문서 |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for idx, (row, doc) in enumerate(display_docs, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{idx:,}",
                    md_escape(row.get("name")),
                    md_escape(row.get("_country_label")),
                    md_escape(row.get("_segment_ko")),
                    md_escape(row.get("email")),
                    md_escape(row.get("phone")),
                    md_link("열기", doc.url),
                ]
            )
            + " |"
        )
    return "\n".join(lines).strip() + "\n"


def build_region_markdown(
    region: str,
    statuses: dict[str, dict[str, list[dict[str, Any]]]],
    status_docs: dict[str, OutlineDoc],
) -> str:
    rows = flatten_region(statuses)
    lines = [
        f"# {region_label(region)} 영업처 후보",
        "",
        "## 지역 요약",
        "",
        f"- 후보 수: {len(rows):,}건",
        f"- 기존/잠재 구분: {status_count_summary(rows)}",
        f"- 국가 수: {len(country_counts(rows)):,}개",
        f"- 주요 국가: {country_count_summary(rows, 8)}",
        f"- 고객군: {summarize_counter(rows, '_segment_ko', 8)}",
        f"- 출처: {summarize_counter(rows, '_source_type_ko', 5)}",
        "",
        "## 구분별 문서",
        "",
        "| 구분 | 업체 수 | 국가 수 | 주요 국가 | 문서 |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for status, countries in sorted(statuses.items(), key=status_sort_key):
        status_rows = flatten_status(countries)
        doc = status_docs.get(status)
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(status),
                    f"{len(status_rows):,}",
                    f"{len(country_counts(status_rows)):,}",
                    md_escape(country_count_summary(status_rows, 5)),
                    md_link("열기", doc.url) if doc else "",
                ]
            )
            + " |"
        )
    return "\n".join(lines).strip() + "\n"


def build_root_markdown(
    rows: list[dict[str, Any]],
    tree: dict[str, dict[str, dict[str, list[dict[str, Any]]]]],
    region_docs: dict[str, OutlineDoc],
    generated_at: str,
) -> str:
    source_counts = Counter(row.get("_source_type_ko") or "미분류" for row in rows)
    segment_counts = Counter(row.get("_segment_ko") or "미분류" for row in rows)
    region_counts = {region: len(flatten_region(statuses)) for region, statuses in tree.items()}
    lines = [
        "# 영업처후보",
        "",
        "## 전체 요약",
        "",
        f"- 생성 기준: {generated_at}",
        f"- 연락처/이메일/주소/선정이유가 모두 있는 영업처 후보: {len(rows):,}건",
        f"- 국가 수: {len({row['_country'] for row in rows}):,}개",
        f"- 지역 수: {len(tree):,}개",
        f"- 기존/잠재 구분: {status_count_summary(rows)}",
        f"- 주요 고객군: {', '.join(f'{name} {count:,}건' for name, count in segment_counts.most_common(6))}",
        f"- 출처 구성: {', '.join(f'{name} {count:,}건' for name, count in source_counts.most_common(5))}",
        "",
        "## 지역 트리",
        "",
        "| Region | 후보 수 | 국가 수 | 주요 국가 | 문서 |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for region, statuses in sorted(tree.items(), key=region_sort_key):
        doc = region_docs.get(region)
        rows_in_region = flatten_region(statuses)
        top_countries = country_count_summary(rows_in_region, 6)
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(region_label(region)),
                    f"{region_counts[region]:,}",
                    f"{len(country_counts(rows_in_region)):,}",
                    md_escape(top_countries),
                    md_link("열기", doc.url) if doc else "",
                ]
            )
            + " |"
        )
    lines += [
        "",
        "## 단계 구조",
        "",
        "- 1단계: 이 루트 문서는 전체 규모, 지역 분포, 주요 고객군을 보여준다.",
        "- 2단계: Region 문서는 기존고객/잠재고객 구분과 국가 분포를 보여준다.",
        "- 3단계: 기존고객/잠재고객 문서는 국가별 문서를 하위에 둔다.",
        "- 4단계: 국가 문서는 해당 국가의 업체 문서들을 하위에 둔다.",
        "- 5단계: 업체 문서는 개별 업체의 연락처, 주소, 웹사이트, 출처, 선정 이유, 데이터 취득 경로, 취급품목 요약, 영업 메모 공간을 담는다.",
    ]
    return "\n".join(lines).strip() + "\n"


def build_dataset(rows: list[dict[str, Any]], tree: dict[str, dict[str, dict[str, list[dict[str, Any]]]]], generated_at: str) -> dict[str, Any]:
    region_counts = {region: len(flatten_region(statuses)) for region, statuses in tree.items()}
    country_counts = Counter(row["_country"] for row in rows)
    return {
        "generated_at": generated_at,
        "source": str(COMPLETE_JSONL),
        "counts": {
            "prospects": len(rows),
            "regions": len(tree),
            "countries": len(country_counts),
        },
        "region_counts": dict(sorted(region_counts.items(), key=lambda item: (-item[1], item[0]))),
        "country_counts": dict(country_counts.most_common()),
        "customer_status_counts": dict(Counter(customer_status(row) for row in rows).most_common()),
        "segment_counts": dict(Counter(row.get("_segment_ko") or "미분류" for row in rows).most_common()),
        "source_type_counts": dict(Counter(row.get("_source_type_ko") or "미분류" for row in rows).most_common()),
    }


def archive_legacy_batch_docs(publisher: OutlinePublisher) -> dict[str, Any]:
    archived: list[str] = []
    failed: list[dict[str, str]] = []
    for key, cached in list((publisher.cache.get("docs") or {}).items()):
        if not key.startswith("batch:"):
            continue
        doc_id = cached.get("id") if isinstance(cached, dict) else None
        if not doc_id:
            publisher.remove_cached_doc(key)
            continue
        if publisher.dry_run:
            archived.append(key)
            continue
        try:
            publisher.client.archive_document(doc_id)
            publisher.remove_cached_doc(key)
            archived.append(key)
            time.sleep(PAUSE_SECONDS)
        except RuntimeError as exc:
            failed.append({"key": key, "error": str(exc)[:400]})
    return {"archived": archived, "failed": failed}


def archive_legacy_country_docs(publisher: OutlinePublisher) -> dict[str, Any]:
    archived: list[str] = []
    failed: list[dict[str, str]] = []
    for key, cached in list((publisher.cache.get("docs") or {}).items()):
        if not key.startswith("country:"):
            continue
        doc_id = cached.get("id") if isinstance(cached, dict) else None
        if not doc_id:
            publisher.remove_cached_doc(key)
            continue
        if publisher.dry_run:
            archived.append(key)
            continue
        try:
            publisher.client.archive_document(doc_id)
            publisher.remove_cached_doc(key)
            archived.append(key)
            time.sleep(PAUSE_SECONDS)
        except RuntimeError as exc:
            failed.append({"key": key, "error": str(exc)[:400]})
    return {"archived": archived, "failed": failed}


def archive_inactive_docs(publisher: OutlinePublisher, prefix: str, active_keys: set[str]) -> dict[str, Any]:
    archived: list[str] = []
    failed: list[dict[str, str]] = []
    for key, cached in list((publisher.cache.get("docs") or {}).items()):
        if not key.startswith(prefix) or key in active_keys:
            continue
        doc_id = cached.get("id") if isinstance(cached, dict) else None
        if not doc_id:
            publisher.remove_cached_doc(key)
            continue
        if publisher.dry_run:
            archived.append(key)
            continue
        try:
            publisher.client.archive_document(doc_id)
            publisher.remove_cached_doc(key)
            archived.append(key)
            time.sleep(PAUSE_SECONDS)
        except RuntimeError as exc:
            failed.append({"key": key, "error": str(exc)[:400]})
    return {"archived": archived, "failed": failed}


def publish(dry_run: bool = False, limit: int | None = None) -> dict[str, Any]:
    generated_at = datetime.now().isoformat(timespec="seconds")
    rows = enrich_rows(read_jsonl(COMPLETE_JSONL))
    if limit:
        rows = rows[:limit]
    tree = build_hierarchy(rows)
    dataset = build_dataset(rows, tree, generated_at)
    save_json(PUBLISH_DATASET, dataset)

    client = OutlineClient(read_env_key("DOF_OUTLINE_KEY"))
    parent = client.document_info(TARGET_URL_ID)
    cache = load_json(DOC_CACHE, {"docs": {}})
    publisher = OutlinePublisher(client, cache, dry_run=dry_run)
    legacy_batch_cleanup = archive_legacy_batch_docs(publisher)

    region_docs: dict[str, OutlineDoc] = {}
    status_docs_by_region: dict[str, dict[str, OutlineDoc]] = defaultdict(dict)
    country_docs_by_region_status: dict[str, dict[str, dict[str, OutlineDoc]]] = defaultdict(lambda: defaultdict(dict))
    company_doc_count = 0
    moved_company_doc_count = 0
    active_region_keys: set[str] = set()
    active_status_keys: set[str] = set()
    active_country_keys: set[str] = set()

    # Create folder-like placeholders first so the later summaries can link downward.
    for region, statuses in sorted(tree.items(), key=region_sort_key):
        region_doc_key = f"region:{region}"
        active_region_keys.add(region_doc_key)
        region_title = region_label(region)
        region_doc = publisher.ensure_document(region_doc_key, region_title, parent["id"], f"# {region_label(region)}\n\n작성 중입니다.\n")
        region_docs[region] = region_doc

        for status, countries in sorted(statuses.items(), key=status_sort_key):
            status_doc_key = status_key(region, status)
            active_status_keys.add(status_doc_key)
            status_title = status
            status_doc = publisher.ensure_document(status_doc_key, status_title, region_doc.id, f"# {status}\n\n작성 중입니다.\n")
            status_docs_by_region[region][status] = status_doc

            for country, country_rows in sorted(countries.items(), key=country_sort_key):
                country_doc_key = country_key(region, status, country)
                active_country_keys.add(country_doc_key)
                country_doc = publisher.ensure_document(
                    country_doc_key,
                    country_title(country, len(country_rows)),
                    status_doc.id,
                    f"# {country_label(country)}\n\n작성 중입니다.\n",
                )
                country_docs_by_region_status[region][status][country] = country_doc
                company_docs: list[tuple[dict[str, Any], OutlineDoc]] = []
                for order, row in enumerate(country_rows, start=1):
                    title = company_title(row, order)
                    key = company_key(region, row["_country"], row)
                    body = build_company_markdown(region, row["_country"], row, order)
                    key = publisher.resolve_company_key(key)
                    cached_company = key in (publisher.cache.get("docs") or {})
                    previous_parent = (publisher.cache.get("docs") or {}).get(key, {}).get("parent_document_id")
                    company_doc = publisher.ensure_company_document(key, title, country_doc.id, body)
                    company_docs.append((row, company_doc))
                    company_doc_count += 1
                    if cached_company and previous_parent != country_doc.id:
                        moved_company_doc_count += 1
                    if company_doc_count % 50 == 0 or company_doc_count == len(rows):
                        print(
                            json.dumps(
                                {
                                    "processed_company_docs": company_doc_count,
                                    "moved_company_docs": moved_company_doc_count,
                                    "latest": title,
                                    "url": company_doc.url,
                                },
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                    if not cached_company:
                        time.sleep(PAUSE_SECONDS)
                country_body = build_country_markdown(region, status, country, country_rows, company_docs)
                country_doc = publisher.ensure_document(country_doc_key, country_title(country, len(country_rows)), status_doc.id, country_body)
                country_docs_by_region_status[region][status][country] = country_doc
                print(json.dumps({"published": f"{region_label(region)}/{status}/{country_label(country)}", "url": country_doc.url}, ensure_ascii=False), flush=True)
                time.sleep(PAUSE_SECONDS)

            status_body = build_status_markdown(region, status, countries, country_docs_by_region_status[region][status])
            status_doc = publisher.ensure_document(status_key(region, status), status_title, region_doc.id, status_body)
            status_docs_by_region[region][status] = status_doc
            print(json.dumps({"published": f"{region_label(region)}/{status}", "url": status_doc.url}, ensure_ascii=False), flush=True)
            time.sleep(PAUSE_SECONDS)

        region_body = build_region_markdown(region, statuses, status_docs_by_region[region])
        region_doc = publisher.ensure_document(f"region:{region}", region_title, parent["id"], region_body)
        region_docs[region] = region_doc
        print(json.dumps({"published": region_title, "url": region_doc.url}, ensure_ascii=False), flush=True)
        time.sleep(PAUSE_SECONDS)

    legacy_country_cleanup = archive_inactive_docs(publisher, "country:", active_country_keys)
    legacy_status_cleanup = archive_inactive_docs(publisher, "status:", active_status_keys)
    legacy_region_cleanup = archive_inactive_docs(publisher, "region:", active_region_keys)
    root_body = build_root_markdown(rows, tree, region_docs, generated_at)
    root_doc = publisher.update_root("root", parent["id"], "영업처후보", root_body)
    result = {
        "dry_run": dry_run,
        "parent": root_doc.__dict__,
        "counts": {
            "prospects": len(rows),
            "regions": len(region_docs),
            "countries": len({row["_country"] for row in rows}),
            "status_docs": sum(len(statuses) for statuses in tree.values()),
            "country_docs": sum(len(countries) for statuses in tree.values() for countries in statuses.values()),
            "company_docs": company_doc_count,
            "moved_company_docs": moved_company_doc_count,
            "legacy_batch_docs_archived": len(legacy_batch_cleanup["archived"]),
            "legacy_batch_docs_archive_failed": len(legacy_batch_cleanup["failed"]),
            "legacy_country_docs_archived": len(legacy_country_cleanup["archived"]),
            "legacy_country_docs_archive_failed": len(legacy_country_cleanup["failed"]),
            "legacy_status_docs_archived": len(legacy_status_cleanup["archived"]),
            "legacy_status_docs_archive_failed": len(legacy_status_cleanup["failed"]),
            "legacy_region_docs_archived": len(legacy_region_cleanup["archived"]),
            "legacy_region_docs_archive_failed": len(legacy_region_cleanup["failed"]),
            "total_docs_including_root": len(publisher.published),
        },
        "legacy_batch_cleanup": legacy_batch_cleanup,
        "legacy_country_cleanup": legacy_country_cleanup,
        "legacy_status_cleanup": legacy_status_cleanup,
        "legacy_region_cleanup": legacy_region_cleanup,
        "regions": {region: doc.__dict__ for region, doc in region_docs.items()},
        "dataset": str(PUBLISH_DATASET),
        "cache": str(DOC_CACHE),
    }
    save_json(PUBLISH_RESULT, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = publish(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
