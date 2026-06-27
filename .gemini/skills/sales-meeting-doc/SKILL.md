---
name: sales-meeting-doc
description: Confluence AX 폴더의 최신 `영업정기회의+AX` 문서를 복제해 오늘 또는 지정 날짜의 영업정기회의 문서를 생성하고, 기존 `주제` 컬럼을 보존한 채 DailyJot와 Teams standup/회사 업무 이슈 기반 `논의항목`을 개조식으로 채운다. "영업정기회의 문서", "영업 정기회의 회의록", "260527 영업정기회의", "sales meeting doc" 요청 시 사용. kubit, Slack, 개인 일, 고려대 관련 내용은 절대 포함하지 않는다.
---

# 영업정기회의 문서 생성

Confluence `AX / 영업정기회의(올해)` 폴더에서 가장 최근 날짜 문서를 **Confluence native copy API**로 복사해 새 회의 문서를 만든다. storage body를 새로 생성하는 방식은 icon, page properties, related/custom contents가 빠질 수 있으므로 쓰지 않는다.

## 기본값

- Confluence folder id: `724271123`
- 제목 형식: 최신 문서의 첫 날짜 토큰 형식을 그대로 유지한다. 현재 폴더는 `YYMMDD 영업정기회의+AX` 형식이다.
- 기준 날짜: 사용자가 지정하지 않으면 Asia/Seoul 오늘.
- 기준 기간: 최신 문서 날짜 다음 날부터 기준 날짜까지.

## 핵심 절차

1. 최신 문서와 표 구조를 확인한다.
   ```bash
   python3 .agents/skills/sales-meeting-doc/scripts/create_sales_meeting_doc.py --date <YYYY-MM-DD> --dry-run
   ```
2. 기준 기간의 daily raw가 있는지 확인한다. 없거나 `raw/teams-standup.json`이 비어 있으면 Teams standup을 먼저 보강 수집한다.
   ```bash
   python3 .agents/skills/sales-meeting-doc/scripts/collect_standup.py --start <YYYY-MM-DD> --end <YYYY-MM-DD>
   ```
   Graph가 실패하면 `/teams-channel` 또는 `/teams-channel-browser` 방식으로 `standup-daily-ax`를 수집해 `data/daily/<date>/raw/teams-standup.json`에 둔다.
3. 아래 source를 직접 읽고 `output/sales-meeting-doc/<date>/discussion.json`을 만든다.
   - 우선: `data/daily/<date>/raw/teams-standup.json`
   - 보조: `summary.md`, `raw/notion-jot.json`, `raw/notion-tasks.json`, `raw/teams-channels.json`, `raw/teams-chats.json`, `raw/atlassian.json`, 회사 Outlook raw
   - 제외: kubit, Slack, 개인 일, 고려대, KakaoTalk/kmsg, 개인 Gmail/Google Calendar/개인 Drive 중심 내용
4. `discussion.json`은 최신 문서의 `주제` 값과 같은 key를 사용한다. 논의항목은 다단 개조식으로 쓴다. 상위 bullet은 이슈 묶음/상태, 하위 bullet은 세부 사실/후속 액션이다.
   ```json
   {
     "주문웹(포탈) & 거래원장 일정": [
       {
         "text": "포탈 고객 국가값 정비",
         "children": [
           "국가 미지정 419건 웹/SF/Google Maps 근거 조사 완료",
           "DB 반영 전 담당자 검수용 Excel 산출"
         ]
       },
       {
         "text": "거래원장 발송 준비",
         "children": [
           "audit summary와 업체별 PDF 검토 요청",
           "미발송 요청 업체는 발송 대상에서 제외 여부 확인 필요"
         ]
       }
     ],
     "주문앱": [
       {
         "text": "영업 실전 테스트 피드백 반영",
         "children": ["안정화 항목 분리", "배포 후 후속 버그 확인"]
       }
     ]
   }
   ```
5. 먼저 dry-run으로 미리보기와 금칙어 검증을 통과시킨다.
   ```bash
   python3 .agents/skills/sales-meeting-doc/scripts/create_sales_meeting_doc.py \
     --date <YYYY-MM-DD> \
     --discussion-json output/sales-meeting-doc/<YYYY-MM-DD>/discussion.json \
     --dry-run
   ```
6. 사용자가 문서 생성을 요청한 작업이면 확인 질문 없이 실제 생성한다.
   ```bash
   python3 .agents/skills/sales-meeting-doc/scripts/create_sales_meeting_doc.py \
     --date <YYYY-MM-DD> \
     --discussion-json output/sales-meeting-doc/<YYYY-MM-DD>/discussion.json \
     --write
   ```
   같은 제목 문서가 이미 있고 내가 재구성/오작성한 문서를 고치는 상황이면 native copy replace를 쓴다.
   ```bash
   python3 .agents/skills/sales-meeting-doc/scripts/create_sales_meeting_doc.py \
     --date <YYYY-MM-DD> \
     --discussion-json output/sales-meeting-doc/<YYYY-MM-DD>/discussion.json \
     --write \
     --replace-existing
   ```

## 작성 규칙

- 최신 문서의 `주제` 컬럼과 행 순서를 유지한다.
- `논의항목`은 이전 최신 회의 이후부터 기준일까지의 회사 업무 이슈만 쓴다.
- 다단 개조식 문장은 짧게 쓴다. 상위 bullet은 2~5개 묶음으로 제한하고, 하위 bullet은 회의에서 바로 읽히는 상태/이슈/요청 중심으로 작성한다.
- 출처가 약한 추측은 쓰지 않는다. Teams standup과 daily raw에서 확인한 내용만 쓴다.
- 절대 포함 금지: `kubit`, `Slack`, `슬랙`, 개인사, 고려대/강의/학생/학교 관련 내용.

## 검증

- dry-run 출력에서 최신 문서 ID, 대상 제목, 주제 목록, preview 경로를 확인한다.
- `discussion.json` key가 실제 `주제`와 맞지 않으면 고친다.
- 금칙어 검증이 실패하면 source를 다시 읽고 회사 업무 내용만 남긴다.
- 생성/교정은 `POST /wiki/rest/api/content/{id}/copy` 기반인지 확인한다.
- 실제 생성 후 출력된 Confluence URL을 열람 가능한 링크로 보고한다.
