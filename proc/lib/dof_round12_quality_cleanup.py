#!/usr/bin/env python3
"""Quality-gate the round12 scanner/milling/CAD-CAM prospect delta.

Round12 intentionally searched broadly across reseller/product/local-language
signals. This script keeps the official locator/PDF rows and stricter dental
business pages, rejects generic search-result noise, and archives any Outline
company docs created by an aborted pre-cleanup publish.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import dof_prospect_outline_publish as pub


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
BASE = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA = BASE / "data"
COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
BASELINE_JSONL = DATA / "backups/prospects_augmented_contact_complete.before_partial_round12_20260604_143856.jsonl"
PROMOTIONS_JSONL = DATA / "partial_distributor_promotions_round12.jsonl"
CLEAN_JSONL = DATA / "partial_distributor_promotions_round12_clean.jsonl"
REJECTED_JSONL = DATA / "partial_distributor_promotions_round12_rejected_quality.jsonl"
RESULT_JSON = BASE / "scanner_milling_cadcam_expansion_round12_result.json"
SUMMARY_MD = BASE / "scanner_milling_cadcam_expansion_round12.md"
ARCHIVE_RESULT_JSON = BASE / "outline_publish/outline_round12_aborted_docs_archive_result.json"


BLACK_DOMAINS = {
    "9to5mac.com",
    "accessforums.net",
    "apkpure.com",
    "business.facebook.com",
    "chiebukuro.yahoo.co.jp",
    "constantcontact.com",
    "crazygames.com",
    "deltadental.com",
    "dentallabnetwork.com",
    "dictionary.cambridge.org",
    "earthrepairradio.com",
    "elevenforum.com",
    "facebook.com",
    "fandom.com",
    "github.com",
    "google.com",
    "guitarcenter.com",
    "handelskammer.bz.it",
    "help.brother-usa.com",
    "alliedvision.cn",
    "brother-usa.com",
    "canon-elec.co.jp",
    "cmc.ph",
    "cybo.com",
    "ensun.io",
    "georgiaiplit.com",
    "globaldentex.com",
    "huvitz.com",
    "importgenius.com",
    "instituteofdigitaldentistry.com",
    "jamieoliver.com",
    "jkmsclbusiness.com",
    "linkedin.com",
    "maps.google.co.in",
    "mayoclinic.org",
    "medicalexpo.com",
    "medicalexpo.es",
    "member.sss.gov.ph",
    "microsoft.com",
    "myfonts.com",
    "nikki.ne.jp",
    "opentable.com.mx",
    "reddit.com",
    "reportsglobe.com",
    "rolanddga.com",
    "shofulabusa.com",
    "stackoverflow.com",
    "support.google.com",
    "support.microsoft.com",
    "safetyculture.com",
    "toboc.com",
    "tradewheel.com",
    "translate.google.co.th",
    "translate.google.com",
    "youtube.com",
    "zhihu.com",
}

VENDOR_SEARCH_DOMAINS = {
    "3shape.com",
    "amanngirrbach.com",
    "carestreamdental.com",
    "dentsplysirona.com",
    "dgshape.com",
    "exocad.com",
    "global.rolanddg.com",
    "imes-icore.com",
    "medit.com",
    "rolanddg.com.br",
    "shining3d.com",
    "shining3ddental.com",
    "vhf.com",
    "zirkonzahn.com",
    "zirkonzahn.biz",
    "yucera.com",
}

PRODUCT_TERMS = re.compile(
    r"(dental|odont|stomat|zahn|cad\W*cam|cadcam|exocad|trios|medit|aoralscan|"
    r"shining\s*3d|intraoral|intra\s*oral|oral scanner|scanner intraoral|scanner intraorale|"
    r"esc[aá]ner|milling|fresadora|fresa dental|dentallab|dental lab|歯科|牙科|口腔|치과|덴탈)",
    re.I,
)

BIZ_TERMS = re.compile(
    r"(dental|dent|odont|stomat|zahn|ortho|cadcam|cad\W*cam|exocad|medit|aoralscan|"
    r"shining\s*3d|3d\s*(dental|solutions)|scan|scanner|milling|fresadora|fresa|"
    r"laborator|lab|supply|depot|d[eé]p[oó]t|deposito|dep[oó]sito|clinic|"
    r"medicodental|bioinnovacion|picodent|technident|supplydoc|schelldental|dentopia|"
    r"dentcore|aurident|openbyte|sodium|roentgen|dentaltronador|shinoda|orthoflex|"
    r"novacek|orthoea|polidental|vitaldent|eurodent|dabiatlante|henryschein|patterson|"
    r"centraldental|mercadodental|edente|axsys|scannice|cad-ray|olympicdental|dent3d|"
    r"evoluteeth|dentaltix|vamasa|futura|orbidental|dentalspeed|doctorline)",
    re.I,
)

GENERIC_NAMES = re.compile(
    r"^(Brazil CAD/CAM|Brazil Dental|Canada$|Costa Rica$|Dental 3D Scanners|"
    r"Dental Lab Milling|Digital 3D Dental Scanner|Diseño Digital|DWX Series|"
    r"Escaneo 3D|Get your questions answered|Klicken|Need help|Su socio|The only Certified|"
    r"Todos los fabricantes|ToolMack, Dental Milling|Trade-in|What Are|Yucera$)",
    re.I,
)

NOISE_NAMES = re.compile(
    r"\b(APP|APK|Aadhaar|Atlanta|BT21|Biography|ChatGPT|DaVinci|Dodgers|Earth End User|"
    r"Facebook Help|GitHub|Google|Guitar|Jamie Oliver|Kimi|LinkedIn Learning|Michelin|"
    r"Microsoft|Naver|OpenAI|OpenTable|Practice Routine|SQL server|Uniqlo|Windows|Yahoo|"
    r"calculator|certificate|login|restaurant|skyscanner|stored procedure|百度知道|床垫|"
    r"高考|炒飯|豆包|通义|福彩|회원가입|証明書|สมัคร)\b",
    re.I,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def domain(url: Any) -> str:
    try:
        host = urlparse(str(url or "")).netloc.lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def domain_is(domain_value: str, candidates: set[str]) -> bool:
    return any(domain_value == candidate or domain_value.endswith(f".{candidate}") for candidate in candidates)


def tag(row: dict[str, Any], key: str) -> str:
    tags = row.get("tags") or {}
    return str(tags.get(key) or row.get(key) or "")


def text_blob(row: dict[str, Any]) -> str:
    evidence = row.get("evidence") or []
    evidence_text = " ".join(str(item) for item in evidence) if isinstance(evidence, list) else str(evidence)
    return " ".join(str(value or "") for value in [row.get("name"), row.get("website"), row.get("source_url"), evidence_text])


def is_quality_keep(row: dict[str, Any]) -> tuple[bool, str]:
    name = str(row.get("name") or "").strip()
    website_domain = domain(row.get("website"))
    source_domain = domain(row.get("source_url"))
    trust = tag(row, "source_trust")
    source_type = str(row.get("source_type") or "")

    if not name:
        return False, "empty_name"
    if name.lower() == "dof" or website_domain == "doflab.com":
        return False, "self_company"

    if source_type in {"vhf official global dental milling reseller page", "exocad official IDS 2025 reseller PDF"}:
        return True, "official_locator_or_pdf"

    if domain_is(website_domain, VENDOR_SEARCH_DOMAINS) or domain_is(source_domain, VENDOR_SEARCH_DOMAINS):
        return False, "vendor_homepage_search_result"
    if domain_is(website_domain, BLACK_DOMAINS) or domain_is(source_domain, BLACK_DOMAINS):
        return False, "blocked_generic_domain"
    if re.search(r"https?://| › |…|\.\.\.", name):
        return False, "search_result_title_not_company"
    if len(name) > 72:
        return False, "overlong_title"
    if NOISE_NAMES.search(name):
        return False, "known_noise_title"
    if GENERIC_NAMES.search(name):
        return False, "generic_product_or_article_title"
    if re.search(r"(blog|forum|thread|topic|question|market|report|news|press|guide|wiki|fandom|constantcontact)", str(row.get("source_url") or ""), re.I):
        return False, "content_or_forum_page"

    blob = text_blob(row)
    if not PRODUCT_TERMS.search(blob):
        return False, "missing_product_context"
    if not BIZ_TERMS.search(" ".join([name, website_domain, str(row.get("source_url") or "")])):
        return False, "missing_dental_business_signal"

    if trust == "medium-high":
        return True, "third_party_partner_or_reseller_page"
    if trust == "low-medium":
        return True, "localized_product_page_with_business_signal"
    return False, f"unsupported_trust:{trust or 'blank'}"


def title_from_domain(url: str) -> str:
    host = domain(url)
    if not host:
        return ""
    parts = [part for part in host.split(".") if part not in {"com", "co", "net", "org", "mx", "br", "ar", "cl", "ca", "pe", "es"}]
    if not parts:
        parts = [host.split(".")[0]]
    return " ".join(part.capitalize() for part in parts[-2:]).replace("-", " ")


def clean_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(row)
    name = str(cleaned.get("name") or "").strip()
    source_url = str(cleaned.get("source_url") or "")
    website = str(cleaned.get("website") or "")

    match = re.match(r"Comprar\s+.+?\s+en\s+(.+)$", name, re.I)
    if match:
        name = match.group(1).strip()
    name = re.sub(r"^\s*[-–]\s*", "", name).strip()
    if GENERIC_NAMES.search(name) or re.search(
        r"^(Distribuidor oficial|ESCANER INTRAORAL|Experts in Intra-Oral|Máquinas CAD/CAM|"
        r"Precisión y Fluidez Digital|Promoción exclusiva|Scanners intraorales|Tu aliado dental digital|"
        r"Fast Turnaround|American Made)",
        name,
        re.I,
    ):
        replacement = title_from_domain(website or source_url)
        if replacement:
            name = replacement
    cleaned["name"] = name
    return cleaned


def summarize(rows: list[dict[str, Any]], rejected: list[dict[str, Any]], baseline_count: int, backup_path: Path) -> dict[str, Any]:
    return {
        "afterRows": baseline_count + len(rows),
        "attemptedRound12Rows": len(rows) + len(rejected),
        "backupBeforeCleanup": str(backup_path),
        "beforeRows": baseline_count,
        "cleanRows": len(rows),
        "contactCompletenessCounts": dict(Counter(tag(row, "contact_completeness") or "unknown" for row in rows)),
        "promotionsJsonl": str(PROMOTIONS_JSONL.resolve()),
        "qualityRejectedRows": len(rejected),
        "rejectedJsonl": str(REJECTED_JSONL.resolve()),
        "segmentCounts": dict(Counter(row.get("segment") or "unknown" for row in rows)),
        "sourceCounts": dict(Counter(row.get("source_type") or "unknown" for row in rows)),
        "summaryMd": str(SUMMARY_MD.resolve()),
        "trustCounts": dict(Counter(tag(row, "source_trust") or "unknown" for row in rows)),
        "qualityRejectReasonCounts": dict(Counter(tag(row, "quality_reject_reason") or "unknown" for row in rejected)),
    }


def write_summary(result: dict[str, Any], clean_rows: list[dict[str, Any]], rejected_rows: list[dict[str, Any]]) -> None:
    country_counts = Counter(row.get("country") or "Unknown" for row in clean_rows)

    def bullets(counter: Counter[str], limit: int | None = None) -> str:
        return "\n".join(f"- {name}: {count:,}" for name, count in counter.most_common(limit))

    SUMMARY_MD.write_text(
        f"""# Round 12 scanner/milling/CAD-CAM focused prospect expansion

## Result after quality cleanup
- Mode: applied with post-search quality gate
- Baseline rows before Round12: {result['beforeRows']:,}
- Broad Round12 rows attempted: {result['attemptedRound12Rows']:,}
- Rejected as search/noise/vendor-homepage junk: {result['qualityRejectedRows']:,}
- Clean Round12 rows retained: {result['cleanRows']:,}
- Complete dataset rows after cleanup: {result['afterRows']:,}
- Backup before cleanup: `{result['backupBeforeCleanup']}`
- Rejected rows file: `{result['rejectedJsonl']}`

## Trust model
- high: official vendor reseller locator/PDF with explicit scanner, milling, or CAD-CAM reseller context.
- medium-high: third-party partner/reseller page with product/channel language.
- low-medium: localized public product page with dental business signal. These are lead seeds and need human sales triage before outreach.
- rejected: search-result titles, generic web pages, vendor homepages surfaced by search, forums/articles/directories without a concrete company lead, and DOF itself.

## Added by segment
{bullets(Counter(row.get('segment') or 'unknown' for row in clean_rows))}

## Added by source
{bullets(Counter(row.get('source_type') or 'unknown' for row in clean_rows))}

## Added by source trust
{bullets(Counter(tag(row, 'source_trust') or 'unknown' for row in clean_rows))}

## Added by contact completeness
{bullets(Counter(tag(row, 'contact_completeness') or 'unknown' for row in clean_rows))}

## Quality reject reasons
{bullets(Counter(tag(row, 'quality_reject_reason') or 'unknown' for row in rejected_rows), 20)}

## Top countries
{bullets(country_counts, 50)}

## Direct source families used
- vhf official dental reseller locator: https://www.vhf.com/en/contact/resellers-dental/
- exocad official IDS 2025 reseller PDF: https://bcontent.exocad.com/fileadmin/content/Events/IDS_2025/exocad_IDS_Reseller_List_EN_web.pdf
- Local-language targeted searches for Medit, Shining3D/Aoralscan, 3Shape/TRIOS, exocad, vhf, DGSHAPE/Roland, imes-icore/CORiTEC, Amann Girrbach/Ceramill, Zirkonzahn and scanner/milling/CAD-CAM terms.

## Notes
- OSM was not used as an acquisition source in this round.
- The earlier broad search produced many false positives, so the complete dataset was restored to the Round12 baseline plus only retained rows.
- The 3,000 target was attempted; only rows with defensible dental scanner/milling/CAD-CAM channel evidence were retained.
""",
        encoding="utf-8",
    )


def collect_created_round12_cache_docs(attempted_rows: list[dict[str, Any]], baseline_count: int) -> list[tuple[str, dict[str, Any]]]:
    cache = pub.load_json(pub.DOC_CACHE, {"docs": {}})
    docs = cache.get("docs") or {}
    enriched = pub.enrich_rows(read_jsonl(COMPLETE_JSONL))
    target_keys: set[str] = set()
    for row in enriched[baseline_count:]:
        key = pub.company_key(row["_region"], row["_country"], row)
        target_keys.add(key)
        suffix = key.removeprefix("company:")
        target_keys.update(k for k in docs if k.startswith("company:") and k.endswith(f":{suffix}"))
    return [(key, docs[key]) for key in sorted(target_keys) if isinstance(docs.get(key), dict) and docs[key].get("id")]


def archive_cached_docs(entries: list[tuple[str, dict[str, Any]]], dry_run: bool) -> dict[str, Any]:
    if not entries:
        result = {"archived": 0, "dryRun": dry_run, "documents": []}
        pub.save_json(ARCHIVE_RESULT_JSON, result)
        return result
    client = pub.OutlineClient(pub.read_env_key("DOF_OUTLINE_KEY"))
    cache = pub.load_json(pub.DOC_CACHE, {"docs": {}})
    archived: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for key, cached in entries:
        row = {"key": key, "id": cached.get("id"), "title": cached.get("title"), "url": cached.get("url")}
        if dry_run:
            archived.append(row | {"dryRun": True})
            continue
        try:
            client.archive_document(str(cached["id"]))
            archived.append(row)
            cache.get("docs", {}).pop(key, None)
            pub.save_json(pub.DOC_CACHE, cache)
            time.sleep(pub.PAUSE_SECONDS)
        except Exception as error:  # noqa: BLE001 - record and continue cleanup.
            errors.append(row | {"error": repr(error)})
    result = {"archived": len(archived), "dryRun": dry_run, "documents": archived, "errors": errors}
    pub.save_json(ARCHIVE_RESULT_JSON, result)
    return result


def run(dry_run: bool, archive_aborted_outline: bool) -> dict[str, Any]:
    baseline_rows = read_jsonl(BASELINE_JSONL)
    complete_rows = read_jsonl(COMPLETE_JSONL)
    attempted_rows = complete_rows[len(baseline_rows) :]
    clean_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    for row in attempted_rows:
        keep, reason = is_quality_keep(row)
        if keep:
            clean_rows.append(clean_row(row))
        else:
            rejected = dict(row)
            rejected.setdefault("tags", {})["quality_reject_reason"] = reason
            rejected_rows.append(rejected)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = DATA / "backups" / f"prospects_augmented_contact_complete.before_round12_quality_cleanup_{timestamp}.jsonl"
    created_cache_docs = collect_created_round12_cache_docs(attempted_rows, len(baseline_rows))
    archive_result = {"archived": 0, "dryRun": dry_run, "documents": []}
    if archive_aborted_outline:
        archive_result = archive_cached_docs(created_cache_docs, dry_run=dry_run)

    result = summarize(clean_rows, rejected_rows, len(baseline_rows), backup_path)
    result["abortedOutlineDocsFoundInCache"] = len(created_cache_docs)
    result["abortedOutlineArchiveResult"] = str(ARCHIVE_RESULT_JSON.resolve())
    result["abortedOutlineDocsArchived"] = archive_result.get("archived", 0)
    result["dryRun"] = dry_run

    if not dry_run:
        shutil.copy2(COMPLETE_JSONL, backup_path)
        write_jsonl(PROMOTIONS_JSONL, clean_rows)
        write_jsonl(CLEAN_JSONL, clean_rows)
        write_jsonl(REJECTED_JSONL, rejected_rows)
        write_jsonl(COMPLETE_JSONL, baseline_rows + clean_rows)
        pub.save_json(RESULT_JSON, result)
        write_summary(result, clean_rows, rejected_rows)

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--archive-aborted-outline", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run, archive_aborted_outline=args.archive_aborted_outline)
