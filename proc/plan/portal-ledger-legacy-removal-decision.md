# portal-ledger: legacy 렌더러 삭제 가능성 검토 및 결정

## 배경

사용자 요청: "Legacy 코드는 지우고 refactor 이후의것만 남겨줄 수 있나? 헷갈린다. **공통으로 쓰고있는거라면 무리하게 분리하지말고 최대한 보수적으로 접근하라.**"

리서치 보고서: [proc/research/portal-ledger-renderer-comparison.md](../research/portal-ledger-renderer-comparison.md)

리서치 보고서의 권고는 **"삭제하지 말 것"**.

## 실제 의존 관계 (정밀 매핑)

### `src/renderer/` (legacy) — Active production

| 파일 | 사용처 | 상태 |
|------|--------|------|
| `GeneralLedgerHtml.js` | `renderFullPackage.js`, `renderLedgerHtml.js`(local, 미사용) | active 간접 |
| `renderFullPackage.js` | **`scripts/statement-build.ts`**, **`scripts/rerender-summary-refine-sample.ts`** | **production active** |
| `adapter.ts` | **`scripts/statement-build.ts`** | **production active** |
| `InvoiceHtml.js` | `renderFullPackage.js` | active 간접 |
| `UnpaidLedgerHtml.js` | `renderLedgerHtml.js`, `renderFullPackage.js` | active 간접 |
| `escape.js`, `Brand.js`, `htmlShell.js`, `assets.js`, `styles.css` | 공통 utility | active 간접 |
| `PkgLedgerHtml.js` | (importer 미발견) | **orphan 후보** |
| `renderLedgerHtml.js`(local) | (importer 미발견) | **orphan 후보** |
| `renderLedgerPdf.js` | (importer 미발견 — `src/statement/render/pdf.ts`가 신 path) | **orphan 후보** |

### `src/builder/refactor/` — New parallel path

| 파일 | 사용처 |
|------|--------|
| `renderHtml.ts` | `scripts/build-refactor.ts` |
| `buildLedger.ts` | `scripts/build-refactor.ts` |
| `loadInputs.ts` | `scripts/build-refactor.ts` |
| `types.ts` | refactor 내부 |

### 별도 path (local과 무관)

- `scripts/build-ledger.ts` — `../hong-works/hong-ledger-and-packages-02/src/renderer/` 동적 import
- `scripts/build-batch.ts` — 동일

이 둘은 local `src/renderer/` 와 무관하므로 본 결정에 영향 없음.

## 핵심 발견

**Legacy = production 활성 경로다.** 5/18까지 `statement-build.ts`(v4)와 `rerender-summary-refine-sample.ts`(v6)가 활발히 업데이트되고 있고, 둘 다 `src/renderer/` 모듈을 직접 import 한다. 만약 `src/renderer/` 를 통째로 삭제하면 **production statement 빌더가 즉시 깨진다.**

Refactor 경로(`src/builder/refactor/` + `build-refactor.ts`)는 별도 출력 디렉토리(`output/refactor/`)에 별도 형식으로 산출물을 만들며, **아직 statement-build.ts를 대체하지 못한다.** 데이터 모델이 다르기 때문이다 (legacy: `{meta, general, pkg}` flat ↔ refactor: rich `CustomerLedger`).

## 결론: 지금 단계에서 legacy 삭제는 무리

사용자의 "공통으로 쓰고있는거라면 무리하게 분리하지말고" 지시에 정확히 해당하는 케이스. **삭제 = 보수적 접근의 반대.**

다만 사용자가 "헷갈린다"고 한 점은 해결해야 함 → **삭제가 아니라 명료화(documentation/이름)로 풀어야 한다.**

## 권장 액션 (보수적 옵션 A — 추천)

**파일 삭제 없음. 명료화만 한다.**

1. `src/renderer/README.md` 신설:
   - "이 폴더는 **production active** legacy 렌더러. `scripts/statement-build.ts`, `scripts/rerender-summary-refine-sample.ts` 가 사용 중."
   - "신규 path는 `src/builder/refactor/` — 데이터 모델 다름, 점진 마이그레이션 대상."
   - "함부로 삭제 금지."

2. `src/builder/refactor/README.md` 신설:
   - "이 폴더는 **신규 path** (2026-05-16 진입). `scripts/build-refactor.ts` 만 사용."
   - "Legacy 경로(`src/renderer/`) 와 병렬 운영 중."
   - "마이그레이션 완료 후 legacy 폐기 예정."

3. **orphan 후보 정리 (안전한 dead-code 제거):**
   - 다음 3개 파일은 importer가 한 곳도 없음:
     - `src/renderer/PkgLedgerHtml.js`
     - `src/renderer/renderLedgerHtml.js` (local) — `build-ledger.ts`는 HONG_ROOT의 동명 파일을 씀
     - `src/renderer/renderLedgerPdf.js` — `src/statement/render/pdf.ts`로 이미 이행됨
   - **단, 삭제 전에 한 번 더 검증** — 동적 import / 문자열 path / build script 가 참조하는지 grep 재확인 필요.
   - 검증 통과 시 삭제 가능 (dead code 제거는 보수적 접근에 부합).

4. `proc/spec/` 에 architecture 문서 추가 (선택):
   - "현재 portal-ledger는 두 렌더러 path가 병렬 운영 중이며, 이는 의도된 상태다."
   - 마이그레이션 로드맵을 짧게 기록.

## 비추천 옵션 B — 진짜 legacy 폐기

만약 사용자가 정말 legacy를 지우고 싶다면, 다음을 모두 해야 함:

1. `statement-build.ts` 와 `rerender-summary-refine-sample.ts` 를 `src/builder/refactor/` 기반으로 재작성
   - `toLedgerJson(stmt, ...)` (legacy) → `buildCustomerLedger(erp, ctx, ...)` (refactor) 로 대체
   - 데이터 모델 변환 작업 필요 (legacy `{meta, general, pkg}` ↔ refactor `CustomerLedger`)
2. 신/구 산출물 등가성 검증 — 동일 거래처 입력 → HTML 출력 비교
3. 검증 통과 후 `src/renderer/` 폴더 + `adapter.ts` 삭제

이건 **사용자가 명시적으로 "보수적 접근하라" 한 지시와 정면 충돌**한다. 또한 작업량 크고 production 산출물 형식 변경 리스크 있음.

## 권고

**옵션 A로 진행하되, orphan dead-code 3개 파일만 검증 후 제거**:
- `src/renderer/PkgLedgerHtml.js`
- `src/renderer/renderLedgerHtml.js`
- `src/renderer/renderLedgerPdf.js`

그 외는 모두 유지. README 2개 추가로 "왜 두 path가 공존하는가" 를 코드 옆에 명시.

---

## 실행 결과 (2026-05-18)

사용자가 옵션 A 선택. 다음 변경을 portal-ledger 저장소에 적용:

### 신규 문서 2개
- `src/renderer/README.md` — legacy production active 폴더임을 명시 + 사용 entry point + ⚠️ 함부로 삭제 금지 + 제거된 dead-code 목록.
- `src/builder/refactor/README.md` — 신규 parallel path. 진입점, 구성, legacy 와의 비교표, 마이그레이션 로드맵.

### Dead-code 3파일 삭제 (총 150 lines)
Importer 정밀 검증 (동적 import / 문자열 path / config / JSON / md 모두 grep) 통과 후 `git rm`:
- `src/renderer/PkgLedgerHtml.js` (72 lines)
- `src/renderer/renderLedgerHtml.js` (30 lines)
- `src/renderer/renderLedgerPdf.js` (48 lines)

**검증 디테일:**
- `PkgLedgerHtml`: importer 0건 (self-reference + proc/plan archive만)
- `renderLedgerHtml` (local): `build-ledger.ts`/`build-batch.ts` 는 `HONG_ROOT/src/renderer/renderLedgerHtml.js` 동적 import — local 파일 아님. local importer 0건.
- `renderLedgerPdf` (local): PDF 렌더는 `src/statement/render/pdf.ts` 로 이행 완료. local importer 0건.

### 검증
- `bun run lint` (= `tsc -b --noEmit`) — 에러 0건, 컴파일 영향 없음 ✅
- `statement-build.ts` / `rerender-summary-refine-sample.ts` 의 active production 경로는 그대로 유지 ✅

### Git 상태
- Staged (deletion): 3 files
- Untracked (new): 2 README files
- **Commit은 사용자 결정으로 위임** — 본 작업이 자동으로 commit 하지 않음.
