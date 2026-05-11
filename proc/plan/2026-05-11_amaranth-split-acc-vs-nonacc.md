# 아마란스 스킬 인벤토리 & 분리 (A↔B)

## 경로
- **A**: `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04` (현재) — **비회계 잔류**
- **B**: `/Users/gq/works/projs/dofing-order-app/order-invoicing/hong-works/hong-ledger-and-packages-02` — **회계 이전 대상**

> ⚠️ **2026-05-11 직정 (수정)**: 처음에 방향을 반대로 옮겼다가 다시 swap 했음 (회계 → B, 비회계 → A).
> 이유: B 디렉토리 이름이 `hong-ledger-and-packages-02` 로 ledger(원장)=회계 도메인이라 회계 자산이 B에 모이는 게 맞음.

---

## 1. 최종 분포 (2026-05-11 swap 완료)

### A — 비회계 6개 잔류

| 스킬 | ERP 화면 | 핵심 helper 함수 (`pwc_amaranth.py`) |
|---|---|---|
| `/amaranth-calendar` | 일정/캘린더 | `calendar_bootstrap`, `calendar_query`, `parse_calendar`, `dev_events_api`, `calendar_list_rows`, `calendar_events`, `dev_events` |
| `/amaranth-org` | 조직도/임직원 | `open_org_dialog`, `search_org`, `research_members` |
| `/amaranth-resource` | 자원(회의실/차량) 예약 | `resource_bookings`, `RES_SEQ` |
| `/amaranth-approval` | 전자결재 문서함 (미결/기결) | `approval_url`, `approval_docs`, `approval_total_count` |
| `/amaranth-leave-request` | 연차휴가신청서 자동 상신 | `submit_leave`, `_dispatch_mouse_click`, `_click_obt_button` |
| `/amaranth-doc-recall` | 상신문서 회수 | `recall_doc`, `_amaranth_outbox_url`, `_click_outbox_row_title` |

### B — 회계 4개 이전

| 스킬 | ERP 화면 | 핵심 helper (`pwc_amaranth.py`) | Excel 빌더 (`pwc_amaranth_excel.py`) |
|---|---|---|---|
| `/amaranth-acc-balance` | ACC3020 거래처계정**잔액** | `acc303x_bootstrap`, `acc3020_query` | — |
| `/amaranth-acc-ledger` | ACC3030 거래처계정**내역** (단일 기간) | `acc303x_bootstrap`, `acc3030_query` | `build_acc3030_xlsx` |
| `/amaranth-acc-period` | ACC3030 — 전체 history fetch + 임의 기간 derive | `acc303x_bootstrap`, `acc3030_history`, `acc3030_period_view` | `build_acc3030_xlsx` |
| `/amaranth-acc-customer-ledger` | ACC3010 거래처**원장** (transaction-level, 월계/누계) | `acc3010_bootstrap`, `acc3010_history`, `acc3010_period_view`, `acc3010_query`, `_acc3010_set_date_range`, `_acc3010_click_inquiry`, `_acc3010_drive_query` | `build_acc3010_xlsx` |

---

## 2. lib 파일 분포

```
A/proc/lib/
  pwc.py                    (playwright-cli wrapper, 양쪽 공통)
  pwc_amaranth.py           (939줄, line 1~939, 비회계만)

B/proc/lib/
  pwc.py                    (A에서 복사)
  pwc_amaranth.py           (1676줄, 풀버전 — 회계 helper가 비회계 공통 helper에 의존하므로 자르지 않고 풀로 둠)
  pwc_amaranth_excel.py     (회계 전용 Excel 빌더, A에서 이전)
```

A의 `pwc_amaranth.py` 자른 위치: line 940 (Accounting helpers 헤더 직전). 회계 함수 14개 제거됨.

---

## 3. 부트스트랩 상태

`playwright-cli` 의 user-data-dir 는 **cwd 해시별 namespaced**:
- A: `~/Library/Caches/ms-playwright/daemon/83e26cdd240f9c2e/ud-amaranth-chrome` ← 로그인 됨
- B: `~/Library/Caches/ms-playwright/daemon/93a8323cc120c791/ud-amaranth-chrome` ← 2026-05-11 로그인 완료 (B의 `.env` 자격증명 자동)

즉 A와 B는 서로 독립된 프로필. 한쪽 로그인 만료되면 다른 쪽에 영향 없음.

---

## 4. CLAUDE.md 갱신

- A: `/browser-harness` 행 다음에 비회계 6개 행 (calendar, org, resource, approval, leave-request, doc-recall)
- B: 회계 4개 행 (acc-ledger, acc-period, acc-customer-ledger, acc-balance) + 브라우저 자동화 아키텍처 섹션
