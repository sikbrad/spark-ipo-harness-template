from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from confluence_ax_reorg_execute_2026_06_08 import Client, MoveSpec, OUT_DIR, make_record


MOVES: list[MoveSpec] = [
    MoveSpec(
        "757039140",
        "[AX-182] 개발 서버 배포",
        "722960415",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱 / 주문웹 기획",
        "포탈 개발/배포 아키텍처 문서",
    ),
    MoveSpec(
        "759922706",
        "배포 인수인계",
        "613941548",
        "AX / 기밀자료(보안) / 웹개발 보안정보",
        "접속/배포/DB 정보가 포함된 인수인계 문서",
    ),
    MoveSpec(
        "772112387",
        "프로세스 개선 요청 할것들",
        "722960415",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱 / 주문웹 기획",
        "핑거 대비 프로세스 개선 요청 메모",
    ),
    MoveSpec(
        "742391811",
        "오픈클로 적용 아이디어",
        "711983125",
        "AX / 리서치(보안)",
        "사내 AI 구독/계정/망 분리 아이디어",
    ),
    MoveSpec(
        "779354212",
        "디버깅모듈 적용",
        "613941548",
        "AX / 기밀자료(보안) / 웹개발 보안정보",
        "디버깅/트래킹 도구 설정값과 secret 성격 정보 포함",
    ),
    MoveSpec(
        "784629763",
        "주문앱 버전관리",
        "711622712",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱",
        "주문앱 버전 기록",
    ),
    MoveSpec(
        "787972100",
        "넥스트 플랜 생각",
        "711622712",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱",
        "주문웹/샵주문/거래원장 후속 계획",
    ),
    MoveSpec(
        "787709958",
        "클로드코드 계정문제 260401",
        "745144330",
        "AX / 기밀자료(보안) / 툴 관련 정보",
        "Claude Code 계정 운영 이슈",
    ),
    MoveSpec(
        "790659077",
        "해외법인 관련 문의",
        "722960415",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱 / 주문웹 기획",
        "포탈 해외법인 전환/운영 문의",
    ),
    MoveSpec(
        "799965185",
        "DOF-OS 로드맵",
        "723255336",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업)",
        "주문포탈/자동화 후속 로드맵",
    ),
    MoveSpec(
        "804225041",
        "영업팀 수금 관련 미팅 260413",
        "722960415",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱 / 주문웹 기획",
        "주문웹 수금/출고 조건 논의",
    ),
    MoveSpec(
        "812875792",
        "세일즈포스 관련 정보 전달",
        "826277897",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-190] SF 데이터 이관 문서 작성",
        "SF 데이터 이전 관련 정보",
    ),
    MoveSpec(
        "815333410",
        "[AX-187] 주문자동화 API 라이센스 받기",
        "711983129",
        "AX / 리서치(보안) / [AX-130] 샵주문자동화",
        "샵주문자동화 API 라이선스 조사/신청",
    ),
    MoveSpec(
        "819822609",
        "주문자동화 미팅 260422",
        "711983129",
        "AX / 리서치(보안) / [AX-130] 샵주문자동화",
        "샵주문자동화 진행 미팅",
    ),
    MoveSpec(
        "820084745",
        "[AX-189] 샵자동주문 데이터삽입요청",
        "711983129",
        "AX / 리서치(보안) / [AX-130] 샵주문자동화",
        "샵자동주문 데이터 삽입 요청 문서",
    ),
    MoveSpec(
        "819986442",
        "[AX-188] SF고객사매핑테이블 검토요청",
        "826277897",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-190] SF 데이터 이관 문서 작성",
        "SF 고객사 매핑 검토 요청",
    ),
    MoveSpec(
        "834207756",
        "[AX-192] outline 서포트 (영업부)",
        "711983125",
        "AX / 리서치(보안)",
        "영업부 Outline 보고/AI 요약 지원",
    ),
    MoveSpec(
        "868745248",
        "Untitled live doc 2026-06-08 (3)",
        "611058287",
        "AX / 휴지통(보안)",
        "본문이 비어 있는 untitled 문서. 삭제하지 않고 휴지통 폴더로 이동",
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--out", default=str(OUT_DIR / "2026-06-08_move_results_remaining_inbox.json"))
    args = parser.parse_args()

    client = Client()
    results = []
    mode = "verify" if args.verify_only else "write" if args.write else "dry-run"
    for index, spec in enumerate(MOVES, start=1):
        before = client.get_page(spec.page_id)
        record = make_record(client, spec, before=before)
        record["index"] = index
        record["mode"] = mode
        record["skipped"] = False
        if record["title_actual"] != spec.title:
            record["error"] = f"title mismatch: {record['title_actual']!r}"
            results.append(record)
            print(f"[{index:02}] ERROR title mismatch {spec.page_id}: {record['title_actual']!r}")
            continue
        if before.get("parentId") == spec.target_id:
            record["skipped"] = True
            record["move_status"] = "already-at-target"
            print(f"[{index:02}] SKIP already at target: {spec.title}")
        elif args.write:
            status, payload = client.move_append(spec.page_id, spec.target_id)
            record["move_status_code"] = status
            record["move_response"] = payload
            print(f"[{index:02}] MOVE {status}: {spec.title} -> {spec.target_path}")
            if status not in (200, 202, 204):
                results.append(record)
                continue
            time.sleep(0.7)
        else:
            print(
                f"[{index:02}] DRY {spec.title}: parent {before.get('parentId')} "
                f"-> {spec.target_id} ({record['target_title']})"
            )

        after = client.get_page(spec.page_id)
        record["after_parent_id"] = after.get("parentId")
        record["after_parent_type"] = after.get("parentType")
        record["after_url"] = record["current_url"]
        record["verified"] = after.get("parentId") == spec.target_id
        results.append(record)

    summary = {
        "mode": mode,
        "write": bool(args.write),
        "total": len(results),
        "verified_count": sum(1 for r in results if r.get("verified")),
        "skipped_count": sum(1 for r in results if r.get("skipped")),
        "error_count": sum(
            1 for r in results if r.get("error") or (r.get("move_status_code") not in (None, 200, 202, 204))
        ),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", args.out)
    print(
        "summary",
        json.dumps({k: summary[k] for k in ["mode", "total", "verified_count", "skipped_count", "error_count"]}, ensure_ascii=False),
    )


if __name__ == "__main__":
    main()
