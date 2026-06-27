from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from notion_api import NotionClient, normalize_id  # noqa: E402

DAY = "2026-06-26"
RAW = Path("data/daily/2026-06-26/raw")
RAW.mkdir(parents=True, exist_ok=True)

JOT_DS = "6c6fb239-012d-47e8-a20f-c614cb01fc0d"
TASK_DS = "312bfde5-d1da-4f7d-94a6-b73c912eb042"
AREA_DS = "8a64fd60-124c-4ca0-9ab9-b10a4e4131ce"


def rt_plain(rich_text: list[dict]) -> str:
    return "".join(x.get("plain_text", "") for x in rich_text or []).strip()


def title_of(page: dict) -> str:
    props = page.get("properties", {})
    for value in props.values():
        if value.get("type") == "title":
            return rt_plain(value.get("title", []))
    return ""


def prop_status(page: dict, name: str) -> str | None:
    value = page.get("properties", {}).get(name)
    if not value:
        return None
    if value.get("type") == "status" and value.get("status"):
        return value["status"].get("name")
    if value.get("type") == "select" and value.get("select"):
        return value["select"].get("name")
    return None


def prop_date_start(page: dict, name: str) -> str | None:
    value = page.get("properties", {}).get(name)
    if value and value.get("type") == "date" and value.get("date"):
        return value["date"].get("start")
    return None


def prop_rel_ids(page: dict, name: str) -> list[str]:
    value = page.get("properties", {}).get(name)
    if value and value.get("type") == "relation":
        return [x["id"] for x in value.get("relation", [])]
    return []


def block_tree(c: NotionClient, block_id: str) -> list[dict]:
    out = []
    for block in c.blocks_children_iter(block_id):
        btype = block.get("type")
        payload = block.get(btype, {}) if btype else {}
        item = {
            "id": block.get("id"),
            "type": btype,
            "text": rt_plain(payload.get("rich_text", [])),
            "checked": payload.get("checked") if btype == "to_do" else None,
            "has_children": block.get("has_children", False),
            "children": [],
        }
        if block.get("has_children"):
            item["children"] = block_tree(c, block["id"])
        out.append(item)
    return out


def query_all(c: NotionClient, ds_id: str, body: dict) -> list[dict]:
    cursor = None
    out = []
    while True:
        payload = dict(body)
        payload.setdefault("page_size", 100)
        if cursor:
            payload["start_cursor"] = cursor
        data = c.request("POST", f"/data_sources/{normalize_id(ds_id)}/query", json=payload)
        out.extend(data.get("results", []))
        if not data.get("has_more"):
            return out
        cursor = data.get("next_cursor")


def main() -> int:
    c = NotionClient.from_cache()

    jots = query_all(
        c,
        JOT_DS,
        {
            "filter": {"property": "시작일자", "date": {"equals": DAY}},
            "sorts": [{"property": "시작일자", "direction": "ascending"}],
        },
    )
    jot_dump = []
    for page in jots:
        jot_dump.append(
            {
                "id": page["id"],
                "url": page.get("url"),
                "title": title_of(page),
                "start": prop_date_start(page, "시작일자"),
                "blocks": block_tree(c, page["id"]),
            }
        )
    (RAW / "notion-jot-live.json").write_text(json.dumps(jot_dump, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAW / "notion-jot.json").write_text(json.dumps(jot_dump, ensure_ascii=False, indent=2), encoding="utf-8")

    today_tasks = query_all(
        c,
        TASK_DS,
        {
            "filter": {
                "or": [
                    {"property": "ActDate", "date": {"equals": DAY}},
                    {"property": "DueDate", "date": {"on_or_before": DAY}},
                    {"property": "Status", "status": {"equals": "Doing"}},
                    {"property": "Status", "status": {"equals": "Ready"}},
                    {"property": "Status", "status": {"equals": "Wait"}},
                    {"property": "Status", "status": {"equals": "Schedule"}},
                ]
            },
            "sorts": [{"property": "ActDate", "direction": "ascending"}],
        },
    )

    since = (date.fromisoformat(DAY) - timedelta(days=7)).isoformat()
    recent_tasks = query_all(
        c,
        TASK_DS,
        {
            "filter": {
                "and": [
                    {"timestamp": "created_time", "created_time": {"on_or_after": since}},
                    {"timestamp": "created_time", "created_time": {"before": DAY}},
                ]
            }
        },
    )

    area_pages = query_all(
        c,
        AREA_DS,
        {
            "filter": {
                "or": [
                    {"property": "상태", "status": {"equals": "Responsible"}},
                    {"property": "상태", "status": {"equals": "Occasional"}},
                ]
            }
        },
    )
    areas = [
        {
            "id": p["id"],
            "title": title_of(p),
            "status": prop_status(p, "상태"),
            "url": p.get("url"),
        }
        for p in area_pages
    ]

    def task_row(page: dict) -> dict:
        return {
            "id": page["id"],
            "title": title_of(page),
            "status": prop_status(page, "Status"),
            "act": prop_date_start(page, "ActDate"),
            "due": prop_date_start(page, "DueDate"),
            "areas": prop_rel_ids(page, "Areas"),
            "url": page.get("url"),
            "created_time": page.get("created_time"),
        }

    task_dump = [task_row(p) for p in today_tasks]
    recent_dump = [task_row(p) for p in recent_tasks]
    (RAW / "notion-tasks-live.json").write_text(json.dumps(task_dump, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAW / "notion-tasks.json").write_text(json.dumps(task_dump, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAW / "notion-recent-tasks.json").write_text(json.dumps(recent_dump, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAW / "notion-areas-active.json").write_text(json.dumps(areas, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"jots": len(jot_dump), "tasks": len(task_dump), "recent_tasks": len(recent_dump), "areas": len(areas)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
