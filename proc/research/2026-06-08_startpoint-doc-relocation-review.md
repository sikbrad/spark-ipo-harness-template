# dof-work-startpoint-04 plan/research 문서 위치 재검토

작성일: 2026-06-08 KST

## 목적

`dof-work-startpoint-04`의 `proc/plan`, `proc/research` 문서 중 실제 기록 소유권이 다른 SPARK/IPO 프로젝트에 더 가까운 항목을 식별한다.

초기 검토는 **실행 전 리서치**로 작성했다. 이후 2026-06-08에 강한 후보 38개를 이동했고, 단일 이동이 부적절한 항목은 cross-link 문서로 처리했다.

실행 결과 문서: `proc/plan/2026-06-08_startpoint-doc-relocation-execution.md`

## 검토 범위

- 현재 프로젝트:
  - `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/proc/plan`
  - `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/proc/research`
- 주변 SPARK/IPO 프로젝트:
  - `/Users/gq/works/projs/**/proc/{plan,research,30_research,50_plan}`
  - 보조 확인: `/Users/gq/works/lecture/**/proc/{plan,research}`
- 제외:
  - `proc/archive/`는 프로젝트 규칙상 열람하지 않았다.
  - 1차 검토 시점에는 실제 재배치 작업을 하지 않았고, 이후 별도 실행 단계에서 이동했다.

## 실행 결과

2026-06-08 실행 단계에서 다음과 같이 정리했다.

| 대상 | 처리 |
|---|---:|
| `dof-order-web-3-az` | 실파일 22개 이동, cross-link 3개 추가 |
| `dofing-order-portal-data-3-az` | 실파일 4개 이동 |
| `portal-ledger-invoice-gen-and-send` | 실파일 2개 이동, cross-link 1개 추가 |
| `hong-ledger-and-packages-02` | 실파일 1개 이동, cross-link 1개 추가 |
| `vibe-coding-book-writing-01` | 실파일 8개 이동 |
| `kubit-bitbot-slack-01` | 실파일 1개 이동, cross-link 1개 추가 |

실파일 이동 합계는 38개다. 이 중 Markdown 문서는 35개, 포털 연락처 변경 보조 Python 스크립트는 3개다.

원본을 유지한 부분 소유권 문서는 `proc/plan/2026-05-11_amaranth-split-acc-vs-nonacc.md`, `proc/plan/2026-05-26_routine-skills.md` 두 개다. 해외/국내 치과 잠재고객, Teams 개인 백업/업무 아바타 문서는 이동하지 않았다.

2026-06-09 2차 검토에서 6개를 추가 이동했다. 실행 문서는 `proc/plan/2026-06-09_startpoint-doc-relocation-pass2.md`다.

| 추가 대상 | 처리 |
|---|---:|
| `dof-order-web-3-az` | 포털/고객지원/물류 리서치 5개 이동 |
| `dental-tech-list-downloader` | 국내 치과기공소 인허가/Outline 리포트 계획 1개 이동 |

1차+2차 누적 실파일 이동 합계는 44개다.

2026-06-09 3차 재검토에서는 추가 이동 대상이 없다고 판단했다. 실행 문서는 `proc/plan/2026-06-09_startpoint-doc-relocation-pass3.md`다. Teams 인물/아바타, routine, 외부 서비스 스킬, Outline 영업 리포트, Confluence AX reorg, Android SMS 리서치는 현재 startpoint-04에 남기는 편이 맞다.

## 판단 기준

다음 조건이 강할수록 startpoint-04보다 다른 프로젝트가 맞다.

1. 문서가 특정 제품 repo의 코드, DB, 배포, 운영 장애, 스키마, 테스트 결과를 직접 기록한다.
2. 문서 본문에 대상 repo의 절대 경로가 명시되어 있다.
3. 실제 산출물과 검증 파일이 대상 repo의 `output/`, `proc/30_research`, `proc/50_plan`, `scripts/`에 있다.
4. 대상 repo 안에 이미 같은 주제의 후속 문서가 존재한다.
5. startpoint-04는 실행 허브 또는 개인/범용 API 스킬 허브 역할만 했다.

반대로 다음은 현 위치 유지가 자연스럽다.

- Gmail, Notion, Raindrop, ChatGPT, Teams 개인 백업, Daily/Night routine처럼 개인 업무 운영 데이터가 startpoint-04의 `data/`와 `proc/lib`를 중심으로 돌아가는 경우.
- 여러 외부 서비스 스킬 자체를 설계한 문서.
- 대상 repo가 없고 startpoint-04의 출력 디렉터리가 사실상 canonical인 일회성 조사.

## 강한 재배치 후보

### 1. 포털 웹/운영 문서 -> `dof-order-web-3-az`

대상:

`/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az`

근거:

- 포털 repo는 자체 `proc/10_spec`, `proc/30_research`, `proc/50_plan` 구조를 이미 가진다.
- startpoint-04의 포털 문서 다수는 본문에서 `dof-order-web-3-az`를 직접 대상 저장소로 지정한다.
- 일부 주제는 이미 포털 repo 안에 후속 문서가 있다. 예: 고객사 좌표, C00354, 504, Sales-prefix PKG 계약, 그룹 멘션.

권장 원칙:

- 제품 기능/운영 runbook/장애 분석/DB 변경 계획은 포털 repo의 `proc/50_plan/tasks` 또는 `proc/50_plan/features`, 분석 결과는 `proc/30_research/{analysis,operation,report}` 쪽으로 병합한다.
- startpoint-04에는 필요하면 "작업 실행 허브에서 수행했음" 정도의 얇은 색인만 남긴다.

강한 후보 문서:

| 현재 파일 | 권장 대상 | 판단 |
|---|---|---|
| `proc/plan/2026-05-25_portal-db-state-refresh.md` | `dof-order-web-3-az/proc/30_research/operation` 또는 `proc/50_plan/tasks` | local/dev/prod DB, web schema, prod dump, ApiToken 보존 절차를 다룬 포털 DB 운영 기록이다. |
| `proc/research/2026-05-25_portal-db-schema-state.md` | `dof-order-web-3-az/proc/30_research/operation` | 포털 DB/Prisma schema parity와 재실행 절차가 핵심이다. `dofing-order-portal-data-3-az` schema도 포함하므로 그쪽에는 cross-link가 적절하다. |
| `proc/plan/2026-05-25_portal-prod-sf-load.md` | 1차 `dofing-order-portal-data-3-az`, 2차 `dof-order-web-3-az/proc/50_plan/tasks` | SF loader 실행은 portal-data 책임이고, prod DB dump/maintenance 검증은 web 운영 책임이다. 단일 이동보다 분할/상호 링크가 안전하다. |
| `proc/plan/2026-05-25_portal-prod-contact-update.md` | `dof-order-web-3-az/proc/50_plan/tasks` | prod `Company` 연락처 변경, schema/API/front 변경, prod dump, SQL 적용 검증이 모두 포털 제품 기록이다. |
| `proc/plan/2026-05-25_portal_contact_update_analyze.py` | `dof-order-web-3-az`의 작업용 script 또는 해당 task 산출물 폴더 | 문서는 아니지만 포털 연락처 업데이트 전용 분석 스크립트다. 현재 `proc/plan`에 남아 있는 것은 위치가 어색하다. |
| `proc/plan/2026-05-25_portal_contact_update_prepare.py` | 동일 | 포털 연락처 업데이트 SQL 생성 스크립트다. |
| `proc/plan/2026-05-25_portal_contact_update_prepare_holds.py` | 동일 | 보류건 후속 적용 준비 스크립트다. |
| `proc/plan/2026-05-26_portal-company-missing-country.md` | `dof-order-web-3-az/proc/30_research/report` 또는 `proc/50_plan/tasks` | 포털 prod 고객사 `Company.country` 감사 결과이며 대상 repo의 report/output을 직접 가리킨다. |
| `proc/plan/2026-05-26_missing-company-country-web-research.md` | `dof-order-web-3-az/proc/30_research/report` | 419개 고객사 국가 조사 산출물이 포털 repo output에 저장되어 있다. |
| `proc/research/2026-05-26_portal-company-country-missing-research.md` | `dof-order-web-3-az/proc/30_research/report` | 위 조사 결과 보고서다. |
| `proc/plan/2026-05-28_portal-company-country-code-update.md` | `dof-order-web-3-az/proc/50_plan/tasks` | prod 국가코드/통화 보정, AuditLog, 덤프, Teams 보고까지 포함하는 포털 운영 변경 기록이다. |
| `proc/plan/2026-05-26_portal-order-status-real-order.md` | `dof-order-web-3-az/proc/50_plan/tasks` | local/dev/prod 주문 상태 직접 보정과 검증 파일이 모두 포털 repo output에 있다. |
| `proc/plan/2026-05-28_portal-order-status-label-rename.md` | `dof-order-web-3-az/proc/50_plan/features` | 포털 코드/명세/테스트를 실제 수정한 표시 라벨 변경 기록이다. |
| `proc/plan/2026-05-28_portal-product-code-exact-match-highlight.md` | `dof-order-web-3-az/proc/50_plan/features` | `ListPageLayout`, 주문 목록 검색 UI, Playwright 검증 등 포털 기능 구현 기록이다. |
| `proc/plan/2026-05-28_portal-cancelled-order-change-rules.md` | `dof-order-web-3-az/proc/50_plan/features` | 주문취소 권한/상태/감사로그 설계 대상이 포털 명세다. |
| `proc/research/2026-05-28_portal-cancelled-order-change-rules.md` | `dof-order-web-3-az/proc/30_research/analysis` | 포털 권한/업무규칙 리서치이며 포털 내부 인터뷰 규칙 문서를 근거로 든다. |
| `proc/plan/2026-05-28_portal-release-ops.md` | `dof-order-web-3-az/proc/50_plan/tasks` | master push, prod notice, release note, prod dump, Teams follow-up까지 포함하는 포털 release ops 기록이다. |
| `proc/plan/2026-06-02_portal-v1.2.2-release-notice.md` | `dof-order-web-3-az/proc/50_plan/tasks` | 포털 `v1.2.1..v1.2.2` 릴리즈 공지 작성 기록이다. |
| `proc/plan/2026-05-31_portal-company-coordinates-osm.md` | `dof-order-web-3-az/proc/50_plan/features` | 고객사 좌표/PostGIS/deck.gl 지도 구현과 DB 백필 기록이다. 대상 repo에는 이미 `proc/50_plan/features/2026-05-31_company-coordinate-osm-map.md`와 관련 research가 있으므로 병합 대상이다. |
| `proc/plan/2026-06-02_portal-group-mention-targets.md` | `dof-order-web-3-az/proc/50_plan/features` | 채터/할일 댓글 그룹 멘션 기능 구현 기록이다. 대상 repo에는 `2026-06-05_mention-groups.md`가 있어 병합/대조가 필요하다. |
| `proc/plan/2026-06-03_portal-shipping-api-provider-research.md` | `dof-order-web-3-az/proc/50_plan/features` 또는 `proc/30_research/analysis` | 포털 주문 배송량과 `shipping-status` 코드 구조를 기준으로 한 API 업체 조사 계획이다. |
| `proc/research/2026-06-04_portal-shipping-api-provider-research.md` | `dof-order-web-3-az/proc/30_research/analysis` | 포털 prod DB shipping volume과 포털 shipping-status service를 근거로 한 제품 의사결정 문서다. |
| `proc/research/2026-06-05_portal-504-gateway-timeout-report.md` | `dof-order-web-3-az/proc/30_research/operation` | 운영 장애 리포트다. 대상 repo에는 이미 `proc/30_research/operation/2026-06-05_portal-doflab-504-incident.md`가 있으므로 단순 이동보다 diff 병합 후보다. |

### 2. 포털 데이터 로더/SF 적재 문서 -> `dofing-order-portal-data-3-az`

대상:

`/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az`

근거:

- 이 repo는 SF/FG 데이터 scrape/load와 포털 DB 적재 로더 책임을 가진다.
- startpoint-04의 일부 문서는 포털 web DB 상태도 다루지만, 결정적인 구현 책임이 `src/loaders/sf-crm` 또는 `plans/sf/loading`에 있다.

강한 후보:

| 현재 파일 | 권장 대상 | 판단 |
|---|---|---|
| `proc/research/2026-06-02_pkg-sales-prefix-contract-portal-research.md` | 1차 `dofing-order-portal-data-3-az/proc/research` 또는 `plans/sf/loading/reports`, 2차 web/ledger cross-link | Sales-prefix PKG 합성 계약을 포털 `Contract`로 만들지 여부를 SF loader/portal DB 관점에서 판정한다. 이후 포털 repo에는 `proc/50_plan/2026-06-03_pkg_contract_management.md`가 생겼으므로 함께 병합해야 한다. |
| `proc/plan/2026-05-25_portal-prod-sf-load.md` | `dofing-order-portal-data-3-az/plans/sf/loading/reports` | 실행 주체가 `load:sf:*`와 SF loader다. 단, prod DB dump와 maintenance 결과는 web repo에도 남겨야 한다. |
| `proc/plan/2026-05-26_contract-c00354-sf-missing-fields.md` | 1차 `dofing-order-portal-data-3-az/plans/sf/loading/reports`, 2차 web report cross-link | 원인은 `ActivatedDate`/`contractDate` 매핑 정책이다. 실제 브라우저 보정은 web 운영 기록이지만, 로더 정책 기록은 portal-data가 canonical이다. |
| `proc/research/2026-05-26_c00354_sf_missing_contract_date.md` | 동일 | 대상 repo에 `reports/2026-05-26-prod-contract-date-customer-backfill.md`가 있으므로 병합 후보다. |

### 3. 거래원장/청구서 문서 -> `portal-ledger-invoice-gen-and-send`

대상:

`/Users/gq/works/projs/dofing-order-app/order-invoicing/portal-ledger-invoice-gen-and-send`

근거:

- 문서가 직접 `src/renderer`, `src/builder/refactor`, `scripts/statement-build.ts` 등 해당 repo 소스 파일을 비교한다.
- startpoint-04는 실행 위치였을 뿐, 장기 보존되어야 할 설계/결정 기록은 거래원장 repo가 맞다.

강한 후보:

| 현재 파일 | 권장 대상 | 판단 |
|---|---|---|
| `proc/research/portal-ledger-renderer-comparison.md` | `portal-ledger-invoice-gen-and-send/proc/research` | 두 renderer path 비교가 전부 해당 repo의 source와 build script에 관한 내용이다. |
| `proc/plan/portal-ledger-legacy-removal-decision.md` | `portal-ledger-invoice-gen-and-send/proc/plan` | legacy renderer 삭제 여부 결정과 실제 dead-code 제거 결과가 해당 repo의 장기 의사결정 기록이다. |
| `proc/research/2026-06-02_pkg-sales-prefix-contract-portal-research.md` | 보조 cross-link | PKG sheet parsing과 `src/pkg/parsePkgSheet.js` 해석은 ledger repo 맥락도 강하다. 다만 주 의사결정은 portal-data/web 쪽이다. |

### 4. 회계 Amaranth 스킬 문서 -> `hong-ledger-and-packages-02`

대상:

`/Users/gq/works/projs/dofing-order-app/order-invoicing/hong-works/hong-ledger-and-packages-02`

근거:

- `proc/plan/2026-05-11_amaranth-split-acc-vs-nonacc.md` 자체가 "회계 -> B, 비회계 -> A"로 정리했다.
- 실제로 B에는 `amaranth-acc-*` skill과 `proc/lib/pwc_amaranth.py`, `pwc_amaranth_excel.py`가 존재한다.
- 현재 startpoint-04에도 회계 skill 복사본이 남아 있어 완전한 단일 소유권은 아직 정리되지 않았다.

후보:

| 현재 파일 | 권장 대상 | 판단 |
|---|---|---|
| `proc/plan/2026-05-09_amaranth-acc-skills.md` | `hong-ledger-and-packages-02/proc/plan` 또는 `proc/research` | ACC3010/3020/3030 회계 화면, 거래처원장, Excel builder 검증 기록은 ledger/accounting 프로젝트가 더 맞다. |
| `proc/plan/2026-05-11_amaranth-split-acc-vs-nonacc.md` | 양쪽에 색인 형태 유지 | 이 문서는 분리 결정 자체라 A/B 양쪽 모두에서 찾히는 것이 유용하다. 단일 이동보다 양쪽 README/plan에 얇은 참조를 두는 편이 안전하다. |

### 5. 바이브코딩 책 제작 문서 -> `vibe-coding-book-writing-01`

대상:

`/Users/gq/works/lecture/vibe-coding-book/vibe-coding-book-writing-01`

근거:

- 별도 SPARK/IPO 책 집필 프로젝트가 이미 있다.
- startpoint-04의 `data/vibecoding-book`가 원천 수집/생성 작업 공간으로 쓰였지만, 책 자체의 기획/원고/출판 결정은 전용 집필 프로젝트가 더 자연스럽다.

주의:

- 현재 전용 프로젝트에는 voice/transcribe 중심 문서만 있고, startpoint-04의 책 산출물과 generation script가 아직 옮겨져 있지 않은 것으로 보인다.
- 따라서 단순 이동 전에 output/data/source-ppts/scripts의 canonical 위치를 먼저 정해야 한다.

후보:

| 현재 파일 | 권장 대상 | 판단 |
|---|---|---|
| `proc/plan/2026-05-26_vibecoding-book-from-latest-ppts.md` | `vibe-coding-book-writing-01/proc/plan` | latest PPT와 Notion/Daily/ChatGPT를 읽어 책 원고와 출간계획을 만든 기록이다. |
| `proc/plan/2026-05-27_vibecoding-book-daily-note-rewrite.md` | 동일 | 책 재기획/재집필 흐름이다. |
| `proc/plan/2026-05-27_vibecoding-book-connected-rewrite.md` | 동일 | 책 구조/원고 결정 기록이다. |
| `proc/plan/2026-05-27_vibecoding-book-market-rewrite.md` | 동일 | 시장형 재구성/제목/독자 포지셔닝 결정이다. |
| `proc/plan/2026-05-28_vibecoding-book-skill-and-source-inventory.md` | 동일 또는 startpoint-04와 cross-link | skill/source inventory는 실행 허브 성격도 있어 양쪽 참조가 맞다. |
| `proc/plan/2026-05-30_vibecoding-story-topics-from-ppts.md` | 동일 | 이야기 꼭지/목차 원천으로 책 프로젝트 소유가 더 강하다. |
| `proc/plan/2026-05-30_ax-vibecoding-company-ipo-book.md` | 동일 | 책 원고 제작 계획이다. |
| `proc/plan/2026-05-31_ax-vibecoding-company-ipo-600p.md` | 동일 | 600쪽 판본 제작/검증 기록이다. |

### 6. KUBIT/Slack/강의 문서 -> KUBIT workspace

대상 후보:

- `/Users/gq/works/lecture/kubit/kubit-bitbot-slack-01`
- `/Users/gq/works/lecture/kubit/kubit-class01-present`

근거:

- KUBIT 프로젝트들은 자체 `proc/plan`, `proc/research`를 가진다.
- startpoint-04 문서 중 일부는 KUBIT 강의 산출물이나 KUBIT Slack posting workflow를 기록한다.

후보:

| 현재 파일 | 권장 대상 | 판단 |
|---|---|---|
| `proc/plan/2026-05-24_kubit-lec2-slack-summary.md` | 1차 `kubit-bitbot-slack-01/proc/plan`, 필요 시 강의 산출 프로젝트 cross-link | Slack 게시와 KUBIT 공유가 핵심이면 bitbot/slack repo가 맞다. PPT 원본 정리까지 포함하므로 강의 자료 repo와도 연결 필요하다. |
| `proc/plan/2026-05-26_routine-skills.md` 중 KUBIT Slack 수집 부분 | 현 위치 유지 + `kubit-bitbot-slack-01` cross-link | morning/night routine은 startpoint-04 소유지만, KUBIT Slack collector 구현/운영 노하우는 bitbot repo에 링크하는 편이 좋다. |

## 중간/애매한 후보

### 1. 해외/국내 치과 잠재고객, Outline 영업처후보 문서

관련 파일:

- `proc/plan/2026-05-30_dof_overseas_customer_prospecting.md`
- `proc/plan/2026-06-02_outline_existing_customer_enrichment.md`
- `proc/plan/2026-06-02_outline_prospect_enrichment.md`
- `proc/plan/2026-06-02_outline_today_added_prospect_enrichment.md`
- `proc/plan/2026-06-03_outline_middle_docs_update.md`
- `proc/plan/2026-06-03_overseas_dental_distributor_expansion_3000.md`
- `proc/plan/2026-06-08_domestic_dental_candidate_report_260607.md`

판단:

- 이 문서들은 포털 고객사 데이터를 일부 참조하지만, 본질은 영업처 후보 발굴/Outline publish/리포트 생성이다.
- `/Users/gq/works/projs/dental-analysis/dental-map-plotter`, `dental-tech-list-downloader`는 국내 치과 시설 지도/다운로드 프로젝트라서 해외 유통사/Outline 영업 리포트 전체를 담기에는 좁다.
- 현재로서는 startpoint-04가 canonical일 가능성이 크다.
- 다만 장기화될 경우 `dof-sales-prospecting` 같은 별도 SPARK/IPO 프로젝트로 분리하는 것이 더 맞다. 기존 프로젝트 중 강제 이동할 만한 곳은 뚜렷하지 않다.

### 2. Teams 개인 백업/업무 아바타 문서

관련 파일:

- `proc/plan/2026-05-15_teams-conversations-dump.md`
- `proc/research/teams_pending_2026-05-12.md`
- `proc/research/teams_pending_2026-05-12.py`
- `proc/plan/2026-06-07_teams-people-avatar-archive.md`

판단:

- `teams-bot-dofi-01`과 `dof-teams-bot`는 bot 제품/배포 프로젝트다.
- 위 문서들은 bot 구현보다 개인 Graph export, 대화 백업, 사람별 업무 지식화가 핵심이다.
- 따라서 현재 위치 유지가 더 자연스럽다. 단, 이 데이터를 bot/RAG 제품 기능으로 전환하는 순간 `teams-bot-dofi-01` 쪽으로 별도 design doc을 만들어야 한다.

### 3. shop-order-auto / ddbot 관련성

현재 startpoint-04의 `proc/plan`, `proc/research`에서 `shop-order-auto-with-api`로 직접 귀속되는 강한 문서는 찾지 못했다. 주문자동화 API와 Teams bot 프로젝트에는 이미 자체 plan/research가 풍부하다.

## 현 위치 유지가 타당한 묶음

다음 유형은 startpoint-04가 실행/데이터 허브이므로 이동 우선순위가 낮다.

- `playwright-cli-*`, `dom-only-skills-api-migration.md`, `browser-harness-setup.md`
- `amaranth-*` 중 비회계 업무: leave/resource/calendar/org/approval/doc recall
- `gmail`, `gcal`, `gcontacts`, `notion`, `raindrop`, `threads`, `naver-blog`, `chatgpt`, `kmsg`
- `daily-jot-to-tasks`, `backfill_areas_*`, `morning-routine`, `night-routine`, `daily-collect`
- `sales-meeting-doc-skill.md` 같은 startpoint skill packaging 문서
- `macos-virtual-desktop-shortcuts.md`

## 우선순위 제안

실제 정리를 한다면 다음 순서가 안전하다.

1. **중복/후속 문서가 이미 있는 포털 repo 주제부터 병합**
   - `504`, `고객사 좌표`, `C00354`, `Sales-prefix PKG`, `그룹 멘션`
   - 대상 repo에 후속 문서가 있으므로 단순 이동보다 diff merge 후 startpoint 문서는 색인/삭제 여부를 판단한다.

2. **포털 운영 DB 변경 plan/research를 target repo로 이전**
   - contact update, country update, order status correction, release ops, shipping API research.
   - prod dump/output 경로와 민감정보 주의사항도 대상 repo 문서에 같이 남겨야 한다.

3. **portal-ledger renderer 비교/legacy 결정 문서를 거래원장 repo로 이전**
   - 두 파일은 startpoint-04에 둘 이유가 거의 없다.

4. **Amaranth 회계 문서와 B repo 상태 정리**
   - 회계 skill이 A/B 양쪽에 남아 있으므로, 먼저 현재 실제 사용 경로를 확인한 뒤 문서 위치를 확정한다.

5. **바이브코딩 책 프로젝트는 전용 repo로 산출물 canonical을 정한 뒤 이동**
   - 문서만 옮기면 원천 `data/vibecoding-book`와 생성 script 참조가 깨질 수 있다.

## 실행 전 체크리스트

실제 이동/병합 전에 확인할 것:

- 대상 repo의 AGENTS/CLAUDE 규칙.
- 대상 repo에 이미 같은 주제의 문서가 있는지와 어느 문서가 최신인지.
- startpoint-04 문서가 참조하는 `output/` 파일이 대상 repo에도 존재하는지.
- 민감 파일 경로, DB dump, credentials가 문서에 노출되지 않는지.
- 이동 후 startpoint-04에는 색인 파일을 남길지, Git history에만 맡길지.
- 파일 이동은 `git mv`로 하되, 이미 대상 문서가 있으면 직접 덮어쓰지 말고 병합한다.

## 결론

가장 명확한 오배치 후보는 포털 웹/운영 문서와 portal-ledger renderer 문서다. 이들은 startpoint-04가 작업 지휘소였을 뿐, 장기적인 맥락 검색은 각 제품 repo에서 이루어지는 편이 맞다.

반면 Daily/Notion/Raindrop/Teams 개인 백업/일상 루틴/범용 스킬 문서는 startpoint-04의 역할과 맞다. 영업처 후보 발굴/Outline 대량 리포트는 지금은 startpoint-04에 두는 것이 자연스럽지만, 작업이 계속 커지면 전용 prospecting 프로젝트를 새로 두는 편이 더 낫다.
