"""ChatGPT (chatgpt.com) helpers for playwright-cli sessions.

Session convention: S('chatgpt') with persistent profile.

Bootstrap once (first-time login via Apple ID):
    playwright-cli -s=chatgpt open https://chatgpt.com/ --persistent --headed
  Click "Log in" → "Continue with Apple" → email/password → Apple 2FA code on
  trusted device. Session persists on disk after that.

Auth model:
  /api/auth/session returns {accessToken, user, expires}. accessToken is the
  Bearer used by /backend-api/*. The cookie session keeps it valid; calling
  /api/auth/session re-issues a fresh accessToken on each request.

Listing endpoint:
  GET /backend-api/conversations?offset=N&limit=28&order=updated
    -> {items: [{title, id, create_time, update_time, ...}], total, ...}
  `total` field is unreliable (sometimes lags). Page until items < limit.

Conversation detail:
  GET /backend-api/conversation/{id}
    -> {mapping: {<msg_id>: {message: {author:{role}, content:{parts:[...]}}}}, ...}
  Walk the mapping tree to extract the first user message.
"""

from __future__ import annotations

import json as _json
import sqlite3 as _sqlite3
import time as _time
from pathlib import Path
from typing import Optional

from pwc import S

DEFAULT_DB_PATH = Path('data/db/chatgpt.sqlite')

BASE_URL = 'https://chatgpt.com/'
PAGE_LIMIT = 28


class HTTPError(RuntimeError):
    status: int = 0
    retry_after: Optional[str] = None
    body: str = ''


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def open_session(s: S, headed: bool = True) -> None:
    """Open chatgpt.com in this session. Caller must verify login state."""
    s.persistent = True
    try:
        s.open(BASE_URL, headed=headed)
    except Exception:
        s.goto(BASE_URL)


def is_logged_in(s: S) -> bool:
    """True if /api/auth/session returns a user object."""
    sess = s.eval(
        "fetch('/api/auth/session').then(r=>r.json()).then(j=>({user: j.user||null}))"
    )
    return bool(sess and sess.get('user'))


def access_token(s: S) -> str:
    """Return a fresh Bearer token from /api/auth/session."""
    j = s.eval("fetch('/api/auth/session').then(r=>r.json())")
    if not isinstance(j, dict) or 'accessToken' not in j:
        raise RuntimeError(f'no accessToken in /api/auth/session: {j!r}')
    return j['accessToken']


# ---------------------------------------------------------------------------
# Conversation list
# ---------------------------------------------------------------------------

def list_conversations(
    s: S,
    limit: Optional[int] = None,
    page_sleep: float = 0.4,
    checkpoint_path: Optional[str | Path] = None,
    partial_ok: bool = False,
    max_retries: int = 12,
) -> list[dict]:
    """Return all (or first `limit`) conversations as
    [{title, id, create_time, update_time}], newest-first by update_time.

    Paginates one page per `eval` call from Python — each call stays well
    under the playwright-cli 60s subprocess cap.

    If `checkpoint_path` is set, the running item list is flushed to disk
    after every successful page so a crash/abort never loses progress.

    If `partial_ok` is True, retry exhaustion (sustained 429) returns the
    partial item list with a warning instead of raising — caller is
    responsible for noting the index is incomplete.
    """
    cap = limit if limit is not None else 100000
    # Escalating backoff for sustained throttling. `level` climbs on every
    # retryable response (429/5xx) and only decays one step per clean page,
    # so a steady stream of 429s ramps the wait up instead of flapping at 60s.
    backoffs = [30, 60, 120, 240, 480]
    cp = Path(checkpoint_path) if checkpoint_path else None

    def _flush(items: list[dict], complete: bool) -> None:
        if not cp:
            return
        cp.parent.mkdir(parents=True, exist_ok=True)
        tmp = cp.with_suffix(cp.suffix + '.tmp')
        tmp.write_text(_json.dumps(
            {'total': len(items), 'complete': complete, 'items': items},
            ensure_ascii=False, indent=2,
        ))
        tmp.rename(cp)

    all_items: list[dict] = []
    off = 0
    level = 0
    retries = 0
    while off < 200000 and len(all_items) < cap:
        js = (
            "(async()=>{"
            "const s=await fetch('/api/auth/session').then(r=>r.json());"
            f"const r=await fetch('/backend-api/conversations?offset={off}&limit={PAGE_LIMIT}&order=updated',"
            "  {headers:{'Authorization':'Bearer '+s.accessToken}});"
            "if(!r.ok) return {status:r.status};"
            "const j=await r.json();"
            "return {items:(j.items||[]).map(i=>({title:i.title, id:i.id, create_time:i.create_time, update_time:i.update_time}))};"
            "})()"
        )
        out = s.eval(js)
        status = out.get('status') if isinstance(out, dict) else None
        if status == 429 or (status is not None and status >= 500):
            retries += 1
            if retries > max_retries:
                _flush(all_items, complete=False)
                msg = (
                    f'index: {max_retries} retries exhausted at offset {off} '
                    f'(last status {status}); got {len(all_items)} items so far'
                )
                if partial_ok:
                    print(f'  WARN: {msg}', flush=True)
                    return all_items[:cap]
                raise RuntimeError(msg + '; rest 10+ min and resume')
            wait = backoffs[min(level, len(backoffs) - 1)]
            level += 1
            print(f'  index {status} at offset {off}; sleeping {wait}s '
                  f'(retry {retries}/{max_retries})', flush=True)
            _time.sleep(wait)
            continue
        if not isinstance(out, dict) or 'items' not in out:
            raise RuntimeError(f'unexpected list result at offset {off}: {out!r}')
        level = max(0, level - 1)
        items = out['items']
        all_items.extend(items)
        _flush(all_items, complete=False)
        if len(items) < PAGE_LIMIT:
            _flush(all_items, complete=True)
            break
        off += PAGE_LIMIT
        _time.sleep(page_sleep)
    return all_items[:cap]


# ---------------------------------------------------------------------------
# Single conversation
# ---------------------------------------------------------------------------

def get_conversation(s: S, conv_id: str) -> dict:
    """Fetch the full conversation tree (as ChatGPT returns it).

    Raises HTTPError on non-2xx (with .status set so callers can detect 429).
    """
    js = (
        "(async()=>{"
        "const s=await fetch('/api/auth/session').then(r=>r.json());"
        f"const r=await fetch('/backend-api/conversation/{conv_id}',"
        "  {headers:{'Authorization':'Bearer '+s.accessToken}});"
        "const text=await r.text();"
        "return {status:r.status, retry_after:r.headers.get('retry-after'), body:text};"
        "})()"
    )
    out = s.eval(js)
    if not isinstance(out, dict) or 'status' not in out:
        raise RuntimeError(f'unexpected conversation result: {out!r}')
    status = out['status']
    if status >= 400:
        err = HTTPError(f'GET /conversation/{conv_id} -> {status}')
        err.status = status
        err.retry_after = out.get('retry_after')
        err.body = (out.get('body') or '')[:500]
        raise err
    try:
        return _json.loads(out['body'])
    except Exception as e:
        raise RuntimeError(f'invalid JSON for {conv_id}: {e}; head={out["body"][:200]!r}')


def first_user_message(conv: dict) -> Optional[str]:
    """Walk a conversation tree and return the text of the first user message
    (oldest by create_time). Concatenates text parts; ignores images/tools.
    """
    mapping = conv.get('mapping') or {}
    user_msgs = []
    for _node_id, node in mapping.items():
        msg = (node or {}).get('message') or {}
        author = (msg.get('author') or {}).get('role')
        if author != 'user':
            continue
        content = msg.get('content') or {}
        parts = content.get('parts') or []
        text_parts = [p for p in parts if isinstance(p, str) and p.strip()]
        if not text_parts:
            continue
        user_msgs.append((msg.get('create_time') or 0, '\n'.join(text_parts)))
    if not user_msgs:
        return None
    user_msgs.sort(key=lambda x: x[0])
    return user_msgs[0][1]


# ---------------------------------------------------------------------------
# Dumps
# ---------------------------------------------------------------------------

def dump_topics(s: S, out_path: str | Path, limit: Optional[int] = None) -> Path:
    """List all conversations and write JSON to out_path."""
    items = list_conversations(s, limit=limit)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps({'total': len(items), 'items': items}, ensure_ascii=False, indent=2))
    return out


def dump_all_conversations(
    s: S,
    out_dir: str | Path,
    db_path: Optional[str | Path] = None,
    sleep_sec: float = 0.6,
    progress_every: int = 25,
    limit: Optional[int] = None,
    refresh_index: bool = True,
    slow_poll: bool = False,
) -> dict:
    """Download every conversation body to `out_dir/conversation_data/{id}.json`,
    backed by sqlite at `db_path` (default `data/db/chatgpt.sqlite`).

    Skip rules (in priority order):
      1. If sqlite row has `update_time` matching the latest index AND the file
         exists -> SKIP (no API call).
      2. If the file exists but no sqlite row, backfill the row from the file's
         top-level `update_time` and re-evaluate (1).
      3. Otherwise FETCH and UPSERT the row.

    Other behaviour:
      - Re-fetches the conversation index unless refresh_index=False. Always
        also writes a JSON snapshot to `out_dir/conversations.json` for
        offline/jq use.
      - On HTTP 429, backs off 60s → 120s → 240s. Four consecutive failures -> abort.
      - Atomic write via `.tmp` + rename.
      - Errors logged to sqlite `errors` table.
      - Conversations seen in DB but not in latest index -> status='deleted'
        (file kept).

    Returns a summary dict {total, fetched, updated, skipped, failed, deleted_seen}.
    `updated` = subset of `fetched` that re-fetched because update_time changed.
    """
    out_root = Path(out_dir)
    data_dir = out_root / 'conversation_data'
    data_dir.mkdir(parents=True, exist_ok=True)

    if slow_poll:
        index_page_sleep = 3.0
        sleep_sec = max(sleep_sec, 1.5)
    else:
        index_page_sleep = 0.4

    db = _db_open(Path(db_path) if db_path else DEFAULT_DB_PATH)
    index_complete = True
    try:
        idx_path = out_root / 'conversations.json'
        if refresh_index or not idx_path.exists():
            idx = list_conversations(
                s,
                limit=limit,
                page_sleep=index_page_sleep,
                checkpoint_path=idx_path,
                partial_ok=slow_poll,
            )
            # In slow_poll mode the run may return early on throttling.
            snap = _json.loads(idx_path.read_text()) if idx_path.exists() else {}
            index_complete = bool(snap.get('complete', not slow_poll))
            (out_root / 'conversations.json').write_text(
                _json.dumps(
                    {'total': len(idx), 'complete': index_complete, 'items': idx},
                    ensure_ascii=False, indent=2,
                )
            )
            _db_set_meta(db, 'last_index_fetch', _now_iso())
            _db_set_meta(db, 'index_total', str(len(idx)))
            _db_set_meta(db, 'index_complete', '1' if index_complete else '0')
        else:
            snap = _json.loads(idx_path.read_text())
            idx = snap['items']
            index_complete = bool(snap.get('complete', True))
            if limit:
                idx = idx[:limit]

        total = len(idx)
        fetched = 0
        updated = 0
        skipped = 0
        failed = 0
        consecutive_429 = 0
        backoffs = [60, 120, 240]

        for i, item in enumerate(idx, 1):
            cid = item['id']
            idx_update = item.get('update_time') or item.get('update')
            idx_create = item.get('create_time') or item.get('create')
            out_file = data_dir / f'{cid}.json'

            row = _db_get_conv(db, cid)

            # Backfill from existing file if no row yet.
            # Trust the file as current — record idx_update_time so the
            # subsequent comparison skips. If the conv was actually modified
            # between body fetch and now, the next sync will catch it.
            if row is None and out_file.exists() and out_file.stat().st_size > 0:
                _db_upsert_conv(db, cid, {
                    'title': item.get('title'),
                    'create_time': idx_create,
                    'update_time': idx_update or _file_update_time(out_file),
                    'fetched_at': _now_iso(),
                    'size': out_file.stat().st_size,
                    'status': 'active',
                })
                row = _db_get_conv(db, cid)

            if (
                out_file.exists()
                and out_file.stat().st_size > 0
                and row
                and row['update_time'] == idx_update
                and row['status'] == 'active'
            ):
                skipped += 1
                continue

            is_update = out_file.exists()

            try:
                conv = get_conversation(s, cid)
            except HTTPError as e:
                if e.status == 429:
                    wait = backoffs[min(consecutive_429, len(backoffs) - 1)]
                    consecutive_429 += 1
                    print(f'  [{i}/{total}] 429 rate-limited on {cid}; sleeping {wait}s', flush=True)
                    _time.sleep(wait)
                    if consecutive_429 > len(backoffs):
                        print(f'  ABORT: 4 consecutive 429s on {cid}', flush=True)
                        break
                    try:
                        conv = get_conversation(s, cid)
                        consecutive_429 = 0
                    except Exception as e2:
                        failed += 1
                        _db_log_error(db, cid, e2)
                        continue
                else:
                    failed += 1
                    _db_log_error(db, cid, e)
                    continue
            except Exception as e:
                failed += 1
                _db_log_error(db, cid, e)
                continue
            else:
                consecutive_429 = 0

            tmp = out_file.with_suffix('.json.tmp')
            tmp.write_text(_json.dumps(conv, ensure_ascii=False))
            tmp.rename(out_file)

            _db_upsert_conv(db, cid, {
                'title': item.get('title'),
                'create_time': idx_create,
                'update_time': idx_update or _file_update_time(out_file),
                'fetched_at': _now_iso(),
                'size': out_file.stat().st_size,
                'status': 'active',
            })
            fetched += 1
            if is_update:
                updated += 1
            if i % progress_every == 0:
                db.commit()
                print(
                    f'  [{i}/{total}] fetched={fetched} updated={updated} '
                    f'skipped={skipped} failed={failed}',
                    flush=True,
                )
            _time.sleep(sleep_sec)

        # Mark deletions — only safe when the index is fully scanned. A
        # partial index (slow_poll abort) doesn't see older pages, so its
        # absences mean nothing.
        if index_complete:
            live_ids = {it['id'] for it in idx}
            deleted_seen = _db_mark_deleted(db, live_ids)
        else:
            deleted_seen = 0
            print('  index partial — skipping deleted-mark', flush=True)
        _db_set_meta(db, 'last_run_at', _now_iso())
        db.commit()
    finally:
        db.close()

    summary = {
        'total': total,
        'fetched': fetched,
        'updated': updated,
        'skipped': skipped,
        'failed': failed,
        'deleted_seen': deleted_seen,
    }
    print(f'DONE: {summary}', flush=True)
    return summary


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
  id           TEXT PRIMARY KEY,
  title        TEXT,
  create_time  TEXT,
  update_time  TEXT,
  fetched_at   TEXT,
  size         INTEGER,
  status       TEXT DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_conv_update ON conversations(update_time);
CREATE INDEX IF NOT EXISTS idx_conv_status ON conversations(status);

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS errors (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  conv_id     TEXT,
  occurred_at TEXT,
  status_code INTEGER,
  msg         TEXT
);
CREATE INDEX IF NOT EXISTS idx_err_conv ON errors(conv_id);
"""


def _db_open(path: Path) -> _sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _sqlite3.connect(str(path))
    conn.row_factory = _sqlite3.Row
    conn.executescript(_DB_SCHEMA)
    conn.commit()
    return conn


def _db_get_conv(conn: _sqlite3.Connection, conv_id: str) -> Optional[dict]:
    row = conn.execute('SELECT * FROM conversations WHERE id=?', (conv_id,)).fetchone()
    return dict(row) if row else None


def _db_upsert_conv(conn: _sqlite3.Connection, conv_id: str, fields: dict) -> None:
    cols = ['title', 'create_time', 'update_time', 'fetched_at', 'size', 'status']
    vals = [fields.get(c) for c in cols]
    placeholders = ','.join('?' for _ in cols)
    set_clause = ','.join(f'{c}=excluded.{c}' for c in cols)
    conn.execute(
        f'INSERT INTO conversations (id,{",".join(cols)}) VALUES (?,{placeholders}) '
        f'ON CONFLICT(id) DO UPDATE SET {set_clause}',
        (conv_id, *vals),
    )


def _db_set_meta(conn: _sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        'INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
        (key, value),
    )


def _db_log_error(conn: _sqlite3.Connection, conv_id: str, exc: Exception) -> None:
    status = exc.status if isinstance(exc, HTTPError) else None
    conn.execute(
        'INSERT INTO errors(conv_id, occurred_at, status_code, msg) VALUES(?,?,?,?)',
        (conv_id, _now_iso(), status, f'{type(exc).__name__}: {str(exc)[:300]}'),
    )


def _db_mark_deleted(conn: _sqlite3.Connection, live_ids: set) -> int:
    """Mark rows whose id is not in live_ids as status='deleted'.
    Returns the number of newly-marked rows.
    """
    rows = conn.execute(
        "SELECT id FROM conversations WHERE status='active'"
    ).fetchall()
    deleted_now = [r['id'] for r in rows if r['id'] not in live_ids]
    if not deleted_now:
        return 0
    conn.executemany(
        "UPDATE conversations SET status='deleted' WHERE id=?",
        [(i,) for i in deleted_now],
    )
    return len(deleted_now)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return _time.strftime('%Y-%m-%dT%H:%M:%SZ', _time.gmtime())


def _file_update_time(path: Path) -> Optional[str]:
    """Read top-level `update_time` from a saved conversation file and return
    it as ISO Z microseconds, matching the index format."""
    try:
        conv = _json.loads(path.read_text())
    except Exception:
        return None
    ts = conv.get('update_time')
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat().replace('+00:00', 'Z')
    return str(ts)


def sync_new(
    s: S,
    out_dir: str | Path = 'output/chatgpt',
    db_path: Optional[str | Path] = None,
    sleep_sec: float = 0.6,
) -> dict:
    """Refresh index and fetch only conversations whose update_time has changed
    (or are missing). Convenience wrapper for incremental updates.
    """
    return dump_all_conversations(
        s, out_dir, db_path=db_path, sleep_sec=sleep_sec, refresh_index=True
    )


def dump_with_first_messages(
    s: S,
    out_path: str | Path,
    limit: Optional[int] = None,
    sleep_sec: float = 0.4,
    progress_every: int = 25,
) -> Path:
    """Like `dump_topics`, but also fetches the first user message per
    conversation. Slow (one HTTP per conversation) — sleep between calls so we
    don't trip server-side rate limits. Resumes nothing; rerun re-downloads.
    """
    items = list_conversations(s, limit=limit)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    enriched = []
    for idx, it in enumerate(items, 1):
        try:
            conv = get_conversation(s, it['id'])
            it = {**it, 'first_user_message': first_user_message(conv)}
        except Exception as e:
            it = {**it, 'first_user_message': None, 'error': str(e)[:200]}
        enriched.append(it)
        if idx % progress_every == 0:
            print(f'  fetched {idx}/{len(items)}', flush=True)
        _time.sleep(sleep_sec)
    out.write_text(_json.dumps({'total': len(enriched), 'items': enriched}, ensure_ascii=False, indent=2))
    return out


__all__ = [
    'BASE_URL',
    'HTTPError',
    'open_session',
    'is_logged_in',
    'access_token',
    'list_conversations',
    'get_conversation',
    'first_user_message',
    'dump_topics',
    'dump_all_conversations',
    'dump_with_first_messages',
    'sync_new',
]
