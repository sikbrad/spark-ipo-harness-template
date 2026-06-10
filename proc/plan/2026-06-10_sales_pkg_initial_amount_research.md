# Sales PKG 초기 계약금 리서치

## 목표
`Sales15705`, `Sales13813`, `Sales14356`, `Sales14454`, `Sales14966`, `Sales16128`, `Sales11804`, `Sales19534`의 계약 시초가를 가능한 근거를 모두 모아 추정한다.

## 범위
- 로컬 workspace 전체 검색: startpoint 기록, 포탈 산출물, 거래원장 산출물
- 포탈/SF 기반 계약금: 기존 v3/v6 Sales PKG 백필 산출물과 DB 원천
- 다우/위하고/FG/PKG 원장: 다우 패키지 원장(`접수` + `출고완료` 전체상태), ACC3030 회계 원장, portal-ledger 산출물
- 필요 시 Salesforce/Amaranth 라이브 조회로 부족한 제품 라인 근거 보강

## 진행
- [x] startpoint workspace와 관련 repo 산출물에서 8개 Sales 번호 검색
- [x] 기존 `sf-vs-daou-initial-amount-*`, `amaranth-inference-v5*`, `active-diff-30-package-usage.json` 확인
- [x] 포탈 DB/백필 산출물에서 source 주문 제품 라인과 계약상품 산정 근거 추출
- [x] ACC3030/거래원장 산출물에서 각 Sales 번호 관련 회계 row 요약
- [x] Salesforce live 조회 대신 포탈 DB의 `importSource=sf` 원 주문/라인아이템과 계약상품 산정 note로 SF 근거 대체
- [x] 다우 패키지 원장을 `20260610T_contract_amount_all_status`로 재스크랩하고 `접수` 128건 + `출고완료` 386건 전체상태 기준으로 재집계
- [x] 다우 파생 Sales 번호(`SalesNNNNN-1`, `SalesNNNNN-2`)를 포함해 계약금 후보 재산정
- [x] 최종 추정 표와 근거/확신도/확인필요 항목 작성

## 현재 판단 메모
- `접수`만 보면 다우 PKG 금액이 과소 집계되는 건이 있다. `출고완료`와 파생 Sales 번호를 포함하면 `Sales13813`, `Sales14356`, `Sales14454`, `Sales14966`은 포탈/SF와 계약금 합계가 일치한다.
- 실제 계약금 차이가 남는 건은 `Sales15705`, `Sales16128`, `Sales11804`, `Sales19534` 중심이다.
- `Sales11804`는 ACC3030 직접 hit가 없어 확신도가 낮다.
- `Sales13813`, `Sales14454`, `Sales16128`, `Sales19534`는 사용행까지 존재하므로 초기금액 차이와 사용액/상태 처리 차이를 분리해야 한다.
- 최종 문서: `proc/research/2026-06-10_sales_pkg_initial_amount_research.md`
