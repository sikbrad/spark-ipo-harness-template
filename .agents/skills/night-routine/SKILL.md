---
name: night-routine
description: 밤 루틴 수집/정리. 음성녹음 transcript를 먼저 모은 뒤 daily-collect로 Notion, Teams, Calendar, Gmail/Outlook, Drive, Jira/Confluence 등을 수집하고, kubit Slack 대화와 people을 갱신한다. Notion DailyJot와 Task DB를 다시 읽어 무엇이 완료/진행/미완료인지 검토하고, Teams standup의 아침 계획/저녁 결산과 대조한다. Raindrop은 dump/infer 후 태그 없는 북마크를 우선 AI 태깅한다. `data/daily/<YYYY-MM-DD>/summary.md`에 그날 있었던 일과 다음 액션을 기록한다. "나이트루틴", "밤 루틴", "오늘 정리해줘", "하루 마감", "night routine" 요청 시 사용. 모닝루틴 소스와 중복 수집해도 된다. kmsg/KakaoTalk은 제외한다.
---

# Night Routine

밤에는 중복보다 누락 방지가 중요하다. `morning-routine`에서 이미 본 소스도 다시 수집해도 된다.

## Core Flow

1. 기준일을 정한다. 명시가 없으면 Asia/Seoul 오늘.
2. 음성녹음을 먼저 처리한다. 이미 transcript가 있으면 `data/daily/<date>/raw/voice-*.txt`에 두고, Drive/로컬에서 audio 원본만 발견되면 반드시 다운로드 후 transcribe하여 `voice-*.txt`를 만든다.
3. startpoint의 기존 `daily-collect` 절차로 주요 raw를 수집한다.
4. Notion DailyJot와 Task DB를 다시 읽어 완료/진행/미완료 상태를 검토한다.
5. Teams standup의 아침 계획과 저녁 결산을 읽고 Jot/Task DB와 대조한다.
6. kubit Slack conversation과 people 데이터를 갱신한다.
7. Notion/Raindrop/Drive/ChatGPT 등 archival source를 필요한 만큼 추가한다.
8. Raindrop에서 태그 없는 북마크를 우선 찾아 infer가 있는 것부터 `raindrop-retag`로 태깅한다.
9. raw를 직접 읽고 `data/daily/<date>/summary.md`를 작성하거나 갱신한다.

## Sources

공통 source routing은 [../morning-routine/references/routine-sources.md](../morning-routine/references/routine-sources.md)를 따른다. `kmsg`는 이 루틴에서 사용하지 않는다.

Night 기본 수집:

| Source | Use |
|---|---|
| voice transcript | 하루 생각/회의/이동 중 메모의 1차 raw |
| `daily-collect` | Notion, Teams, Calendar, Gmail/Outlook, Drive, Jira/Confluence raw + summary |
| Notion DailyJot | 아침 계획, 중간 메모, 체크 상태 재검토 |
| Notion Task DB | 오늘 완료/진행/미완료/overdue 태스크 검토 |
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
