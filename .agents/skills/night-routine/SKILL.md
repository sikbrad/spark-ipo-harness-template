---
name: night-routine
description: 밤 루틴 수집/정리. 음성녹음 transcript를 먼저 모은 뒤 daily-collect로 Notion, Teams, Calendar, Gmail/Outlook, Drive, Jira/Confluence 등을 수집하고, kubit Slack 대화와 people을 갱신하며, `data/daily/<YYYY-MM-DD>/summary.md`에 그날 있었던 일과 다음 액션을 기록한다. "나이트루틴", "밤 루틴", "오늘 정리해줘", "하루 마감", "night routine" 요청 시 사용. 모닝루틴 소스와 중복 수집해도 된다. kmsg/KakaoTalk은 제외한다.
---

# Night Routine

밤에는 중복보다 누락 방지가 중요하다. `morning-routine`에서 이미 본 소스도 다시 수집해도 된다.

## Core Flow

1. 기준일을 정한다. 명시가 없으면 Asia/Seoul 오늘.
2. 음성녹음 transcript를 먼저 찾아 `data/daily/<date>/raw/voice-*.txt`에 둔다.
3. startpoint의 기존 `daily-collect` 절차로 주요 raw를 수집한다.
4. kubit Slack conversation과 people 데이터를 갱신한다.
5. Notion/Raindrop/Drive/ChatGPT 등 archival source를 필요한 만큼 추가한다.
6. raw를 직접 읽고 `data/daily/<date>/summary.md`를 작성하거나 갱신한다.

## Sources

공통 source routing은 [../morning-routine/references/routine-sources.md](../morning-routine/references/routine-sources.md)를 따른다. `kmsg`는 이 루틴에서 사용하지 않는다.

Night 기본 수집:

| Source | Use |
|---|---|
| voice transcript | 하루 생각/회의/이동 중 메모의 1차 raw |
| `daily-collect` | Notion, Teams, Calendar, Gmail/Outlook, Drive, Jira/Confluence raw + summary |
| kubit Slack `collect:conv` | kubit 채널/DM/그룹DM 대화 cache |
| kubit Slack `collect:people` | 사람별 activity, future_self, weekly_report, conversations 갱신 |
| `notion-dump` | Notion 전체 트리 증분 sync |
| `raindrop` | 북마크 dump |
| `raindrop-infer` | 오늘 저장한 중요한 링크 분석 |
| `chatgpt` | 개인 ChatGPT 대화 export, 필요하거나 주기적으로 |
| `gdrive` / `onedrive` / `sharepoint` | 수정/참조 문서 raw |
| `amaranth-approval` / `amaranth-calendar` | 회사 결재/일정 기록 |

`morning-routine`과 겹치는 Teams, Calendar, Gmail, Outlook, Jira, Confluence, kubit Slack light signals도 다시 수집해도 된다.

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

## Voice Transcript

음성 원본 위치가 명시되면 그 위치를 우선한다. 이미 전사된 `.txt`가 있으면 변환하지 말고 날짜별 raw에 복사한다.

저장 규칙:

```text
data/daily/<YYYY-MM-DD>/raw/voice-<source-or-time>.txt
```

전사 원본 경로가 불명확하면 음성 단계만 skip하고 summary에 `Voice: source path not configured`를 남긴다.

## Summary Rules

`summary.md`는 단순 로그가 아니라 그날의 기억이어야 한다.

포함할 것:

- 하루의 큰 흐름
- 실제로 한 일
- 결정과 산출물
- 만난 사람/대화한 사람
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

## 개인 메모 / 음성

## 다음 액션

## Raw Links
```

## Guardrails

- `kmsg` / KakaoTalk 수집은 하지 않는다.
- 외부 게시나 메시지 전송은 하지 않는다.
- 실패한 source는 전체 루틴을 멈추지 말고 `summary.md`에 실패 사유를 남긴다.
- `proc/archive/`는 읽지 않는다.
