---
name: weekly-company-summary
description: 최근 1주일 또는 지정 기간의 회사 업무 기록을 요약한다. Daily summary/raw, Notion Jot/Task, Teams 채팅/채널/standup, Outlook/Gmail/Drive, Jira/Confluence, proc/research/plan 산출물, 포탈 Feedback, 포탈 공지사항/릴리즈노트를 읽고 “내가 회사에서 무엇을 했는지”를 날짜별·주제별로 정리한다. “1주일동안 뭐했냐”, “이번주 회사 업무”, “회사관련 한일”, “주간 업무 정리”, “weekly company summary” 등 요청 시 사용. 포탈 Feedback과 포탈 공지사항 릴리즈노트는 AX팀/사용자 업무 산출물로 포함한다.
---

# Weekly Company Summary

## Scope

- 기본 기간은 Asia/Seoul 기준 오늘을 포함한 최근 7일이다. 답변에는 반드시 절대 날짜 범위를 쓴다.
- 사용자가 `지난주`, `이번주`, `최근 N일`, 특정 날짜를 말하면 그 기간을 우선한다.
- 회사 업무 중심으로 정리한다. DOF, AX, 포탈, 온라인 쇼핑몰, 거래원장, 수금, 고객 발송, 결재, 운영, 지원, Teams, Outlook, Jira, Confluence 기록을 포함한다.
- 개인 프로젝트, 외부 강의, kubit, SNS는 회사 업무와 직접 연결될 때만 포함한다.
- 포탈 `Feedback`과 포탈 공지사항/릴리즈노트는 AX팀 작업 또는 사용자 업무 산출물과 같은 신호로 취급한다.

## Source Order

1. 먼저 `data/daily/<YYYY-MM-DD>/summary.md`와 `morning-brief.md`를 읽어 기간의 큰 흐름을 잡는다.
2. 필요한 날짜는 `data/daily/<YYYY-MM-DD>/raw/`의 raw를 직접 읽는다.
   - `notion-jot.json`
   - `notion-tasks.json`
   - `teams-standup.json`
   - `teams-chat*.json`
   - `teams-channel*.json`
   - `atlassian.json`
   - `portal-feedback.json`
   - `portal-notices.json`
   - `source-errors.json`
3. 포탈 raw가 없고 사용자가 누락분 보강이나 스크랩을 원하면 날짜별로 다음 collector를 실행한다.

```bash
node proc/lib/portal_feedback_collect.mjs <YYYY-MM-DD>
node proc/lib/portal_notice_collect.mjs <YYYY-MM-DD>
```

4. `proc/plan/*.md`, `proc/research/*.md`, `output/` 산출물에서 기간과 관련된 파일을 읽는다.
5. `proc/archive/`는 사용자가 명시적으로 지시하지 않는 한 열람하지 않는다.
6. Teams 세부 내역이 부족하면 기존 `data/teams/full-history/` 또는 `output/teams-business-rules/` 산출물을 먼저 확인한다. 최신 Teams 수집이 꼭 필요할 때만 Teams 관련 skill을 사용한다.

## Interpretation Rules

- 포탈 Feedback triage, 알림 테스트, 담당자 검토, 상태 변경은 AX 운영/개선 업무로 정리한다.
- 포탈 공지사항 릴리즈노트, 배포 공지, 점검 공지는 “한 일/산출물/배포 커뮤니케이션”으로 분류한다.
- 테스트성 feedback이나 notice도 AX/포탈 기능 검증과 연결되면 업무로 포함하되, 고객 요청으로 오해되지 않게 `테스트`라고 표시한다.
- 로그를 나열하지 말고 결과와 의미를 먼저 쓴다. 세부 메시지는 근거가 필요할 때만 짧게 언급한다.
- 서로 다른 소스가 같은 일을 가리키면 하나의 주제로 묶고, Teams/Notion/Confluence/포탈 중 어떤 근거가 있었는지 덧붙인다.
- 수집 실패, DB timeout, raw 누락은 숨기지 말고 마지막에 짧게 적는다.

## Output Shape

- 한국어로 답한다.
- 시작에 날짜 범위와 한 줄 총평을 둔다.
- 기본 섹션은 `핵심 요약`, `주요 축`, `날짜별 흐름`, `포탈 Feedback/공지 반영`, `다음 액션`, `근거와 누락`이다.
- 사용자가 간단히 물으면 압축해서 답하고, 보고서나 상세 정리를 원하면 날짜별·주제별 표를 추가한다.
- “포탈 Feedback/공지 반영”에는 반드시 Feedback과 릴리즈노트가 있었는지, 없으면 raw 누락인지 실제 없음인지 구분한다.
