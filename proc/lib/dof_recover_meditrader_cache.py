#!/usr/bin/env python3
"""Recover Meditrader prospects from the large direct-directory cache.

The main direct-directory collector keeps the full cache in memory. For the
large Meditrader directory this can exceed local memory before the source-level
result is written. This helper streams the cache JSON object and only materializes
one cached response at a time.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Iterator

from bs4 import BeautifulSoup

import dof_prospect_scale5000 as base
from dof_direct_directory_scrapers import (
    CACHE_JSON,
    PROMOTIONS_JSONL,
    RAW_JSONL,
    append_jsonl,
    clean,
    extract_phone,
    first_external_website,
    make_prospect,
    meditrader_address,
    meditrader_category,
    meditrader_name,
    meditrader_segment,
    public_emails,
)


MEDITRADER_PREFIX = "https://mail.meditrader.co.za/"


def stream_json_object(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[tuple[str, Any]]:
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as f:
        buffer = ""
        eof = False

        def ensure() -> None:
            nonlocal buffer, eof
            if not eof:
                chunk = f.read(chunk_size)
                if chunk:
                    buffer += chunk
                else:
                    eof = True

        def skip_ws(pos: int) -> int:
            while True:
                while pos < len(buffer) and buffer[pos].isspace():
                    pos += 1
                if pos < len(buffer):
                    return pos
                if eof:
                    return pos
                ensure()

        ensure()
        pos = skip_ws(0)
        if pos >= len(buffer) or buffer[pos] != "{":
            raise ValueError(f"{path} is not a JSON object")
        pos += 1

        while True:
            pos = skip_ws(pos)
            while pos >= len(buffer) and not eof:
                ensure()
                pos = skip_ws(pos)
            if pos < len(buffer) and buffer[pos] == "}":
                return
            if pos < len(buffer) and buffer[pos] == ",":
                pos += 1
                pos = skip_ws(pos)

            while True:
                try:
                    key, end = decoder.raw_decode(buffer, pos)
                    break
                except JSONDecodeError:
                    if eof:
                        raise
                    ensure()
            if not isinstance(key, str):
                raise ValueError(f"Unexpected non-string key at offset {pos}")
            pos = skip_ws(end)
            if pos >= len(buffer):
                ensure()
                pos = skip_ws(pos)
            if pos >= len(buffer) or buffer[pos] != ":":
                raise ValueError(f"Expected ':' after key {key!r}")
            pos += 1
            pos = skip_ws(pos)

            while True:
                try:
                    value, end = decoder.raw_decode(buffer, pos)
                    break
                except JSONDecodeError:
                    if eof:
                        raise
                    ensure()
            yield key, value

            buffer = buffer[end:]
            pos = 0


def is_meditrader_profile_url(url: str) -> bool:
    if not url.startswith(MEDITRADER_PREFIX):
        return False
    blocked = (
        "controller=search",
        "/category/",
        "/members/",
        "/component/",
        "/media/",
        "/templates/",
        "/images/",
        "/about-",
        "/for-",
        "/medical-trader-home",
    )
    return not any(part in url for part in blocked)


def parse_cached_profile(url: str, html: str) -> base.Prospect | None:
    if not html.strip():
        return None
    soup = BeautifulSoup(html, "html.parser")
    lines = [clean(line) for line in soup.get_text("\n", strip=True).splitlines() if clean(line)]
    text = "\n".join(lines)
    if "DENTISTRY" not in lines and "Dental Laboratory" not in text and "Dentist" not in text:
        return None

    emails = [email for email in public_emails(html, ("meditrader.co.za",)) if not email.endswith("@example.com")]
    phones = [clean(phone) for phone in re.findall(r'href="tel:([^"]+)"', html)]
    phone = next((value for value in phones if 7 <= len(re.sub(r"\D", "", value)) <= 16), "")
    if not phone:
        phone = extract_phone(text)
    address = meditrader_address(lines)
    category = meditrader_category(lines)
    name = meditrader_name(lines, category)
    website = first_external_website(html, ("meditrader.co.za", "google.com"))
    segment = meditrader_segment(category, name, text)
    return make_prospect(
        name=name,
        country="South Africa",
        city_hint="",
        segment=segment,
        email=emails[0] if emails else "",
        phone=phone,
        address=address,
        website=website,
        source_url=url,
        source_type="Meditrader South Africa public dental business directory",
        evidence=[
            f"Meditrader profile: {url}",
            f"Category: {category}" if category else "Meditrader dentistry profile.",
            f"Required contact fields found: email={emails[0] if emails else ''}, phone={phone}, address={address}",
        ],
        tags={"directory": "Meditrader South Africa", "category": category},
    )


def run(target: int, limit: int | None) -> int:
    before_by_key = base.existing_valid()
    valid_by_key = dict(before_by_key)
    promotions: list[base.Prospect] = []
    raw_rows: list[dict[str, object]] = []
    scanned = 0
    parsed_profiles = 0

    for url, record in stream_json_object(CACHE_JSON):
        scanned += 1
        if not is_meditrader_profile_url(url):
            continue
        html = str(record.get("text", "")) if isinstance(record, dict) else str(record)
        parsed_profiles += 1
        prospect = parse_cached_profile(url, html)
        if not prospect:
            continue
        raw_rows.append({"source": "meditrader_cache_recovery", **asdict(prospect)})
        key = base.dedupe_key(prospect)
        if key in valid_by_key:
            continue
        valid_by_key[key] = prospect
        promotions.append(prospect)
        if limit and len(promotions) >= limit:
            break
        if len(valid_by_key) >= target:
            break

    if raw_rows:
        append_jsonl(RAW_JSONL, raw_rows)
    if promotions:
        append_jsonl(PROMOTIONS_JSONL, [{"source": "meditrader_cache_recovery", **asdict(row)} for row in promotions])
    prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
    base.rewrite_valid(prospects)
    print(
        json.dumps(
            {
                "source": "meditrader_cache_recovery",
                "scannedCacheEntries": scanned,
                "parsedMeditraderProfiles": parsed_profiles,
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
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    return run(args.target, args.limit or None)


if __name__ == "__main__":
    raise SystemExit(main())
