---
name: remote-instance
description: 원격/remote 요청에서 원격 인스턴스 SSH 접속, 원격 서버 상태 확인, 원격 경로 확인, 내장 기본 SSH 대상 사용을 고려해야 할 때 사용. "원격", "remote", "원격 접속", "원격 인스턴스", "서버 들어가", "ssh", "SSH", "NotHome", "odung", "odungnest", "ax01" 같은 요청에서 로컬 작업만 하기 전에 이 스킬을 먼저 고려한다.
---

# Remote Instance

원격 인스턴스 접속 여부를 판단하고, 내장 기본 SSH 대상으로 접속 가능성과 원격 경로를 확인한다.

## Default Target

- 기본 대상: odung 컴퓨터
- 기본 접속 명령: `ssh -p 62001 gq@odungnest.iptime.org`
- `ax01` 또는 `AX01`이 명시되면 AX01 회사 컴퓨터를 대상으로 사용한다.
- AX01 접속 명령: `ssh -p 22 ax01@61.36.134.214`
- 참고 문서: `references/connection.md`
- 이 스킬은 외부 접속정보 파일 없이 동작해야 한다.
- `remote-workspace-sync`는 rsync 동기화 전용이다. SSH 접속, 원격 상태 확인, 원격 경로 확인은 이 스킬을 우선 사용한다.

## Workflow

1. 사용자가 "원격" 또는 "remote"를 말하면 원격 인스턴스가 작업 대상인지 먼저 판단한다.
2. 원격 대상 이름이 없으면 odung 컴퓨터를 기본값으로 사용한다.
3. 사용자가 `ax01` 또는 `AX01`을 명시하면 AX01 회사 컴퓨터를 사용한다.
4. 로컬과 원격 중 대상이 불분명하면, 안전한 read-only 확인으로 시작한다.
5. 접속 전 `scripts/remote_probe.sh --show`로 현재 SSH 대상을 확인한다. AX01은 `scripts/remote_probe.sh --target ax01 --show`를 사용한다.
6. 실제 접속 가능성은 `scripts/remote_probe.sh --check`로 비대화형 probe를 먼저 실행한다. AX01은 `scripts/remote_probe.sh --target ax01 --check`를 사용한다.
7. 원격에서 명령을 실행할 때는 먼저 `pwd`, `hostname`, `uname -a`, `test -e <path>` 같은 read-only 명령으로 대상과 경로를 확인한다.
8. 원격 파일 수정, 삭제, 배포, DB 변경처럼 되돌리기 어려운 작업은 사용자 요청 범위가 명확할 때만 수행하고, 가능하면 백업/전후 확인을 남긴다.

## Commands

```bash
# 내장 기본 접속 대상 확인
.agents/skills/remote-instance/scripts/remote_probe.sh --show

# SSH 비대화형 접속 테스트
.agents/skills/remote-instance/scripts/remote_probe.sh --check

# AX01 대상 확인 및 접속 테스트
.agents/skills/remote-instance/scripts/remote_probe.sh --target ax01 --show
.agents/skills/remote-instance/scripts/remote_probe.sh --target ax01 --check

# 일회성으로 다른 SSH 명령을 명시
.agents/skills/remote-instance/scripts/remote_probe.sh --ssh 'ssh -p 22 ax01@61.36.134.214' --check
```

## Path Checks

사용자가 `/Users/gq/...` 같은 "같은 위치" 파일이나 디렉터리를 언급하면 로컬과 원격이 같은 절대 경로를 공유할 수 있다고 보고 확인한다.

```bash
ssh -p 62001 gq@odungnest.iptime.org 'test -e /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04 && pwd && ls -ld /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04'
```

AX01이 명시된 경우:

```bash
ssh -p 22 ax01@61.36.134.214 'test -e /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04 && pwd && ls -ld /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04'
```

명령의 host/port/user는 odung 또는 AX01 기본 대상과 다를 때만 `--ssh`로 재정의한다.
