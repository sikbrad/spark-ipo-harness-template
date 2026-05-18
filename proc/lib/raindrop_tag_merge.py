"""raindrop_tag_merge.py — 동의어/표기 변형 태그 통합.

LLM이 전체 태그 분포(`data/raindrop/dump/raindrops/*.json` 집계)를 보고
**의미가 명확히 같은 태그들만** 묶어 `{target: [sources...]}` plan을 만든다.
사용자가 검수 후 `apply` 로 raindrop API에 적용.

raindrop API:
  PUT /rest/v1/tags/-1   body { "tags": [sources...], "replace": target }
  → 전체 컬렉션(-1) 내 source 태그를 모두 target으로 일괄 rename.

CLI:
    python3 proc/lib/raindrop_tag_merge.py plan         # LLM이 plan 생성 → data/raindrop/tag_merge_plan.json
    python3 proc/lib/raindrop_tag_merge.py show         # 현재 plan 출력
    python3 proc/lib/raindrop_tag_merge.py apply --dry-run
    python3 proc/lib/raindrop_tag_merge.py apply        # 실제 적용
    python3 proc/lib/raindrop_tag_merge.py mirror       # 적용 후 로컬 dump의 tags 필드도 mirror update
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import LLMClient, LLMError  # noqa: E402
from raindrop_api import RaindropClient, RaindropError  # noqa: E402

DUMP_DIR = Path("data/raindrop/dump/raindrops")
PLAN_PATH = Path("data/raindrop/tag_merge_plan.json")

# 영한 동치 사전 — 정규화로 못 잡는 명백한 페어. count 높은 쪽이 target이 되도록 alias로 표현.
KO_EN_ALIASES: dict[str, list[str]] = {
    "AI": ["인공지능", "ai"],
    "머신러닝": ["기계학습", "machinelearning", "Machine Learning", "machine learning"],
    "딥러닝": ["deep learning", "Deep Learning", "deeplearning"],
    "오픈소스": ["Open-source", "open source", "opensource", "Opensource"],
    "Python": ["파이썬"],
    "macOS": ["맥", "Mac", "MacOS"],
    "데브옵스": ["DevOps", "devops"],
    "도커": ["Docker", "docker"],
    "쿠버네티스": ["Kubernetes", "k8s"],
    "깃허브": ["GitHub", "github"],
    "타입스크립트": ["TypeScript", "typescript"],
    "자바스크립트": ["JavaScript", "javascript", "js"],
    "리눅스": ["Linux", "linux"],
    "윈도우": ["Windows", "windows", "Windows 10"],
    "안드로이드": ["Android", "android"],
    "구글": ["Google", "google"],
    "유튜브": ["YouTube", "youtube"],
    "인스타그램": ["Instagram", "instagram", "IG"],
    "노션": ["Notion"],
    "자가호스팅": ["self-hosted", "Self-Hosting", "selfhosted", "Self-Hosted"],
    "데이터베이스": ["DB", "database", "Database"],
    "마크다운": ["Markdown", "markdown"],
    "API": ["api"],
    "CLI": ["cli"],
    "OCR": ["ocr"],
    "RAG": ["rag"],
    "MCP": ["mcp"],
    "LLM": ["llm"],
    "챗GPT": ["GPT", "ChatGPT", "chatgpt"],
    "영상": ["동영상"],
    "웃김": ["유머"],
    "AI 에이전트": ["AI Agent"],
    "VS Code": ["Visual Studio Code", "vscode"],
}


def _normalize(tag: str) -> str:
    """Canonical form for typo/whitespace/case/hyphen dedupe."""
    return (
        tag.lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .strip()
    )


def build_rule_plan(min_count_winner: int = 0) -> dict:
    """Rule-based merge plan:
    1. group by normalized form → if group has >1 distinct tag, merge to highest-count
    2. apply KO_EN_ALIASES dict
    Both passes union. target chosen by count (ties broken alphabetically).
    """
    counts: Counter = Counter()
    for path in DUMP_DIR.glob("*.json"):
        try:
            r = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for t in r.get("tags") or []:
            counts[t] += 1

    # Pass 1: normalization buckets
    buckets: dict[str, list[str]] = {}
    for tag in counts:
        buckets.setdefault(_normalize(tag), []).append(tag)

    merges: list[dict] = []
    used_sources: set[str] = set()

    for norm, members in buckets.items():
        if len(members) < 2:
            continue
        # pick target = highest count (ties → first alphabetically)
        members_sorted = sorted(members, key=lambda t: (-counts[t], t))
        target = members_sorted[0]
        sources = [t for t in members_sorted[1:]]
        if not sources:
            continue
        if counts[target] < min_count_winner:
            continue
        merges.append({
            "target": target,
            "sources": sources,
            "reason": "정규화 동치 (대소문자/띄어쓰기/하이픈)",
            "target_count": counts[target],
            "source_counts": [counts[s] for s in sources],
        })
        used_sources.update(sources)
        used_sources.add(target)

    # Pass 2: explicit 영한 dict — target은 코퍼스 내 count 가장 높은 멤버
    for dict_target, aliases in KO_EN_ALIASES.items():
        all_members = [dict_target] + list(aliases)
        present = [m for m in all_members if m in counts]
        if len(present) < 2:
            continue
        winner = max(present, key=lambda t: (counts[t], -all_members.index(t)))
        new_sources = [m for m in present if m != winner and m not in used_sources]
        if not new_sources:
            continue
        merges.append({
            "target": winner,
            "sources": new_sources,
            "reason": "영한 동치",
            "target_count": counts.get(winner, 0),
            "source_counts": [counts[s] for s in new_sources],
        })
        used_sources.update(new_sources)
        used_sources.add(winner)

    return {"merges": merges, "total_distinct_tags": len(counts)}

MERGE_SYSTEM_PROMPT = """\
당신은 raindrop 북마크 태그를 정리하는 전문가입니다.
**오직 표기 변형 또는 100% 동의어**인 태그들만 묶습니다.
"관련 있다"는 절대 묶지 않습니다.

출력 JSON (다른 키 금지):

{
  "merges": [
    {"target": "AI", "sources": ["인공지능", "ai"], "reason": "영한 동치"},
    {"target": "데이터 분석", "sources": ["데이터분석"], "reason": "띄어쓰기 변형"},
    ...
  ]
}

═══════ 묶어야 할 케이스 (반드시 잡을 것) ═══════

(1) **영한 동치** — 동일 단어의 한국어/영어 표기:
    Python ≡ 파이썬
    macOS ≡ 맥
    DevOps ≡ 데브옵스
    GitHub ≡ 깃허브
    Docker ≡ 도커
    인공지능 ≡ AI
    머신러닝 ≡ 기계학습 ≡ machinelearning ≡ Machine Learning
    딥러닝 ≡ deep learning ≡ Deep Learning
    클라우드 컴퓨팅 ≡ Cloud Computing
    SaaS, B2B SaaS — 자체 보존(이미 약어)

(2) **띄어쓰기/하이픈/대소문자 변형**:
    데이터분석 ≡ 데이터 분석
    데이터관리 ≡ 데이터 관리
    self-hosted ≡ Self-Hosting ≡ 자가호스팅
    Open-source ≡ 오픈소스
    AI 도구 ≡ AI도구

(3) **단순 단복수/명백한 동의어**:
    툴 ≡ 도구 (단, "개발도구"는 별개)
    영상 ≡ 동영상
    웃김 ≡ 유머 ≡ 밈 (각자 살리고 싶으면 보존 가능 — 보수적)

═══════ 절대 묶지 말 것 ═══════

(A) **상위-하위 관계** (포함 관계):
    "기술" ⊃ "코딩" ⊃ "프론트엔드" → 각자 별개
    "코드" vs "코드 리뷰" vs "코드 편집기" → 별개
    "프롬프트" vs "프롬프트 엔지니어링" → 별개 (후자가 더 좁음)
    "AI" vs "AI 코드 생성" → 별개

(B) **관련은 있지만 의미가 다름**:
    "비즈니스" vs "비즈니스 모델" vs "비즈니스 전략" → 각자 별개
    "튜토리얼" vs "강의" vs "교육" → 별개
    "API" vs "인터페이스" → 별개
    "문화" vs "예술" vs "문학" → 별개
    "음악" vs "음악사" → 별개
    "정치" vs "정책" vs "사회적 이슈" → 별개
    "프레임워크" vs "라이브러리" vs "개발 도구" → 별개
    "리더십" vs "팀워크" vs "조직관리" → 별개
    "건강" vs "의료" vs "헬스케어" → 각자 별개 (의료=의료서비스, 헬스케어=건강관리)

(C) **슬래시 묶음 카테고리** ("기술/비즈니스", "기술/교육" 등) → 그대로 두기.

(D) **고유명사** (사람/제품/회사명, 거의 count=1):
    "GLM-OCR", "K장녀", "MBK파트너스" 등 → 그대로 두기.

═══════ target 선택 규칙 ═══════

- 사용 횟수(count)가 **가장 높은 표기**가 target.
- 한글/영문 양쪽이 다 쓰이면 count 높은 쪽 우선 (count 같으면 한국어 우선).
- target은 sources에 들어가지 않음.

═══════ 절차 ═══════

1. 입력 태그 리스트를 처음부터 끝까지 한 번 훑어 (A)~(D)에 해당하지 않으면서
   (1)~(3)에 해당하는 짝을 모두 찾는다.
2. count=1인 롱테일 태그도 빠짐없이 확인 — 거기 표기 변형이 숨어 있음.
3. 의심스러우면 **묶지 않는다** — false positive가 false negative보다 위험.

목표: **표기 변형/영한 동치 위주**로 30~100개 그룹. 의미 유사도 기반 통합은
이 작업의 목적이 아님.
"""


def build_distribution() -> list[dict]:
    c: Counter = Counter()
    for path in DUMP_DIR.glob("*.json"):
        try:
            r = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for t in r.get("tags") or []:
            c[t] += 1
    return [{"tag": t, "count": n} for t, n in c.most_common()]


def build_plan() -> dict:
    dist = build_distribution()
    llm = LLMClient()
    user_prompt = json.dumps(
        {"tag_distribution": dist}, ensure_ascii=False, indent=2
    )
    return llm.chat_json(
        system=MERGE_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=16000,
        temperature=0.1,
    )


def show_plan(plan: dict) -> None:
    merges = plan.get("merges") or []
    print(f"=== merge plan: {len(merges)} groups ===")
    total_sources = 0
    for m in merges:
        target = m.get("target", "?")
        sources = m.get("sources") or []
        reason = m.get("reason", "")
        total_sources += len(sources)
        print(f"  {target}  ←  {', '.join(sources)}")
        if reason:
            print(f"     ({reason})")
    print(f"=== {total_sources} source tags will be merged into "
          f"{len(merges)} target tags ===")


def apply_plan(plan: dict, *, dry_run: bool, verbose: bool) -> dict:
    merges = plan.get("merges") or []
    if not merges:
        return {"applied": 0, "errors": []}
    if dry_run:
        for m in merges:
            print(f"  [dry-run] {m.get('sources')} → {m.get('target')}", flush=True)
        return {"applied": 0, "dry_run": True, "would_apply": len(merges)}

    client = RaindropClient.from_env()
    applied = 0
    errors: list[dict] = []
    for m in merges:
        target = m.get("target")
        sources = [s for s in (m.get("sources") or []) if s != target]
        if not target or not sources:
            continue
        try:
            client.request("PUT", "/tags/-1", json={
                "tags": sources,
                "replace": target,
            })
            applied += 1
            if verbose:
                print(f"  ok  {sources} → {target}", flush=True)
        except RaindropError as e:
            errors.append({
                "target": target, "sources": sources, "error": str(e),
            })
            if verbose:
                print(f"  ERR {sources} → {target}: {e}", flush=True)
    return {"applied": applied, "errors": errors}


def mirror_local(plan: dict, *, verbose: bool) -> dict:
    """Re-write local dump JSON files so each raindrop's tags reflect the merge."""
    merges = plan.get("merges") or []
    src2tgt: dict[str, str] = {}
    for m in merges:
        target = m.get("target")
        for s in (m.get("sources") or []):
            if target and s and s != target:
                src2tgt[s] = target

    updated = 0
    for path in DUMP_DIR.glob("*.json"):
        try:
            r = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        old = r.get("tags") or []
        # remap + dedupe (preserve order; first occurrence kept)
        new: list[str] = []
        seen: set[str] = set()
        for t in old:
            mapped = src2tgt.get(t, t)
            if mapped not in seen:
                new.append(mapped)
                seen.add(mapped)
        if new != old:
            r["tags"] = new
            path.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            updated += 1
            if verbose and updated % 100 == 0:
                print(f"  mirrored {updated} files...", flush=True)
    return {"updated_files": updated, "mappings": len(src2tgt)}


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="raindrop tag merge planner / applier")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("plan", help="LLM-generated merge plan")
    pp.add_argument("--out", default=str(PLAN_PATH))

    pr = sub.add_parser("rule-plan", help="rule-based plan (normalization + 영한 dict)")
    pr.add_argument("--out", default=str(PLAN_PATH))

    ps = sub.add_parser("show", help="show current plan")
    ps.add_argument("--in", dest="inp", default=str(PLAN_PATH))

    pa = sub.add_parser("apply", help="apply plan to raindrop API")
    pa.add_argument("--in", dest="inp", default=str(PLAN_PATH))
    pa.add_argument("--dry-run", action="store_true")
    pa.add_argument("--quiet", action="store_true")

    pm = sub.add_parser("mirror", help="rewrite local dump tags after apply")
    pm.add_argument("--in", dest="inp", default=str(PLAN_PATH))
    pm.add_argument("--quiet", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "plan":
        plan = build_plan()
        Path(args.out).write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        show_plan(plan)
        print(f"=> wrote {args.out}")
        return 0

    if args.cmd == "rule-plan":
        plan = build_rule_plan()
        Path(args.out).write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        show_plan(plan)
        print(f"=> wrote {args.out}")
        return 0

    if args.cmd == "show":
        plan = json.loads(Path(args.inp).read_text(encoding="utf-8"))
        show_plan(plan)
        return 0

    if args.cmd == "apply":
        plan = json.loads(Path(args.inp).read_text(encoding="utf-8"))
        r = apply_plan(plan, dry_run=args.dry_run, verbose=not args.quiet)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "mirror":
        plan = json.loads(Path(args.inp).read_text(encoding="utf-8"))
        r = mirror_local(plan, verbose=not args.quiet)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
