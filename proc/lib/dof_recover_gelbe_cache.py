#!/usr/bin/env python3
"""Recover Gelbe Seiten prospects from a source-specific cache."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

import dof_prospect_scale5000 as base
from dof_direct_directory_scrapers import PROMOTIONS_JSONL, RAW_JSONL, append_jsonl, clean, extract_emails, make_prospect
from dof_recover_meditrader_cache import stream_json_object


CATEGORY_SEGMENTS = {
    "dentallabor": "Dental laboratory / dental technician",
    "zahntechnik": "Dental laboratory / dental technician",
    "zahntechnische-laboratorien": "Dental laboratory / dental technician",
    "dentalbedarf": "Dental distributor / product supplier",
    "zahnarzt": "Dental clinic / practice",
}


def split_gelbe_listing_url(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    if parsed.netloc != "www.gelbeseiten.de":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 3 or parts[0] != "branchen":
        return None
    category = parts[1]
    city = parts[2]
    if category not in CATEGORY_SEGMENTS:
        return None
    return category, city


def parse_listing_page(url: str, html: str) -> list[base.Prospect]:
    parsed = split_gelbe_listing_url(url)
    if not parsed or not html.strip():
        return []
    category, city = parsed
    segment = CATEGORY_SEGMENTS[category]
    city_hint = unquote(city).replace("-", " ").title()
    soup = BeautifulSoup(html, "html.parser")
    prospects: list[base.Prospect] = []
    for item in soup.select("article.mod-Treffer"):
        item_html = str(item)
        emails = extract_emails(item_html)
        if not emails:
            continue
        lines = [clean(line) for line in item.get_text("\n", strip=True).splitlines() if clean(line)]
        if not lines:
            continue
        name = lines[0]
        phone = ""
        for line in reversed(lines):
            digits = re.sub(r"\D", "", line)
            if 7 <= len(digits) <= 16:
                phone = line
                break
        address = ""
        for i, line in enumerate(lines):
            if re.search(r"\b\d{5}\b", line):
                previous = lines[i - 1] if i else ""
                address = clean(", ".join(part for part in [previous, line, "Germany"] if part))
                break
        website = ""
        detail_url = url
        for a in item.find_all("a", href=True):
            href = a["href"]
            if "gelbeseiten.de/gsbiz/" in href:
                detail_url = href
            elif href.startswith("http") and "gelbeseiten.de" not in href:
                website = href
        prospect = make_prospect(
            name=name,
            country="Germany",
            city_hint=city_hint,
            segment=segment,
            email=emails[0],
            phone=phone,
            address=address,
            website=website,
            source_url=detail_url,
            source_type="Gelbe Seiten Germany public business directory",
            evidence=[
                f"Gelbe Seiten listing: {detail_url}",
                f"Category: {category}",
                f"Required contact fields found: email={emails[0]}, phone={phone}, address={address}",
            ],
            tags={"directory": "Gelbe Seiten", "category": category},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def run(cache_path: Path, target: int, limit: int | None) -> int:
    before_by_key = base.existing_valid()
    valid_by_key = dict(before_by_key)
    raw_rows: list[dict[str, object]] = []
    promotions: list[base.Prospect] = []
    scanned = 0
    parsed_pages = 0
    found = 0

    for url, record in stream_json_object(cache_path):
        scanned += 1
        if not split_gelbe_listing_url(url):
            continue
        parsed_pages += 1
        html = str(record.get("text", "")) if isinstance(record, dict) else str(record)
        for prospect in parse_listing_page(url, html):
            found += 1
            raw_rows.append({"source": "gelbeseiten_cache_recovery", **asdict(prospect)})
            key = base.dedupe_key(prospect)
            if key in valid_by_key:
                continue
            valid_by_key[key] = prospect
            promotions.append(prospect)
            if limit and len(promotions) >= limit:
                break
            if len(valid_by_key) >= target:
                break
        if (limit and len(promotions) >= limit) or len(valid_by_key) >= target:
            break

    if raw_rows:
        append_jsonl(RAW_JSONL, raw_rows)
    if promotions:
        append_jsonl(PROMOTIONS_JSONL, [{"source": "gelbeseiten_cache_recovery", **asdict(row)} for row in promotions])
    base.rewrite_valid(sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name)))
    print(
        json.dumps(
            {
                "source": "gelbeseiten_cache_recovery",
                "scannedCacheEntries": scanned,
                "parsedListingPages": parsed_pages,
                "foundValidListings": found,
                "added": len(promotions),
                "before": len(before_by_key),
                "after": len(valid_by_key),
                "target": target,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if len(valid_by_key) >= target else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-path", type=Path, required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    return run(args.cache_path, args.target, args.limit or None)


if __name__ == "__main__":
    raise SystemExit(main())
