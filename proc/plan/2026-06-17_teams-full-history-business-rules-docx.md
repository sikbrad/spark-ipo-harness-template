# 2026-06-17 Teams Full History + Business Rules Docx

## 목표
`ins@doflab.com` 사용자가 속한 모든 Microsoft Teams 채팅방과 채널을 나열하고, 기존 수집분을 포함해 처음부터 현재까지 수집 가능한 전체 메시지를 확보한다. 이후 김규탁, 조소연, 정재회, 김채원, 이미연의 통상업무와 업무규칙을 분석하여 docx 보고서를 만든다.

## 작업 항목
- [x] Teams Graph 인증/현재 사용자 확인
- [x] 모든 Teams chatroom 목록 dump
- [x] 모든 joined team/channel 목록 dump
- [x] 모든 chatroom 히스토리 수집
- [x] 모든 channel thread/reply 히스토리 수집
- [x] 기존 수집분과 신규 수집량 비교
- [x] 5명 관련 메시지/기존 분석자료 추출
- [x] 개발 요청성 대화와 통상업무 대화 분리
- [x] 인물별 업무/업무규칙 정리
- [x] docx 생성
- [x] 결과/한계 기록

## 산출물 예정
- `data/teams/full-history/2026-06-17/`
- `output/teams-business-rules/2026-06-17/`

## 중간 결과
- Graph 사용자: `백인식 Brad <ins@doflab.com>`
- Chatrooms: 114개 (DM 62 / group 37 / meeting 15)
- Joined teams: 4개
- Channels: 35개
- Chatroom history: 114개 파일, 31,475 메시지 수집 완료
- `proc/run_teams_conversations_dump.py --full-history` 플래그 추가
- `.agents/skills/night-routine/SKILL.md`에 Teams full archive 단계 추가
- Channel history: 32/35개 파일, 2,699 threads, 6,381 메시지 수집 완료, channel reply 오류 0
- 미수집 3개: `DOF Inc. / proj-출고-예외승인`, `DOF Inc. / 기술지원 운영`, `DOF Inc. / proj-월결산-생산재고회계` — Graph 403 Forbidden
- 최종 보고서 생성 완료: `output/teams-business-rules/2026-06-17/teams_full_history_business_rules_2026-06-17.docx`

## 2026-06-17 재작성 작업
사용자 피드백에 따라 기존 인물별 나열식 문서는 폐기 기준으로 두고, 인수인계용 SOP 문서로 재작성한다. 핵심은 "누가 언제 무엇을 했는가"가 아니라 "주문 오류, 국가/제도, 재고/출고, 정산/미수, 시스템 권한 문제 상황에서 어떤 순서로 판단하고 처리하는가"이다.

## 재작성 작업 항목
- [x] 기존 Teams evidence와 `data/teams/peoples/*/업무규칙` 자료 재검토
- [x] 인물별 업무유형/상황별 처리규칙 재정의
- [x] 중간 Markdown 문서 5개 생성
- [x] Word 문서 5개 생성 및 ZIP 검증
- [x] 기존 산출물과 새 산출물 경로 분리 기록

## 재작성 산출물
- Markdown: `output/teams-business-rules/2026-06-17/sop_docs/markdown/`
- Word: `output/teams-business-rules/2026-06-17/sop_docs/docx/`
- 생성 스크립트: `proc/plan/build_sop_business_rule_docs_2026_06_17.py`
- 검증: 5개 DOCX 모두 `[Content_Types].xml`, `word/document.xml` 포함 확인

## 2026-06-17 30페이지 인수인계서 재작성
사용자 피드백에 따라 SOP 요약판도 부족하다고 판단했다. 새 문서는 각 인물별로 30개 장을 만들고, 각 장을 수동 페이지 나눔으로 분리해 Word 기준 최소 31페이지가 되도록 생성했다. 문서 구조는 시간순 이력 나열이 아니라 `데이터에서 보인 신호 → 인수인계 판단 → 처리 절차 → 특이사항/예외 → 멈춤 조건 → 기록 항목`이다.

## 30페이지판 산출물
- Markdown: `output/teams-business-rules/2026-06-17/handover_30p_docs/markdown/`
- Word: `output/teams-business-rules/2026-06-17/handover_30p_docs/docx/`
- 검증: `output/teams-business-rules/2026-06-17/handover_30p_docs/verification.json`
- 생성 스크립트: `proc/plan/build_30p_handover_docs_2026_06_17.py`

## 30페이지판 검증 결과
- 김규탁: 30개 장, 수동 페이지브레이크 30개, 최소 31페이지 추정
- 조소연: 30개 장, 수동 페이지브레이크 30개, 최소 31페이지 추정
- 정재회: 30개 장, 수동 페이지브레이크 30개, 최소 31페이지 추정
- 김채원: 30개 장, 수동 페이지브레이크 30개, 최소 31페이지 추정
- 이미연: 30개 장, 수동 페이지브레이크 30개, 최소 31페이지 추정

## 2026-06-17 60페이지 확장판
사용자 추가 요청에 따라 기존 30페이지판을 확장했다. 수집된 Teams 근거에서 키워드, 출처, 대표 발화가 확인되는 주제만 추가했고, 근거가 없는 내용을 억지로 만들지 않는 기준으로 처리했다. 5명 모두 표지 1페이지 + 본문 59페이지 구성까지 확장 가능했다.

## 60페이지판 산출물
- Markdown: `output/teams-business-rules/2026-06-17/handover_60p_docs/markdown/`
- Word: `output/teams-business-rules/2026-06-17/handover_60p_docs/docx/`
- 검증: `output/teams-business-rules/2026-06-17/handover_60p_docs/verification.json`
- 생성 스크립트: `proc/plan/build_60p_handover_docs_2026_06_17.py`

## 60페이지판 검증 결과
- 김규탁: 본문 59개 장, 수동 페이지브레이크 59개, 표지 포함 60페이지
- 조소연: 본문 59개 장, 수동 페이지브레이크 59개, 표지 포함 60페이지
- 정재회: 본문 59개 장, 수동 페이지브레이크 59개, 표지 포함 60페이지
- 김채원: 본문 59개 장, 수동 페이지브레이크 59개, 표지 포함 60페이지
- 이미연: 본문 59개 장, 수동 페이지브레이크 59개, 표지 포함 60페이지

## 60페이지판 이메일 발송
- 발송 시각: 2026-06-17 08:20 KST
- 발신/수신: `ins@doflab.com` -> `ins@doflab.com`
- 제목: `[확장 송부] Teams 업무규칙 인수인계서 60페이지판 DOCX 5건`
- 본문에 각 문서 페이지 수 60페이지를 명시했다.
- 보낸편지함 검증: 동일 제목 메일 확인, `hasAttachments=True`, DOCX 첨부 5개 확인
