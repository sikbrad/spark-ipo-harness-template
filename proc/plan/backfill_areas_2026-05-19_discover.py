"""Discover candidates for Area backfill.

Outputs:
  - backfill_areas_2026-05-19.candidates.json
      { tasks: [{id,title,body_excerpt,status,...}],
        notes: [{id,title,body_excerpt,type,...}],
        areas: [{id,name,status,group}] }

Filtering:
  - Task DB ds 312bfde5… : Areas is_empty
  - Note DB ds 06f18917… : Areas is_empty
  - Area DB ds 8a64fd60… : 상태 ≠ Closed
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from notion_api import NotionClient  # noqa: E402

TASK_DS = "312bfde5-d1da-4f7d-94a6-b73c912eb042"
NOTE_DS = "06f18917-50a8-4d73-979f-b13a8c63f754"
AREA_DS = "8a64fd60-124c-4ca0-9ab9-b10a4e4131ce"

OUT = Path(__file__).with_suffix("").parent / "backfill_areas_2026-05-19.candidates.json"


def rt_to_text(rt: list) -> str:
    return "".join((r.get("plain_text") or "") for r in (rt or []))


def title_of(page: dict) -> str:
    props = page.get("properties", {})
    for p in props.values():
        if p.get("type") == "title":
            return rt_to_text(p.get("title", []))
    return ""


def relation_empty(page: dict, prop_name: str) -> bool:
    p = page.get("properties", {}).get(prop_name)
    if not p:
        return True
    return len(p.get("relation") or []) == 0


def status_value(page: dict, prop_name: str = "상태") -> str:
    p = page.get("properties", {}).get(prop_name)
    if not p:
        return ""
    t = p.get("type")
    if t == "status":
        return (p.get("status") or {}).get("name", "") or ""
    if t == "select":
        return (p.get("select") or {}).get("name", "") or ""
    return ""


def select_value(page: dict, prop_name: str) -> str:
    p = page.get("properties", {}).get(prop_name)
    if not p:
        return ""
    s = p.get("select")
    return (s or {}).get("name", "") or ""


def date_value(page: dict, prop_name: str) -> dict | None:
    p = page.get("properties", {}).get(prop_name)
    if not p or p.get("type") != "date":
        return None
    return p.get("date")


def body_excerpt(c: NotionClient, page_id: str, max_chars: int = 800) -> str:
    out: list[str] = []
    try:
        for blk in c.blocks_children_iter(page_id):
            bt = blk.get("type")
            payload = blk.get(bt, {}) or {}
            rt = payload.get("rich_text") or []
            text = rt_to_text(rt)
            if text.strip():
                out.append(text)
            if sum(len(x) for x in out) >= max_chars:
                break
    except Exception as e:
        out.append(f"[body fetch error: {e}]")
    s = "\n".join(out)
    return s[:max_chars]


def main() -> int:
    c = NotionClient.from_cache()
    result: dict = {"tasks": [], "notes": [], "areas": []}

    print("=== areas (status != Closed) ===")
    for page in c.data_sources_query_iter(AREA_DS):
        st = status_value(page, "상태") or status_value(page, "Status")
        if st == "Closed":
            continue
        name = title_of(page)
        result["areas"].append({
            "id": page["id"],
            "name": name,
            "status": st,
            "url": page.get("url"),
        })
        print(f"  · [{st}] {name}  ({page['id']})")

    print(f"\n=== tasks with empty Areas ===")
    for page in c.data_sources_query_iter(TASK_DS):
        if not relation_empty(page, "Areas"):
            continue
        st = status_value(page, "Status") or status_value(page, "상태")
        # Skip tasks themselves that are Done/Close — user said ignore 'done'.
        # (We are not filtering tasks by done — user said only area-side done is excluded.
        #  Still record status for review.)
        task_type = select_value(page, "TaskType")
        excerpt = body_excerpt(c, page["id"])
        result["tasks"].append({
            "id": page["id"],
            "title": title_of(page),
            "status": st,
            "task_type": task_type,
            "time_span": date_value(page, "TimeSpan"),
            "due": date_value(page, "DueDate"),
            "act": date_value(page, "ActDate"),
            "created_time": page.get("created_time"),
            "last_edited_time": page.get("last_edited_time"),
            "url": page.get("url"),
            "body_excerpt": excerpt,
        })
        print(f"  · [{st}] {title_of(page)}")

    print(f"\n=== notes with empty Areas ===")
    for page in c.data_sources_query_iter(NOTE_DS):
        if not relation_empty(page, "Areas"):
            continue
        ntype = select_value(page, "유형")
        excerpt = body_excerpt(c, page["id"])
        result["notes"].append({
            "id": page["id"],
            "title": title_of(page),
            "type": ntype,
            "created_time": page.get("created_time"),
            "last_edited_time": page.get("last_edited_time"),
            "url": page.get("url"),
            "body_excerpt": excerpt,
        })
        print(f"  · [{ntype}] {title_of(page)}")

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT}  (areas={len(result['areas'])}, tasks={len(result['tasks'])}, notes={len(result['notes'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
