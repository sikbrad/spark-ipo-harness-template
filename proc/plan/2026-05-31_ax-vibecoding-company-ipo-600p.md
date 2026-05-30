# AX와 바이브코딩으로 회사 상장시키기 600쪽 판본 계획

## 목표

기존 500개 이야기 꼭지와 로컬 Daily/Notion/ChatGPT/PPT 자료를 더 반영해 `AX와 바이브코딩으로 회사 상장시키기`의 600쪽 이상 PDF 판본을 만든다. 296쪽 초판을 성공 기준으로 삼지 않고, 실제 PDF 페이지 수가 600쪽 이상임을 검증한다.

## 출력 위치

- 판본 폴더: `data/vibecoding-book/ax-company-ipo-600p-2026-05-31/`
- 재배열 문서: `ordered-topics.md`
- 출판기획서: `publication-plan.md`
- 자료 보강 리포트: `source-deepening-report.md`
- 원고 Markdown: `ax-vibecoding-company-ipo-book.md`
- HTML: `ax-vibecoding-company-ipo-book.html`
- PDF: `ax-vibecoding-company-ipo-book.pdf`
- 검수 기록: `render-review.md`

## 반영 자료

- 500개 꼭지: `data/vibecoding-book/story-topics-2026-05-30/vibecoding-story-topics.md`
- 기존 초판: `data/vibecoding-book/ax-company-ipo-2026-05-30/`
- Source inventory: `data/vibecoding-book/source-inventory-2026-05-31-600p/`
- Daily summary 361개
- Notion Markdown 3,332개
- ChatGPT conversation title 4,326개
- PPT extract deck dirs 30개, extracted slides 9,312개
- Voice transcript 251개

## 작업 원칙

- 새 API 스크랩은 하지 않는다.
- 본문은 자료를 나열하지 않고 새 문장으로 저술한다.
- 말라카 외부 강의와 회사 AX/사내교육은 계속 분리한다.
- `회사 상장시키기`는 상장 보장, 투자 조언, 증권 조언이 아니라 상장 가능한 회사 체질을 만드는 운영서로 정의한다.
- 공개 전 회사 내부 정보, 고객·회계·보안·실명, PPT 이미지 권리는 검토 대상으로 남긴다.

## 작업 항목

- [x] 296쪽 초판과 500개 꼭지 현재 상태 확인.
- [x] Source inventory 재생성.
- [x] 600쪽 판본 계획 문서 작성.
- [x] 600쪽 판본 생성 스크립트 작성.
- [x] 600쪽 이상 Markdown/HTML/PDF 생성.
- [x] PDF 페이지 수, 제목, 텍스트 추출, 금지/오류 패턴 검증.
- [x] HTML 브라우저 시각 검수와 스크린샷 저장.

## 진행 기록

- 2026-05-31 KST: 목표 이어받음. 기존 `ax-company-ipo-2026-05-30` 판본은 296쪽이며 목표의 600쪽 조건을 충족하지 못하므로 새 600쪽 판본을 별도 폴더로 만들기로 결정했다.
- 2026-05-31 KST: `source-inventory-2026-05-31-600p`를 생성했다. 인벤토리 기준 PPT extract deck dirs 30개, extracted slides 9,312개, Daily summaries 361개, Notion markdown 3,327개, hydrated pages 3,352개, voice transcripts 251개, ChatGPT conversations 4,326개를 확인했다.
- 2026-05-31 KST: 기존 296쪽 판본 생성기를 재사용하되 별도 600쪽 판본 생성기 `scripts/ax_vibecoding_company_ipo_600p_book.py`를 추가했다. 절별로 Daily/Notion, ChatGPT 질문 흐름, PPT/voice, 상장 가능한 체질, 실행 체크 문단을 보강하도록 했다.
- 2026-05-31 KST: 1차 600쪽 보강 렌더는 951쪽이라 과도하게 커서 보강 문단을 압축했다. 2차는 585쪽으로 모자라 실행 체크 문단을 추가했고 최종 렌더는 614쪽이다.
- 2026-05-31 KST: 최종 검증 완료. PDF 제목 `AX와 바이브코딩으로 회사 상장시키기`, 614쪽, 500개 꼭지 전부 재배열, 오류/메타 패턴 미검출, 브라우저 HTML 시각 검수 및 스크린샷 저장을 확인했다.
