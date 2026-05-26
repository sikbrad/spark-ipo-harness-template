# Portal order status correction to 실주

## 목표

Prod, test/dev, local Portal DB에서 지정된 15개 Sales 주문의 `Order.status`를 모두 `CLOSED_LOST`(화면 라벨: 실주)로 변경한다.
각 주문별 SF stage, 포탈 주문 상태, 물류/도착 근거를 확인해 `Release / Installation` 또는 도착 완료 정황이 있는 경우 보고서에 별도 표시한다.

## 작업 항목

- [x] 대상 상태 코드와 SF stage 매핑 규칙 확인
- [x] Prod/test/local DB 연결과 대상 주문 존재 여부 확인
- [x] 변경 전 대상 주문 스냅샷 저장
- [x] 주문별 SF 원천/물류/도착 근거 검토
- [x] Prod DB에서 대상 주문 상태를 실주로 변경
- [x] Test/dev DB에서 대상 주문 상태를 실주로 변경
- [x] Local DB에서 대상 주문 상태를 실주로 변경
- [x] 변경 후 검증 스냅샷 저장
- [x] 주문별 조사 보고서 작성

## 실행 기록

### 2026-05-26 시작

- 사용자 요청: 지정 Sales 주문 15건을 prod/test/local 모두 `실주`로 변경.
- 주의 조건: 실제 주문, 물류 발생, 도착까지 확인되는 건은 SF상 `Release / Installation`으로 `주문완료` 대상일 수 있으므로 주문별로 조사해 보고서에 남긴다. 다만 이번 작업의 실제 DB 매핑은 우선 모두 `실주`로 맞춘다.
- 코드 기준 확인:
  - Portal `OrderStatus.CLOSED_LOST`의 화면 라벨은 `실주`.
  - SF loader의 `mapSfStage()`는 `Release / Installation` 또는 `Closed Won`/`Contraction Complete`를 `COMPLETED`, `Closed Lost`를 `CLOSED_LOST`, `In Review`를 `APPROVAL_REQUESTED`로 매핑한다.

### 2026-05-26 변경 전 DB 스냅샷

- 대상 DB:
  - local: `.env` active `DATABASE_URL` (`localhost:54220/dof_portal`)
  - test/dev: `.env` active `DATABASE_URL_REMOTE` (`dof_portal_dev`)
  - prod: `.env` commented `DATABASE_URL_REMOTE` (`dof_portal_prod`)
- 대상 15건은 local/test-dev/prod 세 DB 모두 존재.
- 변경 전 상태는 세 DB 모두 15건 전부 `APPROVAL_REQUESTED`(팀장승인요청).
- 변경 전 스냅샷:
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/before-local.json`
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/before-dev.json`
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/before-prod.json`
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/before-summary.json`

### 2026-05-26 DB 상태 변경 실행

- 첫 실행 시도는 prod 15건을 먼저 커밋한 뒤, 다음 대상인 test/dev 연결에서 SSL 옵션 mismatch로 중단됐다. 이때 prod는 이미 `CLOSED_LOST`로 변경 완료.
- SSL fallback을 적용해 prod -> test/dev -> local 순서로 재실행했다. 재실행 시 prod는 이미 `CLOSED_LOST`였고, test/dev 및 local은 `APPROVAL_REQUESTED`에서 `CLOSED_LOST`로 변경됐다.
- SQL 변경 범위: `Order.status = 'CLOSED_LOST'::"OrderStatus"`, `updatedAt = now()` only.
- 각 DB 트랜잭션에서 대상 주문 15건 존재 확인 후 업데이트했고, 업데이트 row count가 15가 아니면 rollback하도록 실행했다.
- 실행 결과:
  - prod: 15건 `CLOSED_LOST`
  - test/dev: 15건 `CLOSED_LOST`
  - local: 15건 `CLOSED_LOST`
- 실행 결과 파일: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/update-result.json`
- 변경 후 검증 스냅샷:
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/after-local.json`
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/after-dev.json`
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/after-prod.json`
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-order-status-correction-20260526/after-summary.json`

### 2026-05-26 주문별 조사 보고서

- 보고서 작성: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/30_research/report/2026-05-26_order-status-real-order-review.md`
- SF 원천 `opportunities.jsonl` 기준 15건 모두 `StageName = In review`.
- SF `assets.jsonl` 기준 `InstallDate`가 있는 `주문완료` 후보:
  - Sales19672: asset 10건, InstallDate `2025. 7. 1`
  - Sales19814: asset 2건, InstallDate `2025. 6. 18`, `2025. 6. 20`
  - Sales18548: asset 1건, InstallDate `2025. 6. 27`
  - Sales20124: asset 1건, InstallDate `2025. 6. 26`
  - Sales19767: asset 1건, InstallDate `2025. 6. 4`
- 이번 DB 상태는 사용자 지시대로 위 후보를 포함해 모두 `실주`(`CLOSED_LOST`)로 유지.
