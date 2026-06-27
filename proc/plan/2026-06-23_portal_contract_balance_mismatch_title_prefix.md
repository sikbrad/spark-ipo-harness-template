# 포탈 계약잔액미일치 타이틀 prefix 적용

작성일: 2026-06-23

## 범위

- 피드백: `cmqp3vyhz00ba4blh4vguz0wg`
- 사용자 요청: 계약 타이틀에 요청 prefix 적용
- prefix: `[계약잔액미일치] `
- 대상 필드: prod `Contract.contractName`
- 제외: 계약 잔액, 다우 PKG 잔액, 주문/계약 연결, 피드백 상태 변경

## 판단

- 기존 Teams 지시와 과거 산출물 기준 prefix는 `[계약잔액미일치]`이다.
- 기존 30건 중 현재 prod에서 prefix가 빠진 계약은 `Sales11804`, `Sales19534` 2건이다.
- 이번 피드백 대상 PKG 계약은 `Sales12069`이고, 현재 제목은 suffix 형태의 `잔액 미일치` 문구만 있어 prefix로 통일한다.

## 실행 계획

1. prod에서 대상 3건 현재 제목을 백업한다.
2. prefix가 이미 있으면 건너뛰는 idempotent 업데이트를 실행한다.
3. 업데이트 후 3건 제목이 `[계약잔액미일치]`로 시작하는지 재조회한다.
4. 산출물은 `output/portal-contract-title-prefix-20260623/`에 저장한다.

## 롤백

필요 시 백업한 `before` 제목으로 동일 `uk` 3건만 되돌린다.
