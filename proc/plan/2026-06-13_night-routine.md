# 2026-06-13 Night Routine

## 목표
2026-06-13 기준 하루 raw를 가능한 범위에서 수집하고, Notion/Jot/Task/Standup/Raindrop/communication 흐름을 읽어 `data/daily/2026-06-13/summary.md`를 작성한다.

## 작업 항목
- [x] 음성 녹음/전사 후보 확인
- [x] Notion, Google, Microsoft, Atlassian, Raindrop raw 수집
- [x] Notion Task/Note 빈 Areas 후보 discover 및 가능한 경우 backfill
- [x] Teams standup과 Jot/Task raw 대조
- [x] Raindrop dump/infer/untagged retag 처리
- [x] raw를 직접 읽고 summary.md 작성
- [x] 실패 source와 다음 액션 정리

## 결과 메모
- Notion Jot/Task, Atlassian, Raindrop raw를 생성했다.
- Google은 token path 파일 부재, Teams/Outlook은 Graph 권한 부족으로 실패했다.
- 빈 Areas 후보 1건(`당근 공유기`)은 `Home(부부)`로 patch 완료했다.
- Raindrop 4건은 infer + retag 완료했다.

## 로컬 재시도 메모
- 로컬 재시도 스크립트: `proc/plan/night_routine_retry_2026_06_13.py`
- 로컬 재시도 raw: `data/daily/2026-06-13/raw/local-retry/`
- `bispro89` Google은 성공했다: Calendar 6건, Gmail 1건, Drive 2건.
- `sikbrad` Google은 토큰 파일은 있으나 `invalid_scope: Bad Request`로 실패했다.
- Outlook은 성공했다: inbox 2건, sent 0건, errors 없음.
- Teams Graph는 chat list, joined team/channel map 35건, `standup-daily-ax` channel posts 1 thread 읽기에 성공했다. 전체 채널 sweep은 검증 목적 대비 오래 걸려 중단했다.
- kubit Slack은 로컬 package가 있어 실행됐다. `collect:conv`는 exit 0이지만 Slack scope 부족 경고와 fallback이 있었고, `collect:people`은 59 member folder 처리까지 성공했다.
- 세부 상태 파일: `data/daily/2026-06-13/raw/local-retry/source-status.json`

## 원격 재시도 메모
- 원격 host: `NotHome-WS-1203-new`
- rsync dry-run 확인: `dof-work-startpoint-04`만 기준으로 원격에 35,389개 파일, 14.4GB가 아직 빠져 있었다. 기존 전체 push가 `data/notion/assets` 구간에서 끝나지 않아 뒤쪽 `proc/plan`, `scripts`, kubit workspace까지 도달하지 못한 상태였다.
- workspace 밖 누락: Google token은 `/Users/gq/.cache/`, MS Graph token cache는 원격 Python 기준 `/home/gq/.cache/`에도 필요했다. 일반 workspace rsync 대상이 아니므로 별도로 맞췄다.
- 원격 Python에는 Google/MSAL 패키지가 없어 `/Users/gq/.venvs/dof-work-startpoint-night-routine` venv를 만들고 최소 dependency를 설치했다.
- 원격 Node/NPM은 기본 PATH에는 없었지만 `/home/gq/.nvm/nvm.sh`를 source하면 사용 가능했다. kubit은 `package.json`, `package-lock.json`, `src/`, `.env`, 증분 state를 맞추고 `npm install --ignore-scripts`를 실행했다.
- 원격 retry 결과: `bispro89` Google 3종은 성공, `sikbrad` Google 3종은 로컬과 동일하게 `invalid_scope: Bad Request`로 실패했다.
- 첫 원격 retry에서 Teams/Outlook은 MS Graph cache 경로 문제(`/home/gq/.cache`)로 실패했다. cache 경로를 고친 뒤 별도 재검증에서 Graph `/me`, Outlook inbox 2건/sent 0건, Teams chat list 114건, channel map 35건, `standup-daily-ax` 1 thread 읽기에 성공했다.
- kubit 원격 실행은 `collect:conv`, `collect:people` 모두 exit 0이었다. `collect:conv`에는 로컬과 동일하게 Slack scope 부족/fallback 경고가 남는다.
- 원격 결과 pullback: `data/daily/2026-06-13/raw/remote-retry/final-remote-retry-status.json`
