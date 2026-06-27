"""SQLite-backed incremental state for Raindrop.io dump.

Schema (auto-created):

    raindrop_object(kind TEXT, id TEXT, last_update TEXT, parent_id TEXT,
                    title TEXT, fetched_at TEXT, PRIMARY KEY (kind, id))

    raindrop_run(started_at TEXT, finished_at TEXT, counts TEXT, errors TEXT)

`kind` is one of: 'collection' | 'raindrop'.

A row in `raindrop_object` means we have its raw JSON on disk. Comparing the
API's `lastUpdate` to the stored value tells us whether to refetch.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DEFAULT_STATE_PATH = Path("data/raindrop/state.sqlite")


class State:
    def __init__(self, path: str | Path = DEFAULT_STATE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.con:
            self.con.executescript(
                """
                CREATE TABLE IF NOT EXISTS raindrop_object (
                    kind TEXT NOT NULL,
                    id TEXT NOT NULL,
                    last_update TEXT,
                    parent_id TEXT,
                    title TEXT,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (kind, id)
                );
                CREATE INDEX IF NOT EXISTS idx_raindrop_object_lu
                    ON raindrop_object(last_update);

                CREATE TABLE IF NOT EXISTS raindrop_run (
                    started_at TEXT,
                    finished_at TEXT,
                    counts TEXT,
                    errors TEXT
                );
                """
            )

    # ── object metadata ──

    def get_last_update(self, kind: str, id_: str) -> str | None:
        with self._lock:
            cur = self.con.execute(
                "SELECT last_update FROM raindrop_object WHERE kind=? AND id=?",
                (kind, str(id_)),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def upsert_object(
        self,
        *,
        kind: str,
        id_: str | int,
        last_update: str | None,
        parent_id: str | int | None,
        title: str | None,
    ) -> None:
        with self._lock, self.con:
            self.con.execute(
                """
                INSERT INTO raindrop_object(kind, id, last_update, parent_id, title, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(kind, id) DO UPDATE SET
                    last_update = excluded.last_update,
                    parent_id = excluded.parent_id,
                    title = excluded.title,
                    fetched_at = excluded.fetched_at
                """,
                (
                    kind,
                    str(id_),
                    last_update,
                    None if parent_id is None else str(parent_id),
                    title,
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                ),
            )

    def delete_object(self, kind: str, id_: str | int) -> None:
        with self._lock, self.con:
            self.con.execute(
                "DELETE FROM raindrop_object WHERE kind=? AND id=?",
                (kind, str(id_)),
            )

    def all_ids(self, kind: str) -> list[str]:
        with self._lock:
            cur = self.con.execute(
                "SELECT id FROM raindrop_object WHERE kind=?", (kind,)
            )
            return [r[0] for r in cur.fetchall()]

    # ── run history ──

    def record_run(
        self, started_at: str, finished_at: str, counts: dict, errors: list
    ) -> None:
        with self._lock, self.con:
            self.con.execute(
                "INSERT INTO raindrop_run(started_at, finished_at, counts, errors) VALUES (?,?,?,?)",
                (
                    started_at,
                    finished_at,
                    json.dumps(counts, ensure_ascii=False),
                    json.dumps(errors, ensure_ascii=False),
                ),
            )

    def last_run(self) -> dict | None:
        with self._lock:
            cur = self.con.execute(
                "SELECT started_at, finished_at, counts, errors FROM raindrop_run "
                "ORDER BY rowid DESC LIMIT 1"
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "started_at": row[0],
            "finished_at": row[1],
            "counts": json.loads(row[2] or "{}"),
            "errors": json.loads(row[3] or "[]"),
        }

    # ── debug / inspection ──

    def stats(self) -> dict:
        with self._lock:
            by_kind = dict(
                self.con.execute(
                    "SELECT kind, COUNT(*) FROM raindrop_object GROUP BY kind"
                ).fetchall()
            )
            run_count = self.con.execute(
                "SELECT COUNT(*) FROM raindrop_run"
            ).fetchone()[0]
        return {"objects_by_kind": by_kind, "run_count": run_count}

    def close(self) -> None:
        self.con.close()
