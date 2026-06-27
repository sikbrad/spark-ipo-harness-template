#!/usr/bin/env python3
"""Promote incomplete OSM prospects by extracting contact details from websites."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

import dof_prospect_scale5000 as base


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA_DIR = OUT_ROOT / "data"
ENRICH_CACHE_JSON = DATA_DIR / "website_enrichment_cache.json"
ENRICH_LOG_JSONL = DATA_DIR / "website_enrichment_promotions.jsonl"

DEFAULT_TARGET_COUNTRIES = {
    "United States",
    "Japan",
    "Singapore",
    "Malaysia",
    "Thailand",
    "Vietnam",
    "Indonesia",
    "Philippines",
    "Cambodia",
    "Laos",
    "Myanmar",
    "Brunei",
    "Timor-Leste",
}
LOCAL_LAB_DISTRIBUTOR_RE = re.compile(
    r"dental\s*(lab|laborator|technician|design|studio|milling|cad|cam|supply|supplies|depot|distribut|dealer|equipment)"
    r"|dentallabor|zahntechnik|zahn\s*labor|dentaltechnik"
    r"|laboratoire\s+dentaire|proth[ée]siste\s+dentaire|laboratoire\s+de\s+proth"
    r"|laboratorio\s+dental|laboratorio\s+prot[ée]sico|dep[óo]sito\s+dental|distribuidora\s+dental"
    r"|laborat[óo]rio\s+(de\s+pr[óo]tese\s+dent[áa]ria|dental)|distribuidora\s+dental"
    r"|laboratorio\s+odontotecnico|odontotecnico|laboratorio\s+dentale"
    r"|tandtechnisch|tandtechniek|tandprothetisch|tandlabo"
    r"|pracownia\s+protetyczna|laboratorium\s+dentystyczne|technik\s+dentystyczny"
    r"|zubn[íi]\s+laborato|zubn[íi]\s+technik"
    r"|歯科技工所|歯科技工|デンタルラボ|技工所"
    r"|牙科技工所|义齿加工|牙科实验室|牙科器材|口腔器材"
    r"|แล็บทันตกรรม|ห้องปฏิบัติการทันตกรรม"
    r"|labo\s+nha\s+khoa|phòng\s+lab\s+nha\s+khoa|kỹ\s+thuật\s+răng"
    r"|laboratorium\s+gigi|lab\s+gigi|makmal\s+pergigian"
    r"|مختبر\s+أسنان|معمل\s+أسنان"
    r"|diş\s+laboratuvar|diş\s+protez"
    r"|зуботехническая\s+лаборатория|стоматологическая\s+лаборатория",
    re.IGNORECASE,
)
CONTACT_PATH_HINTS = (
    "contact",
    "contacts",
    "kontakt",
    "impressum",
    "appointment",
    "appointments",
    "location",
    "locations",
    "access",
    "about",
    "clinic",
    "inquiry",
    "reserve",
    "reservation",
    "お問い合わせ",
    "アクセス",
)
BAD_EMAIL_PREFIXES = {"example", "test", "privacy", "noreply", "no-reply", "donotreply", "sentry", "abuse"}
BAD_EMAIL_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().\-]{7,}\d)")


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def read_incomplete() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not base.INCOMPLETE_JSONL.exists():
        return rows
    with base.INCOMPLETE_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def normalize_url(url: str) -> str:
    url = base.clean_text(url)
    if not url:
        return ""
    if "@" in url and not re.match(r"https?://", url, re.I):
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not re.match(r"https?://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        return ""
    return url


def domain(url: str) -> str:
    host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def extract_emails(text: str) -> list[str]:
    text = unescape(text).replace("[at]", "@").replace("(at)", "@").replace("＠", "@")
    text = re.sub(r"\s+@\s+", "@", text)
    text = re.sub(r"\s+\.\s+", ".", text)
    seen: set[str] = set()
    emails: list[str] = []
    for raw in EMAIL_RE.findall(text):
        email = raw.strip(".,;:()[]{}<>").lower()
        if not email or email in seen:
            continue
        prefix = email.split("@", 1)[0]
        suffix = email.rsplit(".", 1)[-1]
        if prefix in BAD_EMAIL_PREFIXES:
            continue
        if email.endswith(BAD_EMAIL_SUFFIXES):
            continue
        if len(suffix) > 12:
            continue
        seen.add(email)
        emails.append(email)
    return emails


def extract_phone(text: str) -> str:
    for raw in PHONE_RE.findall(text):
        value = re.sub(r"\s+", " ", raw).strip(" .,-")
        digits = re.sub(r"\D", "", value)
        if 8 <= len(digits) <= 16:
            return value
    return ""


def same_site(base_url: str, href: str) -> str:
    url = normalize_url(urljoin(base_url, href))
    if not url:
        return ""
    if domain(url) != domain(base_url):
        return ""
    return url.split("#", 1)[0]


def contact_links(base_url: str, html: str) -> list[str]:
    links: list[str] = []
    for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.I):
        lowered = unescape(href).lower()
        if any(hint.lower() in lowered for hint in CONTACT_PATH_HINTS):
            url = same_site(base_url, href)
            if url and url not in links:
                links.append(url)
        if len(links) >= 5:
            break
    return links


def fetch(url: str) -> tuple[str, str]:
    headers = {
        "User-Agent": "DOF customer prospect contact research (local agent; public company websites)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=(4, 7), allow_redirects=True)
    ctype = response.headers.get("content-type", "")
    if response.status_code >= 400 or "text/html" not in ctype:
        return response.url, ""
    return response.url, response.text[:500_000]


def inspect_website(row: dict[str, Any]) -> dict[str, Any]:
    tags = row.get("tags") or {}
    website = normalize_url(tags.get("website") or tags.get("contact:website") or "")
    if not website:
        return {"status": "no_website", "website": ""}
    fetched: list[str] = []
    texts: list[str] = []
    errors: list[str] = []
    try:
        final_url, html = fetch(website)
        if html:
            fetched.append(final_url)
            texts.append(html)
            for link in contact_links(final_url, html):
                if link in fetched:
                    continue
                try:
                    page_url, page_html = fetch(link)
                    if page_html:
                        fetched.append(page_url)
                        texts.append(page_html)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{link}: {type(exc).__name__}: {exc}")
                if len(fetched) >= 4:
                    break
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{website}: {type(exc).__name__}: {exc}")
    combined = "\n".join(texts)
    emails = extract_emails(combined)
    phone = extract_phone(combined)
    return {
        "status": "ok" if texts else "fetch_failed",
        "website": website,
        "fetched": fetched,
        "emails": emails[:8],
        "phone": phone,
        "errors": errors[:5],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def candidate_key(row: dict[str, Any]) -> str:
    tags = row.get("tags") or {}
    website = normalize_url(tags.get("website") or tags.get("contact:website") or "")
    return f"{row.get('source_url')}|{website}"


def build_candidates(rows: list[dict[str, Any]], limit: int, target_countries: set[str]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if target_countries and row.get("country") not in target_countries:
            continue
        missing = set(row.get("missing") or [])
        # Keep the strongest candidates first: rows that already have name,
        # phone, address, and only need a website email.
        if not missing or not missing.issubset({"email", "phone"}):
            continue
        tags = row.get("tags") or {}
        website = normalize_url(tags.get("website") or tags.get("contact:website") or "")
        name = base.clean_text(tags.get("name") or tags.get("operator"))
        address = base.address_text({str(k): str(v) for k, v in tags.items()}, row.get("city_hint", ""), row.get("country", ""))
        phone = base.first_phone({str(k): str(v) for k, v in tags.items()})
        if not website or not name or not address:
            continue
        if "phone" in missing and not phone:
            # Phone-only extraction is noisier, so deprioritize it unless the
            # website later provides a clean phone. These rows remain eligible.
            pass
        key = candidate_key(row)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)

    country_rank = {
        "United States": 0,
        "Japan": 1,
        "Singapore": 2,
        "Malaysia": 3,
        "Thailand": 4,
        "Vietnam": 5,
        "Indonesia": 6,
        "Philippines": 7,
        "Cambodia": 8,
        "Laos": 9,
        "Myanmar": 10,
        "Brunei": 11,
        "Timor-Leste": 12,
    }

    def rank(row: dict[str, Any]) -> tuple[int, int, str, str]:
        missing = set(row.get("missing") or [])
        tags = row.get("tags") or {}
        term_blob = " ".join(str(value) for value in tags.values())
        term_rank = 0 if LOCAL_LAB_DISTRIBUTOR_RE.search(term_blob) else 1
        missing_rank = 0 if missing == {"email"} else 1
        return (
            term_rank,
            missing_rank,
            country_rank.get(row.get("country", ""), 99),
            row.get("city_hint", ""),
            candidate_key(row),
        )

    selected.sort(key=rank)
    return selected[:limit]


def promote(row: dict[str, Any], inspection: dict[str, Any]) -> base.Prospect | None:
    tags = {str(k): str(v) for k, v in (row.get("tags") or {}).items()}
    name = base.clean_text(tags.get("name") or tags.get("operator"))
    address = base.address_text(tags, row.get("city_hint", ""), row.get("country", ""))
    phone = base.first_phone(tags) or inspection.get("phone", "")
    emails = inspection.get("emails") or []
    email = emails[0] if emails else ""
    if not (name and address and phone and email):
        return None
    segment, reason, dof_fit = base.segment_and_reason(tags)
    website = normalize_url(tags.get("website") or tags.get("contact:website") or inspection.get("website") or "")
    evidence = [
        f"OSM source: {row.get('source_url')}",
        f"Required contact fields completed with website crawl: email={email}, phone={phone}, address={address}",
    ]
    for fetched in inspection.get("fetched", [])[:3]:
        evidence.append(f"Website checked: {fetched}")
    return base.Prospect(
        name=name,
        country=row.get("country", ""),
        city_hint=row.get("city_hint", ""),
        segment=segment,
        email=email,
        phone=phone,
        address=address,
        website=website,
        source_url=website or row.get("source_url", ""),
        source_type="OSM public tag + official website contact extraction",
        selection_reason=reason,
        dof_fit=dof_fit,
        evidence=evidence,
        osm_type=str(row.get("source_url", "").rstrip("/").split("/")[-2]) if "/" in str(row.get("source_url")) else "",
        osm_id=int(str(row.get("source_url", "0")).rstrip("/").split("/")[-1]) if str(row.get("source_url", "")).rstrip("/").split("/")[-1].isdigit() else 0,
        tags=tags,
        collected_at=datetime.now().isoformat(timespec="seconds"),
    )


def append_promotions(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with ENRICH_LOG_JSONL.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=7151)
    parser.add_argument("--max-sites", type=int, default=2500)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--chunk-size", type=int, default=120)
    parser.add_argument("--card-limit", type=int, default=8000)
    parser.add_argument("--skip-cards", action="store_true", help="Do not regenerate per-company markdown cards during enrichment.")
    parser.add_argument("--start-offset", type=int, default=0, help="Start from this candidate offset after ranking.")
    parser.add_argument(
        "--countries",
        default="",
        help="Comma-separated country names. Empty uses the original US/Japan/SEA set; ALL uses every country present in incomplete rows.",
    )
    args = parser.parse_args(argv)

    valid_by_key = base.existing_valid()
    sources = load_json(base.RAW_SOURCES_JSON, [])
    cache: dict[str, dict[str, Any]] = load_json(ENRICH_CACHE_JSON, {})
    incomplete_rows = read_incomplete()
    if args.countries.upper() == "ALL":
        target_countries = {str(row.get("country") or "") for row in incomplete_rows if row.get("country")}
    elif args.countries:
        target_countries = {country.strip() for country in args.countries.split(",") if country.strip()}
    else:
        target_countries = set(DEFAULT_TARGET_COUNTRIES)
    candidates = build_candidates(incomplete_rows, args.max_sites, target_countries)
    print(
        json.dumps(
            {
                "existingValid": len(valid_by_key),
                "candidates": len(candidates),
                "target": args.target,
                "countries": len(target_countries),
            },
            ensure_ascii=False,
        )
    )

    promoted_records: list[dict[str, Any]] = []
    for offset in range(max(args.start_offset, 0), len(candidates), args.chunk_size):
        if len(valid_by_key) >= args.target:
            break
        chunk = candidates[offset : offset + args.chunk_size]
        todo = [row for row in chunk if candidate_key(row) not in cache]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(inspect_website, row): row for row in todo}
            for future in as_completed(futures):
                row = futures[future]
                key = candidate_key(row)
                try:
                    cache[key] = future.result()
                except Exception as exc:  # noqa: BLE001
                    cache[key] = {"status": "error", "errors": [f"{type(exc).__name__}: {exc}"]}
        save_json(ENRICH_CACHE_JSON, cache)

        new_count = 0
        for row in chunk:
            prospect = promote(row, cache.get(candidate_key(row), {}))
            if not prospect:
                continue
            key = base.dedupe_key(prospect)
            if key in valid_by_key:
                continue
            valid_by_key[key] = prospect
            new_count += 1
            promoted_records.append({"source_url": row.get("source_url"), "website": prospect.website, **asdict(prospect)})
        append_promotions(promoted_records)
        promoted_records = []
        prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
        base.rewrite_valid(prospects)
        if not args.skip_cards:
            base.write_cards(prospects, limit=args.card_limit)
        base.write_readme(prospects, sources, args.target)
        print(
            json.dumps(
                {
                    "chunk": f"{offset}-{offset + len(chunk)}",
                    "newPromoted": new_count,
                    "totalValid": len(valid_by_key),
                    "cacheSize": len(cache),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        time.sleep(0.5)

    prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
    base.rewrite_valid(prospects)
    if not args.skip_cards:
        base.write_cards(prospects, limit=args.card_limit)
    base.write_readme(prospects, sources, args.target)
    print(json.dumps({"done": True, "valid": len(prospects), "target": args.target, "cache": len(cache)}, ensure_ascii=False, indent=2))
    return 0 if len(prospects) >= args.target else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
