#!/usr/bin/env python3
"""Promote website-backed incomplete prospects using curl process timeouts."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import dof_prospect_scale5000 as base
import dof_enrich_incomplete_websites as enrich


FAST_CACHE_JSON = enrich.DATA_DIR / "website_enrichment_fast_cache.json"
FAST_LOG_JSONL = enrich.DATA_DIR / "website_enrichment_fast_promotions.jsonl"


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def curl_text(url: str) -> tuple[str, str]:
    cmd = [
        "curl",
        "-L",
        "--silent",
        "--show-error",
        "--compressed",
        "--connect-timeout",
        "4",
        "--max-time",
        "9",
        "-A",
        "DOF customer prospect contact research (public company websites)",
        "-H",
        "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        url,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=11)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise TimeoutError(f"curl timed out: {url}") from exc
    result = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).decode("utf-8", errors="ignore")[:300])
    return url, result.stdout[:500_000].decode("utf-8", errors="ignore")


def fast_contact_links(base_url: str, html: str) -> list[str]:
    links: list[str] = []
    for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.I):
        lowered = href.lower()
        if any(hint.lower() in lowered for hint in enrich.CONTACT_PATH_HINTS):
            url = enrich.same_site(base_url, href)
            if url and url not in links:
                links.append(url)
        if len(links) >= 3:
            break
    for fallback in ("/contact", "/kontakt", "/impressum"):
        url = enrich.same_site(base_url, urljoin(base_url, fallback))
        if url and url not in links:
            links.append(url)
        if len(links) >= 3:
            break
    return links


def inspect_fast(row: dict[str, Any]) -> dict[str, Any]:
    tags = row.get("tags") or {}
    website = enrich.normalize_url(tags.get("website") or tags.get("contact:website") or "")
    if not website:
        return {"status": "no_website", "website": ""}
    fetched: list[str] = []
    texts: list[str] = []
    errors: list[str] = []
    try:
        page_url, html = curl_text(website)
        if html:
            fetched.append(page_url)
            texts.append(html)
            if enrich.extract_emails(html) and enrich.extract_phone(html):
                combined = "\n".join(texts)
                return {
                    "status": "ok",
                    "website": website,
                    "fetched": fetched,
                    "emails": enrich.extract_emails(combined)[:8],
                    "phone": enrich.extract_phone(combined),
                    "errors": errors,
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                }
            for link in fast_contact_links(page_url, html):
                if link in fetched:
                    continue
                try:
                    link_url, link_html = curl_text(link)
                    if link_html:
                        fetched.append(link_url)
                        texts.append(link_html)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{link}: {type(exc).__name__}: {exc}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{website}: {type(exc).__name__}: {exc}")
    combined = "\n".join(texts)
    return {
        "status": "ok" if texts else "fetch_failed",
        "website": website,
        "fetched": fetched,
        "emails": enrich.extract_emails(combined)[:8],
        "phone": enrich.extract_phone(combined),
        "errors": errors[:5],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def append_promotions(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with FAST_LOG_JSONL.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run(args: argparse.Namespace) -> int:
    valid_by_key = base.existing_valid()
    rows = enrich.read_incomplete()
    if args.countries.upper() == "ALL":
        target_countries = {str(row.get("country") or "") for row in rows if row.get("country")}
    elif args.countries:
        target_countries = {country.strip() for country in args.countries.split(",") if country.strip()}
    else:
        target_countries = set(enrich.DEFAULT_TARGET_COUNTRIES)
    candidates = enrich.build_candidates(rows, args.max_sites, target_countries)
    old_cache: dict[str, dict[str, Any]] = load_json(enrich.ENRICH_CACHE_JSON, {})
    fast_cache: dict[str, dict[str, Any]] = load_json(FAST_CACHE_JSON, {})
    print(
        json.dumps(
            {
                "existingValid": len(valid_by_key),
                "candidates": len(candidates),
                "target": args.target,
                "oldCache": len(old_cache),
                "fastCache": len(fast_cache),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    for offset in range(max(args.start_offset, 0), len(candidates), args.chunk_size):
        if len(valid_by_key) >= args.target:
            break
        chunk = candidates[offset : offset + args.chunk_size]
        todo = [row for row in chunk if enrich.candidate_key(row) not in old_cache and enrich.candidate_key(row) not in fast_cache]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(inspect_fast, row): row for row in todo}
            for future in as_completed(futures):
                row = futures[future]
                key = enrich.candidate_key(row)
                try:
                    fast_cache[key] = future.result()
                except Exception as exc:  # noqa: BLE001
                    fast_cache[key] = {"status": "error", "errors": [f"{type(exc).__name__}: {exc}"]}
        save_json(FAST_CACHE_JSON, fast_cache)

        promotions: list[dict[str, Any]] = []
        new_count = 0
        for row in chunk:
            key = enrich.candidate_key(row)
            result = old_cache.get(key) or fast_cache.get(key, {})
            prospect = enrich.promote(row, result)
            if not prospect:
                continue
            dedupe = base.dedupe_key(prospect)
            if dedupe in valid_by_key:
                continue
            valid_by_key[dedupe] = prospect
            new_count += 1
            promotions.append({"source_url": row.get("source_url"), "website": prospect.website, **asdict(prospect)})
        append_promotions(promotions)
        prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
        base.rewrite_valid(prospects)
        print(
            json.dumps(
                {
                    "chunk": f"{offset}-{offset + len(chunk)}",
                    "checked": len(todo),
                    "newPromoted": new_count,
                    "totalValid": len(valid_by_key),
                    "fastCache": len(fast_cache),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
    base.rewrite_valid(prospects)
    print(json.dumps({"done": True, "valid": len(prospects), "target": args.target, "fastCache": len(fast_cache)}, ensure_ascii=False, indent=2))
    return 0 if len(prospects) >= args.target else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--countries", default="ALL")
    parser.add_argument("--max-sites", type=int, default=50000)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--chunk-size", type=int, default=80)
    parser.add_argument("--start-offset", type=int, default=0)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
