# startpoint 문서 재배치 실행 계획

작성일: 2026-06-08 KST

## 목적

`dof-work-startpoint-04`에 남아 있는 `proc/plan`, `proc/research` 문서 중 실제 소유 프로젝트가 더 명확한 항목을 대상 SPARK/IPO 프로젝트로 이동한다.

## 기준

- 이전 리서치 문서: `proc/research/2026-06-08_startpoint-doc-relocation-review.md`
- 바로 이동/병합 대상은 문서 35개와 포털 연락처 변경 보조 스크립트 3개다.
- 단순 이동보다 양쪽 색인이 맞는 항목은 원본을 유지하고 대상 프로젝트에 얇은 cross-link 문서를 둔다.
- 애매 후보와 개인/범용 실행 허브 성격 문서는 이동하지 않는다.

## 실행 단계

1. 대상 프로젝트의 AGENTS.md와 기존 SPARK/IPO 디렉터리 구조를 확인한다.
2. 대상별 디렉터리를 만들고, 충돌 없는 파일명으로 이동한다.
3. 중복/부분 소유권 항목은 단일 원본 이동 대신 cross-link 문서로 남긴다.
4. 이동 전후 파일 존재 여부와 `git status`를 확인한다.
5. 리서치 문서에 실행 결과를 반영한다.

## 진행 기록

- 2026-06-08: 이동 전 구조와 기존 사용자 변경 상태 확인.
- 2026-06-08: 실파일 38개 이동 완료.
- 2026-06-08: 보조 소유권이 있는 항목에 cross-link 문서 6개 추가.

## 이동 결과

| 대상 | 이동 수 | 비고 |
|---|---:|---|
| `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az` | 22 | 포털 web 운영/기능/장애/리서치 문서 19개, 연락처 보정 스크립트 3개 |
| `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az` | 4 | SF loader/PKG/C00354/portal prod SF load 기록 |
| `/Users/gq/works/projs/dofing-order-app/order-invoicing/portal-ledger-invoice-gen-and-send` | 2 | renderer 비교, legacy 제거 결정 |
| `/Users/gq/works/projs/dofing-order-app/order-invoicing/hong-works/hong-ledger-and-packages-02` | 1 | Amaranth 회계 ACC 스킬 계획 |
| `/Users/gq/works/lecture/vibe-coding-book/vibe-coding-book-writing-01` | 8 | 바이브코딩 책 제작 계획 |
| `/Users/gq/works/lecture/kubit/kubit-bitbot-slack-01` | 1 | KUBIT Slack/강의 공유 계획 |

합계: 38개.

## Cross-link 결과

| 위치 | 목적 |
|---|---|
| `dof-order-web-3-az/proc/50_plan/tasks/2026-05-25_portal-prod-sf-load-crosslink.md` | portal-data로 이동한 prod SF load 기록의 web 운영 색인 |
| `dof-order-web-3-az/proc/30_research/analysis/2026-06-02_pkg-sales-prefix-contract-portal-research-crosslink.md` | portal-data로 이동한 PKG Sales-prefix 계약 조사 색인 |
| `dof-order-web-3-az/proc/30_research/report/2026-05-26_c00354_sf_missing_contract_date-crosslink.md` | portal-data로 이동한 C00354 계약일 조사/계획 색인 |
| `portal-ledger-invoice-gen-and-send/proc/research/2026-06-02_pkg-sales-prefix-contract-portal-research-crosslink.md` | PKG sheet/ledger 맥락 보조 색인 |
| `hong-ledger-and-packages-02/proc/plan/2026-05-11_amaranth-split-acc-vs-nonacc-crosslink.md` | startpoint에 남긴 Amaranth 분리 결정의 회계 repo 색인 |
| `kubit-bitbot-slack-01/proc/plan/2026-05-26_routine-skills-kubit-slack-crosslink.md` | startpoint에 남긴 routine 계획 중 KUBIT Slack 부분 색인 |

## 유지한 항목

- `proc/plan/2026-05-11_amaranth-split-acc-vs-nonacc.md`: 분리 결정 자체는 startpoint와 회계 repo 양쪽에서 찾아야 하므로 원본 유지.
- `proc/plan/2026-05-26_routine-skills.md`: morning/night routine 전체 계획은 startpoint 소유이므로 원본 유지.
- 해외/국내 치과 잠재고객, Teams 개인 백업/업무 아바타 문서는 이전 리서치 판단대로 이동하지 않음.
