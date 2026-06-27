---
name: threads-vibecoding-scheduler
description: 로컬 바이브코딩/AX 책·꼭지 자료를 바탕으로 개인정보와 회사 내부 정보를 제거한 Threads 연재 글을 작성하고, 말라카 등 본인 Threads 계정에 매일 지정 시각 예약 발행한다. "바이브코딩 글 Threads 예약", "책 꼭지로 쓰레드 연재", "말라카 계정에 예약발송", "AX 리더 글감으로 Threads 일정 예약", "매일 아침 Threads 예약" 요청 시 사용한다. vibecoding-book, threads, playwright-cli를 결합한 공개용 연재 자동화 스킬이다.
---

# Threads Vibecoding Scheduler

로컬 바이브코딩/AX 원고와 꼭지 목록을 공개 가능한 Threads 연재 글로 바꾸고, `playwright-cli` headful 세션으로 기간별 예약 발행한다.

## Core Rules

- 복잡한 요청이면 먼저 `proc/plan/`에 계획 문서를 만들고 체크리스트를 갱신한다.
- 로컬 자료를 우선한다. 새 API 스크랩은 사용자가 명시하지 않으면 하지 않는다.
- 개인 실명, 회사명, 고객명, 내부 프로젝트명, 내부 URL, 계정/조직 상황은 쓰지 않는다.
- 회사 AX나 강의 경험은 특정 조직 사례가 아니라 추상적인 `AX 리더`, `바이브코더`, `실무자` 관점으로 바꾼다.
- 사용자 문체 예시가 있으면 구조와 리듬만 참고하고, 내용은 로컬 자료에서 뽑은 생각으로 새로 쓴다.
- Threads 한 블록은 500자 이하로 유지한다. 한 날짜는 기본적으로 `본문 / 첫 댓글 / 두 번째 댓글` 3블록 체인으로 작성한다.
- 예약 발행은 실제 외부 서비스 변경이다. 사용자가 계정·기간·예약 발행을 이미 명시한 경우에만 실행한다.

## Workflow

1. 요청사항을 계획 문서에 기록한다.
   - 계정, 기간, 시간대, 시작일/종료일, 문체 기준, 금지 정보, 출력 폴더.
2. 로컬 자료를 찾는다.
   - 우선 후보:
     - `data/vibecoding-book/**/ordered-topics.md`
     - `data/vibecoding-book/**/vibecoding-story-topics.md`
     - `data/vibecoding-book/**/publication-plan.md`
     - `data/vibecoding-book/**/summary.json`
     - `data/vibecoding-book/**/market-toc.md`
   - 필요하면 `/vibecoding-book`의 `inventory_sources.py`를 실행한다.
3. 공개 가능한 글감만 선별한다.
   - 좋은 주제: 문제 쪼개기, 검증 기준, 위임 기준, 상태값 정의, 승인 구조, MVP 축소, 프롬프트를 명세로 쓰기, AI 작업 로그, 버리는 기능 목록.
   - 제외 주제: 특정 회사 운영, 고객명, 내부 시스템명, 실명, 계정명, 내부 링크, 매출/계약/인사/정산 세부사항.
4. 날짜별 초안을 작성한다.
   - 파일 위치 예: `output/threads-vibecoding-YYYY-MM/YYYY-MM-DD.md`
   - 포맷:
     ```markdown
     본문
     ---
     첫 댓글
     ---
     두 번째 댓글
     ```
5. 검증한다.
   ```bash
   python3 .agents/skills/threads-vibecoding-scheduler/scripts/validate_threads_posts.py \
     output/threads-vibecoding-YYYY-MM
   ```
6. Threads 세션을 확인한다.
   ```bash
   playwright-cli -s=threads open https://www.threads.com/ --persistent --headed
   playwright-cli -s=threads snapshot
   ```
   프로필 링크나 compose 모달에서 대상 계정을 확인한다.
7. 예약 발행한다.
   ```bash
   python3 .agents/skills/threads-vibecoding-scheduler/scripts/schedule_threads_posts.py \
     --base output/threads-vibecoding-YYYY-MM \
     --session threads \
     --time 08:00 \
     --result output/threads-vibecoding-YYYY-MM/schedule-result.json
   ```
   날짜별 랜덤 시각이 필요하면 `--time-window`와 `--seed`를 쓴다.
   ```bash
   python3 .agents/skills/threads-vibecoding-scheduler/scripts/schedule_threads_posts.py \
     --base output/threads-vibecoding-YYYY-MM \
     --session threads \
     --time-window 07:00-09:00 \
     --seed threads-vibecoding-YYYY-MM \
     --result output/threads-vibecoding-YYYY-MM/schedule-result.json
   ```
8. 결과를 검증하고 계획 문서를 닫는다.
   - 결과 JSON의 모든 항목이 `scheduled`인지 확인한다.
   - 실패 항목은 열린 초안을 `Don't save`로 버리고, 실패 항목만 제거한 뒤 `--start-after`로 재개한다.

## Style Pattern

사용자 예시가 없을 때의 기본 톤:

- 짧은 문장.
- 첫 문장은 최근 느낀 문제 제기.
- 중간에는 구체적인 실무 장면 3~4개.
- 끝은 질문형으로 마무리.
- 첫 댓글은 관점 확장.
- 두 번째 댓글은 체크리스트나 실천 기준.

## Safety Scan

검증 스크립트 기본 키워드는 보수적이다. `김` 같은 일반 음절은 오탐이 날 수 있으므로 결과를 직접 읽고 판단한다.

추가 스캔이 필요하면:

```bash
rg -n "회사명|고객명|실명|내부 URL|CRM|ERP|Salesforce|Teams|Slack|Jira|Confluence" output/threads-vibecoding-YYYY-MM
```

## Recovery

- `Done` 버튼이 비활성: 날짜 선택이 반영되지 않았거나 시간이 잘못 들어간 상태다. 스크립트는 날짜 셀 중심 좌표 클릭과 `hh`/`mm` 접근성 이름 입력을 사용한다.
- 실패 초안 정리:
  ```bash
  playwright-cli -s=threads run-code "async page => { const closeButtons = await page.getByRole('button', {name:'Close'}).all(); if (closeButtons.length) await closeButtons[0].click({force:true}); await page.waitForTimeout(700); const dont = page.getByRole('button', {name:\"Don't save\"}); if (await dont.count()) await dont.click({force:true}); return 'closed'; }"
  ```
- 재개:
  ```bash
  python3 .agents/skills/threads-vibecoding-scheduler/scripts/schedule_threads_posts.py \
    --base output/threads-vibecoding-YYYY-MM \
    --start-after YYYY-MM-DD.md
  ```

## Output Contract

완료 보고에는 다음을 포함한다.

- 계획 문서 경로.
- 초안 폴더와 예약 결과 JSON 경로.
- 예약 계정, 기간, 시각, 총 건수.
- 초안 검증 결과: 3블록 여부, 500자 이하 여부, 개인정보/회사정보 스캔 결과.
- 예약 UI 확인에서 확인한 것과 확인하지 못한 것.
