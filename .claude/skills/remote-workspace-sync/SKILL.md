---
name: remote-workspace-sync
description: dof-work-startpoint.code-workspace의 모든 workspace folder를 rsync로 맥북과 원격 Linux `NotHome-WS-1203-new` 사이에 동기화한다. "원격 싱크", "rsync", "맥에서 리눅스로 보내기", "리눅스에서 맥으로 받기", "remote pull", "remote push", "양방향 동기화", "workspace sync" 요청 시 사용.
---

# Remote Workspace Sync

`scripts/sync_workspace_to_linux.sh`를 사용해 `dof-work-startpoint.code-workspace`의 `folders[]` 전체 또는 일부를 원격 Linux와 동기화한다.

## 방향 매핑

- 보내기: `--direction push` / 맥북 -> 원격
- 받기: `--direction pull` / 원격 -> 맥북
- 양방향: `--direction both` / 원격 -> 맥북 후 맥북 -> 원격

기본값은 `push`다.

## 표준 명령

```bash
# workspace folder 목록 확인
scripts/sync_workspace_to_linux.sh --list

# 보내기 dry-run
scripts/sync_workspace_to_linux.sh --direction push --dry-run

# 보내기 실행
scripts/sync_workspace_to_linux.sh --direction push

# 받기 dry-run
scripts/sync_workspace_to_linux.sh --direction pull --dry-run

# 받기 실행
scripts/sync_workspace_to_linux.sh --direction pull

# 양방향 dry-run
scripts/sync_workspace_to_linux.sh --direction both --dry-run

# 양방향 실행
scripts/sync_workspace_to_linux.sh --direction both

# 특정 workspace folder만
scripts/sync_workspace_to_linux.sh --direction pull --only dof-work-startpoint-04 --dry-run
```

## Dry-run 판정 규칙

- 받아올/보낼 후보 판단은 `--itemize-changes` 라인을 기준으로 한다. `Number of files transferred` / `Total transferred file size` 같은 `--stats` 값만 보고 "없음"이라고 결론내리지 않는다.
- 특히 macOS `openrsync`와 Linux rsync 3.x 조합에서는 `pull --dry-run` 통계가 0으로 보여도 `>f+++++++`, `>f..t....`, `cd+++++++`, `>L...p...` 라인에 실제 수신 후보가 찍힐 수 있다.
- `>f`는 파일 수신/송신 후보, `cd`는 새 디렉터리 후보, `>L` 또는 `.L`은 symlink 후보로 본다. 이런 라인이 있으면 stats가 0이어도 "동기화 후보 있음"으로 보고한다.
- 한글/깨진 바이트가 섞인 경로 때문에 macOS `awk`가 실패할 수 있으니 요약 필터에는 `LC_ALL=C`를 붙인다.

```bash
# 받기 dry-run itemized 요약
LC_ALL=C scripts/sync_workspace_to_linux.sh --direction pull --dry-run | awk '
/^==> / { folder=$2; order[++n]=folder; next }
folder && $1 ~ /^>f/ { files[folder]++; if (files[folder] <= 10) samples[folder]=samples[folder] "\n  " $0; next }
folder && $1 ~ /^cd/ { dirs[folder]++; next }
folder && $1 ~ /^[.>]L/ { links[folder]++; next }
END {
  for (i=1; i<=n; i++) {
    f=order[i]
    printf "%s\tfiles=%d\tdirs=%d\tsymlinks=%d\n", f, files[f]+0, dirs[f]+0, links[f]+0
    if (samples[f] != "") printf "  samples:%s\n", samples[f]
  }
}'
```

사용자가 특정 파일명이나 산출물을 언급하면 전체 요약만 믿지 말고 로컬/원격에서 직접 찾는다.

```bash
find /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04 -name '*night-routine*'
ssh NotHome-WS-1203-new 'find /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04 -name "*night-routine*"'
```

긴 실행은 `tmux`에서 돌리고 `.omx/logs/`에 로그를 남긴다.

```bash
log=".omx/logs/workspace-rsync-linux-$(date +%Y%m%d-%H%M%S).log"
tmux new-session -d -s workspace-rsync-linux \
  "/bin/bash -lc 'cd /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04 && scripts/sync_workspace_to_linux.sh --direction push 2>&1 | tee $log'"
```

## 안전 규칙

- 스크립트는 시작 전 원격에서 `/Users/gq` 또는 `/Users` 중 하나가 mountpoint인지 확인한다. 둘 다 `/` 루트 파일시스템의 일반 디렉터리라면 rsync를 시작하지 않는다.
- `.git`은 항상 제외한다. Git 이력과 branch/state는 rsync로 맞추지 말고 Git으로 관리한다.
- `node_modules`, build/cache/log, `.venv` / `.venv-*`, `.omx` runtime state, Python bytecode, Playwright runtime, rsync partial/temp 파일도 제외한다.
- `--delete`는 명시 요청이 있을 때만 사용한다.
- `--direction both --delete`는 금지다.
- `both`는 충돌 병합이 아니다. 같은 파일을 양쪽에서 수정했으면 먼저 실행되는 pull이 맥북 파일을 덮고, 이후 push가 그 상태를 원격에 보낸다.
- 소스 충돌 가능성이 있으면 Git commit/status/diff로 먼저 확인하고, 데이터 산출물 위주로 rsync한다.

## 확인

- 실행 중 확인: `tmux list-sessions | grep workspace-rsync-linux`
- 로그 확인: `tail -f .omx/logs/workspace-rsync-linux-*.log`
- 원격 mount guard 확인:

```bash
ssh NotHome-WS-1203-new 'findmnt -T /Users/gq -o TARGET,SOURCE,FSTYPE,OPTIONS -n; mountpoint /Users/gq || mountpoint /Users'
```

- 원격 크기 확인:

```bash
ssh NotHome-WS-1203-new 'du -sh /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04 2>/dev/null || true'
```
