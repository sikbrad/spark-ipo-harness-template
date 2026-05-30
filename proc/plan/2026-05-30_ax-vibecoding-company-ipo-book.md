# AX와 바이브코딩으로 회사 상장시키기 제작 계획

## 목표

500개 이야기 꼭지를 책의 독서 순서로 재배열한 문서를 새로 만들고, 그 순서를 바탕으로 `AX와 바이브코딩으로 회사 상장시키기`라는 제목의 초판 책 원고를 만든다. 결과물은 Markdown, HTML, PDF로 저장한다.

## 사용자 요청

- 계획문서/이야기 꼭지 문서의 꼭지들을 책으로 만들기 위해 순서대로 재배열한 문서를 새로 만든다.
- 책 이름은 `AX와 바이브코딩으로 회사 상장시키기`로 한다.
- 단순 자료집이나 기존 PDF 엮기가 아니라 책으로 읽히는 원고를 만든다.

## 출력 위치

- 판본 폴더: `data/vibecoding-book/ax-company-ipo-2026-05-30/`
- 재배열 문서: `ordered-topics.md`
- 출판기획서: `publication-plan.md`
- 원고 Markdown: `ax-vibecoding-company-ipo-book.md`
- HTML: `ax-vibecoding-company-ipo-book.html`
- CSS: `ax-vibecoding-company-ipo-book.css`
- PDF: `ax-vibecoding-company-ipo-book.pdf`
- 검수 기록: `render-review.md`
- 생성 요약: `summary.json`

## 작업 원칙

- 새 API 스크랩은 하지 않는다.
- 근거는 기존 로컬 자료: `story-topics-2026-05-30/vibecoding-story-topics.md`, PPT 추출물, Notion dump, Daily summary, ChatGPT 로컬 DB 제목, 기존 책 산출물.
- `말라카 외부 강의`와 `회사 AX/사내교육/업무 자동화`를 분리한다.
- `회사 상장시키기`는 투자 조언이나 상장 보장을 뜻하지 않는다. 본문에서는 “상장 가능한 체질을 만드는 운영서”로 정의한다.
- 회사명, 실명, 고객/회계/보안/계정 정보는 외부 공개 전 익명화·법무 검토 대상으로 표시한다.

## 작업 항목

- [x] 새 요청과 기존 500개 꼭지 문서 확인.
- [x] 새 판본의 파트/장 구조 결정.
- [x] 500개 꼭지를 책 순서로 재배열한 문서 작성.
- [x] 출판기획서 작성.
- [x] 새 제목 기준 Markdown 원고 작성.
- [x] HTML/CSS/PDF 렌더링.
- [x] PDF 페이지 수, 텍스트 추출, 민감/오류 패턴, HTML 구조 검증.
- [x] 브라우저로 HTML 표지/목차/본문/뒷표지 시각 검수.

## 진행 기록

- 2026-05-30 KST: 작업 시작. `vibecoding-book` 스킬 규칙을 확인하고 기존 500개 이야기 꼭지의 최종 병합 지도를 읽었다.
- 2026-05-30 KST: 새 제목에 맞춰 책의 중심축을 `상장을 보장하는 법`이 아니라 `상장 가능한 회사 체질을 만드는 AX 운영서`로 정했다.
- 2026-05-30 KST: 500개 꼭지를 6부 24장 구조로 재배열하기로 결정했다. 순서는 저자 각오 → 상장 가능한 회사 체질 → SPARK-IPO → 바이브코딩 실행법 → 회사 AX 운영 → 말라카 강의/인재 엔진 → 검증/거버넌스/미래 설계 흐름으로 둔다.
- 2026-05-30 KST: `scripts/ax_vibecoding_company_ipo_book.py`를 추가해 500개 꼭지를 파싱하고, 각 꼭지를 최초 배치 장에 1회만 두는 `ordered-topics.md`를 생성했다. 재배열 수는 500개로 검증했다.
- 2026-05-30 KST: `publication-plan.md`, `ax-vibecoding-company-ipo-book.md`, `ax-vibecoding-company-ipo-book.html`, `ax-vibecoding-company-ipo-book.pdf`를 생성했다. 새 API 스크랩 없이 로컬 자료만 사용했다.
- 2026-05-30 KST: 1차 렌더가 177쪽이라 이전 장문 책 기준에 맞춰 각 절에 현장 적용 노트와 공개판 정제 기준을 추가했고, 중간 PDF를 231쪽으로 재렌더했다.
- 2026-05-30 KST: 브라우저 시각 검수에서 HTML 섹션 내부 Markdown 헤딩이 일부 그대로 보이는 문제를 발견했다. `md_in_html` 렌더링을 적용해 HTML/PDF를 다시 생성했다.
- 2026-05-30 KST: 추가 텍스트 검수에서 `...이다은` 식의 조사 결합 오류를 발견해 문장을 수정했다. 최종 PDF는 296쪽이며, 제목/페이지 수/500개 재배열/브라우저 구조/민감 메타 패턴 검증을 통과했다.
