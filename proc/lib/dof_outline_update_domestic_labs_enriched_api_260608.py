#!/usr/bin/env python3
"""API-backed Outline update to materialize enriched domestic dental-lab Markdown."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dof_outline_update_domestic_labs_enriched_db_260608 as db_update  # noqa: E402
import dof_prospect_outline_publish as outline_publish  # noqa: E402
import dof_outline_reformat_domestic_labs_like_ab as fmt  # noqa: E402


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_DIR = ROOT / "output/domestic-dental-labs-260607/web_enrich_260608"
RESULT_JSON = OUT_DIR / "outline_enriched_api_update_result.json"


def outline_update(doc: dict[str, str], key: str, timeout: int = 120) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}"})
    payload = {"id": doc["id"], "title": doc["title"], "text": doc["text"], "publish": True, "fullWidth": True}
    last_error = ""
    for attempt in range(1, 6):
        try:
            response = session.post(f"{fmt.OUTLINE_BASE}/api/documents.update", json=payload, timeout=timeout)
            if response.status_code < 400:
                data = response.json().get("data") or {}
                return {"ok": True, "id": doc["id"], "title": doc["title"], "urlId": data.get("urlId"), "attempt": attempt}
            last_error = f"{response.status_code}: {response.text[:500]}"
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(min(20, attempt * 2))
    return {"ok": False, "id": doc["id"], "title": doc["title"], "error": last_error}


def outline_info(doc_id: str, key: str) -> dict[str, Any]:
    response = requests.post(
        f"{fmt.OUTLINE_BASE}/api/documents.info",
        json={"id": doc_id},
        headers={"Authorization": f"Bearer {key}"},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["data"]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = json.loads(db_update.DATA_JSON.read_text(encoding="utf-8"))
    docs = db_update.fetch_subtree_docs()
    structure = fmt.fetch_collection_structure()
    updates, meta = db_update.build_updates(rows, docs, structure)
    key = outline_publish.read_env_key("DOF_OUTLINE_KEY")
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(outline_update, update, key): update for update in updates}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if not result.get("ok"):
                failures.append(result)
            done += 1
            if done % 100 == 0:
                print(f"api_update {done}/{len(updates)} failures={len(failures)}", flush=True)
    report = outline_info(fmt.REPORT_DOC_ID, key)
    report_text = report.get("text") or ""
    sample_card = next(update for update in updates if "포털 확인 근거" in update["text"])
    sample = outline_info(sample_card["id"], key)
    sample_text = sample.get("text") or ""
    verification = {
        "report_title": report.get("title"),
        "report_has_portal_counts": "포털 전수 매칭 분포" in report_text,
        "report_has_web_summary": "웹/업체정보 흔적 확인" in report_text,
        "report_text_length": len(report_text),
        "sample_card_title": sample.get("title"),
        "sample_card_has_portal_basis": "포털 확인 근거" in sample_text,
        "sample_card_has_web_basis": "웹/뉴스/행사 근거" in sample_text,
    }
    result = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "requested_updates": len(updates),
        "ok_updates": sum(1 for item in results if item.get("ok")),
        "failures": failures,
        "meta": meta,
        "verification": verification,
    }
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures and verification["report_has_portal_counts"] and verification["sample_card_has_portal_basis"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
