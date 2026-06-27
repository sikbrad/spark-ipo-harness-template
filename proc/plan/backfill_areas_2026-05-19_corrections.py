"""Apply user corrections to area assignments from backfill_areas_2026-05-19.

User-directed reassignments (overrides safety guard since these pages already have an Area):
  - 강호남 점심          : Uncategorizable → Suited
  - POC클리닉 기획안     : Uncategorizable → Lecturing
  - 카카오 GeoAI 시절 12건: Career → GeoAI  (GeoAI is Closed but user explicitly wants it)

Looks up GeoAI area page id by name (status=Closed allowed here).

Usage:
    python proc/plan/backfill_areas_2026-05-19_corrections.py [--dry-run]
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from notion_api import NotionClient, normalize_id  # noqa: E402

AREA_DS = "8a64fd60-124c-4ca0-9ab9-b10a4e4131ce"

SUITED = "1018372d-c5ca-8097-b84d-f46d5c39a0ca"
LECTURING = "1018372d-c5ca-8085-94a7-f266c4b9401e"

KAKAO_GEOAI_TASKS = [
    "1ec8372d-c5ca-80e9-b890-eccc1b7cbd8e",  # cli interface 만들기
    "1ec8372d-c5ca-800d-8f96-c2b7a05c9db7",  # 좌표계 바꾸기
    "1ec8372d-c5ca-80e2-9c45-f51a6fcecbf0",  # laz 스케일오류 수정
    "1ec8372d-c5ca-8029-9dc2-f8680d35d5b8",  # dam_datagen 패키징
    "1ec8372d-c5ca-8038-84a2-c025bf94b1ec",  # 카카오 레지스터리
    "1a68372d-c5ca-805a-a82b-c7cf2bf0df45",  # Grid size 가변 검토
    "1a68372d-c5ca-8024-9577-cea7f0db7e45",  # Thomas 타일과 연동
    "1a68372d-c5ca-8065-ac6b-d3d5904569d1",  # pcd grid 저장형식
    "1a68372d-c5ca-809d-aabc-e368ad4f4344",  # DAM dataset 생성
    "1a68372d-c5ca-805c-880e-c66fdae27a33",  # RandLaNet&Toronto3D
    "1a68372d-c5ca-8032-9d8d-f6522b2b958f",  # 영등포리눅스 pred
    "1a68372d-c5ca-80e9-b9d4-cb53f442f966",  # 맥북 RandLaNet SemanticKitti
    "1a68372d-c5ca-80eb-b0b7-e381297e492b",  # Weight 계산식 재검토
]
# Note: 13 tasks total here. Original plan said 12. Let me list - actually 13.

EXTRA_REASSIGN = [
    ("35d8372d-c5ca-81dd-90d9-f921db54a4bc", SUITED, "강호남 점심"),
    ("31e8372d-c5ca-8038-8029-f1e6386613b6", LECTURING, "POC클리닉 기획안"),
]


def rt_to_text(rt: list) -> str:
    return "".join((r.get("plain_text") or "") for r in (rt or []))


def title_of(page: dict) -> str:
    for p in page.get("properties", {}).values():
        if p.get("type") == "title":
            return rt_to_text(p.get("title", []))
    return ""


def find_area_by_name(c: NotionClient, name: str) -> dict | None:
    for page in c.data_sources_query_iter(AREA_DS):
        if title_of(page).strip() == name:
            return page
    return None


def patch_area(c: NotionClient, page_id: str, area_page_id: str) -> dict:
    return c.request(
        "PATCH",
        f"/pages/{normalize_id(page_id)}",
        json={"properties": {"Areas": {"relation": [{"id": normalize_id(area_page_id)}]}}},
    )


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    c = NotionClient.from_cache()

    print("=== resolving GeoAI area page ===")
    geoai = find_area_by_name(c, "GeoAI")
    if not geoai:
        print("ERROR: GeoAI area not found in Area DB.")
        return 1
    geoai_id = geoai["id"]
    print(f"  GeoAI = {geoai_id}  (status: see Area DB)")

    results: list[dict] = []

    print(f"\n=== {'dry-run' if dry_run else 'apply'} ===")
    for pid in KAKAO_GEOAI_TASKS:
        page = c.pages_retrieve(pid)
        t = title_of(page)
        if dry_run:
            print(f"  ◌ {t} → GeoAI")
            results.append({"id": pid, "title": t, "new_area": "GeoAI", "status": "dry"})
            continue
        patch_area(c, pid, geoai_id)
        print(f"  ✓ {t} → GeoAI")
        results.append({"id": pid, "title": t, "new_area": "GeoAI", "status": "patched"})

    for pid, area_id, label in EXTRA_REASSIGN:
        page = c.pages_retrieve(pid)
        t = title_of(page)
        if dry_run:
            print(f"  ◌ {t} → (area_id {area_id[:8]}…)")
            results.append({"id": pid, "title": t, "new_area_id": area_id, "status": "dry"})
            continue
        patch_area(c, pid, area_id)
        print(f"  ✓ {t} → (area_id {area_id[:8]}…)")
        results.append({"id": pid, "title": t, "new_area_id": area_id, "status": "patched"})

    out = Path(__file__).with_suffix(".result.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {out}  ({len(results)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
