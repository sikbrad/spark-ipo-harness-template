"""raindrop-infer: per-bookmark content fetch → LLM summary → md.

Reads `data/raindrop/dump/raindrops/*.json` (produced by `raindrop_dump.py`),
routes each link to the appropriate fetcher, sends content to OpenAI for
JSON-mode summarization, and writes `data/raindrop/infer/<id>.md` plus
updates `data/raindrop/infer_state.sqlite`.

CLI:
    python proc/lib/raindrop_infer.py run                     # incremental
    python proc/lib/raindrop_infer.py run --limit 10          # smoke
    python proc/lib/raindrop_infer.py run --domain youtube.com
    python proc/lib/raindrop_infer.py run --id 1362373671
    python proc/lib/raindrop_infer.py run --force
    python proc/lib/raindrop_infer.py status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetchers import auth_wall, generic, github, route, share_google, youtube  # noqa: E402
from infer_state import DEFAULT_STATE_PATH, InferState  # noqa: E402
from llm import INFER_SYSTEM_PROMPT, LLMClient, LLMError, render_md  # noqa: E402

DUMP_DIR = Path("data/raindrop/dump/raindrops")
INFER_DIR = Path("data/raindrop/infer")
DEFAULT_STATE = DEFAULT_STATE_PATH

FETCHERS = {
    "youtube": youtube.fetch,
    "github": github.fetch,
    "share_google": share_google.fetch,
    "threads": auth_wall.fetch_threads,
    "instagram": auth_wall.fetch_instagram,
    "linkedin": auth_wall.fetch_linkedin,
    "generic": generic.fetch,
}


def _load_raindrops() -> list[dict]:
    items = []
    for p in sorted(DUMP_DIR.glob("*.json")):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return items


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _domain(link: str) -> str:
    from urllib.parse import urlparse
    try:
        return urlparse(link).netloc.lower().removeprefix("www.").removeprefix("m.")
    except Exception:
        return ""


def _format_user_prompt(rd: dict, fetch_result: dict) -> str:
    text = fetch_result.get("text") or ""
    return json.dumps({
        "raindrop": {
            "title": rd.get("title"),
            "excerpt": rd.get("excerpt"),
            "note": rd.get("note"),
            "tags": rd.get("tags") or [],
            "type": rd.get("type"),
            "domain": _domain(rd.get("link", "")),
            "created": rd.get("created"),
            "lastUpdate": rd.get("lastUpdate"),
            "link": rd.get("link"),
        },
        "fetched": {
            "fetcher": fetch_result.get("fetcher"),
            "fetch_status": fetch_result.get("status"),
            "meta": fetch_result.get("meta"),
            "text": text,
        },
    }, ensure_ascii=False, indent=2)


def _process_one(
    rd: dict,
    state: InferState,
    llm: LLMClient,
    out_dir: Path,
    *,
    force: bool,
    verbose: bool,
) -> str:
    rid = str(rd.get("_id"))
    link = rd.get("link") or ""
    if not link:
        return "skipped-no-link"

    cur_lu = rd.get("lastUpdate")
    existing = state.get(rid)
    md_path = out_dir / f"{rid}.md"

    # skip if cached + same lastUpdate + md exists + not force
    if (not force) and existing and existing.get("status") == "ok" \
            and existing.get("raindrop_lu") == cur_lu and md_path.exists():
        return "skip"

    fetcher_name = route(link)
    fetcher_fn = FETCHERS[fetcher_name]
    if verbose:
        print(f"  [{rid}] {fetcher_name:11s} {link[:80]}", flush=True)

    try:
        result = fetcher_fn(link, rd)
    except Exception as e:
        result = {
            "status": "failed",
            "fetcher": fetcher_name,
            "text": "",
            "meta": {"final_url": link},
            "error": f"fetcher exception: {type(e).__name__}: {e}",
        }

    status = result.get("status", "failed")
    text = result.get("text") or ""
    err = result.get("error")

    if status == "failed" and not text:
        # nothing for LLM to chew on — record and bail
        state.upsert(
            id_=rid, link=link, domain=_domain(link),
            fetcher=fetcher_name, status="failed",
            raindrop_lu=cur_lu, content_hash=None, error=err,
            retry_inc=True,
        )
        return "failed"

    # LLM summarize
    try:
        llm_out = llm.chat_json(
            system=INFER_SYSTEM_PROMPT,
            user=_format_user_prompt(rd, result),
            max_tokens=1400,
        )
    except LLMError as e:
        state.upsert(
            id_=rid, link=link, domain=_domain(link),
            fetcher=fetcher_name, status="failed",
            raindrop_lu=cur_lu, content_hash=_content_hash(text),
            error=f"llm: {e}", retry_inc=True,
        )
        return "llm-failed"

    md_meta = {
        "id": rid,
        "link": link,
        "title": rd.get("title"),
        "type": rd.get("type"),
        "domain": _domain(link),
        "fetcher": fetcher_name,
        "status": status,
        "raindrop_tags": rd.get("tags") or [],
        "raindrop_created": rd.get("created"),
        "raindrop_last_update": cur_lu,
        "inferred_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    md = render_md(md_meta, llm_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")

    state.upsert(
        id_=rid, link=link, domain=_domain(link),
        fetcher=fetcher_name, status=status if status != "ok" else "ok",
        raindrop_lu=cur_lu, content_hash=_content_hash(text), error=err,
    )
    return "ok"


def run(
    *,
    state_path: Path,
    out_dir: Path,
    limit: int | None,
    domain_filter: str | None,
    id_filter: str | None,
    force: bool,
    verbose: bool,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    state = InferState(state_path)
    llm = LLMClient()

    items = _load_raindrops()
    if id_filter:
        items = [it for it in items if str(it.get("_id")) == id_filter]
    if domain_filter:
        items = [it for it in items if _domain(it.get("link", "")) == domain_filter]

    counts = {"ok": 0, "skip": 0, "failed": 0, "llm-failed": 0,
              "skipped-no-link": 0, "exception": 0}
    processed = 0
    t0 = time.time()
    for rd in items:
        if limit is not None and processed >= limit:
            break
        try:
            r = _process_one(rd, state, llm, out_dir,
                             force=force, verbose=verbose)
            counts[r] = counts.get(r, 0) + 1
            if r != "skip":
                processed += 1
        except KeyboardInterrupt:
            print("interrupted", flush=True)
            break
        except Exception:
            counts["exception"] += 1
            print(traceback.format_exc(limit=3), flush=True)

    elapsed = time.time() - t0
    state.close()
    return {"counts": counts, "elapsed_sec": round(elapsed, 1),
            "processed": processed}


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="raindrop-infer driver")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="process raindrops")
    pr.add_argument("--state", default=str(DEFAULT_STATE))
    pr.add_argument("--out", default=str(INFER_DIR))
    pr.add_argument("--limit", type=int, default=None)
    pr.add_argument("--domain", default=None,
                    help="only this domain (e.g. youtube.com)")
    pr.add_argument("--id", default=None, help="only this raindrop id")
    pr.add_argument("--force", action="store_true")
    pr.add_argument("--quiet", action="store_true")

    ps = sub.add_parser("status")
    ps.add_argument("--state", default=str(DEFAULT_STATE))

    args = p.parse_args(argv)

    if args.cmd == "status":
        s = InferState(args.state)
        print(json.dumps(s.stats(), ensure_ascii=False, indent=2))
        s.close()
        return 0

    if args.cmd == "run":
        summary = run(
            state_path=Path(args.state),
            out_dir=Path(args.out),
            limit=args.limit,
            domain_filter=args.domain,
            id_filter=args.id,
            force=args.force,
            verbose=not args.quiet,
        )
        print()
        print(f"=== done in {summary['elapsed_sec']}s ===")
        print(f"  processed {summary['processed']}")
        print(f"  counts    {summary['counts']}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
