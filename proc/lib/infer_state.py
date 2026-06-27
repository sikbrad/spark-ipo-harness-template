"""SQLite state for raindrop-infer.

Tracks per-raindrop processing state: status, last raindrop lastUpdate,
content hash, error, retry count. Lives next to the dump state at
`data/raindrop/infer_state.sqlite`.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE_PATH = Path("data/raindrop/infer_state.sqlite")


class InferState:
    def __init__(self, path: str | Path = DEFAULT_STATE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.con:
            self.con.executescript(
                """
                CREATE TABLE IF NOT EXISTS raindrop_infer (
                    id            TEXT PRIMARY KEY,
                    link          TEXT,
                    domain        TEXT,
                    fetcher       TEXT,
                    status        TEXT,
                    raindrop_lu   TEXT,
                    fetched_at    TEXT,
                    content_hash  TEXT,
                    error         TEXT,
                    retry_count   INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_infer_status
                    ON raindrop_infer(status);
                CREATE INDEX IF NOT EXISTS idx_infer_domain
                    ON raindrop_infer(domain);
                """
            )

    def get(self, rid: str) -> dict | None:
        with self._lock:
            cur = self.con.execute(
                "SELECT id, link, domain, fetcher, status, raindrop_lu, "
                "fetched_at, content_hash, error, retry_count "
                "FROM raindrop_infer WHERE id=?",
                (str(rid),),
            )
            row = cur.fetchone()
        if not row:
            return None
        cols = ("id", "link", "domain", "fetcher", "status", "raindrop_lu",
                "fetched_at", "content_hash", "error", "retry_count")
        return dict(zip(cols, row))

    def upsert(
        self,
        *,
        id_: str,
        link: str,
        domain: str,
        fetcher: str,
        status: str,
        raindrop_lu: str | None,
        content_hash: str | None,
        error: str | None = None,
        retry_inc: bool = False,
    ) -> None:
        existing = self.get(id_)
        retry_count = (existing["retry_count"] if existing else 0) + (1 if retry_inc else 0)
        if status == "ok":
            retry_count = 0
        with self._lock, self.con:
            self.con.execute(
                """
                INSERT INTO raindrop_infer(id, link, domain, fetcher, status,
                    raindrop_lu, fetched_at, content_hash, error, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    link=excluded.link,
                    domain=excluded.domain,
                    fetcher=excluded.fetcher,
                    status=excluded.status,
                    raindrop_lu=excluded.raindrop_lu,
                    fetched_at=excluded.fetched_at,
                    content_hash=excluded.content_hash,
                    error=excluded.error,
                    retry_count=excluded.retry_count
                """,
                (
                    str(id_), link, domain, fetcher, status,
                    raindrop_lu,
                    datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                    content_hash, error, retry_count,
                ),
            )

    def stats(self) -> dict:
        with self._lock:
            by_status = dict(self.con.execute(
                "SELECT status, COUNT(*) FROM raindrop_infer GROUP BY status"
            ).fetchall())
            by_fetcher = dict(self.con.execute(
                "SELECT fetcher, COUNT(*) FROM raindrop_infer GROUP BY fetcher"
            ).fetchall())
        return {"by_status": by_status, "by_fetcher": by_fetcher}

    def close(self) -> None:
        self.con.close()
