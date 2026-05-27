# Vibecoding book rewrite from daily note

## 목표

사용자의 2026-05-27 daily note 요청을 기준으로 바이브코딩 책을 다시 기획한다. API로 새 스크랩을 하지 않고, 이미 내려받은 PPT 추출물, Notion hydrated dump, daily summaries, ChatGPT conversation title DB를 조합해 목차를 먼저 팽창시킨 뒤 200쪽 이상 신규 저술본을 만든다.

## 사용자 요청 핵심

- "강의 자체를 책으로 바꾸는걸 먼저해야 하지 않나 — 내가 가장 잘 아는 내용"을 큰 축으로 삼는다.
- SPARK IPO 관련 내용을 책의 방법론 중심축으로 넣는다.
- "170명 실습강좌 설계하는 요령"을 말라카 강사 챕터로 담는다.
- daily note처럼 매일 쓰기보다 "요령을 하나씩 툭툭 던지는" 스타일을 책의 구성법으로 삼는다.
- 슬라이드에 있는 정보를 챕터 하나씩으로 팽창시킨다.
- 말라카 자신, 카카오모빌리티를 나오게 된 이야기, 회사에서 추구하는 책 스타일, 강의에서 다루는 내용들을 목차에 넣는다.
- 기존 다운로드 자료만 조합한다. 새 API 스크랩은 하지 않는다.
- 목차를 먼저 잘 만들고, 그다음 200쪽 이상 직접 저술한다.
- 코딩으로 기존 PDF/슬라이드를 페이지 단위로 엮지 않는다.
- HTML 기반 출판 스타일을 사용하고, PPT에 있는 그림도 가져온다.
- 요청사항은 리포트에 기록한다.

## 작업 항목

- [x] 새 요청사항을 계획 문서에 기록
- [x] 로컬 자료 위치 확인: `data/vibecoding-book`, `data/notion/hydrated`, `data/daily`, `data/db/chatgpt.sqlite`
- [x] 요청사항 리포트 작성
- [x] ChatGPT/Notion/Daily/PPT 로컬 근거를 요약
- [x] 확장 목차 작성
- [x] PPT 대표 이미지 로컬 추출
- [x] 새 Markdown/HTML/PDF 책 생성
- [x] PDF 200쪽 이상, raw metadata leak 없음, API 재스크랩 없음 검증

## 산출물 위치

- 작업 폴더: `data/vibecoding-book/rewrite-2026-05-27/`
- 요청 리포트: `request-report.md`
- 확장 목차: `expanded-toc.md`
- 새 책: `malaka-vibecoding-lecture-to-book.md/html/pdf`
- 검증 요약: `rewrite-summary.json`

## 원칙

- `input/`과 `proc/archive/`는 건드리지 않는다.
- 기존 `data/vibecoding-book/final/` 책은 이전 버전으로 보존하고, 이번 요청은 별도 rewrite 폴더에 새로 만든다.
- PPT 이미지는 로컬 PPTX 내부 media만 추출한다.
- 본문은 새 문장으로 저술하고, 원천 자료는 근거와 목차 설계에만 사용한다.

## 결과

- 요청 리포트: `data/vibecoding-book/rewrite-2026-05-27/request-report.md`
- 확장 목차: `data/vibecoding-book/rewrite-2026-05-27/expanded-toc.md`
- 새 원고: `data/vibecoding-book/rewrite-2026-05-27/malaka-vibecoding-lecture-to-book.md`
- 새 HTML: `data/vibecoding-book/rewrite-2026-05-27/malaka-vibecoding-lecture-to-book.html`
- 새 PDF: `data/vibecoding-book/rewrite-2026-05-27/malaka-vibecoding-lecture-to-book.pdf`
- PPT 이미지: `data/vibecoding-book/rewrite-2026-05-27/assets/ppt-images/` 18개
- 구성: 8부, 24장, 216절
- 검증: `pdfinfo` 기준 547쪽, raw metadata leak 0건, 새 API 스크랩 없음
