"""Retry just the pages that errored in the last dump run.

Reads data/notion/dump/_index.json, picks errors with op in {page_exception, database_exception},
retries each one (up to 5 times with backoff), saves the resulting JSON into the dump tree,
upserts state, and rewrites _index.json so errors[] only contains still-failing items.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "proc/lib")

from notion_api import NotionClient, normalize_id  # noqa: E402
from notion_state import State, DEFAULT_STATE_PATH  # noqa: E402

ROOT = Path("data/notion/dump")
INDEX = ROOT / "_index.json"
PAGES_DIR = ROOT / "pages"
DBS_DIR = ROOT / "databases"


def _save(kind: str, uid: str, obj: dict) -> Path:
    base = PAGES_DIR if kind == "page" else DBS_DIR
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"{uid.replace('-', '')}.json"
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return p


def _retry(call, *args, max_attempts: int = 5, base_delay: float = 2.0):
    last = None
    for attempt in range(1, max_attempts + 1):
        try:
            return call(*args)
        except Exception as e:  # noqa: BLE001
            last = e
            delay = base_delay * (2 ** (attempt - 1))
            print(f"  attempt {attempt} failed: {type(e).__name__}: {str(e)[:100]}; sleep {delay:.1f}s")
            time.sleep(delay)
    raise last  # type: ignore[misc]


def main() -> None:
    idx = json.loads(INDEX.read_text())
    errors = list(idx.get("errors", []))
    if not errors:
        print("no errors to retry")
        return

    print(f"retrying {len(errors)} errored objects")
    client = NotionClient.from_cache()
    state = State(DEFAULT_STATE_PATH)

    still_failing: list[dict] = []
    fixed = 0
    for e in errors:
        op = e.get("op")
        uid = normalize_id(e["id"])
        try:
            if op == "page_exception":
                obj = _retry(client.pages_retrieve, uid)
                _save("page", uid, obj)
                title_prop = obj.get("properties", {})
                title = ""
                for v in title_prop.values():
                    if v.get("type") == "title":
                        rich = v.get("title") or []
                        title = "".join(r.get("plain_text", "") for r in rich)
                        break
                parent = obj.get("parent", {})
                parent_id = (
                    parent.get("page_id")
                    or parent.get("database_id")
                    or parent.get("block_id")
                    or parent.get("workspace")
                )
                state.upsert_object(
                    kind="page",
                    id_=uid,
                    last_edited_time=obj.get("last_edited_time", ""),
                    parent_id=str(parent_id) if parent_id else None,
                    title=title,
                )
                fixed += 1
                print(f"  fixed page  {uid}  {title!r}")
            elif op == "database_exception":
                obj = _retry(client.databases_retrieve, uid)
                _save("database", uid, obj)
                title = "".join(
                    r.get("plain_text", "") for r in obj.get("title", [])
                )
                parent = obj.get("parent", {})
                parent_id = (
                    parent.get("page_id")
                    or parent.get("database_id")
                    or parent.get("block_id")
                    or parent.get("workspace")
                )
                state.upsert_object(
                    kind="database",
                    id_=uid,
                    last_edited_time=obj.get("last_edited_time", ""),
                    parent_id=str(parent_id) if parent_id else None,
                    title=title,
                )
                fixed += 1
                print(f"  fixed db    {uid}  {title!r}")
            else:
                print(f"  skip op={op!r} (not handled)")
                still_failing.append(e)
        except Exception as exc:  # noqa: BLE001
            print(f"  STILL FAILING {op} {uid}: {type(exc).__name__}: {str(exc)[:100]}")
            still_failing.append(
                {"op": op, "id": uid, "msg": str(exc)[:300]}
            )

    idx["errors"] = still_failing
    idx["counts"]["errors"] = len(still_failing)
    idx["retried_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=2))
    state.close()
    print(f"\nfixed={fixed} still_failing={len(still_failing)}")


if __name__ == "__main__":
    main()
