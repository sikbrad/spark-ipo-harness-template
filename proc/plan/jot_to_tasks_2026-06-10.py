from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from notion_api import NotionClient, normalize_id  # noqa: E402
from notion_task import create_task  # noqa: E402

NOTE_DS = "06f18917-50a8-4d73-979f-b13a8c63f754"


def append_chip(c: NotionClient, block_id: str, target_page_id: str, *, suffix_text: str | None = None) -> None:
    block = c.blocks_retrieve(block_id)
    block_type = block["type"]
    payload = copy.deepcopy(block.get(block_type, {}))
    rich_text = payload.get("rich_text", []) or []
    rich_text.append({"type": "text", "text": {"content": " "}, "annotations": {}, "plain_text": " "})
    rich_text.append(
        {
            "type": "mention",
            "mention": {"type": "page", "page": {"id": normalize_id(target_page_id)}},
            "annotations": {},
            "plain_text": "",
        }
    )
    if suffix_text:
        rich_text.append(
            {
                "type": "text",
                "text": {"content": " " + suffix_text},
                "annotations": {},
                "plain_text": " " + suffix_text,
            }
        )
    c.request("PATCH", f"/blocks/{normalize_id(block_id)}", json={block_type: {"rich_text": rich_text}})


def create_note(c: NotionClient, title: str, area_page_id: str, note_type: str) -> dict:
    return c.request(
        "POST",
        "/pages",
        json={
            "parent": {"type": "data_source_id", "data_source_id": NOTE_DS},
            "properties": {
                "명칭": {"title": [{"type": "text", "text": {"content": title}}]},
                "유형": {"select": {"name": note_type}},
                "Areas": {"relation": [{"id": normalize_id(area_page_id)}]},
            },
        },
    )


def main(argv: list[str]) -> int:
    mapping_path = Path(argv[0]) if argv else Path(__file__).with_suffix(".mapping.json")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    client = NotionClient.from_cache()
    results = {"act_date": mapping.get("act_date"), "tasks": [], "notes": []}

    for item in mapping.get("tasks", []):
        if item.get("existing_task_id"):
            existing_id = normalize_id(item["existing_task_id"])
            existing = client.pages_retrieve(existing_id)
            append_chip(client, item["jot_block"], existing_id, suffix_text="끌올")
            results["tasks"].append({**item, "task_id": existing_id, "url": existing["url"], "reused": True})
            continue

        page = create_task(
            item["title"],
            act_date=mapping.get("act_date"),
            task_type="Task",
            status="Ready",
            client=client,
        )
        client.request(
            "PATCH",
            f"/pages/{page['id']}",
            json={"properties": {"Areas": {"relation": [{"id": normalize_id(item["area_page_id"])}]}}},
        )
        append_chip(client, item["jot_block"], page["id"])
        results["tasks"].append({**item, "task_id": page["id"], "url": page["url"], "reused": False})

    for item in mapping.get("notes", []):
        page = create_note(client, item["title"], item["area_page_id"], item["type"])
        append_chip(client, item["jot_block"], page["id"])
        results["notes"].append({**item, "note_id": page["id"], "url": page["url"]})

    if mapping_path.name.endswith(".mapping.json"):
        result_path = mapping_path.with_name(mapping_path.name.replace(".mapping.json", ".result.json"))
    else:
        result_path = mapping_path.with_suffix(".result.json")
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"tasks": len(results["tasks"]), "notes": len(results["notes"]), "result": str(result_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
