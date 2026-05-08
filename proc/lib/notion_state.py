"""SQLite-backed incremental state for Notion dump.

Schema (auto-created):

    notion_object(kind TEXT, id TEXT, last_edited_time TEXT, parent_id TEXT,
                  title TEXT, fetched_at TEXT, PRIMARY KEY (kind, id))

    notion_child(parent_kind TEXT, parent_id TEXT, child_kind TEXT, child_id TEXT,
                 PRIMARY KEY (parent_kind, parent_id, child_kind, child_id))

    notion_run(started_at TEXT, finished_at TEXT, counts TEXT, errors TEXT)

A row exists in `notion_object` iff we previously fetched + dumped the object's
content. Comparing the API's `last_edited_time` to the stored value tells us
whether to skip the refetch.

`notion_child` lets us walk the cached subtree without re-fetching the parent's
blocks/rows when the parent is unchanged.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable


DEFAULT_STATE_PATH = Path("data/notion_state.sqlite")


class State:
    def __init__(self, path: str | Path = DEFAULT_STATE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self.con:
            self.con.executescript(
                """
                CREATE TABLE IF NOT EXISTS notion_object (
                    kind TEXT NOT NULL,
                    id TEXT NOT NULL,
                    last_edited_time TEXT,
                    parent_id TEXT,
                    title TEXT,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (kind, id)
                );
                CREATE INDEX IF NOT EXISTS idx_notion_object_let
                    ON notion_object(last_edited_time);

                CREATE TABLE IF NOT EXISTS notion_child (
                    parent_kind TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    child_kind TEXT NOT NULL,
                    child_id TEXT NOT NULL,
                    PRIMARY KEY (parent_kind, parent_id, child_kind, child_id)
                );
                CREATE INDEX IF NOT EXISTS idx_notion_child_parent
                    ON notion_child(parent_kind, parent_id);

                CREATE TABLE IF NOT EXISTS notion_run (
                    started_at TEXT,
                    finished_at TEXT,
                    counts TEXT,
                    errors TEXT
                );
                """
            )

    # ── object metadata ──

    def get_let(self, kind: str, id_: str) -> str | None:
        cur = self.con.execute(
            "SELECT last_edited_time FROM notion_object WHERE kind=? AND id=?",
            (kind, id_),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def upsert_object(
        self,
        *,
        kind: str,
        id_: str,
        last_edited_time: str | None,
        parent_id: str | None,
        title: str | None,
    ) -> None:
        with self.con:
            self.con.execute(
                """
                INSERT INTO notion_object(kind, id, last_edited_time, parent_id, title, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(kind, id) DO UPDATE SET
                    last_edited_time = excluded.last_edited_time,
                    parent_id = excluded.parent_id,
                    title = excluded.title,
                    fetched_at = excluded.fetched_at
                """,
                (
                    kind,
                    id_,
                    last_edited_time,
                    parent_id,
                    title,
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                ),
            )

    # ── parent → child links ──

    def get_children(self, parent_kind: str, parent_id: str) -> list[tuple[str, str]]:
        cur = self.con.execute(
            "SELECT child_kind, child_id FROM notion_child "
            "WHERE parent_kind=? AND parent_id=?",
            (parent_kind, parent_id),
        )
        return [(k, i) for k, i in cur.fetchall()]

    def replace_children(
        self,
        parent_kind: str,
        parent_id: str,
        children: Iterable[tuple[str, str]],
    ) -> None:
        with self.con:
            self.con.execute(
                "DELETE FROM notion_child WHERE parent_kind=? AND parent_id=?",
                (parent_kind, parent_id),
            )
            self.con.executemany(
                "INSERT OR IGNORE INTO notion_child"
                "(parent_kind, parent_id, child_kind, child_id) VALUES (?,?,?,?)",
                [(parent_kind, parent_id, ck, ci) for ck, ci in children],
            )

    # ── run history ──

    def record_run(self, started_at: str, finished_at: str, counts: dict, errors: list) -> None:
        with self.con:
            self.con.execute(
                "INSERT INTO notion_run(started_at, finished_at, counts, errors) VALUES (?,?,?,?)",
                (
                    started_at,
                    finished_at,
                    json.dumps(counts, ensure_ascii=False),
                    json.dumps(errors, ensure_ascii=False),
                ),
            )

    # ── debug / inspection ──

    def stats(self) -> dict:
        cur = self.con.execute(
            "SELECT kind, COUNT(*) FROM notion_object GROUP BY kind"
        )
        by_kind = dict(cur.fetchall())
        run_count = self.con.execute("SELECT COUNT(*) FROM notion_run").fetchone()[0]
        return {"objects_by_kind": by_kind, "run_count": run_count}

    def close(self) -> None:
        self.con.close()
