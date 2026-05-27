# 바이브코딩 책 연결형 재집필 계획

- 시작: 2026-05-27 23:40 KST
- 목표: 기존 `rewrite-2026-05-27` 원고의 "챕터 간 연결 부족" 문제를 해결하는 새 판을 별도로 집필한다.
- 새 출력 위치: `data/vibecoding-book/connected-rewrite-2026-05-27/`

## 최신 요청

사용자는 기존 원고가 장 사이에 잘 이어지지 않는다고 판단했다. 새 작업은 다음 조건을 만족해야 한다.

- 목차를 더 만들고, 큰 제목/작은 제목의 순서와 정렬을 다시 잡는다.
- 웹에서 HTML로 책을 쓰는 법과, 독자가 좋아할 만한 장문 서술 방식을 참고한다.
- 참고한 내용은 HTML/PDF 제작 방식과 장문 서술 구조에 반영한다.
- 출처는 footer에 표기한다.
- HTML로 만든 뒤 렌더링을 직접 확인하고, 이상하거나 어색한 부분은 수정한다.
- 코드로 기존 페이지를 엮는 수준이 아니라 실제 판매될 책처럼 줄글 중심으로 집필한다.
- 챕터 내부와 챕터 사이가 자연스럽게 읽혀야 한다.

## 웹 참고 기준

- MDN CSS Paged Media: `@page`, 판형, 여백, 좌우 페이지, 헤더/푸터, 페이지 분할 기준.
- MDN `@page`: margin at-rule과 페이지 번호/여백 박스 사용.
- Paged.js: HTML을 브라우저 기반 paged material로 만드는 접근.
- Vivliostyle: HTML+CSS 원고를 CLI로 PDF 조판하는 접근과 preview/build 루프.
- W3C paged media task note: 러닝 헤더/푸터, 책 제목/장 제목/페이지 번호 배치.
- Reedsy/Scribe/Jane Friedman: 논픽션 장은 독자의 핵심 질문, hook, thesis, evidence, advice, segue가 이어져야 한다.

## 새 판의 설계 원칙

1. 목차는 "저자 서사 → 강의가 책이 되는 이유 → SPARK IPO → 바이브코딩 핵심 → 대규모 강의 운영 → 회사 AX → 슬라이드/노트 집필법 → HTML 출판 루프"로 재정렬한다.
2. 각 장은 이전 장에서 남긴 질문을 받아 시작하고, 다음 장의 필요성을 만들며 끝난다.
3. 각 절은 bullet이 아니라 줄글 중심으로 쓴다. 단, 독자 행동을 정리하는 짧은 문장만 보조적으로 쓴다.
4. PPT 이미지는 장식이 아니라 장면 증거로 쓰고, 캡션에 로컬 PPT 출처를 둔다.
5. PDF footer에는 현재 장의 로컬 출처를 표기한다.
6. 웹 자료는 새 API/스크래핑 데이터가 아니라 제작 방식 참고 자료로만 사용한다.

## 진행 기록

- [x] 기존 산출물과 스크립트 점검.
- [x] 웹 참고 자료 확인.
- [x] 기존 원고의 반복 문장틀 문제 확인: 동일 문장 패턴 648회.
- [x] 연결형 새 목차/리포트/원고/HTML/PDF 생성.
- [x] HTML/PDF 렌더 검수.
- [x] 검수 후 CSS/원고 수정.
- [x] 최종 산출물 경로와 검증 결과 기록.

## 최종 산출물

- 요청 리포트: `data/vibecoding-book/connected-rewrite-2026-05-27/request-report-connected.md`
- 웹 참고 리서치: `data/vibecoding-book/connected-rewrite-2026-05-27/web-writing-research.md`
- 연결형 확장 목차: `data/vibecoding-book/connected-rewrite-2026-05-27/expanded-toc-connected.md`
- 원고 Markdown: `data/vibecoding-book/connected-rewrite-2026-05-27/malaka-vibecoding-connected-book.md`
- HTML: `data/vibecoding-book/connected-rewrite-2026-05-27/malaka-vibecoding-connected-book.html`
- PDF: `data/vibecoding-book/connected-rewrite-2026-05-27/malaka-vibecoding-connected-book.pdf`
- 렌더 검수: `data/vibecoding-book/connected-rewrite-2026-05-27/render-review.md`

## 검증 결과

- PDF 페이지 수: 334쪽 (`pdfinfo`)
- 구성: 31장, 155절, PPT 이미지 18개
- footer 출처: `pdftotext` 샘플에서 `출처:` 확인
- HTML 렌더: 로컬 HTTP 서버로 Browser 확인
- PDF 샘플 렌더: 1, 8, 45, 220쪽 PNG 확인
- 수정 반영: 표지 제목/부제 음절 단위 줄바꿈 문제 수정
- 수정 반영: 반복 접속문 변주 추가
- 기존 원고 반복 문장틀 누수: 없음 (`rg` 확인)
- raw metadata 누수: 없음 (`rg` 확인)
