"""DailyJot → Task/Note pusher.

Reads a mapping JSON (built by a human after inspecting each Area's content),
creates Notion pages, and appends a hyperlinked '링크' to each original Jot bullet.

The mapping file is the single source of truth — this script does NOT contain
any keyword-based area inference. See ./jot_to_tasks_2026-05-19.mapping.json
for the schema.

Usage:
    python proc/plan/jot_to_tasks_2026-05-19.py [mapping.json]
"""
from __future__ import annotations
import sys, json, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from notion_api import NotionClient, normalize_id  # noqa: E402
from notion_task import create_task  # noqa: E402

NOTE_DS = "06f18917-50a8-4d73-979f-b13a8c63f754"


def create_note(c: NotionClient, title: str, area_pid: str, note_type: str) -> dict:
    props = {
        "명칭": {"title": [{"type": "text", "text": {"content": title}}]},
        "유형": {"select": {"name": note_type}},
        "Areas": {"relation": [{"id": normalize_id(area_pid)}]},
    }
    body = {
        "parent": {"type": "data_source_id", "data_source_id": NOTE_DS},
        "properties": props,
    }
    return c.request("POST", "/pages", json=body)


def append_chip(c: NotionClient, block_id: str, target_page_id: str, *,
                suffix_text: str | None = None) -> None:
    """Append a Notion page-mention chip to the block's rich_text.
    If suffix_text is given, also append it as a plain text after the chip
    (used e.g. for '끌올' when reusing a past task)."""
    b = c.blocks_retrieve(block_id)
    bt = b["type"]
    payload = copy.deepcopy(b.get(bt, {}))
    rt = payload.get("rich_text", []) or []
    rt.append({"type": "text", "text": {"content": " "}, "annotations": {}, "plain_text": " "})
    rt.append({
        "type": "mention",
        "mention": {"type": "page", "page": {"id": normalize_id(target_page_id)}},
        "annotations": {},
        "plain_text": "",
    })
    if suffix_text:
        rt.append({"type": "text", "text": {"content": " " + suffix_text},
                   "annotations": {}, "plain_text": " " + suffix_text})
    c.request("PATCH", f"/blocks/{normalize_id(block_id)}", json={bt: {"rich_text": rt}})


def main(argv: list[str]) -> int:
    mapping_path = Path(argv[0]) if argv else Path(__file__).with_suffix("").with_name("jot_to_tasks_2026-05-19.mapping.json")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    c = NotionClient.from_cache()
    results = {"tasks": [], "notes": []}
    act = mapping.get("act_date")

    print("=== processing tasks ===")
    for item in mapping.get("tasks", []):
        # Past-week dup: if 'existing_task_id' is set, reuse it (chip + '끌올'), no create.
        if item.get("existing_task_id"):
            existing_id = normalize_id(item["existing_task_id"])
            existing = c.pages_retrieve(existing_id)
            url = existing["url"]
            print(f"  ↻ {item['title']} → reuse {url}  (끌올)")
            append_chip(c, item["jot_block"], existing_id, suffix_text="끌올")
            results["tasks"].append({**item, "task_id": existing_id, "url": url, "reused": True})
            continue

        page = create_task(
            title=item["title"],
            act_date=act,
            task_type="Task",
            status="Ready",
            client=c,
        )
        c.request("PATCH", f"/pages/{page['id']}",
                  json={"properties": {"Areas": {"relation": [{"id": normalize_id(item["area_page_id"])}]}}})
        url = page["url"]
        print(f"  ✓ {item['title']} → {url}")
        append_chip(c, item["jot_block"], page["id"])
        # Embed sub-bullet children into the task body (rule: sub-items under a checkbox
        # go INSIDE the task doc, not as separate Tasks/Notes).
        for child_bid in item.get("embed_children", []):
            cb = c.blocks_retrieve(normalize_id(child_bid))
            cbt = cb["type"]
            cb_rt = cb.get(cbt, {}).get("rich_text", []) or []
            c.request("PATCH", f"/blocks/{page['id']}/children",
                      json={"children": [{"object":"block","type":"bulleted_list_item",
                                          "bulleted_list_item":{"rich_text": cb_rt}}]})
        results["tasks"].append({**item, "task_id": page["id"], "url": url})

    print()
    print("=== creating notes ===")
    for item in mapping.get("notes", []):
        page = create_note(c, item["title"], item["area_page_id"], item["type"])
        url = page["url"]
        print(f"  ✓ {item['title'][:40]}… → {url}")
        append_chip(c, item["jot_block"], page["id"])
        results["notes"].append({**item, "note_id": page["id"], "url": url})

    out = Path(__file__).with_suffix(".result.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresult → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
