"""Notion Task DB — create a task page from template.

Targets the Quick My Ocean Task DB (single data source).

CLI:
    python proc/lib/notion_task.py "강호남 점심" \\
        --start 2026-05-28T12:00:00+09:00 \\
        --end   2026-05-28T14:00:00+09:00

Python API:
    from notion_task import create_task
    res = create_task("강호남 점심",
                      time_span=("2026-05-28T12:00:00+09:00",
                                 "2026-05-28T14:00:00+09:00"))
    print(res["url"])
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notion_api import NotionClient, normalize_id  # noqa: E402

TASK_DB_ID = "71c69a38-772b-4ea0-b9e6-0bb23f64ac7c"
TASK_DATA_SOURCE_ID = "312bfde5-d1da-4f7d-94a6-b73c912eb042"
DEFAULT_TEMPLATE_PAGE_ID = "bdda3e4b-2727-49a0-adc9-e15a7c1b2c26"  # "tk" template

# Block types the create-block API rejects (Notion-managed / read-only).
SKIP_BLOCK_TYPES = {"unsupported", "child_database", "child_page"}


def _strip_nones(obj):
    if isinstance(obj, dict):
        return {k: _strip_nones(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nones(x) for x in obj]
    return obj


def _sanitize(blk: dict) -> Optional[dict]:
    btype = blk.get("type")
    if not btype or btype in SKIP_BLOCK_TYPES:
        return None
    payload = blk.get(btype)
    if payload is None:
        return None
    payload = _strip_nones(copy.deepcopy(payload))
    payload.pop("children", None)
    return {"object": "block", "type": btype, btype: payload}


def _fetch_tree(c: NotionClient, block_id: str) -> list[dict]:
    out: list[dict] = []
    for ch in c.blocks_children_iter(block_id):
        s = _sanitize(ch)
        if s is None:
            continue
        if ch.get("has_children"):
            sub = _fetch_tree(c, ch["id"])
            if sub:
                btype = s["type"]
                s[btype]["children"] = sub
        out.append(s)
    return out


def create_task(
    title: str,
    *,
    time_span: Optional[tuple[str, Optional[str]]] = None,
    due_date: Optional[str] = None,
    act_date: Optional[str] = None,
    task_type: str = "Task",
    status: str = "Ready",
    impact: Optional[str] = None,
    template_id: Optional[str] = DEFAULT_TEMPLATE_PAGE_ID,
    client: Optional[NotionClient] = None,
) -> dict:
    """Create a task page in the Task DB. Returns the created page dict."""
    c = client or NotionClient.from_cache()

    props: dict = {
        "명칭": {"title": [{"type": "text", "text": {"content": title}}]},
        "TaskType": {"select": {"name": task_type}},
        "Status": {"status": {"name": status}},
    }
    if time_span:
        start, end = time_span
        date_obj: dict = {"start": start}
        if end:
            date_obj["end"] = end
        props["TimeSpan"] = {"date": date_obj}
    if due_date:
        props["DueDate"] = {"date": {"start": due_date}}
    if act_date:
        props["ActDate"] = {"date": {"start": act_date}}
    if impact:
        props["Impact"] = {"select": {"name": impact}}

    body = {
        "parent": {"type": "data_source_id", "data_source_id": TASK_DATA_SOURCE_ID},
        "properties": props,
    }
    page = c.request("POST", "/pages", json=body)
    new_id = page["id"]

    if template_id:
        children = _fetch_tree(c, normalize_id(template_id))
        CHUNK = 100
        for i in range(0, len(children), CHUNK):
            c.request(
                "PATCH",
                f"/blocks/{new_id}/children",
                json={"children": children[i:i + CHUNK]},
            )

    return page


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Create a task in Notion Task DB")
    p.add_argument("title", help="task title (e.g. '강호남 점심')")
    p.add_argument("--start", help="TimeSpan start (ISO, e.g. 2026-05-28T12:00:00+09:00)")
    p.add_argument("--end", help="TimeSpan end")
    p.add_argument("--due", help="DueDate (ISO date or datetime)")
    p.add_argument("--act", help="ActDate (ISO date)")
    p.add_argument("--task-type", default="Task", choices=["Task", "Project", "Chore"])
    p.add_argument("--status", default="Ready",
                   help="Ready|Todo|Doing|Wait|Schedule|Done|Close|Someday")
    p.add_argument("--impact", help="⭐ | ⭐⭐ | ⭐⭐⭐")
    p.add_argument("--template", default=DEFAULT_TEMPLATE_PAGE_ID,
                   help="template page id (default: tk-bdda3e4b…)")
    p.add_argument("--no-template", action="store_true",
                   help="skip template body copy (overrides --template)")
    args = p.parse_args(argv)

    res = create_task(
        title=args.title,
        time_span=(args.start, args.end) if args.start else None,
        due_date=args.due,
        act_date=args.act,
        task_type=args.task_type,
        status=args.status,
        impact=args.impact,
        template_id=None if args.no_template else args.template,
    )
    print(json.dumps({"id": res["id"], "url": res["url"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
