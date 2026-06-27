#!/usr/bin/env python3
"""Enrich domestic dental lab prospects with portal and web evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_DIR = ROOT / "output/domestic-dental-labs-260607"
WEB_DIR = OUT_DIR / "web_enrich_260608"
SELECTED_JSON = OUT_DIR / "domestic_dental_labs_selected.json"
ENRICHED_JSON = OUT_DIR / "domestic_dental_labs_selected_enriched_260608.json"
PORTAL_SNAPSHOT_JSON = WEB_DIR / "portal_companies_orders_snapshot.json"
WEB_CACHE_JSONL = WEB_DIR / "naver_search_cache.jsonl"
RESULT_JSON = WEB_DIR / "portal_web_enrich_result.json"

PORTAL_QUERY = ROOT / "proc/lib/dof_portal_query_companies_orders.mjs"
NAVER_WEB = "https://search.naver.com/search.naver?where=web&query="
DDG_HTML = "https://html.duckduckgo.com/html/?q="

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

NAME_STRIP_PATTERNS = [
    r"\(주\)",
    r"（주）",
    r"㈜",
    r"주식회사",
    r"유한회사",
    r"의료법인",
    r"재단법인",
]
GENERIC_DENTAL_PATTERNS = [
    r"치과기공소",
    r"치과기공",
    r"기공소",
    r"덴탈랩",
    r"덴탈",
    r"dental",
    r"laboratory",
    r"laborator",
    r"lab",
]
GENERIC_BASE_KEYS = {"원", "미소", "스마일", "서울", "중앙", "현대", "미래", "새한", "하나", "우리", "좋은", "나래"}

NEWS_DOMAINS = {
    "dentalnews.or.kr",
    "dentalarirang.com",
    "dentalzero.com",
    "dentalfocus.co.kr",
    "denfoline.co.kr",
    "dailydental.co.kr",
    "dtnews24.com",
    "news.naver.com",
    "yna.co.kr",
}
CONFERENCE_WORDS = ("sidex", "kdx", "yesdex", "gamex", "hode", "학술대회", "세미나", "컨퍼런스", "전시회", "박람회", "보수교육")
LISTING_DOMAINS = {
    "march14th.net",
    "duli.co.kr",
    "localmap.co.kr",
    "purpleo.co.kr",
    "moneypin.biz",
    "mypet-119.com",
    "114.co.kr",
    "kadeora.net",
    "ayo.pe.kr",
    "forwarder.kr",
    "modoodoc.com",
    "findcompany.kr",
    "saramin.co.kr",
    "data.go.kr",
    "jobkorea.co.kr",
    "wanted.co.kr",
    "job2804.com",
    "hopeus.or.kr",
    "allthatcompany.com",
    "bizno.net",
    "corp.udanax.org",
}
SOCIAL_DOMAINS = {"blog.naver.com", "facebook.com", "instagram.com", "youtube.com"}


def compact(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def normalize_name(value: str, *, strip_dental: bool = False) -> str:
    text = (value or "").lower()
    for pattern in NAME_STRIP_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.I)
    if strip_dental:
        for pattern in GENERIC_DENTAL_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.I)
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def phone_digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def address_tokens(value: str) -> set[str]:
    tokens = set()
    for raw in re.split(r"[\s,()·/.-]+", value or ""):
        token = raw.strip()
        if len(token) >= 2:
            tokens.add(token)
    return tokens


def portal_phones(company: dict[str, Any]) -> set[str]:
    values = [company.get("phone"), company.get("mobile1"), company.get("mobile2")]
    for customer in company.get("customers") or []:
        values.extend([customer.get("phone"), customer.get("officePhone")])
    latest = company.get("latest_order") or {}
    values.append(latest.get("phone"))
    return {digits for digits in (phone_digits(value) for value in values) if len(digits) >= 8}


def portal_addresses(company: dict[str, Any]) -> list[str]:
    values = [company.get("address"), company.get("addressDetail")]
    for shipping in company.get("shipping_addresses") or []:
        values.extend([shipping.get("address"), shipping.get("addressDetail")])
    latest = company.get("latest_order") or {}
    values.append(latest.get("shippingAddress"))
    return [compact(value, 220) for value in values if compact(value)]


def portal_names(company: dict[str, Any]) -> list[str]:
    values = [company.get("name"), company.get("businessName")]
    return [compact(value, 120) for value in values if compact(value)]


def prepare_portal_companies(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared = []
    for company in companies:
        names = portal_names(company)
        addrs = portal_addresses(company)
        addr_join = " ".join(addrs)
        prepared.append(
            {
                "company": company,
                "names": names,
                "full_names": [normalize_name(name) for name in names],
                "base_names": [normalize_name(name, strip_dental=True) for name in names],
                "phones": portal_phones(company),
                "addresses": addrs,
                "addr_join": addr_join,
                "addr_tokens": address_tokens(addr_join),
            }
        )
    return prepared


def fetch_portal_snapshot(refresh: bool) -> list[dict[str, Any]]:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    if PORTAL_SNAPSHOT_JSON.exists() and not refresh:
        return json.loads(PORTAL_SNAPSHOT_JSON.read_text(encoding="utf-8"))
    raw = subprocess.check_output(["node", str(PORTAL_QUERY)], cwd=ROOT, text=True)
    rows = json.loads(raw)
    save_json(PORTAL_SNAPSHOT_JSON, rows)
    return rows


def portal_match_one(lab: dict[str, Any], companies: list[dict[str, Any]]) -> dict[str, Any]:
    lab_name = lab.get("name") or ""
    lab_full = normalize_name(lab_name)
    lab_base = normalize_name(lab_name, strip_dental=True)
    lab_phone = phone_digits(lab.get("phone"))
    lab_addr = lab.get("address") or ""
    lab_tokens = address_tokens(lab_addr)
    lab_city = lab.get("city") or ""
    lab_province = lab.get("province") or ""
    best: tuple[int, dict[str, Any], list[str]] | None = None

    for prepared in companies:
        company = prepared["company"]
        full_names = prepared["full_names"]
        base_names = prepared["base_names"]
        phones = prepared["phones"]
        addr_join = prepared["addr_join"]
        score = 0
        reasons: list[str] = []

        if lab_phone and lab_phone in phones:
            score += 65
            reasons.append("전화번호 일치")
        if lab_full and lab_full in full_names:
            score += 45
            reasons.append("상호 정규화 일치")
        elif lab_full and len(lab_full) >= 5 and any(lab_full in name or name in lab_full for name in full_names if len(name) >= 5):
            score += 25
            reasons.append("상호 부분 일치")

        base_ok = lab_base and len(lab_base) >= 3 and lab_base not in GENERIC_BASE_KEYS
        if base_ok and lab_base in base_names:
            score += 30
            reasons.append("상호 핵심어 일치")
        elif base_ok and len(lab_base) >= 5 and any(lab_base in name or name in lab_base for name in base_names if len(name) >= 5):
            score += 15
            reasons.append("상호 핵심어 부분 일치")

        if lab_city and lab_city in addr_join:
            score += 14
            reasons.append("시군구 일치")
        if lab_province and lab_province[:2] in addr_join:
            score += 8
            reasons.append("시도 일치")
        common_addr = lab_tokens & prepared["addr_tokens"]
        if len(common_addr) >= 3:
            score += 18
            reasons.append("주소 토큰 다수 일치")
        elif len(common_addr) >= 2:
            score += 8
            reasons.append("주소 토큰 일부 일치")

        # Avoid generic-name false positives unless another strong signal exists.
        if lab_base in GENERIC_BASE_KEYS and not (lab_phone and lab_phone in phones):
            score -= 30
            reasons.append("상호가 일반어라 보수 감점")

        if best is None or score > best[0]:
            best = (score, company, reasons)

    if best is None or best[0] < 45:
        return {
            "portal_match_status": "포털 미발견",
            "portal_match_confidence": "낮음",
            "portal_match_score": 0,
            "portal_match_summary": "포털 DB 회사/주문 스냅샷에서 전화·주소·상호 기준 직접 매칭 없음",
        }

    score, company, reasons = best
    has_phone_or_geo = (
        "전화번호 일치" in reasons
        or "주소 토큰 다수 일치" in reasons
        or ("시군구 일치" in reasons and "시도 일치" in reasons)
    )
    if not has_phone_or_geo and score >= 70:
        score = 60
        reasons.append("지역/전화 근거 없어 유사명으로 강등")
    orders_count = int(company.get("orders_count") or 0)
    latest = company.get("latest_order") or {}
    if score >= 85:
        status = "포털 주문 발생" if orders_count else "포털 등록 확인"
        confidence = "높음"
    elif score >= 70:
        status = "포털 주문 가능성 높음" if orders_count else "포털 등록 가능성 높음"
        confidence = "중간"
    else:
        status = "포털 유사명 검토"
        confidence = "낮음"

    recent_order = compact(
        " / ".join(
            value
            for value in [
                latest.get("orderNo"),
                latest.get("orderName"),
                latest.get("orderDate") or latest.get("createdAt"),
            ]
            if value
        ),
        140,
    )
    portal_summary = (
        f"{status}: portal company id {company.get('id')} / {company.get('name')} / "
        f"주문 {orders_count}건"
    )
    if recent_order:
        portal_summary += f" / 최근 {recent_order}"
    if reasons:
        portal_summary += " / 근거 " + ", ".join(reasons[:4])
    return {
        "portal_match_status": status,
        "portal_match_confidence": confidence,
        "portal_match_score": score,
        "portal_company_id": company.get("id"),
        "portal_company_uk": company.get("uk"),
        "portal_company_name": company.get("name"),
        "portal_company_country": company.get("country"),
        "portal_company_phone": company.get("phone"),
        "portal_company_address": company.get("address"),
        "portal_company_website": company.get("website"),
        "portal_orders_count": orders_count,
        "portal_latest_order": latest,
        "portal_product_names": company.get("product_names") or [],
        "portal_match_reasons": reasons,
        "portal_match_summary": compact(portal_summary, 300),
    }


def load_web_cache() -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    if not WEB_CACHE_JSONL.exists():
        return cache
    with WEB_CACHE_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            engine = item.get("engine") or "naver"
            cache[f"{engine}::{item['query']}"] = item
    return cache


def append_cache(item: dict[str, Any]) -> None:
    WEB_CACHE_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with WEB_CACHE_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def host_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def source_type(url: str, text: str) -> str:
    host = host_of(url)
    lower = f"{host} {text}".lower()
    if host in NEWS_DOMAINS or any(host.endswith("." + domain) for domain in NEWS_DOMAINS):
        return "뉴스/업계매체"
    if any(word in lower for word in CONFERENCE_WORDS):
        return "컨퍼런스/세미나"
    if host in SOCIAL_DOMAINS or any(host.endswith("." + domain) for domain in SOCIAL_DOMAINS):
        return "소셜/블로그"
    if host in LISTING_DOMAINS or any(host.endswith("." + domain) for domain in LISTING_DOMAINS):
        if "data.go.kr" in host:
            return "정부/공공"
        if "saramin" in host or "findcompany" in host:
            return "기업정보/채용"
        return "지도/업체목록"
    if "place.naver.com" in url or "map.naver.com" in url:
        return "지도/플레이스"
    return "웹"


def result_matches_lab(text: str, url: str, lab: dict[str, Any]) -> bool:
    hay = normalize_name(text + " " + url)
    name = normalize_name(lab.get("name") or "")
    base = normalize_name(lab.get("name") or "", strip_dental=True)
    city = normalize_name(lab.get("city") or "")
    if name and name in hay:
        return True
    if base and len(base) >= 3 and base not in GENERIC_BASE_KEYS and base in hay and ("치과" in text or "기공" in text or city in hay):
        return True
    return False


def parse_naver_results(html: str, lab: dict[str, Any]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    by_url: dict[str, dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        if not href.startswith("http"):
            continue
        host = host_of(href)
        if host.endswith("pstatic.net") or host in {"search.naver.com", "ssl.pstatic.net"}:
            continue
        text = compact(anchor.get_text(" ", strip=True), 240)
        if len(text) < 5:
            continue
        if not result_matches_lab(text, href, lab):
            continue
        item = by_url.setdefault(
            href,
            {
                "title": compact(text, 140),
                "url": href,
                "snippet": "",
                "type": source_type(href, text),
            },
        )
        if text != item["title"] and len(item["snippet"]) < 260:
            item["snippet"] = compact((item["snippet"] + " " + text).strip(), 260)
    return list(by_url.values())[:8]


def ddg_target_url(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else href
    return href


def parse_ddg_results(html: str, lab: dict[str, Any]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in soup.select(".result"):
        anchor = block.select_one("a.result__a")
        if not anchor or not anchor.get("href"):
            continue
        href = ddg_target_url(str(anchor.get("href") or ""))
        if not href.startswith("http") or href in seen:
            continue
        title = compact(anchor.get_text(" ", strip=True), 160)
        snippet_el = block.select_one(".result__snippet")
        snippet = compact(snippet_el.get_text(" ", strip=True) if snippet_el else block.get_text(" ", strip=True), 300)
        combined = f"{title} {snippet}"
        if not result_matches_lab(combined, href, lab):
            continue
        seen.add(href)
        results.append({"title": title, "url": href, "snippet": snippet, "type": source_type(href, combined)})
        if len(results) >= 8:
            break
    return results


def fetch_engine(
    engine: str,
    query: str,
    lab: dict[str, Any],
    cache: dict[str, dict[str, Any]],
    timeout: int,
    offline: bool = False,
) -> dict[str, Any]:
    cache_key = f"{engine}::{query}"
    if cache_key in cache:
        return cache[cache_key]
    if offline:
        return {
            "engine": engine,
            "query": query,
            "searched_at": datetime.now().isoformat(timespec="seconds"),
            "search_url": (NAVER_WEB if engine == "naver" else DDG_HTML) + quote_plus(query),
            "status_code": 0,
            "results": [],
            "error": "offline; no cached result",
        }
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"})
    url = (NAVER_WEB if engine == "naver" else DDG_HTML) + quote_plus(query)
    error = ""
    results: list[dict[str, str]] = []
    status_code = 0
    try:
        response = session.get(url, timeout=timeout)
        status_code = response.status_code
        response.raise_for_status()
        if engine == "naver":
            results = parse_naver_results(response.text, lab)
        else:
            results = parse_ddg_results(response.text, lab)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    item = {
        "engine": engine,
        "query": query,
        "searched_at": datetime.now().isoformat(timespec="seconds"),
        "search_url": url,
        "status_code": status_code,
        "results": results,
        "error": error,
    }
    append_cache(item)
    cache[cache_key] = item
    return item


def fetch_web_one(lab: dict[str, Any], cache: dict[str, dict[str, Any]], timeout: int, offline: bool) -> dict[str, Any]:
    query = f"{lab.get('name')} {lab.get('province')} {lab.get('city')} 치과기공소"
    naver = fetch_engine("naver", query, lab, cache, timeout, offline=offline)
    needs_fallback = bool(naver.get("error")) or not naver.get("results")
    ddg = fetch_engine("duckduckgo", query, lab, cache, timeout, offline=offline) if needs_fallback else {
        "engine": "duckduckgo",
        "query": query,
        "search_url": DDG_HTML + quote_plus(query),
        "status_code": 0,
        "results": [],
        "error": "skipped; naver had matched results",
    }
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in (naver, ddg):
        for result in source.get("results") or []:
            url = result.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(result)
            if len(merged) >= 8:
                break
        if len(merged) >= 8:
            break
    return {
        "engine": "combined",
        "query": query,
        "searched_at": datetime.now().isoformat(timespec="seconds"),
        "search_url": f"{naver.get('search_url')} / {ddg.get('search_url')}",
        "status_code": {"naver": naver.get("status_code"), "duckduckgo": ddg.get("status_code")},
        "results": merged,
        "error": " / ".join(error for error in [naver.get("error"), ddg.get("error")] if error and not str(error).startswith("skipped")),
    }


def summarize_web(lab: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    results = item.get("results") or []
    type_counts = Counter(result.get("type") for result in results)
    has_media = any(result.get("type") in {"뉴스/업계매체", "컨퍼런스/세미나"} for result in results)
    web_candidates = [result for result in results if result.get("type") in {"웹", "지도/플레이스", "소셜/블로그"}]
    listings = [result for result in results if result.get("type") in {"정부/공공", "지도/업체목록", "기업정보/채용"}]
    if web_candidates:
        website_status = "웹/플레이스 검색 흔적 있음"
    elif listings:
        website_status = "업체목록/기업정보 검색 흔적 있음"
    elif results:
        website_status = "일반 검색 흔적 있음"
    else:
        website_status = "검색 결과에서 명확한 업체 웹 흔적 미확인"

    if has_media:
        media_status = "뉴스/컨퍼런스/세미나 관련 검색 흔적 있음"
    else:
        media_status = "뉴스·컨퍼런스 직접 흔적 미확인"

    if results and (web_candidates or listings):
        confidence = "중간"
    elif results:
        confidence = "낮음"
    else:
        confidence = "낮음"
    evidence_parts = []
    for result in results[:3]:
        title = compact(result.get("title"), 70)
        evidence_parts.append(f"{result.get('type')}: {title} ({result.get('url')})")
    evidence = " / ".join(evidence_parts) if evidence_parts else "검색 결과 없음 또는 상호-지역 직접 확인 불가"
    summary = f"{website_status}; {media_status}"
    if type_counts:
        summary += "; " + ", ".join(f"{key} {value}" for key, value in type_counts.most_common(4))
    return {
        "web_search_query": item.get("query"),
        "web_search_url": item.get("search_url"),
        "web_result_count": len(results),
        "web_summary": compact(summary, 260),
        "web_evidence": compact(evidence, 700),
        "web_confidence": confidence,
        "web_has_news_or_conference": has_media,
        "web_results": results,
    }


def enrich_rows(limit: int, refresh_portal: bool, refresh_web: bool, workers: int, timeout: int, offline_web: bool) -> dict[str, Any]:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    rows = json.loads(SELECTED_JSON.read_text(encoding="utf-8"))
    if limit > 0:
        rows = rows[:limit]
    companies = fetch_portal_snapshot(refresh=refresh_portal)
    prepared_companies = prepare_portal_companies(companies)
    for row in rows:
        row.update(portal_match_one(row, prepared_companies))

    cache = {} if refresh_web else load_web_cache()
    web_by_mgmt: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch_web_one, row, cache, timeout, offline_web): row for row in rows}
        done = 0
        for future in as_completed(futures):
            row = futures[future]
            web_by_mgmt[row["management_no"]] = future.result()
            done += 1
            if done % 100 == 0:
                print(f"web_search {done}/{len(rows)}", flush=True)
            time.sleep(0.02)
    for row in rows:
        row.update(summarize_web(row, web_by_mgmt.get(row["management_no"], {})))

    save_json(ENRICHED_JSON, rows)
    portal_counts = Counter(row.get("portal_match_status") for row in rows)
    web_counts = Counter(row.get("web_summary", "").split(";")[0] for row in rows)
    media_count = sum(1 for row in rows if row.get("web_has_news_or_conference"))
    result = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "rows": len(rows),
        "portal_snapshot_rows": len(companies),
        "portal_counts": dict(portal_counts.most_common()),
        "web_counts": dict(web_counts.most_common()),
        "web_news_or_conference_count": media_count,
        "outputs": {
            "portal_snapshot": str(PORTAL_SNAPSHOT_JSON),
            "web_cache": str(WEB_CACHE_JSONL),
            "enriched_json": str(ENRICHED_JSON),
        },
    }
    save_json(RESULT_JSON, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Limit rows for testing. 0 means all selected rows.")
    parser.add_argument("--refresh-portal", action="store_true")
    parser.add_argument("--refresh-web", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--offline-web", action="store_true", help="Use cached web-search results only; do not perform new searches.")
    args = parser.parse_args()
    result = enrich_rows(args.limit, args.refresh_portal, args.refresh_web, args.workers, args.timeout, args.offline_web)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
