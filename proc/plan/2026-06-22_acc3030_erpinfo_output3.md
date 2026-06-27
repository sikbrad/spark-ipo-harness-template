# ACC3030 ERP정보 output-3 적재

## 목표
기존 거래원장/ACC3030 규칙을 변경하지 않고, 확인 가능한 ACC3030 결과를 기준으로 포털 로컬 DB의 `erpInfo` JSON을 최대한 추정 적재한다.

## 작업 항목
- [x] ACC3030 기존 규칙과 사용 가능한 산출물 확인
- [x] output-3 작업 디렉터리와 로컬 DB 대상 확인
- [x] ACC3030 row 정규화 및 Company/Order/OrderCollection 매칭
- [x] 적재 전 백업, 로컬 DB 업데이트, read-back 검증
- [x] output-3에 요약/미매칭/검증 결과 저장

## 주의
- `proc/spec`는 수정하지 않는다.
- 기존 `erpInfo` 스키마 초안(`source`, `schemaVersion`, `match`, `ledgerRows`)을 따른다.
- 직접 확정할 수 없는 매칭은 confidence와 근거를 남기고 과도하게 확정하지 않는다.

## 결과
- 작업 루트: `output-3/acc3030-erpinfo-20260622/`
- 주문/수금: 기존 `backfill-erp-info.ts`를 `output-3` 경로로 재실행했다. 현재 로컬 DB에는 이미 반영된 상태라 이번 apply의 신규 업데이트는 주문 0건, 수금 0건이다.
- 고객사: Track B ACC3030 full-history 기준으로 `Company.erpId = ACC3030.trCd`가 맞는 1,324개 `Company.erpInfo`를 신규 적재했다.
- 검증: `readback-verification.md/json` 기준 `Company.erpInfo` 1,324건, `Order.erpInfo` 10,566건, `OrderCollection.erpInfo` 16,429건이 모두 JSON object다.
- 전체 ACC3030 normalized row는 `company-apply/acc3030-normalized-transactions.jsonl`에 보존했다.
