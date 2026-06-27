# 원격 워크스페이스 Git/데이터 동기화 정책 리서치

작성일: 2026-06-22
범위: 맥북과 `NotHome-WS-1203-new` 사이에서 동기화하는 `dof-work-startpoint.code-workspace` 워크스페이스들.

## 문제 정의

목표는 맥북 내용을 원격 리눅스 장비로 단순 복제하는 것이 아니다.

실제로 필요한 작업 방식은 다음과 같다.

- 맥북과 원격 리눅스 양쪽에서 모두 개발한다.
- 어느 쪽에서든 커밋하고 `git push`할 수 있어야 한다.
- Git 이력, 브랜치, remote, index, stash, reflog, 로컬 Git 설정은 각 장비의 독립 상태로 둔다.
- 동시에 Git으로 관리하지 않는 작업 데이터인 `input/`, `output/`, `data/` 등은 양쪽에 동기화한다.

따라서 `.git`은 rsync 대상에서 계속 제외해야 한다. 부족한 기능은 `.git` 동기화가 아니라, Git이 소스/이력을 관리하는 동안 `.gitignore` 대상 데이터 경로만 따로 동기화하는 기능이다.

## 현재 로컬 근거

- `scripts/sync_workspace_to_linux.sh`는 `/.git/`을 제외한다.
- `.agents/skills/remote-workspace-sync/SKILL.md`는 Git 이력과 branch/state를 rsync가 아니라 Git으로 관리하라고 명시한다.
- `proc/plan/2026-06-13_workspace-rsync-linux-sync.md`는 `input/`, `output/`, `data/`를 포함하고, `.git/`, 의존성 폴더, 빌드/캐시/로그/runtime 상태는 제외한다고 정리한다.
- 이 repo의 `.gitignore`는 `input/`, `output/`, `data/`를 ignore한다.
- 다른 workspace repo들도 `data/`, `output/`, `input/`, 업로드, DB 백업, 로그, Playwright 산출물, 로컬 env 파일 같은 데이터/산출물 경로를 ignore한다.

## 외부 동작 기준

- rsync는 파일 복사/갱신 도구다. 파일 메타데이터와 옵션을 보고 전송 대상을 판단하며, Git refs, index lock, branch switch, merge state, reflog를 이해하지 못한다.
- rsync `--update`는 목적지 파일이 원본보다 최신이면 건너뛸 뿐이다. 충돌 감지가 아니다.
- rsync `--delete`는 받는 쪽에만 있는 파일을 삭제한다. 미러링에는 유용하지만, 양쪽에서 모두 작업하는 상황에서는 위험하다.
- Git은 `.git` 아래에 branch/reference/object/index 상태를 저장한다. `HEAD`는 현재 active branch를 가리키고, refs는 branch/tag/remote-tracking tip을 기록한다.
- Git branch switch는 tracked local modification이 덮어써질 수 있으면 기본적으로 전환을 거부한다. rsync에는 이런 Git-aware 보호 장치가 없다.

출처:

- rsync manual: https://download.samba.org/pub/rsync/rsync.1
- Git repository layout: https://git-scm.com/docs/gitrepository-layout
- Git switch behavior: https://git-scm.com/docs/git-switch

## 결정

`.git`은 동기화하지 않는다.

채널을 둘로 나눈다.

1. Git 채널: 코드, 문서, tracked 설정, 브랜치, 이력.
2. Rsync 채널: `input/`, `output/`, `data/` 같은 ignored runtime/research/data artifact.

맥북과 원격 장비는 각각 정상적인 Git working copy여야 한다. 양쪽 모두 다음 흐름을 사용할 수 있어야 한다.

```bash
git status
git pull --ff-only
git switch <branch>
git commit
git push
```

rsync는 작업 재현이나 이어서 작업하는 데 필요한 non-Git 데이터/산출물 경로만 옮긴다.

## 이 방식이 문제를 해결하는 이유

`.git`까지 rsync하면 한 장비의 로컬 Git 데이터베이스가 다른 장비의 source of truth가 된다. `.git`에는 공유 이력뿐 아니라 현재 checkout 상태, index, reflog, stash, local config 같은 active local state가 들어 있으므로, "양쪽에서 모두 개발하고 push"하려는 모델과 맞지 않는다.

반대로 `.git`은 제외하되 source file까지 양방향 rsync하면 branch checkout 이후에도 혼란이 생길 수 있다. checkout된 source file은 rsync 입장에서는 그냥 파일이기 때문이다. 더 안전한 모델은 다음처럼 엄격히 나누는 것이다.

- tracked file은 Git으로만 이동한다.
- ignored data/artifact file은 rsync로 이동한다.
- tracked source의 충돌 해결 도구로 rsync를 쓰지 않는다.

## 권장 운영 방식

어느 장비에서든 개발을 시작하기 전에:

```bash
git status
git pull --ff-only
```

어느 장비에서든 개발을 마친 뒤:

```bash
git status
git add <tracked files>
git commit
git push
```

데이터/산출물 동기화에는 명시적인 data-only rsync 모드를 쓴다. 개념적으로 workspace별 동기화 대상은 다음과 같다.

- `input/`
- `output/`
- `data/`
- 각 repo에서 의도적으로 보존해야 하는 ignored artifact directory

계속 제외해야 하는 대상은 다음과 같다.

- `.git/`
- `node_modules/`, virtualenv 같은 의존성 폴더
- build/cache/log/runtime 폴더
- 명시 요청과 검토가 없는 local env/secrets
- `.omx/`, `.omc/`, Playwright runtime/session 폴더

## Ignored 데이터의 충돌 규칙

rsync는 여전히 진짜 양방향 merge engine이 아니다. 다음 규칙이 필요하다.

- 한쪽에서만 데이터를 만들고 다른 쪽은 소비만 한다면 one-way rsync가 안전하다.
- 양쪽에서 서로 다른 파일을 unique run directory 아래에 만든다면, dry-run 검토 후 bidirectional rsync를 사용할 수 있다.
- 양쪽이 같은 ignored file path를 수정할 수 있다면 현재 rsync는 안전하지 않다. `both`의 pull/push 순서에 따라 한쪽 변경이 덮어써질 수 있다.
- 같은 경로의 mutable data는 append-only timestamped output path, 장비별 subdirectory, SQLite export/import + application-level merge, 또는 conflict detection이 있는 도구를 우선 고려한다.

`--update`는 오래된 파일이 잘못 덮어써지는 후보를 줄여주지만, 정합성을 보장하지 않는다. 목적지 mtime 기준으로 판단할 뿐, 양쪽이 독립적으로 수정했는지는 알 수 없다.

`--delete`는 opt-in으로 유지해야 하고, bidirectional data sync와 함께 쓰면 안 된다. `--delete`는 collaboration merge가 아니라 mirror operation이다.

## 스크립트 개선 방향

현재 full workspace sync는 bootstrap과 대량 이관에는 유용했다. 그러나 지속적인 개발 workflow에는 더 좁은 모드가 필요하다.

예상 명령:

```bash
scripts/sync_workspace_to_linux.sh --direction both --data-only --dry-run
```

`--data-only`의 기대 동작:

- 같은 `dof-work-startpoint.code-workspace` folders를 순회한다.
- durable ignored data/artifact root만 전송한다.
- `.git`은 계속 제외한다.
- source file은 one-time bootstrap이나 recovery를 명시적으로 요청한 경우가 아니면 rsync하지 않는다.
- 항상 dry-run을 먼저 수행하고, itemized change를 workspace와 direction별로 요약한다.
- `both`에서는 `--delete`를 피한다.

이렇게 하면 역할이 분명해진다. Git은 협업 가능한 source history를 관리하고, rsync는 Git이 의도적으로 추적하지 않는 대용량/로컬 데이터 상태만 운반한다.

## 실무 권장안

`.git`은 영구적으로 제외한다.

지속적인 원격/맥북 병행 개발에는 data-only sync 경로를 추가하거나 사용한다. 기존 full workspace sync는 초기 seeding, 복구, 또는 한쪽이 명확한 source of truth인 deliberate one-way copy에만 쓴다.

"양쪽 장비에서 같은 ignored data file을 능동적으로 수정하고, 충돌도 보존해야 한다"가 요구사항이라면 rsync만으로는 부족하다. 이 경우 conflict-aware sync layer를 평가하거나, 해당 data file을 append-only/versioned artifact 구조로 바꾸는 편이 맞다.
