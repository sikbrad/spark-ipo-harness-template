#!/usr/bin/env python3
"""Overlay portal companies onto the DOF overseas prospect dataset.

Reads active portal companies from the local portal DB, applies the saved
country-remediation result for rows whose local country is still empty, compares
portal customers against the prospect list, and writes augmented datasets.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
PORTAL_ROOT = Path("/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az")
BASE = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA_DIR = BASE / "data"
CARDS_DIR = BASE / "portal_addendum_cards"
REPORT = BASE / "portal_overlay_report.md"

PROSPECTS_JSONL = DATA_DIR / "prospects_valid.jsonl"
PORTAL_FOREIGN_JSONL = DATA_DIR / "portal_foreign_companies.jsonl"
PORTAL_FOREIGN_CSV = DATA_DIR / "portal_foreign_companies.csv"
MATCHES_JSONL = DATA_DIR / "portal_customer_matches.jsonl"
MATCHES_CSV = DATA_DIR / "portal_customer_matches.csv"
ADDITIONS_JSONL = DATA_DIR / "portal_foreign_additions.jsonl"
ADDITIONS_CSV = DATA_DIR / "portal_foreign_additions.csv"
ADDITIONS_COMPLETE_JSONL = DATA_DIR / "portal_foreign_additions_contact_complete.jsonl"
ADDITIONS_COMPLETE_CSV = DATA_DIR / "portal_foreign_additions_contact_complete.csv"
ADDITIONS_INCOMPLETE_JSONL = DATA_DIR / "portal_foreign_additions_contact_incomplete.jsonl"
ADDITIONS_INCOMPLETE_CSV = DATA_DIR / "portal_foreign_additions_contact_incomplete.csv"
AUGMENTED_JSONL = DATA_DIR / "prospects_augmented_with_portal.jsonl"
AUGMENTED_CSV = DATA_DIR / "prospects_augmented_with_portal.csv"
AUGMENTED_COMPLETE_JSONL = DATA_DIR / "prospects_augmented_contact_complete.jsonl"
AUGMENTED_COMPLETE_CSV = DATA_DIR / "prospects_augmented_contact_complete.csv"
PORTAL_RAW_JSON = DATA_DIR / "portal_active_companies_raw.json"

COUNTRY_UPDATE = ROOT / "output/portal-company-country-update-20260528/company-country-update-apply-result.json"
COUNTRY_CANDIDATES = ROOT / "output/portal-company-country-update-20260528/workbook-country-candidates.json"
FINAL_VERIFICATION = ROOT / "output/portal-company-country-update-20260528/company-country-update-final-verification.json"
COUNTRIES_JSON = PORTAL_ROOT / "output/portal-company-country-web-research-20260526/countries.json"

BAD_MATCH_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
    "google.com",
    "maps.google.com",
    "goo.gl",
    "wa.me",
    "whatsapp.com",
    "linktr.ee",
    "openstreetmap.org",
}

LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "gmbh",
    "co",
    "kg",
    "ag",
    "srl",
    "spa",
    "sa",
    "sas",
    "bv",
    "pte",
    "pty",
    "corp",
    "corporation",
    "company",
    "plc",
    "pvt",
    "private",
    "the",
}

FIELDNAMES = [
    "name",
    "country",
    "city_hint",
    "segment",
    "email",
    "phone",
    "address",
    "website",
    "source_url",
    "source_type",
    "selection_reason",
    "dof_fit",
    "validation_status",
    "portal_company_id",
    "portal_company_uk",
    "portal_orders_count",
    "portal_match_status",
    "portal_missing_contact_fields",
    "portal_country_source",
    "collected_at",
]

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
PLACEHOLDER_VALUES = {"", "-", ".", "n/a", "na", "none", "null", "doesnt have", "doesn't have", "no", "unknown"}


def read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value.strip().strip('"').strip("'")
    return env


def query_portal_companies() -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["node", str(ROOT / "proc/lib/dof_portal_query_companies.mjs")],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PORTAL_ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def country_overlay() -> dict[int, dict[str, Any]]:
    overlay: dict[int, dict[str, Any]] = {}
    apply_result = load_json(COUNTRY_UPDATE, {})
    for row in apply_result.get("updated", []):
        overlay[int(row["id"])] = {
            "country": row.get("targetCountry"),
            "source": "2026-05-28 portal country update apply result",
            "confidence": None,
            "evidence": row.get("currencyRule", ""),
        }
    for row in load_json(COUNTRY_CANDIDATES, []):
        company_id = int(row["id"])
        overlay.setdefault(
            company_id,
            {
                "country": row.get("country"),
                "source": "2026-05-28 country candidate workbook",
                "confidence": row.get("confidence"),
                "evidence": row.get("evidenceSummary", ""),
                "evidenceUrl": row.get("evidenceUrl", ""),
            },
        )
    return overlay


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def meaningful(value: Any) -> str:
    value = clean(value)
    if value.lower() in PLACEHOLDER_VALUES:
        return ""
    return value


def email_candidates_from_text(value: Any) -> list[str]:
    text = clean(value)
    if not text:
        return []
    # Repair common portal typo patterns such as "name@gmail. com" without
    # accepting arbitrary non-email text as an email.
    text = re.sub(r"(?<=\.)\s+(?=[A-Za-z]{2,}\b)", "", text)
    seen: set[str] = set()
    emails: list[str] = []
    for match in EMAIL_RE.findall(text):
        email = match.strip(" ;,").lower()
        if email not in seen:
            seen.add(email)
            emails.append(email)
    return emails


def has_valid_phone(value: Any) -> bool:
    value = meaningful(value)
    return bool(value and re.search(r"\d", value))


def has_valid_address(value: Any) -> bool:
    value = meaningful(value)
    if not value:
        return False
    return len(value) >= 4


def domain(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    if "@" in value and "://" not in value:
        value = value.split("@", 1)[1]
    if "://" not in value:
        value = "https://" + value
    host = urlparse(value).netloc.lower()
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def is_matchable_domain(value: str) -> bool:
    if not value:
        return False
    if value in BAD_MATCH_DOMAINS:
        return False
    return not any(value == d or value.endswith("." + d) for d in BAD_MATCH_DOMAINS)


def normalize_name(value: str) -> str:
    text = clean(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9가-힣]+", " ", text)
    tokens = [t for t in text.split() if t and t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def country_name_map() -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for row in load_json(COUNTRIES_JSON, []):
        alpha2 = row.get("alpha2")
        if not alpha2:
            continue
        names = {alpha2, clean(row.get("nameEn")), clean(row.get("nameKr"))}
        if alpha2 == "US":
            names.add("United States")
        if alpha2 == "GB":
            names.add("United Kingdom")
            names.add("UK")
        if alpha2 == "KR":
            names.add("South Korea")
        mapping[alpha2] = {n.lower() for n in names if n}
    return mapping


COUNTRY_NAME_MAP = country_name_map()


def same_country(portal_alpha2: str, prospect_country: str) -> bool:
    country = clean(prospect_country).lower()
    return bool(country and country in COUNTRY_NAME_MAP.get(portal_alpha2, {portal_alpha2.lower()}))


def preferred_email(company: dict[str, Any]) -> str:
    for key in ("email", "email2"):
        values = email_candidates_from_text(company.get(key))
        if values:
            return values[0]
    for customer in company.get("customers", []):
        values = email_candidates_from_text(customer.get("email"))
        if values:
            return values[0]
    return ""


def all_emails(company: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    values.update(email_candidates_from_text(company.get("email")))
    values.update(email_candidates_from_text(company.get("email2")))
    for customer in company.get("customers", []):
        values.update(email_candidates_from_text(customer.get("email")))
    return values


def preferred_phone(company: dict[str, Any]) -> str:
    for key in ("phone", "mobile1", "mobile2"):
        value = meaningful(company.get(key))
        if has_valid_phone(value):
            return value
    for customer in company.get("customers", []):
        for key in ("phone", "officePhone"):
            value = meaningful(customer.get(key))
            if has_valid_phone(value):
                return value
    return ""


def preferred_address(company: dict[str, Any]) -> str:
    parts = [clean(company.get("zipCode")), clean(company.get("address")), clean(company.get("addressDetail"))]
    direct = ", ".join(p for p in parts if p)
    if has_valid_address(direct):
        return direct
    for addr in company.get("shipping_addresses", []):
        parts = [clean(addr.get("zipCode")), clean(addr.get("address")), clean(addr.get("addressDetail"))]
        value = ", ".join(p for p in parts if p)
        if has_valid_address(value):
            return value
    return ""


def segment_for(company: dict[str, Any]) -> str:
    blob = " ".join(
        clean(company.get(k))
        for k in ("name", "businessName", "type", "website")
    ).lower()
    if "lab" in blob or "laborator" in blob or "milling" in blob:
        return "Portal customer / dental lab or milling"
    if "dental" in blob or "dent" in blob:
        return "Portal customer / dental business"
    if company.get("type") == "DEALER":
        return "Portal customer / dealer or channel"
    return "Portal customer / overseas account"


def source_url_for(company: dict[str, Any], overlay: dict[str, Any] | None) -> str:
    if clean(company.get("website")):
        return clean(company.get("website"))
    if overlay and clean(overlay.get("evidenceUrl")):
        return clean(overlay.get("evidenceUrl"))
    return f"https://portal.doflab.com/companies/{company['id']}"


def prospect_from_portal(company: dict[str, Any], resolved_country: str, overlay_info: dict[str, Any] | None, match_status: str) -> dict[str, Any]:
    orders_count = int(company.get("orders_count") or 0)
    contracts_count = int(company.get("contracts_count") or 0)
    reason_bits = [
        "DOF portal에 이미 등록된 해외 고객사이므로 기존 거래/영업 관계 또는 리드 이력이 확인된다."
    ]
    if orders_count:
        reason_bits.append(f"포털 주문 {orders_count}건이 연결되어 실제 고객 활동 근거가 있다.")
    if contracts_count:
        reason_bits.append(f"계약 {contracts_count}건이 연결되어 있다.")
    if overlay_info and overlay_info.get("source"):
        reason_bits.append(f"국가 근거: {overlay_info['source']}.")
    email = preferred_email(company)
    phone = preferred_phone(company)
    address = preferred_address(company)
    missing = [k for k, v in {"email": email, "phone": phone, "address": address}.items() if not v]
    status = "portal_foreign_contact_complete" if not missing else "portal_foreign_contact_incomplete"
    return {
        "name": clean(company.get("name")),
        "country": resolved_country,
        "city_hint": "",
        "segment": segment_for(company),
        "email": email,
        "phone": phone,
        "address": address,
        "website": clean(company.get("website")),
        "source_url": source_url_for(company, overlay_info),
        "source_type": "DOF portal Company",
        "selection_reason": " ".join(reason_bits),
        "dof_fit": "Existing DOF account: prioritize account expansion, scanner replacement, service renewal, or channel follow-up depending on account type.",
        "evidence": [
            f"portal company id={company['id']}",
            f"portal type={company.get('type')}",
            f"orders_count={orders_count}",
            f"contracts_count={contracts_count}",
        ],
        "validation_status": status,
        "portal_company_id": company["id"],
        "portal_company_uk": company["uk"],
        "portal_orders_count": orders_count,
        "portal_match_status": match_status,
        "portal_missing_contact_fields": missing,
        "portal_country_source": overlay_info.get("source") if overlay_info else "Company.country",
        "collected_at": datetime.now().isoformat(timespec="seconds"),
    }


@dataclass
class Match:
    portal_company_id: int
    portal_name: str
    portal_country: str
    prospect_name: str
    prospect_country: str
    match_type: str
    match_value: str
    score: float
    prospect_source_url: str


def load_prospects() -> list[dict[str, Any]]:
    rows = []
    with PROSPECTS_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_indexes(prospects: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    by_email: dict[str, list[dict[str, Any]]] = {}
    by_domain: dict[str, list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for prospect in prospects:
        email = clean(prospect.get("email")).lower()
        if email:
            by_email.setdefault(email, []).append(prospect)
        for value in (prospect.get("website"), prospect.get("source_url")):
            d = domain(clean(value))
            if d and is_matchable_domain(d):
                by_domain.setdefault(d, []).append(prospect)
        name_key = normalize_name(clean(prospect.get("name")))
        if name_key:
            by_name.setdefault(name_key, []).append(prospect)
    return by_email, by_domain, by_name


def find_match(company: dict[str, Any], resolved_country: str, indexes: tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]], prospects: list[dict[str, Any]]) -> Match | None:
    by_email, by_domain, by_name = indexes
    for email in sorted(all_emails(company)):
        if email in by_email:
            p = by_email[email][0]
            return Match(company["id"], company["name"], resolved_country, p["name"], p["country"], "email_exact", email, 1.0, p["source_url"])
    for value in (company.get("website"),):
        d = domain(clean(value))
        if d and is_matchable_domain(d) and d in by_domain:
            p = by_domain[d][0]
            return Match(company["id"], company["name"], resolved_country, p["name"], p["country"], "domain_exact", d, 0.99, p["source_url"])
    keys = [normalize_name(clean(company.get("name"))), normalize_name(clean(company.get("businessName")))]
    for key in [k for k in keys if k]:
        if key in by_name:
            country_matches = [p for p in by_name[key] if same_country(resolved_country, p.get("country", ""))]
            if country_matches:
                p = country_matches[0]
                return Match(company["id"], company["name"], resolved_country, p["name"], p["country"], "name_exact_normalized_same_country", key, 0.98, p["source_url"])
    return None


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = row.copy()
            for key, value in list(flat.items()):
                if isinstance(value, (list, dict)):
                    flat[key] = json.dumps(value, ensure_ascii=False)
            writer.writerow(flat)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return s.strip("-")[:80] or "portal-customer"


def write_cards(rows: list[dict[str, Any]]) -> None:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    for old in CARDS_DIR.glob("*.md"):
        old.unlink()
    for idx, row in enumerate(rows, start=1):
        path = CARDS_DIR / f"{idx:04d}-{slug(row['name'])}.md"
        missing = ", ".join(row.get("portal_missing_contact_fields") or []) or "없음"
        content = f"""# {row['name']}

- Portal company id: {row['portal_company_id']}
- Country: {row['country']}
- Segment: {row['segment']}
- Email: {row.get('email') or '미확인'}
- Phone/contact: {row.get('phone') or '미확인'}
- Address: {row.get('address') or '미확인'}
- Website/source: {row.get('source_url')}
- Portal match status: {row.get('portal_match_status')}
- Missing contact fields: {missing}

## 선정이유
{row['selection_reason']}

## DOF 관점
{row['dof_fit']}
"""
        path.write_text(content, encoding="utf-8")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    prospects = load_prospects()
    portal = query_portal_companies()
    PORTAL_RAW_JSON.write_text(json.dumps(portal, ensure_ascii=False, indent=2), encoding="utf-8")
    overlay = country_overlay()
    indexes = build_indexes(prospects)

    portal_with_country = []
    foreign = []
    for company in portal:
        country = clean(company.get("country"))
        overlay_info = overlay.get(int(company["id"]))
        if not country and overlay_info:
            country = clean(overlay_info.get("country"))
        company["_resolvedCountry"] = country
        company["_countryOverlay"] = overlay_info
        portal_with_country.append(company)
        if country and country != "KR":
            foreign.append(company)

    matches: list[Match] = []
    foreign_matches: list[Match] = []
    matched_foreign_ids: set[int] = set()
    matched_any_prospect_names: set[str] = set()
    matched_any_prospect_keys: set[str] = set()
    for company in portal_with_country:
        if not company["_resolvedCountry"]:
            continue
        match = find_match(company, company["_resolvedCountry"], indexes, prospects)
        if match:
            matches.append(match)
            matched_any_prospect_names.add(match.prospect_name)
            matched_any_prospect_keys.add(f"{match.prospect_name}|{match.prospect_source_url}")
            if company["_resolvedCountry"] != "KR":
                foreign_matches.append(match)
                matched_foreign_ids.add(company["id"])

    portal_foreign_rows: list[dict[str, Any]] = []
    additions: list[dict[str, Any]] = []
    for company in foreign:
        match_status = "already_in_found_prospects" if company["id"] in matched_foreign_ids else "portal_foreign_added"
        row = prospect_from_portal(company, company["_resolvedCountry"], company.get("_countryOverlay"), match_status)
        portal_foreign_rows.append(row)
        if company["id"] not in matched_foreign_ids:
            additions.append(row)

    augmented = list(prospects) + additions
    complete_additions = [row for row in additions if row["validation_status"] == "portal_foreign_contact_complete"]
    incomplete_additions = [row for row in additions if row["validation_status"] != "portal_foreign_contact_complete"]
    augmented_complete = list(prospects) + complete_additions

    write_jsonl(PORTAL_FOREIGN_JSONL, portal_foreign_rows)
    write_csv(PORTAL_FOREIGN_CSV, portal_foreign_rows, FIELDNAMES)
    write_jsonl(MATCHES_JSONL, [m.__dict__ for m in matches])
    write_csv(MATCHES_CSV, [m.__dict__ for m in matches], list(Match.__annotations__.keys()))
    write_jsonl(ADDITIONS_JSONL, additions)
    write_csv(ADDITIONS_CSV, additions, FIELDNAMES)
    write_jsonl(ADDITIONS_COMPLETE_JSONL, complete_additions)
    write_csv(ADDITIONS_COMPLETE_CSV, complete_additions, FIELDNAMES)
    write_jsonl(ADDITIONS_INCOMPLETE_JSONL, incomplete_additions)
    write_csv(ADDITIONS_INCOMPLETE_CSV, incomplete_additions, FIELDNAMES)
    write_jsonl(AUGMENTED_JSONL, augmented)
    write_csv(AUGMENTED_CSV, augmented, FIELDNAMES)
    write_jsonl(AUGMENTED_COMPLETE_JSONL, augmented_complete)
    write_csv(AUGMENTED_COMPLETE_CSV, augmented_complete, FIELDNAMES)
    write_cards(additions)

    from collections import Counter

    portal_country_counts = Counter(c["_resolvedCountry"] or "UNKNOWN" for c in portal_with_country)
    foreign_country_counts = Counter(c["_resolvedCountry"] for c in foreign)
    addition_status_counts = Counter(row["validation_status"] for row in additions)
    match_type_counts = Counter(m.match_type for m in matches)
    foreign_match_type_counts = Counter(m.match_type for m in foreign_matches)

    summary = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "portalActiveCompanies": len(portal),
        "portalCountryCounts": dict(portal_country_counts.most_common()),
        "portalForeignCompanies": len(foreign),
        "portalForeignCountryCounts": dict(foreign_country_counts.most_common()),
        "foundProspectsOriginal": len(prospects),
        "foundProspectsMatchingAnyPortalCompany": len(matched_any_prospect_keys),
        "portalForeignCompaniesAlreadyInFoundProspects": len(matched_foreign_ids),
        "portalForeignAdditions": len(additions),
        "portalForeignAdditionsContactComplete": len(complete_additions),
        "portalForeignAdditionsContactIncomplete": len(additions) - len(complete_additions),
        "augmentedWithPortalRows": len(augmented),
        "augmentedContactCompleteRows": len(augmented_complete),
        "matchTypeCounts": dict(match_type_counts),
        "foreignMatchTypeCounts": dict(foreign_match_type_counts),
        "finalVerificationSource": str(FINAL_VERIFICATION),
    }
    (DATA_DIR / "portal_overlay_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    sample_matches = "\n".join(
        f"- Portal `{m.portal_name}` ({m.portal_country}) -> Found `{m.prospect_name}` ({m.match_type}, {m.score:.2f})"
        for m in foreign_matches[:30]
    )
    sample_additions = "\n".join(
        f"- `{row['name']}` ({row['country']}) | {row['validation_status']} | {row.get('email') or 'email 없음'}"
        for row in additions[:50]
    )
    REPORT.write_text(
        f"""# Portal Customer Overlay

## Summary
- Portal active companies read: {summary['portalActiveCompanies']}
- Portal foreign companies after country overlay: {summary['portalForeignCompanies']}
- Original found prospects: {summary['foundProspectsOriginal']}
- Found prospects matching any portal company: {summary['foundProspectsMatchingAnyPortalCompany']}
- Portal foreign companies already present in found prospects: {summary['portalForeignCompaniesAlreadyInFoundProspects']}
- Portal foreign companies added as addendum: {summary['portalForeignAdditions']}
- Added portal companies with email+phone+address complete: {summary['portalForeignAdditionsContactComplete']}
- Added portal companies missing at least one contact field: {summary['portalForeignAdditionsContactIncomplete']}
- Augmented rows including all portal foreign additions: {summary['augmentedWithPortalRows']}
- Augmented contact-complete rows only: {summary['augmentedContactCompleteRows']}

## Portal Foreign Country Counts
{json.dumps(summary['portalForeignCountryCounts'], ensure_ascii=False, indent=2)}

## Match Type Counts
{json.dumps(summary['matchTypeCounts'], ensure_ascii=False, indent=2)}

## Sample Existing Matches
{sample_matches or '- No matches'}

## Sample Portal Additions
{sample_additions or '- No additions'}

## Files
- `data/portal_foreign_companies.jsonl`
- `data/portal_customer_matches.jsonl`
- `data/portal_foreign_additions.jsonl`
- `data/portal_foreign_additions_contact_complete.jsonl`
- `data/portal_foreign_additions_contact_incomplete.jsonl`
- `data/prospects_augmented_with_portal.jsonl`
- `data/prospects_augmented_contact_complete.jsonl`
- `portal_addendum_cards/`
""",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
