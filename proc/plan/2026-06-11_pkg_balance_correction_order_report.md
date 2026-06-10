# PKG 잔액보정 정정주문 리포트 계획

## 목표
`Sales15705`, `Sales13813`, `Sales14356`, `Sales14454`, `Sales14966`, `Sales16128`, `Sales11804`, `Sales19534`에 대해 잔액보정 정정주문을 넣는 가정에서 필요한 주문 생성 정보를 산출한다.

## 계산 기준
- 포탈 계약 잔액 산식: `Contract.totalAmount - SUM(Order.totalAmount)`; 주문 상태는 `APPROVAL_REQUESTED` 이상만 반영된다.
- 목표 잔액: 다우 전체상태 재스크랩 `20260610T_contract_amount_all_status/all-package-contracts.jsonl`에서 같은 Sales 번호와 파생 번호(`-1`, `-2`)를 합산한 PKG 잔액.
- 보정 주문 금액: `현재 포탈 계산잔액 - 목표 다우 잔액`.
- 보정 제품: `DOF-PKG-Balance` / `Promotion PKG 잔액 이관`.

## 진행
- [x] 계약 잔액 계산 코드 확인
- [x] 보정용 제품 마스터 확인
- [x] 기존 `DOF-PKG-Balance` 주문 사용 패턴 확인
- [x] 8개 Sales의 현재 계약잔액, 다우 목표잔액, 보정 주문 금액 산출
- [x] 주문 생성용 필드/라인 금액 리포트 작성

## 산출물
- `proc/research/2026-06-11_pkg_balance_correction_order_report.md`
