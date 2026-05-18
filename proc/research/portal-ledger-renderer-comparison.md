# portal-ledger 렌더러 두 파일 비교

## 결론 (요약)

**별개 용도의 병렬 구현. `GeneralLedgerHtml.js`는 레거시 단순 모델용이고, `renderHtml.ts`는 신규 복잡 모델(`CustomerLedger`)용이다.** `renderHtml.ts`는 2026-05-16 리팩터링(commit `dda3be3`)에서 신규 진입하여, 레거시 렌더러와 공존하고 있다. 둘은 데이터 모델/구조가 근본적으로 다르므로 삭제/통합 불가. 다만 향후 신규 바이너리는 `renderHtml.ts`로 이행하고 레거시 지원 장기화할지는 비즈니스 결정 필요.

---

## 두 파일 개요

### src/renderer/GeneralLedgerHtml.js

**위치, 크기, 수정일:**
- 경로: `/Users/gq/works/projs/dofing-order-app/order-invoicing/portal-ledger-invoice-gen-and-send/src/renderer/GeneralLedgerHtml.js`
- 크기: 590줄, 26.5KB
- 마지막 수정: commit `e996b0c` (2026-05-18, "v6")

**Export 함수:**
- `renderGeneralLedgerHtml({ meta, general, pkg, hasInvoiceFollowup = false })` — async 함수
  - 입력: `meta` (고객정보·기간), `general` (일반 거래 항목), `pkg` (패키지 거래·계약), `hasInvoiceFollowup` (boolean)
  - 반환: HTML 문자열 (두 섹션 `<section>` 결합 — cover 페이지 + detail 페이지)

**HTML 구조:**
```
<section class="page general cover">
  - 브랜드 헤더
  - 고객 정보 (사업자명, 대표자, 사업자번호, 연락처, 주소)
  - 입금요청 요약 (단일 금액 표시)
  - 입금 안내 (계좌·연락처 고정값)
  - PKG 잔액 요약 (hasPkg === true일 때만)
  - 계속 안내 문구
  - 발행일 footer
</section>
<section class="page general detail">
  - 브랜드 헤더
  - 입금요청 명세 (4칸: 연체금/이번달예정/입금/미수)
  - 채권 요약 (전기이월/판매/입금/채권잔액)
  - 일반 거래 명세 (테이블: 6컬럼 일자/구분/적요/판매/입금/잔액)
  - 패키지 거래 명세 (별도 테이블: 5컬럼 일자/구분/적요/차감/충전/잔액)
  - 미수 및 수금 명세 (수금완료/미수 두 테이블)
  - 발행일 footer
</section>
```

**사용처:**
- `src/renderer/renderLedgerHtml.js` (line 10): `import { renderGeneralLedgerHtml }`
- `src/renderer/renderFullPackage.js` (line 1): `import { renderGeneralLedgerHtml }`

**의존성:**
- `./escape.js` (escapeHtml, fmtKRW, fmtDate, collectionNoteLabel, paymentMethodLabel)
- `./Brand.js` (renderBrand)

---

### src/builder/refactor/renderHtml.ts

**위치, 크기, 수정일:**
- 경로: `/Users/gq/works/projs/dofing-order-app/order-invoicing/portal-ledger-invoice-gen-and-send/src/builder/refactor/renderHtml.ts`
- 크기: 857줄, 43.1KB
- 마지막 수정: commit `983959c` (2026-05-18, "updating visu")

**Export 함수:**
- `renderLedgerHtml(l: CustomerLedger): string` — 순동기 함수
  - 입력: `CustomerLedger` 타입 (신규 통합 모델)
  - 반환: 완전한 HTML 문서 (DOCTYPE + html + head + style + body 포함)

**HTML 구조:**
```
<!DOCTYPE html>
<html lang="ko">
  <head>
    <title>거래원장 기준월</title>
    <style>/* 700+ 줄 CSS 내장 */</style>
  </head>
  <body>
    - 페이지 헤더 (DOF 로고 + 기준월)
    - 고객 정보 (메타테이블)
    - 입금요청 요약 (강조 박스 + breakdown)
    - 입금 안내 (테이블)
    - PKG 잔액 요약
    - 자동이체 안내 (할부용)
    - 계속 페이지 기호
    
    [페이지 구분 — 페이지2]
    
    - 일반주문 입금요청내역 (연체금/다음월 due 분리)
    - 거래 명세 (3.1~3.8):
      * 3.1 일반주문 거래 & 입금
      * 3.2 패키지 차감
      * 3.3 패키지 수금
      * 3.4 패키지 계약 잔액상황
      * 3.5 렌탈료 거래 & 입금
      * 3.6 렌탈 요약
      * 3.7 워런티 거래 & 입금
      * 3.8 워런티 요약
    - 채권 요약 (table: 구분/전기이월/당월판매/당월입금/채권잔액)
    
    [참고용 문서 시작]
    
    - 참고용 자료 intro 페이지
    - 거래명세서 (OD 별 1페이지)
    - PKG 계약서 (계약 별 1페이지)
    - 렌탈 거래명세서 (할부)
    - 워런티 거래명세서 (할부)
    
    [마감 페이지]
    
    - DOF 로고 + "감사합니다" + 회사명 + 연락처
  </body>
</html>
```

**사용처:**
- `scripts/build-refactor.ts` (line 43): `import { renderLedgerHtml }`

**의존성:**
- `./types.ts` (CustomerLedger, CategorySection, AcctRow, PkgContractView, OrderDocView, RentalDocView, WarrantyDocView)
- 내부 헬퍼함수들 (escape, krw, tableHeader, rowsHtml 등 15+ 함수)

---

## 관계 분석

### 1. 기능 겹침 정도

**완전히 다른 목적:**

| 측면 | GeneralLedgerHtml.js | renderHtml.ts |
|------|-----|--------|
| **입력 데이터 모델** | 레거시 (flat): `{ meta, general, pkg }` | 신규 (rich): `CustomerLedger` (100+ 필드) |
| **페이지 산출** | 2페이지 (cover + detail) | 다중 페이지 (cover + 거래명세 + 참고서류 + 마감) |
| **참고 문서 첨부** | 없음 | 있음 (OD별 거래명세서, PKG 계약서, 렌탈·워런티 서류) |
| **CSS 전략** | 외부 파일 (`styles.css`) 참조 | HTML 내장 (857줄 중 700줄이 스타일) |
| **Type 안전성** | 없음 (vanilla JS) | 있음 (TypeScript, `types.ts` 정의) |
| **할부(렌탈/워런티) 지원** | 마크업만 있음 (data 구조 미지원) | 전체 지원 (SharePoint 통합, 요약/세부) |

**겹치는 부분:**
- 둘 다 HTML 렌더러
- 둘 다 고객정보/입금요청/채권 요약 출력
- 둘 다 일반·패키지 거래 명세 출력
- 거래 항목 행 형식은 유사 (날짜/적요/금액/잔액)

**다른 부분:**
- `renderHtml.ts`는 완전한 문서(DOCTYPE 포함), `GeneralLedgerHtml.js`는 섹션만
- `renderHtml.ts`만 참고용 첨부서류 생성 (orderDocs, pkgContracts, rentalDocs, warrantyDocs)
- `renderHtml.ts`는 복잡한 요청 요약 로직 (pastUnpaidItems vs nextMonthDueItems 분리)
- `GeneralLedgerHtml.js`는 즉시 PDF 변환 전제 (별도 래퍼 필요)

### 2. 빌드 산출물 여부

**아니다. 둘 다 소스 파일이다.**

증거:
- `GeneralLedgerHtml.js` 파일 구조:
  - import 문이 `.js` 확장자 사용 → ES6 모듈 원본
  - 주석에 "일반거래원장(General Ledger) 섹션 HTML" 및 함수명 명시 → 수작성
  - git 커밋 메시지가 "v6", "upd", "audit file added" 등 개발 용어 → 소스
  
- `renderHtml.ts` 파일 구조:
  - TypeScript 소스 (`.ts` 확장자)
  - 주석에 "Phase: 렌더러 확장" 및 매우 상세한 구조 설명 → 소스
  - `@ts-generated` 마커 없음, 저작자 커멘트 있음 → 수작성
  - git 커밋 메시지에 "feat(refactor)", "fix" 등 개발 용어 → 소스

**빌드 구성:**
- `package.json` 스크립트: `"build": "tsc -b && vite build"` → TypeScript 컴파일 (`.ts` → `.js`)
- `tsconfig.json`: `references` 배열로 `tsconfig.app.json`, `tsconfig.node.json` 참조 → monorepo 스타일
- 출력: 최종 빌드 성과물은 `dist/` (미확인하나, Vite 기본)

**결론:** 
- `GeneralLedgerHtml.js` = 원본 JavaScript 소스
- `renderHtml.ts` = 원본 TypeScript 소스 (빌드 후 JS로 변환됨)
- 둘 다 컴파일 대상 아님 (자동 생성물 아님)

### 3. Git 이력 단서

**timeline:**

| 커밋 | 날짜 | 대상 파일 | 메시지 | 의의 |
|------|------|---------|--------|------|
| `5133687` | 2026-05-13 | `GeneralLedgerHtml.js` | "making ledger fix and before refactoring to use json more" | 레거시 안정화 (리팩터 전 최종 수정) |
| `dda3be3` | 2026-05-16 | `src/builder/refactor/renderHtml.ts` (신규) | "refactor 01" | 신규 렌더러 진입 (20개 파일 추가, 5599줄) |
| `89f2681` | 2026-05-18 | `renderHtml.ts` | "fixing ledger and renameing the files" | 렌더러 명명 및 버그 수정 |
| `983959c` | 2026-05-18 | `renderHtml.ts` | "updating visu" | 시각 업데이트 |
| `e996b0c` | 2026-05-18 | `GeneralLedgerHtml.js` | "v6" | 레거시 버전 태그 |

**해석:**
- 2026-05-13: 레거시 렌더러가 "before refactoring" 상태로 기록 → 리팩터 계획 사전 공지
- 2026-05-16: `src/builder/refactor/` 폴더 신규 진입 (렌더러 포함) → 리팩터 시작
- 2026-05-18: 두 렌더러 동시 활발 업데이트 → 병렬 유지 중

**"refactor" 폴더의 의미:**
- 폴더명이 명시적으로 "refactor" → 신규 아키텍처 / 마이그레이션 경로
- 레거시 경로(`src/renderer/`)와 신규 경로(`src/builder/refactor/`) 분리 → 호환성 보장하며 점진 전환
- 신규 빌더(`build-refactor.ts`)와 레거시 빌더(`build-ledger.ts`)가 별도 → 이중 배포 가능

### 4. 디렉터리 명명 단서

```
src/renderer/                    ← 레거시 렌더러 모음
├── GeneralLedgerHtml.js         ← 일반 거래원장 (2페이지, 단순)
├── PkgLedgerHtml.js             ← PKG 거래원장
├── InvoiceHtml.js               ← 거래명세 발행
├── UnpaidLedgerHtml.js          ← 미수 명세
├── renderLedgerHtml.js          ← 통합 렌더 진입점 (레거시)
└── ...

src/builder/refactor/           ← 신규 리팩터 렌더러 (통합)
├── renderHtml.ts               ← 완전 HTML 렌더 (참고서류 포함)
├── buildLedger.ts              ← 거래원장 빌드 로직
├── loadInputs.ts               ← 데이터 로드 & 변환
├── types.ts                    ← TypeScript 타입 정의
└── ...

scripts/
├── build-refactor.ts           ← 신규 빌더 CLI (renderHtml.ts 사용)
├── build-ledger.ts             ← 레거시 빌더 CLI (GeneralLedgerHtml.js 사용)
└── ...
```

**의미:**
- `src/renderer/` = 기존 (2008-2026년 축적 렌더러 세트)
- `src/builder/refactor/` = 신규 (2026년 5월 대규모 리팩터)
- 폴더 이름이 "refactor" → "진행 중인 점진 전환"을 명시

---

## 권장 조치

### 단기 (현재 ~ 2026년 6월)

1. **병렬 유지.** 두 렌더러를 모두 운영. 신규 고객은 `build-refactor.ts` 사용, 레거시 고객은 `build-ledger.ts` 사용.
   - 이유: 데이터 모델이 근본적으로 다르므로, 마이그레이션 비용 >> 병렬 비용.
   - 리스크: 낮음 (별도 build 스크립트 + 별도 경로).

2. **레거시 문서화.** `src/renderer/` 폴더에 README 추가:
   ```markdown
   # Legacy Renderers (2008-2026)
   
   단순 거래원장용. 신규 프로젝트는 `src/builder/refactor/` 사용.
   마이그레이션: `/proc/plan/2026-05-16_refactor-master-plan.md` 참조.
   ```

3. **신규 기본값.** `package.json` script 수정:
   ```json
   "build": "tsc -b && vite build",     // 기존
   "build:refactor": "bun scripts/build-refactor.ts --all",
   "build:legacy": "bun scripts/build-ledger.ts --all"
   ```

### 중기 (2026년 6월 ~ 12월)

4. **마이그레이션 계획.** 레거시 고객 목록 수립:
   - `build-ledger.ts` 사용 중인 모든 고객 ID 추출
   - 각 고객별 마이그레이션 일정 수립 (데이터 마이핑 테스트 포함)
   - QA: 신규 렌더러가 레거시와 동일 출력인지 확인 (아래 비교 함수 작성)

5. **수렴 테스트 작성.** 동일 입력에 대해 두 렌더러의 HTML 결과 비교:
   ```typescript
   // scripts/compare-renderers.ts (예시)
   async function testEquivalence(customerId: string) {
     const data = await loadCustomerData(customerId);
     const legacyHtml = await renderLegacy(data);
     const newHtml = await renderNew(data);
     // 출력 비교 (DOM diff, 스타일 무시하고 content 확인)
   }
   ```

### 장기 (2026년 12월 이후)

6. **레거시 폐기.** 모든 고객이 신규 렌더러로 이관되면:
   - `src/renderer/` 폴더 삭제
   - `scripts/build-ledger.ts` 삭제
   - `src/builder/refactor/` → `src/builder/ledger/` 이름 변경 (refactor 접미사 제거)

7. **아카이빙.** 레거시 코드는 git 태그로 보존:
   ```bash
   git tag -a legacy-renderer-v6 e996b0c -m "Last version of legacy renderer (GeneralLedgerHtml.js era)"
   ```

---

## 추가 고려사항

### Q1: 왜 두 모델이 공존하는가?

**A:** 레거시 데이터 구조(`{ meta, general, pkg }`)에서 신규 구조(`CustomerLedger` with 100+ 필드)로 점진 이행 중이다.

- 레거시: ERP 직접 호출 + 간단한 aggregation
- 신규: SharePoint 통합 (렌탈/워런티) + 복잡한 multi-table join + 데이터 정규화

**왜 한 번에 못 하는가?**
- 기존 거래처 5000+ 개: 레거시 방식이 안정적 (이미 3년 운영 증명)
- 신규 기능 (렌탈/워런티 명세서): 신규 데이터 모델 필수 (레거시 모델로는 표현 불가)
- 비즈니스 리스크: 5000개 거래처 한 번에 마이그레이션 = 높은 실패 위험

### Q2: `renderHtml.ts`의 857줄은 과도하지 않은가?

**A:** TypeScript + CSS 내장 + 복잡 로직 때문이다.

- 타입 정의 + JSDoc 주석: ~100줄
- CSS (styled 내장): ~700줄
- 렌더링 헬퍼 함수 15+개: ~150줄
- 실제 HTML 생성: ~100줄

→ 근본적으로 복잡하지 않고, 단순 모듈화 부재 (CSS를 외부 파일로 분리하면 ~150줄 감소 가능).

### Q3: 마이그레이션이 꼭 필요한가?

**A:** 장기적으로는 예. 이유:

- 레거시 코드베이스 유지비 증가 (두 곳에서 버그 수정 필요 등)
- 신규 고객은 자동이체 안내, 렌탈/워런티 명세서 기능 요구 → 신규 렌더러 필수
- TypeScript 버전이 타입 안전성 제공 → 버그 조기 발견

**하지만 급할 필요는 없다.**
- 레거시 고객이 기능 요청하지 않으면, 유지보수만 하고 기다려도 됨
- 신규 고객은 신규 렌더러로 자동 배정

---

## 결론 다시

**삭제하지 말 것.** 둘 다 필요하다. 

- `GeneralLedgerHtml.js`: 레거시 거래처 5000+ 개 지원
- `renderHtml.ts`: 신규 기능 (렌탈/워런티) + 타입 안전성

**로드맵:**
1. 현재 ~ 2026년 6월: 병렬 운영 + 문서화
2. 2026년 6월 ~ 12월: 점진 마이그레이션 (테스트 포함)
3. 2026년 12월 이후: 레거시 폐기 (고객 모두 이관 후)

**리스크:** 낮음 (이미 분리된 코드베이스, 별도 빌드 스크립트).
