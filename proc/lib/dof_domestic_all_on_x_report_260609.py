#!/usr/bin/env python3
"""Build and publish the domestic all-on-x / edentulous implant report for 260609."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dof_domestic_report_260607 as base  # noqa: E402
import dof_prospect_outline_publish as outline_publish  # noqa: E402


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_DIR = ROOT / "output/domestic-all-on-x-edentulous-260609"
SEARCH_JSONL = OUT_DIR / "search_results.jsonl"
VISITS_JSON = OUT_DIR / "visited_pages.json"
CANDIDATES_JSON = OUT_DIR / "all_on_x_candidates.json"
REPORT_MD = OUT_DIR / "report_260609_domestic_all_on_x_edentulous.md"
RESULT_JSON = OUT_DIR / "report_260609_domestic_all_on_x_edentulous_result.json"

OUTLINE_BASE = "https://outline.doflab.com"
REPORT_PARENT_ID = "07b08eec-2ecb-42aa-b043-8e89f5ac6fb9"
REPORT_PARENT_URL = "https://outline.doflab.com/doc/66as7ys7yq4-cJZ5YdyvPw"
DOMESTIC_ROOT_URL = "https://outline.doflab.com/doc/ab-eGA5WmKiEM"
REFERENCE_REPORT_URL = "https://outline.doflab.com/doc/260607-uYfPMA4rC2"
REPORT_TITLE = "리포트260609-국내-무치악"

USER_AGENT = base.USER_AGENT
TIMEOUT = 12
MAX_BODY = 900_000
MAX_WORKERS = 12

SEARCH_QUERIES = [
    '"올온엑스" 치과 무치악',
    '"all-on-x" 치과 무치악',
    '"AOX" 치과 무치악 올온엑스',
    '"디지털 풀아치" 치과 무치악',
    '"디지털 풀아치 임플란트" 치과',
    '"전악 임플란트" "고난도" 치과',
    '"전체 임플란트" "고난도" 치과',
    '"무치악" "전악 임플란트" 치과',
    '"틀니" "올온엑스" 치과',
    '"하이브리드 임플란트" "무치악" 치과',
    '"All on 4" 치과 무치악',
    '"All-on-4" 치과 임플란트',
    '"당일 임시치아" "전악" 치과',
    '"뼈이식 없이" "올온엑스" 치과',
    '"임플란트 불가 판정" "올온엑스"',
    '"재수술 임플란트" "전악" 치과',
    '"상악동" "전악 임플란트" 치과',
    '"치아 재건축" "전악 임플란트" 치과',
]

MANUAL_SEEDS = [
    {
        "name": "더와이즈치과병원",
        "url": "https://www.thewisedental.com/homepage_media_view.html?cate=%EB%B3%B4%EB%8F%84&pid=66646",
        "evidence_url": "https://www.chosun.com/special/special_section/2026/01/27/O5LEI2RDCVH23OQILL2YDS6QVM/",
        "note": "임세웅 대표원장 고난도 임플란트/올온엑스 기사",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "성수동 우리치과",
        "url": "https://www.wdental.co.kr/community_01.html",
        "evidence_url": "https://sports.donga.com/life/article/all/20260208/133317384/1",
        "note": "강일남 원장 올온엑스 기사",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "바른탑치과의원",
        "url": "https://baruntop.co.kr/",
        "evidence_url": "https://www.jeonmin.co.kr/news/articleView.html?idxno=435589",
        "note": "천안 AOX 시스템 도입 기사",
        "region": "충청",
        "subregion": "천안",
    },
    {
        "name": "닥터뷰티치과병원",
        "url": "https://dbdh.co.kr/treatments/implant-allonx",
        "evidence_url": "https://dbdh.co.kr/treatments/implant-allonx",
        "note": "올온엑스 전용 공식 페이지",
        "region": "수도권",
        "subregion": "의정부",
    },
    {
        "name": "에투알드서울치과",
        "url": "https://www.e2rs.co.kr/all-on-x-implant",
        "evidence_url": "https://www.e2rs.co.kr/all-on-x-implant",
        "note": "ALL ON X 공식 페이지",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "하루플란트치과",
        "url": "https://haruplant.com/",
        "evidence_url": "https://news.nate.com/view/20260226n30772",
        "note": "올온엑스 전악 치료 기사",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "우리더블유치과의원",
        "url": "https://www.wooriw.co.kr/",
        "evidence_url": "https://www.jeonmin.co.kr/news/articleView.html?idxno=430685",
        "note": "평촌 범계 올온엑스 기사",
        "region": "수도권",
        "subregion": "평촌",
    },
    {
        "name": "서울K치과",
        "url": "https://www.kdent.co.kr/column/?bmode=view&idx=168441608",
        "evidence_url": "https://www.kdent.co.kr/column/?bmode=view&idx=168441608",
        "note": "올온엑스 실제 사례 컬럼",
        "region": "수도권",
        "subregion": "김포",
    },
    {
        "name": "더굿모닝치과 청량리점",
        "url": "https://thegoodmorningdental.com/blog/%EC%A0%84%EC%B2%B4%EC%9E%84%ED%94%8C%EB%9E%80%ED%8A%B8-vs-%EC%98%AC%EC%98%A8%EC%97%91%EC%8A%A4allonx-%EC%B0%A8%EC%9D%B4%EC%A0%90%EA%B3%BC-%EC%84%A0%ED%83%9D-%EA%B8%B0%EC%A4%80-172972",
        "evidence_url": "https://thegoodmorningdental.com/blog/%EC%A0%84%EC%B2%B4%EC%9E%84%ED%94%8C%EB%9E%80%ED%8A%B8-vs-%EC%98%AC%EC%98%A8%EC%97%91%EC%8A%A4allonx-%EC%B0%A8%EC%9D%B4%EC%A0%90%EA%B3%BC-%EC%84%A0%ED%83%9D-%EA%B8%B0%EC%A4%80-172972",
        "note": "전체임플란트 vs 올온엑스 공식 블로그",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "블랑쉬치과의원",
        "url": "https://www.blanche.kr/special/implant",
        "evidence_url": "https://www.blanche.kr/special/implant",
        "note": "디지털 풀아치 공식 페이지",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "서울니어치과",
        "url": "https://neardent.com/full_arch",
        "evidence_url": "https://neardent.com/full_arch",
        "note": "전체/전악 임플란트 공식 페이지",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "서울디아치과",
        "url": "https://seouldia.com/fullarch-implants",
        "evidence_url": "https://seouldia.com/fullarch-implants",
        "note": "전악 재건 임플란트 공식 페이지",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "디에르치과",
        "url": "https://dier.kr/",
        "evidence_url": "https://dier.kr/",
        "note": "디지털 전체 임플란트/풀아치 공식 사이트",
        "region": "충청",
        "subregion": "대전",
    },
    {
        "name": "탑플란트치과",
        "url": "https://topplant.kr/",
        "evidence_url": "https://topplant.kr/",
        "note": "디지털 풀아치/무치악 임플란트 공식 사이트",
        "region": "호남/제주",
        "subregion": "익산",
    },
    {
        "name": "뿌리사랑치과 운정점",
        "url": "https://bburiloveunjung.com/implants/complex-cases/",
        "evidence_url": "https://bburiloveunjung.com/implants/complex-cases/",
        "note": "고난도 임플란트/전악 임플란트 공식 페이지",
        "region": "수도권",
        "subregion": "파주",
    },
    {
        "name": "서울수치과의원",
        "url": "https://seoulsoodentalclinic.com/sub025",
        "evidence_url": "https://seoulsoodentalclinic.com/sub025",
        "note": "임플란트 틀니/전악 임플란트 공식 페이지",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "청담i치과",
        "url": "https://chungdami.com/",
        "evidence_url": "https://m.healthcaren.com/news/news_article_yong.jsp?mn_idx=469133",
        "note": "무치악 하이브리드 임플란트 기사",
        "region": "수도권",
        "subregion": "의정부",
    },
    {
        "name": "플란치과 수원점",
        "url": "https://plantdentalsuwon.com/",
        "evidence_url": "https://mdtoday.co.kr/news/view/1065605093376627",
        "note": "무치악 하이브리드 임플란트 기사",
        "region": "수도권",
        "subregion": "수원",
    },
    {
        "name": "부산 결치과",
        "url": "https://gyeoldental.com/",
        "evidence_url": "https://www.peterspickpick.com/756",
        "note": "부산 전악 임플란트 큐레이션 보조 근거",
        "region": "영남",
        "subregion": "부산",
    },
    {
        "name": "퍼펙트치과",
        "url": "https://bsdc.co.kr/implant8",
        "evidence_url": "https://bsdc.co.kr/implant8",
        "note": "전악 임플란트 공식 페이지",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "드림연합치과",
        "url": "https://xn--vb0bq78almeexi.kr/%EC%9A%B8%EC%82%B0-%EC%9E%84%ED%94%8C%EB%9E%80%ED%8A%B8-%EC%A0%95%EB%B3%B4/%EB%AC%B4%EC%B9%98%EC%95%85-%EC%9E%84%ED%94%8C%EB%9E%80%ED%8A%B8%EC%97%90-%EB%8C%80%ED%95%9C-%EB%AA%A8%EB%93%A0-%EA%B2%83/",
        "evidence_url": "https://xn--vb0bq78almeexi.kr/%EC%9A%B8%EC%82%B0-%EC%9E%84%ED%94%8C%EB%9E%80%ED%8A%B8-%EC%A0%95%EB%B3%B4/%EB%AC%B4%EC%B9%98%EC%95%85-%EC%9E%84%ED%94%8C%EB%9E%80%ED%8A%B8%EC%97%90-%EB%8C%80%ED%95%9C-%EB%AA%A8%EB%93%A0-%EA%B2%83/",
        "note": "무치악 임플란트 공식 컬럼",
        "region": "영남",
        "subregion": "울산",
    },
    {
        "name": "하버디안치과",
        "url": "https://harvardian.co.kr/",
        "evidence_url": "https://isplus.com/article/view/isp201809150061",
        "note": "올온포/무치악 기사",
        "region": "수도권",
        "subregion": "서울",
    },
    {
        "name": "해운대결치과",
        "url": "https://www.k2implant.com/html/implant/implant_03.html",
        "evidence_url": "https://www.k2implant.com/html/implant/implant_03.html",
        "note": "해운대 올온엑스/무치악 치료 공식 페이지",
        "region": "영남",
        "subregion": "부산",
    },
    {
        "name": "디지털스마일치과",
        "url": "https://www.digitalsmiledc.com/blog-advanced-implant/?q=YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9&bmode=view&idx=171361127&t=board",
        "evidence_url": "https://www.digitalsmiledc.com/blog-advanced-implant/?q=YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9&bmode=view&idx=171361127&t=board",
        "note": "전악 임플란트 재수술/상악동 골이식 고난도 증례 공식 페이지",
        "region": "충청",
        "subregion": "대전",
    },
]

SIGNAL_PATTERNS = [
    ("All-on-X/AOX/올온엑스", r"All[-\s]?on[-\s]?X|올\s*온\s*엑스|올온엑스|AOX"),
    ("All-on-4/6", r"All[-\s]?on[-\s]?[46]|올온[포식스]|All\s*on\s*4|All\s*on\s*6"),
    ("디지털 풀아치", r"디지털\s*풀\s*아치|풀\s*아치|Full[-\s]?Arch"),
    ("무치악/다수치 상실", r"무치악|치아(?:를)?\s*(?:대부분|모두|전체)\s*(?:상실|잃)|다수(?:의)?\s*치아(?:를)?\s*상실|전체\s*치아(?:가)?\s*상실"),
    ("전악/전체 임플란트", r"전악\s*임플란트|전체\s*임플란트|전악\s*재건|전체\s*재건"),
    ("임플란트 틀니/하이브리드", r"임플란트\s*틀니|하이브리드\s*임플란트|고정성\s*보철|고정식\s*임플란트"),
    ("고난도 케이스", r"고난도|고난이도|어려운\s*임플란트|임플란트\s*불가|재수술|상악동|치조골|뼈\s*이식|잇몸뼈\s*부족"),
    ("소수 식립/4-6개", r"4\s*[~-]\s*6\s*개|4\s*개|6\s*개|최소\s*식립|소수(?:의)?\s*임플란트|경사\s*식립"),
    ("당일 임시치아", r"당일\s*임시\s*치아|수술\s*당일|즉시\s*보철|당일\s*식사|원데이"),
    ("디지털 진단/가이드", r"3D\s*CT|CBCT|구강\s*스캐너|디지털\s*가이드|네비게이션\s*임플란트|내비게이션\s*임플란트|CAD\s*/?\s*CAM|밀링\s*바|티타늄\s*바"),
    ("수면/협진/전문의", r"수면|진정|전문의|협진|구강외과|치주과|영상치의학"),
]

BAD_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "kprofiles.com",
    "panewslab.com",
    "demesilo.com",
    "arxiv.org",
    "medit.com",
    "naver.com",
    "modoodoc.com",
    "ezday.co.kr",
    "eroun.net",
    "joongang.co.kr",
    "jeonmin.co.kr",
    "news.nate.com",
    "sports.donga.com",
    "chosun.com",
    "mdtoday.co.kr",
    "healthcaren.com",
    "isplus.com",
    "jhealthmedia.joins.com",
}


@dataclass
class Hit:
    query: str
    title: str
    url: str
    snippet: str
    source: str


@dataclass
class Candidate:
    name: str
    url: str
    evidence_url: str
    source_note: str = ""
    source_titles: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    page_title: str = ""
    evidence_title: str = ""
    page_status: str = ""
    evidence_status: str = ""
    final_url: str = ""
    evidence_final_url: str = ""
    text_sample: str = ""
    signals: list[str] = field(default_factory=list)
    score: int = 0
    priority: str = "B-검증후접촉"
    trust: str = "중간"
    region: str = "기타/확인필요"
    subregion: str = "확인필요"
    phone: str = ""
    address: str = ""
    portal_status: str = "포털/주문 직접 매칭 미확인"
    description: str = ""
    recommendation: str = ""
    follow_up: str = ""
    recent: list[str] = field(default_factory=list)


def domain_of(url: str) -> str:
    return base.domain_of(url)


def clean_text(raw: str) -> str:
    return re.sub(r"\s+", " ", raw or "").strip()


def fetch_page(url: str) -> dict[str, Any]:
    if not url:
        return {"status": "no link", "final_url": "", "title": "", "text": ""}
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        status = f"{response.status_code} {'OK' if response.status_code < 400 else 'WARN'}"
        if response.content[:4] == b"%PDF":
            return {"status": status, "final_url": response.url, "title": "PDF", "text": ""}
        raw = response.text[:MAX_BODY]
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        title = base.compact(soup.title.get_text(" ", strip=True) if soup.title else "", 160)
        text = base.compact(soup.get_text(" ", strip=True), 8000)
        return {"status": status, "final_url": response.url, "title": title, "text": text}
    except Exception as error:
        return {"status": f"ERROR {type(error).__name__}", "final_url": url, "title": "", "text": str(error)}


def detect_signals(text: str) -> list[str]:
    found: list[str] = []
    for label, pattern in SIGNAL_PATTERNS:
        if re.search(pattern, text, re.I):
            found.append(label)
    return found


def extract_recent(text: str) -> list[str]:
    out: list[str] = []
    for pattern in (r"2026[^.。]{0,90}", r"2025[^.。]{0,90}", r"최근[^.。]{0,90}", r"사례[^.。]{0,90}"):
        for match in re.finditer(pattern, text):
            snip = base.compact(match.group(0), 150)
            if snip and snip not in out:
                out.append(snip)
            if len(out) >= 2:
                return out
    return out


def naver_search(query: str, start: int = 1) -> list[Hit]:
    hits = base.naver_search(query, start=start)
    out: list[Hit] = []
    for hit in hits:
        domain = domain_of(hit.url)
        if any(domain.endswith(bad) or bad in domain for bad in BAD_DOMAINS):
            continue
        out.append(Hit(query=hit.query, title=hit.title, url=hit.url, snippet=hit.snippet, source=hit.source))
    return out


def collect_search_hits(limit_queries: int) -> list[Hit]:
    rows: list[Hit] = []
    for query in SEARCH_QUERIES[:limit_queries]:
        for start in (1, 11):
            try:
                rows.extend(naver_search(query, start=start))
                time.sleep(0.08)
            except Exception as error:
                rows.append(Hit(query=query, title=f"SEARCH_ERROR {type(error).__name__}", url="", snippet=str(error), source="error"))
    return rows


def candidate_name_from_hit(hit: Hit) -> str:
    name = base.extract_clinic_name(hit.title, hit.snippet)
    if not name or "치과" not in name:
        text = f"{hit.title} {hit.snippet}"
        match = re.search(r"([가-힣A-Za-z0-9·&\-\s]{2,24}(?:치과병원|치과의원|치과))", text)
        if match:
            name = base.clean_clinic_name(match.group(1))
    return name


def build_seed_candidates(hits: list[Hit]) -> dict[str, Candidate]:
    candidates: dict[str, Candidate] = {}
    manual_domain_keys: dict[str, str] = {}
    for seed in MANUAL_SEEDS:
        key = base.normalize_key(seed["name"])
        candidates[key] = Candidate(
            name=seed["name"],
            url=seed["url"],
            evidence_url=seed.get("evidence_url") or seed["url"],
            source_note=seed.get("note", ""),
            region=seed.get("region", "기타/확인필요"),
            subregion=seed.get("subregion", "확인필요"),
        )
        seed_domain = domain_of(seed["url"])
        if seed_domain:
            manual_domain_keys[seed_domain] = key
    for hit in hits:
        if not hit.url:
            continue
        domain = domain_of(hit.url)
        if any(domain.endswith(bad) or bad in domain for bad in BAD_DOMAINS):
            continue
        if not base.candidate_domain_allowed(hit.url):
            continue
        if domain in manual_domain_keys:
            cand = candidates[manual_domain_keys[domain]]
            cand.source_titles.append(hit.title)
            cand.search_queries.append(hit.query)
            continue
        blob = f"{hit.title} {hit.snippet}"
        if len(detect_signals(blob)) < 2:
            continue
        name = candidate_name_from_hit(hit)
        if not name or "치과" not in name or base.GENERIC_BAD_NAME_RE.search(name):
            continue
        key = base.normalize_key(name)
        if len(key) < 4:
            continue
        if key not in candidates:
            candidates[key] = Candidate(name=name, url=hit.url, evidence_url=hit.url)
        candidates[key].source_titles.append(hit.title)
        candidates[key].search_queries.append(hit.query)
        if not candidates[key].evidence_url:
            candidates[key].evidence_url = hit.url
    return candidates


def portal_status_for(name: str, existing_keys: set[str]) -> str:
    key = base.normalize_key(name)
    if not key:
        return "포털/주문 직접 매칭 미확인"
    for existing in existing_keys:
        if key == existing or (len(key) >= 5 and key in existing) or (len(existing) >= 5 and existing in key):
            return "기존 포털/주문 유사명 확인 필요"
    return "포털/주문 직접 매칭 없음"


def score_candidate(cand: Candidate, page: dict[str, Any], evidence: dict[str, Any], existing_keys: set[str]) -> Candidate:
    combined = clean_text(" ".join([page.get("title", ""), page.get("text", ""), evidence.get("title", ""), evidence.get("text", ""), cand.source_note]))
    cand.page_title = page.get("title", "")
    cand.evidence_title = evidence.get("title", "")
    cand.page_status = page.get("status", "")
    cand.evidence_status = evidence.get("status", "")
    cand.final_url = page.get("final_url", "") or cand.url
    cand.evidence_final_url = evidence.get("final_url", "") or cand.evidence_url
    cand.signals = detect_signals(combined)
    cand.recent = extract_recent(combined)
    official_text = clean_text(" ".join([page.get("title", ""), page.get("text", "")]))
    if page.get("status", "").startswith("200"):
        cand.phone = base.extract_first(base.PHONE_RE, official_text)
        cand.address = base.extract_first(base.ADDRESS_RE, official_text)
    elif cand.evidence_url == cand.url or domain_of(cand.evidence_url) == domain_of(cand.url):
        cand.phone = base.extract_first(base.PHONE_RE, combined)
        cand.address = base.extract_first(base.ADDRESS_RE, combined)
    else:
        cand.phone = ""
        cand.address = ""
    inferred_region, inferred_subregion = base.infer_region(cand.address, " ".join(cand.search_queries), cand.name, combined, cand.phone)
    if cand.region == "기타/확인필요" and cand.subregion == "확인필요":
        cand.region, cand.subregion = inferred_region, inferred_subregion
    cand.portal_status = portal_status_for(cand.name, existing_keys)

    score = len(cand.signals)
    if "All-on-X/AOX/올온엑스" in cand.signals:
        score += 5
    if "디지털 풀아치" in cand.signals:
        score += 4
    if "무치악/다수치 상실" in cand.signals:
        score += 3
    if "고난도 케이스" in cand.signals:
        score += 3
    if "당일 임시치아" in cand.signals:
        score += 2
    if "디지털 진단/가이드" in cand.signals:
        score += 2
    if cand.page_status.startswith("200"):
        score += 2
    if cand.evidence_status.startswith("200") and cand.evidence_url != cand.url:
        score += 1
    if "기존 포털" in cand.portal_status:
        score -= 3
    cand.score = score

    if score >= 14 and ("All-on-X/AOX/올온엑스" in cand.signals or "디지털 풀아치" in cand.signals):
        cand.priority = "A-우선접촉"
    elif score >= 10:
        cand.priority = "B-검증후접촉"
    else:
        cand.priority = "C-추가확인"

    official_ok = cand.page_status.startswith("200") and domain_of(cand.url) == domain_of(cand.final_url)
    if official_ok and len(cand.signals) >= 5 and cand.priority == "A-우선접촉":
        cand.trust = "높음"
    elif len(cand.signals) >= 4:
        cand.trust = "중간"
    else:
        cand.trust = "낮음"

    if "All-on-X/AOX/올온엑스" in cand.signals:
        service = "올온엑스/AOX 기반 전악 재건"
    elif "디지털 풀아치" in cand.signals:
        service = "디지털 풀아치 기반 전악 재건"
    elif "전악/전체 임플란트" in cand.signals:
        service = "전악/전체 임플란트 중심"
    else:
        service = "무치악/고난도 임플란트 후보"
    cand.description = f"{service} 신호가 확인되는 국내 치과"

    signal_short = ", ".join(cand.signals[:5]) or "무치악/전악 관련 신호 추가 확인 필요"
    cand.recommendation = f"{signal_short} 근거가 있어 무치악·전악·고난도 임플란트 환자를 많이 다루는 후보로 우선 검토할 만하다."
    if cand.priority == "A-우선접촉":
        cand.follow_up = "원장/임플란트 센터 담당자에게 AOX·풀아치 보철 제작/스캔 workflow 확인"
    elif cand.priority == "B-검증후접촉":
        cand.follow_up = "전화 또는 네이버플레이스로 실제 올온엑스/전악 케이스 운영 여부 확인"
    else:
        cand.follow_up = "언론/블로그 근거 중심이라 공식 페이지·진료 항목 재확인 후 접촉"
    cand.text_sample = base.compact(combined, 700)
    return cand


def enrich_candidates(candidates: dict[str, Candidate], existing_keys: set[str]) -> tuple[list[Candidate], list[dict[str, Any]]]:
    urls: dict[str, str] = {}
    for cand in candidates.values():
        urls[cand.url] = cand.url
        if cand.evidence_url:
            urls[cand.evidence_url] = cand.evidence_url
    visits: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(fetch_page, url): url for url in urls if url}
        for future in as_completed(future_map):
            url = future_map[future]
            visits[url] = future.result()

    enriched: list[Candidate] = []
    for cand in candidates.values():
        page = visits.get(cand.url) or {"status": "not fetched", "final_url": cand.url, "title": "", "text": ""}
        evidence = visits.get(cand.evidence_url) or page
        enriched.append(score_candidate(cand, page, evidence, existing_keys))

    visit_rows = [{"url": url, **{k: v for k, v in data.items() if k != "text"}, "text_len": len(data.get("text") or "")} for url, data in visits.items()]
    return enriched, visit_rows


def candidate_to_dict(cand: Candidate) -> dict[str, Any]:
    return {
        "name": cand.name,
        "url": cand.url,
        "evidence_url": cand.evidence_url,
        "source_note": cand.source_note,
        "source_titles": cand.source_titles,
        "search_queries": cand.search_queries,
        "page_title": cand.page_title,
        "evidence_title": cand.evidence_title,
        "page_status": cand.page_status,
        "evidence_status": cand.evidence_status,
        "final_url": cand.final_url,
        "evidence_final_url": cand.evidence_final_url,
        "signals": cand.signals,
        "score": cand.score,
        "priority": cand.priority,
        "trust": cand.trust,
        "region": cand.region,
        "subregion": cand.subregion,
        "phone": cand.phone,
        "address": cand.address,
        "portal_status": cand.portal_status,
        "description": cand.description,
        "recommendation": cand.recommendation,
        "follow_up": cand.follow_up,
        "recent": cand.recent,
        "text_sample": cand.text_sample,
    }


def make_report(rows: list[Candidate], all_count: int, visit_count: int, outline_status: str) -> str:
    counts = Counter(row.priority for row in rows)
    regions = Counter(row.region for row in rows)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 260609 국내 무치악/all-on-x 임플란트 영업후보 추천 요약",
        "",
        "## 작성 기준",
        f"* 대상: {DOMESTIC_ROOT_URL} 국내 치과 후보를 참고하되, 별도 공개 검색으로 all-on-x, 무치악, 전악/전체 임플란트, 디지털 풀아치, 고난도 임플란트 신호가 있는 치과를 보강했다.",
        f"* 참고 형식: {REFERENCE_REPORT_URL} 의 추천 요약/추천 업체 테이블 구조를 유지했다.",
        "* 우선순위 기준: 공식 페이지나 병원 컬럼에서 `올온엑스/AOX`, `디지털 풀아치`, `무치악`, `전악/전체 임플란트`, `고난도/뼈이식/상악동/재수술`, `당일 임시치아`, `3D CT/구강스캐너/가이드/밀링바` 신호가 같이 확인되는 곳을 상위로 두었다.",
        "* 포털/주문 기준: 로컬 portal/contact/order 산출물의 회사명·거래명세서 파일명과 강한 이름 매칭이 있는 경우 주의 표시했다.",
        "* 신뢰도 기준: 병원 공식 페이지 200 OK + all-on-x/풀아치/무치악 본문 근거가 있으면 높음, 언론 기사 중심이면 중간 이하로 표시했다.",
        f"* 작성 시각: {now} KST. 방문 확인 URL: {visit_count}개. Outline API 상태: {outline_status}",
        "",
        "## 추천 요약",
        f"* 검색·수집 후보: {all_count}개",
        f"* 추천 반영: {len(rows)}개",
        f"* A-우선접촉: {counts.get('A-우선접촉', 0)}개",
        f"* B-검증후접촉: {counts.get('B-검증후접촉', 0)}개",
        f"* C-추가확인: {counts.get('C-추가확인', 0)}개",
        "* 핵심 소싱 방법: 네이버 웹 검색, 공개 웹검색, 병원 공식 페이지/컬럼 직접 fetch, 언론 기사 보조 근거, 로컬 portal/order 이름 매칭.",
        "* 권역 분포: " + ", ".join(f"{k} {v}" for k, v in regions.most_common()) if rows else "* 권역 분포: 없음",
        "",
        "## 추천 업체 테이블",
        "| 우선순위 | 대분류 | 중분류 | 소분류 | 업체/치과 | 어떤 곳인지 | 포털 존재 여부 | 확인된 무치악/all-on-x 신호 | 왜 추천하는지 | 연락/웹 | 확인 출처 | 웹 링크 상태 | 최근 온라인 흔적 | 신뢰도 | 후속 액션 |",
        "|------|-----|-----|-----|-------|--------|----------|---------------|---------|------|-------|---------|-----------|-----|-------|",
    ]
    for row in rows:
        contact_bits = []
        if row.phone:
            contact_bits.append(row.phone)
        if row.address:
            contact_bits.append(row.address)
        if row.final_url or row.url:
            contact_bits.append(f"[web]({row.final_url or row.url})")
        source_label = row.evidence_title or row.page_title or row.source_note or base.result_source(row.evidence_url)
        source = f"[{base.md_escape(source_label, 90)}]({row.evidence_final_url or row.evidence_url or row.final_url or row.url})"
        recent = "<br>".join(base.md_escape(item, 140) for item in row.recent[:2]) or "최근연도 직접 신호 미확인"
        lines.append(
            "| "
            + " | ".join(
                [
                    base.md_escape(row.priority, 80),
                    "국내 무치악/all-on-x 영업후보",
                    base.md_escape(row.region, 60),
                    base.md_escape(row.subregion, 60),
                    f"[{base.md_escape(row.name, 80)}]({row.final_url or row.url})",
                    base.md_escape(row.description, 140),
                    base.md_escape(row.portal_status, 120),
                    base.md_escape(", ".join(row.signals) or "추가확인", 190),
                    base.md_escape(row.recommendation, 240),
                    "<br>".join(base.md_escape(x, 120) for x in contact_bits) or "연락처 웹 확인 필요",
                    source,
                    base.md_escape(f"공식 {row.page_status}; 근거 {row.evidence_status}", 100),
                    recent,
                    base.md_escape(row.trust, 60),
                    base.md_escape(row.follow_up, 150),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 신뢰도 메모",
            "* 높음: 병원 공식 페이지에서 all-on-x/AOX/디지털 풀아치/무치악/전악 임플란트 신호가 복수로 확인되고 링크가 정상 응답.",
            "* 중간: 공식 사이트는 확인됐지만 세부 시술 근거가 약하거나, 언론 기사·병원 컬럼 중심으로 확인된 후보.",
            "* 낮음: 전악/무치악 키워드는 있으나 실제 케이스 규모나 all-on-x 운영 여부가 약해 전화 확인이 필요한 후보.",
            "",
            "## 후속 작업",
            "* A 후보는 임플란트 센터/대표원장/상담실에 AOX·풀아치 케이스 수, 보철 제작 방식, 구강스캔/밀링바/임시치아 workflow를 확인한다.",
            "* 디지털 풀아치와 AOX 후보는 단순 구강스캐너보다 무치악 스캔, 임시 보철, 기공소/밀링센터 연동 관점으로 제안한다.",
            "* 기사 근거만 강한 후보는 공식 진료 페이지 또는 네이버플레이스 진료 항목으로 실제 운영 여부를 확인한 뒤 접촉한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def outline_api(session: requests.Session, endpoint: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = session.post(f"{OUTLINE_BASE}/api/{endpoint}", json=body, timeout=timeout)
    response.raise_for_status()
    return response.json()


def publish_to_outline(markdown: str, timeout: int) -> dict[str, Any]:
    key = outline_publish.read_env_key("DOF_OUTLINE_KEY")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}"})
    parent = outline_api(session, "documents.info", {"id": REPORT_PARENT_ID}, timeout)["data"]
    existing_id = ""
    existing_url = ""
    listed = outline_api(session, "documents.list", {"parentDocumentId": REPORT_PARENT_ID, "limit": 100, "offset": 0}, timeout)
    for doc in listed.get("data") or []:
        if doc.get("title") == REPORT_TITLE:
            existing_id = doc.get("id") or ""
            existing_url = f"{OUTLINE_BASE}/doc/{doc.get('urlId')}"
            break
    if existing_id:
        data = outline_api(
            session,
            "documents.update",
            {"id": existing_id, "title": REPORT_TITLE, "text": markdown, "publish": True, "fullWidth": True},
            timeout,
        )["data"]
        action = "updated"
    else:
        data = outline_api(
            session,
            "documents.create",
            {"title": REPORT_TITLE, "parentDocumentId": REPORT_PARENT_ID, "text": markdown, "publish": True, "fullWidth": True},
            timeout,
        )["data"]
        action = "created"
    doc_id = data.get("id") or existing_id
    readback = outline_api(session, "documents.info", {"id": doc_id}, timeout)["data"]
    text = readback.get("text") or ""
    return {
        "published": True,
        "action": action,
        "parent_title": parent.get("title"),
        "doc_id": doc_id,
        "url": f"{OUTLINE_BASE}{readback.get('url')}" if readback.get("url") else existing_url,
        "title": readback.get("title"),
        "text_length": len(text),
        "has_table": "| 우선순위 | 대분류 |" in text,
        "row_count": text.count("| A-우선접촉 |") + text.count("| B-검증후접촉 |") + text.count("| C-추가확인 |"),
        "has_all_on_x": any(token in text for token in ["올온엑스", "All-on-X", "AOX", "디지털 풀아치"]),
    }


def run(target_count: int, limit_queries: int, publish: bool, outline_timeout: int) -> dict[str, Any]:
    hits = collect_search_hits(limit_queries)
    write_jsonl(SEARCH_JSONL, [hit.__dict__ for hit in hits])

    candidates = build_seed_candidates(hits)
    existing_keys = base.load_existing_customer_keys()
    enriched, visit_rows = enrich_candidates(candidates, existing_keys)
    save_json(VISITS_JSON, visit_rows)

    filtered = [
        row
        for row in enriched
        if row.priority != "C-추가확인" or ("All-on-X/AOX/올온엑스" in row.signals or "디지털 풀아치" in row.signals)
    ]
    filtered.sort(key=lambda row: (-row.score, row.priority, row.region, row.name))

    seen_domains: set[str] = set()
    rows: list[Candidate] = []
    for row in filtered:
        domain = domain_of(row.final_url or row.url)
        if domain and domain in seen_domains:
            continue
        if domain:
            seen_domains.add(domain)
        rows.append(row)
        if len(rows) >= target_count:
            break

    outline_status = "publish skipped"
    markdown = make_report(rows, len(enriched), len(visit_rows), outline_status)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(markdown, encoding="utf-8")

    publish_result: dict[str, Any] = {"published": False, "skipped": not publish}
    if publish:
        markdown = make_report(rows, len(enriched), len(visit_rows), "publishing")
        REPORT_MD.write_text(markdown, encoding="utf-8")
        publish_result = publish_to_outline(markdown, outline_timeout)
        outline_status = "healthy"
        markdown = make_report(rows, len(enriched), len(visit_rows), outline_status)
        REPORT_MD.write_text(markdown, encoding="utf-8")
        publish_result = publish_to_outline(markdown, outline_timeout)

    save_json(CANDIDATES_JSON, [candidate_to_dict(row) for row in rows])
    result = {
        "target_count": target_count,
        "search_hits": len(hits),
        "candidate_count": len(enriched),
        "selected_count": len(rows),
        "visited_url_count": len(visit_rows),
        "report_md": str(REPORT_MD),
        "search_jsonl": str(SEARCH_JSONL),
        "visits_json": str(VISITS_JSON),
        "candidates_json": str(CANDIDATES_JSON),
        "publish_result": publish_result,
        "priority_counts": Counter(row.priority for row in rows),
    }
    save_json(RESULT_JSON, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-count", type=int, default=24)
    parser.add_argument("--limit-queries", type=int, default=len(SEARCH_QUERIES))
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--outline-timeout", type=int, default=80)
    args = parser.parse_args()
    result = run(args.target_count, args.limit_queries, args.publish, args.outline_timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
