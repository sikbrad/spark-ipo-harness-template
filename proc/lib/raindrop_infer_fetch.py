"""raindrop-infer manual mode — fetch content only, no LLM.

Used when the summary is written by hand (e.g. Claude in conversation).
Workflow:

  1) python3 proc/lib/raindrop_infer_fetch.py fetch --domain github.com
       → fetches each matching raindrop, writes JSON to
         data/raindrop/.fetched/<id>.json (raindrop + fetched text/meta)

  2) Manually write the md to data/raindrop/infer/<id>.md.

  3) python3 proc/lib/raindrop_infer_fetch.py mark-done --id <id>
       → updates SQLite state so the regular driver counts it as done.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetchers import auth_wall, generic, github, route, share_google, youtube  # noqa: E402
from infer_state import DEFAULT_STATE_PATH, InferState  # noqa: E402

DUMP_DIR = Path("data/raindrop/dump/raindrops")
FETCHED_DIR = Path("data/raindrop/.fetched")

FETCHERS = {
    "youtube": youtube.fetch,
    "github": github.fetch,
    "share_google": share_google.fetch,
    "threads": auth_wall.fetch_threads,
    "instagram": auth_wall.fetch_instagram,
    "linkedin": auth_wall.fetch_linkedin,
    "generic": generic.fetch,
}


def _domain(link: str) -> str:
    try:
        return urlparse(link).netloc.lower().removeprefix("www.").removeprefix("m.")
    except Exception:
        return ""


def _load_raindrops() -> list[dict]:
    items = []
    for p in sorted(DUMP_DIR.glob("*.json")):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return items


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fetch_one(rd: dict, *, verbose: bool = True) -> dict | None:
    rid = str(rd.get("_id"))
    link = rd.get("link") or ""
    if not link:
        return None
    fetcher_name = route(link)
    if verbose:
        print(f"  [{rid}] {fetcher_name:11s} {link[:90]}", flush=True)
    try:
        result = FETCHERS[fetcher_name](link, rd)
    except Exception as e:
        result = {
            "status": "failed", "fetcher": fetcher_name, "text": "",
            "meta": {"final_url": link},
            "error": f"{type(e).__name__}: {e}",
        }
    out = {
        "raindrop": {
            "id": rid,
            "link": link,
            "title": rd.get("title"),
            "excerpt": rd.get("excerpt"),
            "note": rd.get("note"),
            "tags": rd.get("tags") or [],
            "type": rd.get("type"),
            "domain": _domain(link),
            "created": rd.get("created"),
            "lastUpdate": rd.get("lastUpdate"),
        },
        "fetched": {
            "fetcher": result.get("fetcher"),
            "status": result.get("status"),
            "meta": result.get("meta"),
            "text": result.get("text"),
            "error": result.get("error"),
        },
        "fetched_at": _now(),
    }
    FETCHED_DIR.mkdir(parents=True, exist_ok=True)
    (FETCHED_DIR / f"{rid}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


def cmd_fetch(args) -> int:
    items = _load_raindrops()
    if args.id:
        items = [it for it in items if str(it.get("_id")) == args.id]
    if args.domain:
        items = [it for it in items if _domain(it.get("link", "")) == args.domain]
    if args.limit is not None:
        items = items[: args.limit]
    if not items:
        print("no matching raindrops")
        return 1
    t0 = time.time()
    n = 0
    for rd in items:
        try:
            r = fetch_one(rd, verbose=not args.quiet)
            if r:
                n += 1
        except KeyboardInterrupt:
            print("interrupted")
            break
    print(f"\nfetched {n} → {FETCHED_DIR}  ({round(time.time()-t0,1)}s)")
    return 0


def cmd_mark_done(args) -> int:
    state = InferState(args.state)
    fetched_path = FETCHED_DIR / f"{args.id}.json"
    if not fetched_path.exists():
        print(f"no .fetched/{args.id}.json — run fetch first")
        return 1
    blob = json.loads(fetched_path.read_text(encoding="utf-8"))
    rd = blob["raindrop"]
    f = blob["fetched"]
    state.upsert(
        id_=rd["id"],
        link=rd["link"],
        domain=rd["domain"],
        fetcher=f.get("fetcher") or "manual",
        status=args.status,
        raindrop_lu=rd.get("lastUpdate"),
        content_hash=_hash(f.get("text") or ""),
        error=None,
    )
    state.close()
    print(f"marked {args.id} as {args.status}")
    return 0


def cmd_list(args) -> int:
    """List raindrops matching filter, showing whether each has an md output."""
    items = _load_raindrops()
    if args.domain:
        items = [it for it in items if _domain(it.get("link", "")) == args.domain]
    out = Path(args.out)
    for rd in items:
        rid = str(rd.get("_id"))
        md = out / f"{rid}.md"
        marker = "✓" if md.exists() else " "
        print(f"  {marker} {rid}  {(rd.get('title') or '')[:80]}")
        print(f"      {rd.get('link')}")
    return 0


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="raindrop-infer manual-mode helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("fetch", help="fetch content, write JSON, no LLM")
    pf.add_argument("--id")
    pf.add_argument("--domain")
    pf.add_argument("--limit", type=int)
    pf.add_argument("--quiet", action="store_true")

    pm = sub.add_parser("mark-done", help="mark a single raindrop done in state")
    pm.add_argument("--id", required=True)
    pm.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    pm.add_argument("--status", default="ok",
                    choices=["ok", "partial", "failed"])

    pl = sub.add_parser("list", help="list raindrops + md presence")
    pl.add_argument("--domain")
    pl.add_argument("--out", default="data/raindrop/infer")

    args = p.parse_args(argv)
    if args.cmd == "fetch":
        return cmd_fetch(args)
    if args.cmd == "mark-done":
        return cmd_mark_done(args)
    if args.cmd == "list":
        return cmd_list(args)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
