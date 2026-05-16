"""raindrop_retag.py — re-tag raindrops (정확히 3개) + AI 메모를 note에 append.

For each raindrop:
1. Read dump/raindrops/<id>.json (current tags + note + title)
2. Read infer/<id>.md (LLM-generated summary already on disk)
3. Send both to LLM, get back:
     - tags: 3 best-fit tags (prefer existing vocab in tags.json)
     - memo: 1-line "언제 다시 보면 좋을지" trigger
4. PUT /raindrop/<id> with:
     - tags: 3 LLM-chosen tags
     - note: existing_note + "\n\n--- ai memo ----\n{memo}\n----------------\n"
5. Idempotent: skip if note already contains '--- ai memo ----' (unless --force).

CLI:
    python proc/lib/raindrop_retag.py run --id 1112329686 --dry-run
    python proc/lib/raindrop_retag.py run --id 1112329686
    python proc/lib/raindrop_retag.py run --limit 5
    python proc/lib/raindrop_retag.py run                        # all
    python proc/lib/raindrop_retag.py run --force                # ignore marker
    python proc/lib/raindrop_retag.py status                     # progress count
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import LLMClient, LLMError  # noqa: E402
from raindrop_api import RaindropClient, RaindropError  # noqa: E402

DUMP_DIR = Path("data/raindrop/dump/raindrops")
TAGS_PATH = Path("data/raindrop/dump/tags.json")
INFER_DIR = Path("data/raindrop/infer")

AI_MEMO_HEAD = "--- ai memo ----"
AI_MEMO_TAIL = "----------------"

TOP_TAGS_K = 80  # ground LLM on top-N existing tags

RETAG_SYSTEM_PROMPT = """\
당신은 사용자의 raindrop 북마크 1건을 분석해
(1) 가장 적합한 태그 정확히 3개와
(2) "언제 이 북마크를 다시 펴보면 좋을지" 짧은 한국어 메모를
만드는 어시스턴트입니다.

출력은 반드시 다음 JSON 스키마(다른 키 금지):

{
  "tags": ["...", "...", "..."],     // 정확히 3개, 중복 금지
  "memo": "..."                       // 80자 이내 한 줄, 한국어
}

태그 규칙:
- 정확히 3개. 중복 금지. 의미가 겹치는 태그도 금지 (예: "AI"+"LLM"는 OK,
  "AI"+"인공지능"는 중복으로 간주).
- top_tags 목록 안의 태그를 우선 선택. 거기에 정말로 들어맞는 게 없을 때만
  새 태그를 1-2개 만들 수 있음.
- 한국어 단일 단어/구. 너무 일반적("기술") 보다 의미가 잡히는 것("LLM",
  "프롬프트", "자동화") 선호.
- 카테고리 mixed 태그("기술/비즈니스" 같은 슬래시 묶음)는 피하기.
- current_tags(사용자가 이미 단 태그)는 참고만 — 그대로 복사 금지. 컨텐츠
  본질을 다시 판단할 것.

메모 규칙:
- "언제 다시 보면 좋을지" 한 줄 트리거 문장.
- 80자 이내. 구체적 상황 1-2개 명시 권장
  ("신입 멘토링 시", "팀에 OCR 도입 검토할 때" 등).
- "참고", "유용", "도움이 됨" 같은 일반어/막연한 표현 금지.
- 본 북마크가 evergreen(재방문 가치 높음)이면 트리거 위주, short(뉴스성)이면
  "다시 안 봐도 됨" 같은 솔직한 표현도 가능.
"""


def _load_top_tags(k: int = TOP_TAGS_K) -> list[str]:
    if not TAGS_PATH.exists():
        return []
    raw = json.loads(TAGS_PATH.read_text(encoding="utf-8"))
    items = raw.get("items") or []
    return [it["_id"] for it in items[:k]]


def _has_ai_memo(note: str) -> bool:
    return AI_MEMO_HEAD in (note or "")


def _build_new_note(existing_note: str, ai_memo: str) -> str:
    base = (existing_note or "").rstrip()
    block = f"{AI_MEMO_HEAD}\n{ai_memo.strip()}\n{AI_MEMO_TAIL}"
    if not base:
        return block
    return f"{base}\n\n{block}"


def _format_user_prompt(rd: dict, infer_md: str, top_tags: list[str]) -> str:
    return json.dumps({
        "raindrop": {
            "id": rd.get("_id"),
            "title": rd.get("title"),
            "link": rd.get("link"),
            "excerpt": rd.get("excerpt"),
            "type": rd.get("type"),
            "current_tags": rd.get("tags") or [],
        },
        "infer_md": infer_md,
        "top_tags": top_tags,
    }, ensure_ascii=False, indent=2)


def process_one(
    *,
    rid: str,
    client: RaindropClient | None,
    llm: LLMClient,
    top_tags: list[str],
    force: bool,
    dry_run: bool,
    verbose: bool,
) -> dict:
    rd_path = DUMP_DIR / f"{rid}.json"
    md_path = INFER_DIR / f"{rid}.md"

    if not rd_path.exists():
        return {"id": rid, "status": "no-dump"}
    rd = json.loads(rd_path.read_text(encoding="utf-8"))
    if not md_path.exists():
        return {"id": rid, "status": "no-infer"}
    infer_md = md_path.read_text(encoding="utf-8")

    note = rd.get("note") or ""
    if (not force) and _has_ai_memo(note):
        return {"id": rid, "status": "skip-already-tagged"}

    user_prompt = _format_user_prompt(rd, infer_md, top_tags)
    try:
        out = llm.chat_json(
            system=RETAG_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=400,
            temperature=0.2,
        )
    except LLMError as e:
        return {"id": rid, "status": "llm-failed", "error": str(e)}

    new_tags = out.get("tags") or []
    ai_memo = (out.get("memo") or "").strip()
    if not isinstance(new_tags, list) or len(new_tags) != 3 or not ai_memo:
        return {"id": rid, "status": "bad-llm-output", "raw": out}
    # dedupe (case-insensitive) — sometimes LLM still slips a dupe in
    seen: list[str] = []
    for t in new_tags:
        if isinstance(t, str) and t.strip() and t.strip().lower() not in {s.lower() for s in seen}:
            seen.append(t.strip())
    if len(seen) != 3:
        return {"id": rid, "status": "bad-llm-output", "raw": out}
    new_tags = seen

    new_note = _build_new_note(note, ai_memo)

    if verbose:
        title = (rd.get("title") or "")[:60]
        print(f"  [{rid}] {title}", flush=True)
        print(f"        tags: {' / '.join(new_tags)}", flush=True)
        print(f"        memo: {ai_memo}", flush=True)

    if dry_run:
        return {
            "id": rid, "status": "dry-run",
            "tags": new_tags, "memo": ai_memo,
            "new_note": new_note,
        }

    if client is None:
        return {"id": rid, "status": "no-client"}

    try:
        client.request("PUT", f"/raindrop/{rid}", json={
            "tags": new_tags,
            "note": new_note,
        })
    except RaindropError as e:
        return {"id": rid, "status": "api-failed", "error": str(e)}

    # mirror change back into local dump so future runs see new state
    rd["tags"] = new_tags
    rd["note"] = new_note
    rd_path.write_text(
        json.dumps(rd, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {"id": rid, "status": "ok", "tags": new_tags, "memo": ai_memo}


def _iter_ids() -> list[str]:
    return sorted(p.stem for p in DUMP_DIR.glob("*.json"))


def run(
    *,
    ids: list[str] | None,
    limit: int | None,
    force: bool,
    dry_run: bool,
    verbose: bool,
) -> dict:
    top_tags = _load_top_tags()
    llm = LLMClient()
    client = None if dry_run else RaindropClient.from_env()

    pool = ids if ids else _iter_ids()
    counts: dict[str, int] = {}
    processed = 0
    t0 = time.time()

    for rid in pool:
        if limit is not None and processed >= limit:
            break
        try:
            r = process_one(
                rid=rid,
                client=client,
                llm=llm,
                top_tags=top_tags,
                force=force,
                dry_run=dry_run,
                verbose=verbose,
            )
        except KeyboardInterrupt:
            print("interrupted", flush=True)
            break
        except Exception:  # noqa: BLE001
            counts["exception"] = counts.get("exception", 0) + 1
            print(traceback.format_exc(limit=3), flush=True)
            continue
        st = r.get("status", "?")
        counts[st] = counts.get(st, 0) + 1
        if st != "skip-already-tagged":
            processed += 1
        if verbose and processed and processed % 25 == 0:
            print(f"  -- progress: processed={processed} {counts}", flush=True)

    return {
        "counts": counts,
        "processed": processed,
        "elapsed_sec": round(time.time() - t0, 1),
    }


def status() -> dict:
    total = 0
    tagged = 0
    untagged = 0
    no_infer = 0
    for p in DUMP_DIR.glob("*.json"):
        total += 1
        try:
            rd = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if _has_ai_memo(rd.get("note") or ""):
            tagged += 1
        else:
            untagged += 1
        if not (INFER_DIR / f"{p.stem}.md").exists():
            no_infer += 1
    return {
        "total_raindrops": total,
        "with_ai_memo": tagged,
        "without_ai_memo": untagged,
        "missing_infer_md": no_infer,
    }


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="raindrop-retag driver")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="process raindrops")
    pr.add_argument("--id", action="append", default=None,
                    help="specific raindrop id(s); repeat for multiple")
    pr.add_argument("--limit", type=int, default=None)
    pr.add_argument("--force", action="store_true",
                    help="re-tag even if '--- ai memo ----' marker exists")
    pr.add_argument("--dry-run", action="store_true",
                    help="LLM only; no API write, no local mirror")
    pr.add_argument("--quiet", action="store_true")

    sub.add_parser("status", help="count tagged vs untagged")

    args = p.parse_args(argv)

    if args.cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "run":
        summary = run(
            ids=args.id,
            limit=args.limit,
            force=args.force,
            dry_run=args.dry_run,
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
