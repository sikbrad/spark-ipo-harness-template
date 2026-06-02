#!/usr/bin/env python3
"""Enrich prospect Outline pages with public source research."""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

import dof_outline_existing_customer_enrich as existing
import dof_prospect_outline_publish as publish


OUT_DIR = publish.PUBLISH_ROOT / "prospect_enrichment"
RESEARCH_JSONL = OUT_DIR / "prospect_research.jsonl"
SUMMARY_JSON = OUT_DIR / "prospect_enrichment_summary.json"
VERIFY_JSON = OUT_DIR / "prospect_outline_verification.json"

TODAY_LABEL = "2026-06-02"
SECTION_TITLE = f"## 공개 조사 보강 ({TODAY_LABEL})"
DEFAULT_WORKERS = 8

OFFICIAL_OR_STRONG_SOURCES = [
    "official website contact extraction",
    "VDDI German dental industry member directory API",
    "Swiss Dental Laboratories VZLS public lab finder",
    "NBC Certified Dental Laboratories public directory",
    "HealthSpace Philippines public healthcare directory",
    "vhf dental reseller directory",
    "Bredent global distributor locator",
    "Henry Schein international distributor locator",
    "Ivoclar BPS public dental laboratory directory",
    "German Pavilion dental trade fair exhibitor directory",
    "Italian Trade Agency AEEDC 2026 Italian Pavilion PDF",
]
INDUSTRY_DIRECTORY_SOURCES = [
    "LMTmag dental laboratory and supplier company directory",
    "Modern Dentistry Media dental directory PDF 2024",
    "Myerson authorized EMA dental laboratory PDF list",
    "Meditrader South Africa public dental business directory",
    "CompeDent dental laboratory network directory",
    "Gelbe Seiten Germany public business directory",
    "local.ch Switzerland public yellow pages directory",
    "USA Dental Products regional supplier directory",
]
EVENT_OR_MEDIA_TERMS = re.compile(
    r"(German Pavilion|AEEDC|exhibitor|trade fair|pavilion|LMTmag|Modern Dentistry Media|conference|expo|exhibition|IDS|CAPP)",
    re.I,
)

_thread_local = threading.local()


@dataclass(frozen=True)
class ProspectDoc:
    key: str
    doc_id: str
    title: str
    url: str
    status: str
    country_key: str
    row: dict[str, Any]


def session_for(api_key: str) -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {api_key}"})
        _thread_local.session = session
    return session


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def source_contains(source_type: str, candidates: list[str]) -> bool:
    lower = source_type.lower()
    return any(candidate.lower() in lower for candidate in candidates)


def infer_services(row: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(row.get("name") or ""),
            str(row.get("segment") or ""),
            str(row.get("dof_fit") or ""),
            str(row.get("selection_reason") or ""),
            str(row.get("source_type") or ""),
            " ".join(str(item) for item in (row.get("evidence") or [])[:5] if isinstance(row.get("evidence"), list)),
            " ".join(str(value) for value in (row.get("tags") or {}).values()) if isinstance(row.get("tags"), dict) else "",
        ]
    )
    found = existing.infer_services(text)
    segment = str(row.get("segment") or "").lower()
    if "orthodont" in segment and "교정치료/교정치과" not in found:
        found.insert(0, "교정치료/교정치과")
    if ("distributor" in segment or "supplier" in segment) and "치과 유통/장비 공급" not in found:
        found.insert(0, "치과 유통/장비 공급")
    if ("laboratory" in segment or "lab" in segment) and "치기공/보철 제작" not in found:
        found.insert(0, "치기공/보철 제작")
    if ("clinic" in segment or "practice" in segment) and "치과 병·의원 진료" not in found:
        found.insert(0, "치과 병·의원 진료")
    return list(dict.fromkeys(found))[:5]


def exposure_summary(source_type: str, row: dict[str, Any]) -> tuple[str, bool]:
    evidence_text = " ".join(str(item) for item in (row.get("evidence") or [])[:5] if isinstance(row.get("evidence"), list))
    text = f"{source_type} {evidence_text}"
    if EVENT_OR_MEDIA_TERMS.search(text):
        return ("전시·업계 매체·행사성 디렉터리 노출이 확인됨.", True)
    if source_contains(source_type, ["VDDI", "VZLS", "NBC Certified", "HealthSpace", "Bredent", "Henry Schein", "Ivoclar", "vhf"]):
        return ("협회·인증·제조사/유통사 locator 등 공식성 있는 디렉터리 노출이 확인됨.", True)
    if source_contains(source_type, ["Gelbe Seiten", "local.ch", "OpenStreetMap", "Meditrader", "CompeDent"]):
        return ("공개 지도·업종 디렉터리 노출은 확인되지만, 별도 언론 기사성 노출은 확인하지 못함.", False)
    return ("명확한 언론 기사/행사 노출은 이번 공개 근거에서 확인하지 못함.", False)


def trust_for(row: dict[str, Any], has_exposure: bool) -> tuple[str, str]:
    source_type = str(row.get("source_type") or "")
    website = existing.normalize_url(row.get("website")) or existing.normalize_url(row.get("source_url"))
    evidence = row.get("evidence") or []
    has_evidence = bool(evidence)
    if source_contains(source_type, OFFICIAL_OR_STRONG_SOURCES) or (
        source_contains(source_type, ["official website contact extraction"]) and website
    ):
        return ("높음", "공식 웹사이트·협회·정부/공공·제조사 locator·전시 주최 측 등 상대적으로 공식성 있는 출처와 연락처 근거가 함께 있다.")
    if source_contains(source_type, INDUSTRY_DIRECTORY_SOURCES) or has_exposure:
        return ("중간", "업계 디렉터리·PDF·전시/미디어성 공개 자료에서 확인됐으나, 업체 공식 본문까지 모두 직접 확인한 것은 아니다.")
    if website and has_evidence:
        return ("중간", "웹사이트/출처 URL과 연락처 근거가 있으나, 출처가 일반 지도·공개 디렉터리 중심이다.")
    if source_contains(source_type, ["OpenStreetMap"]):
        return ("낮음", "공개 지도 태그와 연락처 기반이므로 동일성·업역 해석을 보수적으로 봐야 한다.")
    return ("낮음", "공개 수집 근거는 있으나 공식성 있는 추가 근거가 제한적이다.")


def evidence_lines(row: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    source_type = str(row.get("source_type") or "")
    source_url = str(row.get("source_url") or "")
    website = existing.normalize_url(row.get("website"))
    if source_url:
        lines.append(f"- 공개 출처: [{publish.md_escape(source_type or source_url)}]({source_url})")
    elif source_type:
        lines.append(f"- 공개 출처: {publish.md_escape(source_type)}")
    if website and website != source_url:
        lines.append(f"- 업체 웹사이트 후보: [{publish.md_escape(existing.domain_of(website) or website)}]({website})")
    evidence = row.get("evidence") or []
    if isinstance(evidence, list):
        for item in evidence[:4]:
            lines.append(f"- 근거 메모: {publish.md_escape(existing.compact(item, 260))}")
    elif evidence:
        lines.append(f"- 근거 메모: {publish.md_escape(existing.compact(evidence, 260))}")
    return lines


def research_prospect(doc: ProspectDoc) -> dict[str, Any]:
    row = doc.row
    source_type = str(row.get("source_type") or "")
    exposure, has_exposure = exposure_summary(source_type, row)
    trust, trust_reason = trust_for(row, has_exposure)
    services = infer_services(row)
    return {
        "key": doc.key,
        "doc_id": doc.doc_id,
        "title": doc.title,
        "outline_url": doc.url,
        "status": doc.status,
        "name": row.get("name"),
        "country": row.get("_country") or row.get("country"),
        "source_type": source_type,
        "source_url": row.get("source_url"),
        "website": row.get("website"),
        "services": services,
        "exposure": exposure,
        "has_exposure": has_exposure,
        "trust": trust,
        "trust_reason": trust_reason,
        "evidence": evidence_lines(row),
        "researched_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_section(research: dict[str, Any]) -> str:
    services = research.get("services") or []
    services_text = ", ".join(services) if services else "공개 출처만으로 구체 업역을 확정하기 어려움"
    lines = [
        SECTION_TITLE,
        "",
        "### 요약",
        "",
        "- 확인 방법: 기존 공개 수집 출처, 업체 웹사이트/출처 URL, 업계 디렉터리·협회·전시·PDF·지도 데이터 근거를 종합.",
        f"- 치과 관련 활동: {publish.md_escape(services_text)}.",
        f"- 언론·외부 노출: {publish.md_escape(research.get('exposure'))}",
        f"- 신뢰도: **{publish.md_escape(research.get('trust'))}** — {publish.md_escape(research.get('trust_reason'))}",
        "",
        "### 확인 근거",
        "",
    ]
    evidence = research.get("evidence") or []
    lines.extend(evidence if evidence else ["- 별도 근거 텍스트 없음."])
    lines += [
        "",
        "### 보수적 해석",
        "",
        "- 위 내용은 공개 웹·디렉터리·지도·PDF 수집 결과 기반이다. 동명 업체 가능성이나 오래된 디렉터리 정보가 있을 수 있어, 신뢰도 `중간` 이하 항목은 영업 전 재확인을 권장한다.",
    ]
    return "\n".join(lines).strip() + "\n"


def number_from_title(title: str) -> int:
    match = re.match(r"^(\d{1,5})\.", title or "")
    return int(match.group(1)) if match else 1


def build_document_text(doc: ProspectDoc, research: dict[str, Any]) -> str:
    row = doc.row
    body = publish.build_company_markdown(row["_region"], row["_country"], row, number_from_title(doc.title))
    return existing.replace_section(body, build_section(research))


def update_document(api_key: str, doc: ProspectDoc, research: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    text = build_document_text(doc, research)
    if dry_run:
        return {"key": doc.key, "title": doc.title, "updated": False, "changed": True, "text_len": len(text)}
    body = {"id": doc.doc_id, "title": doc.title, "text": text, "publish": True, "fullWidth": True}
    last_error = ""
    for attempt in range(1, 6):
        response = session_for(api_key).post(
            f"{publish.OUTLINE_BASE}/api/documents.update",
            json=body,
            timeout=publish.REQUEST_TIMEOUT,
        )
        if response.status_code < 400:
            data = response.json()["data"]
            return {
                "key": doc.key,
                "title": doc.title,
                "updated": True,
                "changed": True,
                "url": publish.doc_url(data),
                "text_len": len(text),
            }
        last_error = response.text[:500]
        if response.status_code in {429, 500, 502, 503, 504} and attempt < 5:
            time.sleep(min(30, attempt * 2))
            continue
        break
    return {"key": doc.key, "title": doc.title, "updated": False, "changed": False, "error": last_error}


def load_targets(limit: int | None = None) -> list[ProspectDoc]:
    cache = existing.load_json(publish.DOC_CACHE, {"docs": {}}).get("docs", {})
    country_docs = {value["id"]: key for key, value in cache.items() if key.startswith("country:")}
    rows = publish.enrich_rows(publish.read_jsonl(publish.COMPLETE_JSONL))
    row_by_key = {publish.company_key(row["_region"], row["_country"], row): row for row in rows}
    targets: list[ProspectDoc] = []
    for key, doc in sorted(cache.items(), key=lambda item: item[1].get("title", "")):
        if not key.startswith("company:") or key.startswith("company:portal:"):
            continue
        country_key = country_docs.get(doc.get("parent_document_id"), "")
        parts = country_key.split(":")
        status = parts[2] if len(parts) >= 4 else ""
        if not status.startswith("잠재고객-"):
            continue
        row = row_by_key.get(key)
        if not row:
            continue
        targets.append(
            ProspectDoc(
                key=key,
                doc_id=doc["id"],
                title=doc.get("title", ""),
                url=doc.get("url", ""),
                status=status,
                country_key=country_key,
                row=row,
            )
        )
        if limit and len(targets) >= limit:
            break
    return targets


def run(limit: int | None, workers: int, dry_run: bool, research_only: bool, update_only: bool) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = load_targets(limit)
    if update_only:
        research_by_key = {row["key"]: row for row in read_jsonl(RESEARCH_JSONL)}
        research_rows = [research_by_key[target.key] for target in targets if target.key in research_by_key]
    else:
        research_rows = [research_prospect(target) for target in targets]
        write_jsonl(RESEARCH_JSONL, research_rows)
        research_by_key = {row["key"]: row for row in research_rows}

    update_results: list[dict[str, Any]] = []
    if not research_only:
        api_key = publish.read_env_key("DOF_OUTLINE_KEY")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(update_document, api_key, target, research_by_key[target.key], dry_run): target
                for target in targets
                if target.key in research_by_key
            }
            for index, future in enumerate(as_completed(future_map), start=1):
                result = future.result()
                update_results.append(result)
                if index % 250 == 0 or index == len(future_map):
                    print(
                        json.dumps(
                            {
                                "updated_checked": index,
                                "target": len(future_map),
                                "updated": sum(1 for row in update_results if row.get("updated")),
                                "failed": sum(1 for row in update_results if row.get("error")),
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )

    trust_counts = Counter(row.get("trust") for row in research_rows)
    service_counts = Counter(service for row in research_rows for service in row.get("services", []))
    status_counts = Counter(row.get("status") for row in research_rows)
    source_counts = Counter(row.get("source_type") for row in research_rows)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_prospects": len(targets),
        "research_rows": len(research_rows),
        "status_counts": dict(status_counts),
        "trust_counts": dict(trust_counts),
        "service_counts": dict(service_counts),
        "top_source_counts": dict(source_counts.most_common(30)),
        "with_website": sum(1 for row in research_rows if existing.normalize_url(row.get("website"))),
        "with_event_or_external_exposure": sum(1 for row in research_rows if row.get("has_exposure")),
        "dry_run": dry_run,
        "research_only": research_only,
        "update_only": update_only,
        "updated": sum(1 for row in update_results if row.get("updated")),
        "failed": [row for row in update_results if row.get("error")],
        "research_jsonl": str(RESEARCH_JSONL),
    }
    save_json(SUMMARY_JSON, summary)
    return summary


def verify(limit: int | None = None, workers: int = DEFAULT_WORKERS) -> dict[str, Any]:
    targets = load_targets(limit)
    api_key = publish.read_env_key("DOF_OUTLINE_KEY")
    client_local = threading.local()

    def client() -> publish.OutlineClient:
        instance = getattr(client_local, "client", None)
        if instance is None:
            instance = publish.OutlineClient(api_key)
            client_local.client = instance
        return instance

    def check(target: ProspectDoc) -> dict[str, Any]:
        info = client().document_info(target.doc_id)
        text = info.get("text") or ""
        return {
            "key": target.key,
            "title": info.get("title") or target.title,
            "id": target.doc_id,
            "url": target.url,
            "status": target.status,
            "archivedAt": info.get("archivedAt"),
            "has_enrichment_section": "공개 조사 보강 (2026-06-02)" in text,
            "text_len": len(text),
            "trust_high": "신뢰도: **높음**" in text,
            "trust_medium": "신뢰도: **중간**" in text,
            "trust_low": "신뢰도: **낮음**" in text,
        }

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(check, target): target for target in targets}
        for index, future in enumerate(as_completed(future_map), start=1):
            target = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                results.append({"key": target.key, "title": target.title, "id": target.doc_id, "error": str(exc)[:500]})
            if index % 500 == 0 or index == len(targets):
                print(json.dumps({"checked": index, "target": len(targets)}, ensure_ascii=False), flush=True)

    summary = {
        "verified_at": datetime.now().isoformat(timespec="seconds"),
        "target": len(targets),
        "checked": len(results),
        "has_section": sum(1 for row in results if row.get("has_enrichment_section")),
        "archived": sum(1 for row in results if row.get("archivedAt")),
        "errors": [row for row in results if row.get("error")],
        "missing_section": [row for row in results if not row.get("has_enrichment_section") and not row.get("error")],
        "trust_in_text": {
            "높음": sum(1 for row in results if row.get("trust_high")),
            "중간": sum(1 for row in results if row.get("trust_medium")),
            "낮음": sum(1 for row in results if row.get("trust_low")),
        },
    }
    save_json(VERIFY_JSON, {"summary": summary, "results": sorted(results, key=lambda row: row.get("title", ""))})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--research-only", action="store_true")
    parser.add_argument("--update-only", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify(limit=args.limit, workers=args.workers), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(run(args.limit, args.workers, args.dry_run, args.research_only, args.update_only), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
