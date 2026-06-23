---
name: workspace-commit-sweep
description: 워크스페이스 전체 Git 변경사항을 repo별로 검사하고 의미 단위로 검증·커밋한다. "전체 커밋", "ws 의 모든 경로", "code workspace 모든 경로", "적절한 이름으로 커밋", "포탈은 상세히", "코드 그대로 설명하지 말고 의미를 담아" 요청 시 사용.
argument-hint: "[커밋 대상 범위 또는 강조사항]"
---

# Workspace Commit Sweep

워크스페이스의 여러 Git repo를 빠짐없이 훑고, 변경 내용을 실제로 이해한 뒤 의미 단위로 커밋한다. 이 스킬은 단일 repo 커밋보다 "전체 경로를 다시 확인해서 빠진 커밋이 없게 하라"는 요청을 우선한다.

## 범위 선택

1. 사용자가 `code workspace`를 말하면 `dof-work-startpoint.code-workspace`의 `folders[]`만 대상으로 삼는다.
2. 사용자가 `ws`, `workspace`, `모든 경로`, `전체`만 말하면 `/Users/gq/works/projs` 아래 모든 Git repo를 대상으로 삼는다.
3. 사용자가 특정 repo를 같이 말하면 전체 스캔은 유지하되, 그 repo의 diff와 커밋 메시지를 더 자세히 작성한다.
4. 첫 스캔과 마지막 스캔 모두에서 대상 repo 수와 dirty repo 수를 보고한다. 완료 기준은 대상 범위의 `DIRTY 0`이다.

## 표준 스캔

```bash
# code workspace folder 목록
python3 - <<'PY'
import json, re
from pathlib import Path
ws = Path('/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/dof-work-startpoint.code-workspace')
text = re.sub(r'//.*', '', ws.read_text())
base = ws.parent
for folder in json.loads(text).get('folders', []):
    path = (base / folder['path']).resolve()
    print(path)
PY

# 모든 repo dirty census
find /Users/gq/works/projs -name .git -type d -prune -print |
  while read -r gitdir; do
    repo=${gitdir%/.git}
    status=$(git -C "$repo" status --porcelain)
    if [ -n "$status" ]; then
      printf 'DIRTY\t%s\n' "$repo"
      printf '%s\n' "$status" | sed 's/^/  /'
    fi
  done
```

대상 repo가 많으면 스캔 스크립트를 임시 파일로 두지 말고 일회성 shell/Python으로 실행한다. 결과는 커밋하지 않는다.

## 커밋 분할 원칙

- repo마다 diff를 읽고 변경 의도를 파악한 뒤 커밋한다. 상태 목록만 보고 커밋하지 않는다.
- 같은 repo 안에서도 서로 다른 업무 의미가 있으면 커밋을 나눈다.
- 산출물, 스크린샷, 조사 문서, 소스 변경은 의미가 다르면 분리한다.
- `git add .`로 전체를 밀어 넣지 말고, 확인한 파일 그룹만 명시적으로 stage한다.
- `.env`, secret, local cache, build output, Playwright runtime, 임시 로그, 무의미한 lock/cache 변경은 커밋하지 않는다.
- 사용자가 만든 변경을 되돌리지 않는다. 커밋 대상에서 제외할 필요가 있으면 제외 사유를 보고한다.

## Lore 커밋 메시지

모든 커밋은 Lore 프로토콜을 따른다. 첫 줄은 "무엇을 바꿨는지"가 아니라 "왜 이 커밋이 필요한지"를 쓴다.

```text
<why-focused intent line>

<narrative context: 변경의 업무적 의미, 제약, 판단 근거>

Constraint: <외부 제약 또는 요청 조건>
Rejected: <대안> | <버린 이유>
Confidence: <low|medium|high>
Scope-risk: <narrow|moderate|broad>
Directive: <미래 수정자에게 남길 주의>
Tested: <검증한 것>
Not-tested: <검증하지 못한 것>
Co-authored-by: OmX <omx@oh-my-codex.dev>
```

`Rejected:`는 실제로 비교한 대안이 있을 때만 쓴다. `Not-tested:`는 없으면 `Not-tested: No additional runtime validation; documentation-only change`처럼 솔직하게 남긴다.

## 포탈 계열 특별 규칙

포탈 repo는 특히 상세하게 쓴다. 대표 대상:

- `dof-order-web-3-az`
- `portal-ledger-invoice-gen-and-send`
- 포탈 운영 데이터, 송장, 원장, 주문, 발송, 권한, 정산과 직접 연결된 repo

포탈 커밋 메시지는 코드 구조를 풀어 쓰는 설명이 아니라, 운영상 무엇이 안전해졌는지와 어떤 업무 판단을 보존하는지에 집중한다.

- 좋은 방향: "카카오/이메일 발송 권한을 모든 사용자에게 일관되게 보장한다", "미수금 대시보드가 국내/해외 고객 구분을 유지한 채 공유 가능해진다"
- 피할 방향: "파일 A에 함수 B를 추가했다", "컴포넌트 C의 prop을 바꿨다"
- 포탈 메시지에는 요청 맥락, 데이터/권한/고객 영향, 검증 범위, 남은 리스크를 본문에 남긴다.
- `dof-order-web-3-az`는 commit hook이 Lore 형식과 `Co-authored-by: OmX <omx@oh-my-codex.dev>`를 요구할 수 있으므로 첫 시도부터 포함한다.

## 검증 규칙

커밋 전에 repo 성격에 맞게 최소 검증을 한다.

- 공통: `git diff --check` 또는 `git diff --staged --check`
- 문서만 변경: 파일 경로, 제목, 링크/참조, 이동 의도 확인
- shell script: `bash -n <file>`
- Python script: `python3 -m py_compile <file>`
- TypeScript/portal backend: 가능한 범위의 targeted test, typecheck, build
- UI 변경: build와 필요한 경우 Playwright/browser-visible 확인 또는 스크린샷 증거 보존

검증을 생략하면 커밋 메시지의 `Not-tested:`에 이유를 쓴다.

## 완료 보고

최종 보고에는 다음을 포함한다.

- 스캔 범위와 대상 repo 수
- 생성한 커밋 해시와 의미 요약
- 포탈 repo가 있었다면 포탈 커밋의 업무적 의미 요약
- 실행한 검증
- 마지막 전체 재스캔 결과: `DIRTY 0` 또는 남은 dirty repo와 제외 사유
