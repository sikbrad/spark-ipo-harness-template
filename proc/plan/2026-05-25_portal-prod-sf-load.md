# Portal prod SF load and schema sync

## 목표

Prod DB를 백업한 뒤 기존 prod 데이터를 reset/delete 하지 않고 Salesforce 데이터만 prod DB에 적재한다.
부가로 A(local DB)와 E(portal-data Prisma schema)의 schema-only 최신화 결과도 같은 작업 흐름에 기록한다.

## 작업 항목

- [x] A(local DB) schema를 D(web Prisma schema) 기준으로 업데이트
- [x] E(portal-data Prisma schema)를 최신 DB schema에서 pull
- [x] Prod DB full dump 생성
- [x] `load:sf:full`과 `load:sf:db` 차이 확인
- [x] Reset 없는 SF loader만 prod에 실행
- [x] Prod 적재 전후 row count 검증
- [x] SF load 후 현재 prod 상태 dump 생성
- [x] 05:30 nightly maintenance 파이프라인 prod 수동 실행
- [x] Maintenance 후 현재 prod 상태 dump 생성
- [x] 실행 결과와 리스크 기록

## 실행 기록

### A/E schema-only update

요청: A(local DB)와 E(portal-data Prisma schema)의 schema만 업데이트. 데이터 갱신은 범위 밖.

실행:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az
bun run --cwd apps/server db:push

cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
DATABASE_URL='postgresql://...local.../dof_portal' npm run pull:schema
```

검증:

- A local DB: 45 tables / 677 columns
- D web Prisma schema: 45 models / 677 scalar columns
- E portal-data Prisma schema: 45 models / 677 scalar columns
- A/D/E pairwise table/column diff: 0

주의:

- 사용자가 데이터는 괜찮다고 정정하기 전에 로컬 SF load와 FG post-load가 일부 실행됐다.
- 이후 FG scrape 프로세스는 종료했고, 추가 데이터 갱신은 진행하지 않았다.

### Prod dump

요청: prod DB dump 생성 후 SF 데이터 적재.

실행:

```bash
pg_dump "$PROD_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/db-dumps/prod-before-sf-load-20260525_130829.dump
```

결과:

- Dump path: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/db-dumps/prod-before-sf-load-20260525_130829.dump`
- Size: 35MB
- Format: PostgreSQL custom archive
- `pg_restore --list` 확인 완료
- Source database: `dof_portal_prod`
- Dumped from PostgreSQL 17.7
- Dumped by `pg_dump` 18.3
- Note: 이 파일은 생성 직후 검증했으나, 최종 파일시스템 확인 시에는 `proc/db-dumps/`에 남아 있지 않았다. 현재 보존된 기준 dump는 아래 `prod-after-sf-load-maintenance-20260525_132106.dump`다.

### SF loader selection

`package.json` 확인 결과:

```json
{
  "load:sf:db": "tsx src/loaders/sf-crm/index.ts",
  "load:sf:full": "tsx src/scripts/reset-sf-data.ts && tsx src/loaders/sf-crm/index.ts"
}
```

판단:

- `load:sf:full`은 먼저 `reset-sf-data.ts`를 실행하므로 prod에는 부적합.
- `load:sf:db`는 reset 없이 SF loader만 실행하므로 이번 요구사항에 맞음.

사용한 명령:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
DATABASE_URL='postgresql://...prod.../dof_portal_prod' npm run load:sf:db
```

사용하지 않은 명령:

```bash
npm run load:sf:full
tsx src/scripts/reset-sf-data.ts
```

## Prod row count 검증

### 적재 전

| Table | Count |
| --- | ---: |
| Asset | 1,605 |
| AssetHistory | 1,656 |
| Company | 2,970 |
| CompanyShippingAddress | 1,280 |
| Contract | 350 |
| Customer | 976 |
| Hashtag | 148 |
| Order | 6,380 |
| OrderCollection | 6,127 |
| OrderConsolidatedShipment | 933 |
| OrderProduct | 23,807 |
| OrderRecovery | 297 |
| Product | 4,234 |
| Quotation | 339 |
| User | 70 |

### 적재 후

| Table | Count |
| --- | ---: |
| Asset | 13,848 |
| AssetHistory | 11,709 |
| Company | 3,289 |
| CompanyShippingAddress | 9,156 |
| Contract | 994 |
| Customer | 2,477 |
| Hashtag | 1,502 |
| Order | 26,127 |
| OrderCollection | 33,697 |
| OrderConsolidatedShipment | 3,749 |
| OrderProduct | 95,359 |
| OrderRecovery | 3,204 |
| Product | 4,967 |
| Quotation | 15,783 |
| User | 112 |

### `importSource='sf'` / `source='sf'` 확인

| Table | SF count |
| --- | ---: |
| User | 42 |
| Product | 733 |
| Company | 319 |
| Customer | 1,501 |
| Order | 19,747 |
| Contract | 644 |
| Quotation | 15,444 |
| CompanyShippingAddress | 7,876 |
| OrderProduct | 71,552 |
| OrderCollection | 27,570 |
| OrderRecovery | 2,907 |
| Asset | 12,243 |
| AssetHistory | 10,053 |
| Hashtag | 1,354 |

## SF loader result summary

Load ID: `sf-load-20260525-130902`

| Phase | Source | Loaded | Skipped |
| --- | ---: | ---: | ---: |
| User | 58 | 42 | 0 |
| Product | 975 | 733 | 79 |
| Company | 1,822 | 1,129 | 0 |
| Customer | 2,062 | 2,045 | 17 |
| Order | 19,747 | 19,747 | 0 |
| Contract | 644 | 644 | 0 |
| Quotation | 15,444 | 15,444 | 0 |
| CompanyShippingAddress | 21,569 | 7,876 | 0 |
| OrderConsolidatedShipment | 19,747 | 2,816 | 0 |
| OrderProduct | 71,643 | 71,552 | 91 |
| OrderCollection | 34,051 | 27,570 | 6,481 |
| OrderRecovery | 2,907 | 2,907 | 0 |
| Asset | 12,503 | 12,243 | 43 |

Total runtime: 217.6 seconds.

Mapping report saved at:

```text
/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/logs/sf-mapping-failures-summary.json
```

Notable mapping report items:

- `order.paymentTerms.fallbackOther`: 8,769
- `customer.dedupe.tier2.phoneName`: 483
- `companyMatcher.missing.sfOnly`: 319
- `companyMatcher.confidence.low`: 49
- `customer.unknownAccountId`: 17
- `collection.currency.fallback`: 2

### Post-load prod dump

SF load 완료 후 현재 prod 상태도 별도 dump로 저장했다.

실행:

```bash
pg_dump "$PROD_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/db-dumps/prod-after-sf-load-20260525_131440.dump
```

결과:

- Dump path: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/db-dumps/prod-after-sf-load-20260525_131440.dump`
- Size: 50MB
- Format: PostgreSQL custom archive
- `pg_restore --list` 확인 완료
- Archive created at: 2026-05-25 13:14:40 KST
- Source database: `dof_portal_prod`
- Dumped from PostgreSQL 17.7
- Dumped by `pg_dump` 18.3
- Note: 이 파일은 생성 직후 검증했으나, maintenance 실행 후 최종 파일시스템 확인 시에는 `proc/db-dumps/`에 남아 있지 않았다. 현재 보존된 기준 dump는 아래 `prod-after-sf-load-maintenance-20260525_132106.dump`다.

### Nightly maintenance manual run

사용자가 언급한 "5:30 cron"은 OS crontab이 아니라 앱 내부 Nest scheduler다.

근거:

- `apps/server/src/maintenance/maintenance.scheduler.ts`
- `@Cron('30 5 * * *', { name: 'nightly-maintenance', timeZone: 'Asia/Seoul' })`

정의된 실행 흐름:

1. AUTO 백업 생성
2. `recalc-collection-status`
3. `delayed-collection-transition`
4. `recalc-receivables`
5. `contract-expiration-check`
6. `erp-closing-sync`

수동 실행:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/apps/server
DATABASE_URL='postgresql://...prod.../dof_portal_prod' \
  bun --env-file=../../.env -e "import { NestFactory } from '@nestjs/core'; import { AppModule } from './src/app.module'; import { MaintenanceService } from './src/maintenance/maintenance.service'; const app = await NestFactory.createApplicationContext(AppModule, { logger: ['log','error','warn'] }); try { const svc = app.get(MaintenanceService); await svc.runNightlyPipeline(); } finally { await app.close(); }"
```

결과:

- AUTO 백업: 실패
  - 원인: `AdminDataService` 내부 백업 구현이 `docker exec dof-postgres pg_dump -h localhost -p 5432 -U dofax -d dof_portal_prod` 형태로 로컬 Docker 컨테이너를 바라봄.
  - 실패 메시지: `FATAL: role "dofax" does not exist`
  - 영향: `MaintenanceService` 설계상 백업 실패는 task 실행을 막지 않음. 별도 prod `pg_dump`는 이미 생성되어 있었음.
- `recalc-collection-status`: 성공
  - scanned: 33,434
  - drift: 1,272
  - updated: 1,272
- `delayed-collection-transition`: 성공
  - matched: 0
  - updated: 0
- `recalc-receivables`: 성공
  - reset: 0
  - recalc: 24,281
  - changed: 632
  - netDelta: 1,310,980,706.56
  - absDelta: 1,322,686,706.56
  - AuditLog: 632건 기록
- `contract-expiration-check`: 성공
  - matched: 51
  - updated: 51
- `erp-closing-sync`: 성공
  - 조회 기간: 20260518 ~ 20260525
  - ERP 조회 결과: 56
  - processed: 0
  - updated: 0
  - skipped: 0
  - errors: 0
- Total runtime: 6,952ms

### Post-maintenance prod dump

Nightly maintenance 수동 실행 후 현재 prod 상태를 다시 dump로 저장했다.

실행:

```bash
pg_dump "$PROD_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/db-dumps/prod-after-sf-load-maintenance-20260525_132106.dump
```

결과:

- Dump path: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/db-dumps/prod-after-sf-load-maintenance-20260525_132106.dump`
- Size: 50MB
- Format: PostgreSQL custom archive
- `pg_restore --list` 확인 완료
- Archive created at: 2026-05-25 13:21:06 KST
- Source database: `dof_portal_prod`
- Dumped from PostgreSQL 17.7
- Dumped by `pg_dump` 18.3

## 리스크 / 주의사항

- `load:sf:db`는 reset은 하지 않지만 upsert/보강 로더다. 기존 prod row 중 매칭되는 행은 일부 업데이트될 수 있다.
- 이번 로그에서 `Company enrich: 1503건 NULL 보강`, `Customer note갱신=544`가 있었다.
- `Quotation` 단계가 prod RDS에서 가장 오래 걸렸다. 원인은 다수의 `Order.quotationUk` 백링크 업데이트였고, `pg_stat_activity` 확인 당시 lock 대기 상태는 아니었다.
- 앱 내부 AUTO 백업은 prod URL 수동 주입 상황에서 로컬 Docker `dof-postgres`를 바라봐 실패했다. 운영 prod 백업으로는 본 문서의 명시적 `pg_dump` 파일들을 기준으로 삼는다.
- 현재 파일시스템에 보존된 prod dump는 `prod-after-sf-load-maintenance-20260525_132106.dump`이며 git untracked 상태다.
