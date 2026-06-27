---
name: night-routine
description: 밤 루틴 수집/정리. 음성녹음 transcript를 먼저 모은 뒤 daily-collect로 Notion, Teams, Calendar, Gmail/Outlook, Drive, Jira/Confluence, 포탈 Feedback, 포탈 공지사항/릴리즈노트 등을 수집하고, kubit Slack 대화와 people을 갱신한다. Notion DailyJot와 Task DB를 다시 읽어 무엇이 완료/진행/미완료인지 검토하고, Task DB / Note DB의 Areas relation이 비어 있으면 backfill-empty-areas로 Area를 부여한다. Teams standup의 아침 계획/저녁 결산과 대조한다. Raindrop은 dump/infer 후 태그 없는 북마크를 우선 AI 태깅한다. `data/daily/<YYYY-MM-DD>/summary.md`에 그날 있었던 일과 다음 액션을 기록한다. "나이트루틴", "밤 루틴", "오늘 정리해줘", "하루 마감", "night routine" 요청 시 사용. 모닝루틴 소스와 중복 수집해도 된다. kmsg/KakaoTalk은 제외한다.
---

# Night Routine

밤에는 중복보다 누락 방지가 중요하다. `morning-routine`에서 이미 본 소스도 다시 수집해도 된다.

## Core Flow

1. 기준일을 정한다. 명시가 없으면 Asia/Seoul 오늘.
2. 음성녹음을 먼저 처리한다. 이미 transcript가 있으면 `data/daily/<date>/raw/voice-*.txt`에 두고, Drive/로컬에서 audio 원본만 발견되면 반드시 다운로드 후 transcribe하여 `voice-*.txt`를 만든다.
3. startpoint의 기존 `daily-collect` 절차로 주요 raw를 수집한다.
4. 포탈 `Feedback` raw를 `portal_feedback_collect.mjs`로 추가 수집한다.
5. 포탈 공지사항/릴리즈노트 raw를 `portal_notice_collect.mjs`로 추가 수집한다.
6. Teams는 날짜별 raw만으로 끝내지 말고 `ins@doflab.com`이 현재 볼 수 있는 모든 chatroom/team/channel full-history archive를 갱신한다.
7. Notion DailyJot와 Task DB를 다시 읽어 완료/진행/미완료 상태를 검토한다.
8. Task DB / Note DB에서 `Areas` relation이 비어 있는 페이지가 있으면 `backfill-empty-areas`를 실행한다.
9. Teams standup의 아침 계획과 저녁 결산을 읽고 Jot/Task DB와 대조한다.
10. kubit Slack conversation과 people 데이터를 갱신한다.
11. Notion/Raindrop/Drive/ChatGPT 등 archival source를 필요한 만큼 추가한다.
12. Raindrop에서 태그 없는 북마크를 우선 찾아 infer가 있는 것부터 `raindrop-retag`로 태깅한다.
13. raw를 직접 읽고 `data/daily/<date>/summary.md`를 작성하거나 갱신한다.

## Sources

공통 source routing은 [../morning-routine/references/routine-sources.md](../morning-routine/references/routine-sources.md)를 따른다. `kmsg`는 이 루틴에서 사용하지 않는다.

Night 기본 수집:

| Source | Use |
|---|---|
| voice transcript | 하루 생각/회의/이동 중 메모의 1차 raw |
| `daily-collect` | Notion, Teams, Calendar, Gmail/Outlook, Drive, Jira/Confluence, 포탈 Feedback/공지사항 raw + summary |
| portal feedback | 포탈 `Feedback`/`Notification` 변경분과 active feedback snapshot. AX팀 작업 신호로 취급 |
| portal notices | 포탈 공지사항과 릴리즈노트. 릴리즈노트는 AX팀/사용자 업무 산출물로 취급 |
| Teams full archive | `ins@doflab.com`이 속한 모든 chatroom/team/channel의 전체 히스토리 archive |
| Notion DailyJot | 아침 계획, 중간 메모, 체크 상태 재검토 |
| Notion Task DB | 오늘 완료/진행/미완료/overdue 태스크 검토 |
| `backfill-empty-areas` | Task DB / Note DB의 빈 `Areas` relation을 의미 기반으로 보강 |
| Teams standup | 아침 계획과 저녁 결산 대조 |
| kubit Slack `collect:conv` | kubit 채널/DM/그룹DM 대화 cache |
| kubit Slack `collect:people` | 사람별 activity, future_self, weekly_report, conversations 갱신 |
| `notion-dump` | Notion 전체 트리 증분 sync |
| `raindrop` | 북마크 dump |
| `raindrop-infer` | 오늘 저장한 중요한 링크 분석 |
| `raindrop-retag` | 태그 없는 북마크 우선 AI 태깅 + AI 메모 |
| `chatgpt` | 개인 ChatGPT 대화 export, 필요하거나 주기적으로 |
| `gdrive` / `onedrive` / `sharepoint` | 수정/참조 문서 raw |
| `amaranth-approval` / `amaranth-calendar` | 회사 결재/일정 기록 |

`morning-routine`과 겹치는 Teams, Calendar, Gmail, Outlook, Jira, Confluence, kubit Slack light signals도 다시 수집해도 된다.

## Portal Feedback

포탈 `Feedback`은 AX팀이 만든/운영하는 업무 입력이며, 사용자의 회사 업무 기록과 같은 의미로 취급한다. 나이트루틴에서 포탈 피드백을 스크랩할 때는 다음 raw를 반드시 만든다.

```bash
node proc/lib/portal_feedback_collect.mjs <YYYY-MM-DD>
```

저장 위치:

```text
data/daily/<YYYY-MM-DD>/raw/portal-feedback.json
```

수집 내용:

- KST 기준 해당 날짜에 생성, 수정, 알림 전송된 `Feedback`
- 현재 `NEW`, `REVIEWED`, `DOING`, `PRE_DEPLOY` 상태인 active feedback snapshot
- 같은 날짜의 `FEEDBACK` 타입 `Notification`

운영 규칙:

- 기본 DB는 포탈 저장소 `.env`의 `DATABASE_URL_REMOTE`이며, 없으면 `DATABASE_URL`을 사용한다.
- 수집기는 `BEGIN READ ONLY` 안에서 SELECT만 수행한다.
- 실패해도 전체 나이트루틴을 멈추지 말고 `summary.md`와 `source-errors.json`에 실패 이유를 남긴다.
- 요약할 때 포탈 피드백은 "외부 요청"으로만 치지 말고, AX팀이 접수/검토/처리한 업무 흐름으로 읽는다.
- 테스트성 피드백은 테스트/검증 작업으로 분류하고, 실제 사용자 업무 요청은 다음 액션에 반영한다.

## Portal Notices / Release Notes

포탈 공지사항의 릴리즈노트는 AX팀이 배포/운영한 결과물이므로, 사용자의 회사 업무 기록과 같은 의미로 취급한다. 나이트루틴에서 포탈 공지사항을 스크랩할 때는 다음 raw를 반드시 만든다.

```bash
node proc/lib/portal_notice_collect.mjs <YYYY-MM-DD>
```

저장 위치:

```text
data/daily/<YYYY-MM-DD>/raw/portal-notices.json
```

수집 내용:

- KST 기준 해당 날짜에 생성/수정된 `Notice`
- 제목/본문상 릴리즈노트로 보이는 공지 snapshot
- 현재 게시 중인 공지 snapshot

운영 규칙:

- 기본 DB는 포탈 저장소 `.env`의 `DATABASE_URL_REMOTE`이며, 없으면 `DATABASE_URL`을 사용한다.
- 수집기는 `BEGIN READ ONLY` 안에서 SELECT만 수행한다.
- 실패해도 전체 나이트루틴을 멈추지 말고 `summary.md`와 `source-errors.json`에 실패 이유를 남긴다.
- 요약할 때 릴리즈노트는 “한 일/산출물/배포 커뮤니케이션”으로 분류한다.
- 점검 공지는 운영 커뮤니케이션으로, 일반 릴리즈 공지는 배포 산출물로 읽는다.

## Teams Full Archive

날짜별 `teams-chats.json`/`teams-channels.json`은 그날 요약용 raw이고, 전체 백업으로 간주하지 않는다. 밤 루틴에서 Teams를 스크랩할 때는 다음 archive도 함께 갱신한다.

```bash
python3 proc/run_teams_conversations_dump.py --full-history
```

운영 규칙:

- 기준 계정은 Microsoft Graph 현재 사용자 `ins@doflab.com`이어야 한다.
- 모든 `/me/chats` chatroom과 `/me/joinedTeams`의 모든 channel을 나열한다.
- channel parent messages와 replies를 모두 수집한다. 큰 채널은 `--full-history`가 자동으로 channel page size 10을 사용해 Graph skiptoken timeout을 피한다.
- 산출물은 `output/teams/conversations/`의 raw JSON/Markdown과 `_summary.json`이다.
- 이 archive가 이미 구축된 뒤에는 증분 갱신도 가능하지만, “처음부터 현재까지 모두” 검증이 필요한 날은 반드시 `--full-history`를 사용한다.
- 수집 오류가 있으면 `output/teams/conversations/_summary.json`의 `team_errors`/`chat_errors`를 확인하고, 실패 채널만 `--only-team`/`--only-channel`로 재시도한다.
- `--full-history` 또는 증분 갱신이 장시간 무출력/무업데이트 상태가 되면 루틴 전체를 붙잡지 않는다. 기존 `_summary.json`의 `extracted_at`이 오래됐는지 기록하고, 당일 요약은 `data/daily/<YYYY-MM-DD>/raw/teams-chats.json`, `teams-channels.json`, `teams-standup.json`으로 진행한다. summary에는 archive stale/partial 상태를 남긴다.

## Notion Review

밤에는 Jot을 다시 읽는다. 목적은 새 Task 생성만이 아니라 하루의 실제 진행 상태를 판정하는 것이다.

확인할 것:

- 오늘 DailyJot 체크박스 중 체크된 것 / 안 된 것
- 오늘 DailyJot bullet 중 작업기록, 생각, 내일로 넘길 것
- `daily-jot-to-tasks`가 만든 Task/Note page mention
- Task DB에서 `ActDate`가 오늘인 Task
- Task DB에서 오늘 `Status`가 `Done`, `Doing`, `Wait`, `Ready`, `Schedule`인 Task
- `DueDate`가 오늘 또는 지난 미완료 Task

자동으로 Task 상태를 바꾸지 않는다. 사용자가 명시적으로 요청한 경우에만 Notion Task DB를 수정한다.

## Notion Area Backfill

밤 루틴에는 `backfill-empty-areas`를 포함한다. 목적은 DailyJot/Task/Note 정리 후 남은 Task DB / Note DB 페이지 중 `Areas` relation이 비어 있는 항목을 다음 날로 넘기지 않는 것이다.

실행 규칙:

- `backfill-empty-areas` 스킬의 discover → mapping.json → dry-run → push 흐름을 따른다.
- 이미 `Areas`가 부여된 Task/Note는 절대 건드리지 않는다.
- PATCH 직전에 페이지를 재조회해서 `Areas`가 여전히 비어 있을 때만 수정한다.
- Area 후보는 `Closed` 상태만 제외한다.
- Area 결정은 LLM이 Area 콘텐츠와 후보 페이지 title/body를 직접 읽고 의미적으로 판단한다. 코드 키워드 매칭은 금지한다.
- 판단 근거와 결과는 해당 스킬의 plan/mapping/result 파일에 남기고, `summary.md`에는 처리 개수와 애매한 후보만 요약한다.

이 단계는 Task의 `Status`, `ActDate`, `DueDate`를 바꾸지 않는다. Areas relation만 보강한다.

## Teams Standup Review

standup source는 다음 순서로 사용한다:

1. 전용 standup 스킬/스크립트가 생겨 있으면 그것을 우선한다.
2. 없으면 `teams-channel`로 `standup-daily-ax` 채널의 오늘 thread/replies를 조회한다.
3. 이미 수집된 경우 `data/daily/<date>/raw/teams-standup.json`을 읽는다.

검토할 것:

- 아침 standup에 적은 계획
- 낮/저녁에 추가로 올린 변경사항
- 저녁 결산 또는 완료 보고
- Jot/Task DB와 비교했을 때 완료된 일
- 진행 중이지만 끝나지 않은 일
- 계획에는 없었지만 실제로 한 일

`summary.md`에는 "완료", "진행", "미완료/이월", "계획 외 완료"를 분리해서 남긴다.

## kubit Slack

```bash
cd /Users/gq/works/lecture/kubit/kubit-bitbot-slack-01
npm run collect:conv
npm run collect:people
```

필요하면 DM만 빠르게:

```bash
npm run collect:conv:dm
```

## Raindrop Untagged Retag

밤에는 새 북마크 dump/infer 후 태그 없는 항목을 우선 정리한다.

기본 순서:

```bash
python3 proc/lib/raindrop_dump.py dump
python3 proc/lib/raindrop_infer.py run
python3 proc/lib/raindrop_retag.py status
```

당일 `data/daily/<YYYY-MM-DD>/raw/raindrop.json`에 항목이 있으면 **그 id를 먼저** 처리한다. 전체 `raindrop_infer.py run`은 오래된 백로그 전체로 새어 루틴을 잡아먹을 수 있으므로, 당일 요약 전에는 `--id`로 오늘 항목만 infer/retag한다.

```bash
python3 proc/lib/raindrop_infer.py run --id <today-raindrop-id>
python3 proc/lib/raindrop_retag.py run --id <today-raindrop-id>
```

`raindrop_retag.py`는 현재 `--only-untagged` 옵션이 없으므로, 태그가 빈 raindrop id를 dump에서 골라 `--id`로 넘긴다.

```bash
python3 - <<'PY' > /tmp/raindrop-untagged-ids.txt
import json
from pathlib import Path
for p in sorted(Path('data/raindrop/dump/raindrops').glob('*.json')):
    d = json.loads(p.read_text())
    if not (d.get('tags') or []):
        print(p.stem)
PY

head -20 /tmp/raindrop-untagged-ids.txt | while read -r id; do
  python3 proc/lib/raindrop_retag.py run --id "$id"
done
```

운영 규칙:

- 처음에는 20건 정도로 제한해 품질을 본다.
- infer md가 없는 항목은 `no-infer`로 skip되므로 다음 나이트루틴에서 재시도한다.
- 이미 사용자 태그가 있는 북마크는 이 단계에서 건드리지 않는다.
- 전체 재태깅이나 `--force`는 사용자가 명시 요청할 때만 한다.

## Voice Transcript

음성 원본 위치가 명시되면 그 위치를 우선한다. 이미 전사된 `.txt`가 있으면 변환하지 말고 날짜별 raw에 복사한다.

원본이 Google Drive raw에 잡힌 경우:

1. `raw/gdrive-*.json`에서 `mimeType`이 `audio/*` 이거나 파일명이 `음성`, `voice`, `recording`을 포함하는 항목을 찾는다.
2. 파일명의 날짜(`260526` 등)와 실제 내용 날짜를 기준으로 `data/daily/<YYYY-MM-DD>/raw/audio-*.m4a`에 다운로드한다.
3. 로컬 `whisper` 또는 사용 가능한 STT 도구로 반드시 전사한다.
4. 전사 결과를 같은 날짜의 `raw/voice-*.txt`로 저장한다.
5. `summary.md`의 `개인 메모 / 음성` 또는 `음성 녹음` 섹션을 전사 내용으로 보강한다.

기본 로컬 전사 예:

```bash
whisper data/daily/<YYYY-MM-DD>/raw/audio-*.m4a \
  --model turbo \
  --language ko \
  --output_format txt \
  --output_dir /tmp/night-routine-whisper
```

`whisper` CLI/패키지가 없으면 기존 `OPENAI_API_KEY`와 REST `POST /v1/audio/transcriptions`(`model=whisper-1`, `language=ko`)를 사용한다. Samsung/Android 녹음처럼 `m4a` 확장자지만 API가 `Invalid file format`을 반환하거나 파일이 24MB를 넘으면 먼저 `ffmpeg`로 16k mono mp3를 만든 뒤 업로드한다.

```bash
ffmpeg -y -i data/daily/<YYYY-MM-DD>/raw/audio-<source>.m4a \
  -ac 1 -ar 16000 -b:a 32k \
  data/daily/<YYYY-MM-DD>/raw/audio-<source>.transcribe.mp3
```

Google Drive 다운로드 예:

```bash
python3 proc/lib/gdrive_api.py download --account bispro89 \
  --id <drive-file-id> \
  --out data/daily/<YYYY-MM-DD>/raw/audio-<source-or-time>.m4a
```

저장 규칙:

```text
data/daily/<YYYY-MM-DD>/raw/voice-<source-or-time>.txt
```

전사 원본 경로가 불명확할 때만 음성 단계만 skip하고 summary에 `Voice: source path not configured`를 남긴다. Drive나 로컬에서 audio 원본을 발견했으면 skip하면 안 된다.

## Summary Rules

`summary.md`는 단순 로그가 아니라 그날의 기억이어야 한다.

포함할 것:

- 하루의 큰 흐름
- 실제로 한 일
- 결정과 산출물
- 포탈 Feedback 접수/검토/처리 상태와 AX팀 후속 작업
- 포탈 공지사항 릴리즈노트와 배포 커뮤니케이션
- 만난 사람/대화한 사람
- Jot/Task DB/standup 기준 완료·진행·미완료
- 감정/생각/음성메모에서 드러난 주제
- 다음 액션
- 원문 링크 또는 local raw path

권장 구조:

```markdown
# YYYY-MM-DD

## 하루 흐름

## 작업 / 산출물

## 커뮤니케이션

## kubit

## Jot / Task / Standup 판정

## 개인 메모 / 음성

## 다음 액션

## Raw Links
```

## Guardrails

- `kmsg` / KakaoTalk 수집은 하지 않는다.
- 외부 게시나 메시지 전송은 하지 않는다.
- 실패한 source는 전체 루틴을 멈추지 말고 `summary.md`에 실패 사유를 남긴다.
- `proc/archive/`는 읽지 않는다.
