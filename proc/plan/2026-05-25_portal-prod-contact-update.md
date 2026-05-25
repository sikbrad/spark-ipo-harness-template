# Portal prod contact update

## 목표
`customer_contacts_latest.xlsx`의 `통계` 시트만 기준으로 포탈 prod `Company` 연락처를 갱신한다.
모든 대상 행을 매칭/변경 여부별로 검토하고, 갱신 전 정보는 `Company.memo`에 `---- AX ----` 블록으로 보존한 뒤 데이터 유실 없이 적용한다.

## 작업 항목
- [x] 범위 고정: `통계` 시트만 사용하고 JSON/다른 시트는 제외
- [x] 입력 컬럼과 연락처 정규화 규칙 확인
- [x] prod DB 스키마와 현행 `Company` 연락처 필드 확인
- [x] `통계` 시트 전체 행을 포탈 업체와 매칭
- [x] 모든 행에 대해 로드 가능/보류/이미 최신/변경 필요 여부를 검토한 리포트 생성
- [x] 유선/모바일 분리 규칙 적용: `010` 시작 번호는 모바일 후보로 분리
- [x] 변경 전 연락처를 `Company.contactMemo`의 `---- AX ----` 블록에 보존하는 SQL/스크립트 준비
- [x] prod 적용 전 dump 생성 및 dry-run 결과 검증
- [x] prod DB 적용
- [x] 적용 후 샘플 및 전체 count 검증

## 현재 결정
- 입력 workbook: `/Users/gq/works/projs/crm-migration/dofing_crm_facade/output/pack/latest_data/contact/customer_contacts_latest.xlsx`
- 입력 sheet: `통계`
- 제외: `contact_list_parsed.json`, `PKG업체`, `non PKG 업체`, `55개 연락처 업데이트_이미연`, `통계_cpy260531`
- DB 대상 1차 테이블: `Company`
- 기존 정보 보존 위치: 신규 `Company.contactMemo`
- 보존 블록 형식:

```text
---- AX ----
(이전정보)
------------
```

## 리스크 메모
- 업체명은 고유키가 아니므로 `회사명 (FG 기준)`, `회사명(세금계산서기준)`, `다른이름1`, ERP ID를 함께 써서 매칭한다.
- `010`으로 시작하는 번호는 회사 유선번호가 아니라 모바일 후보로 분류한다. `Company.mobile1`, `Company.mobile2`를 신규 추가하여 저장한다.
- prod 쓰기 전에는 `pg_dump` custom archive를 만들고, dry-run 리포트에서 보류 건이 남아 있으면 해당 건은 적용 대상에서 제외한다.

## 실행 결과

- 입력: `통계` 시트 574 data rows.
- 1차 매칭: matched 552, ambiguous 17, unmatched 5.
- 최종 적용: 531개 고객사 업데이트.
- 보류: 24행.
  - ambiguous match: 17
  - unmatched: 5
  - 발송테스트용: 1
  - 동일 고객사 동일 연락처 중복행: 1
- 신규 컬럼: `email2`, `mobile1`, `mobile2`, `contactMemo`.
- 필드별 적용 수:
  - `mobile1`: 526
  - `phone`: 309
  - `email`: 32
  - `mobile2`: 26
  - `email2`: 7
- 사후 검증: ready 531개 uk fetch, missing 0, mismatch 0.

## 산출물

- 분석 리포트: `output/portal-contact-update-20260525/contact-update-analysis.xlsx`
- 적용 대상: `output/portal-contact-update-20260525/contact-update-ready.xlsx`
- 보류 대상: `output/portal-contact-update-20260525/contact-update-holds.xlsx`
- 적용 SQL: `output/portal-contact-update-20260525/contact-update-prod.sql`
- 사후 검증: `output/portal-contact-update-20260525/post-apply-verification.md`
- 적용 전 dump: `output/portal-contact-update-20260525/prod-before-contact-update-20260525_135246.dump`
- 적용 후 dump: `output/portal-contact-update-20260525/prod-after-contact-update-20260525_135405.dump`

## 코드 변경

- 포탈 앱 schema/API/server/front에 연락처 추가 필드 반영.
- `email`은 하위 호환을 위해 기존 컬럼을 유지하고 UI 라벨만 `이메일1`로 표시.
- 신규 migration: `apps/server/prisma/migrations/008_company_contact_fields.sql`.

## 보류 엑셀 검토 보강

- 사용자 입력이 추가된 `contact-update-holds.xlsx`의 결정 열을 `apply`/`skip` 형태로 정리했다.
- 백업: `output/portal-contact-update-20260525/contact-update-holds.before-ai-fill-20260525_141051.xlsx`
- 사용자 회신 반영 전 결정 결과: `apply` 18건, `skip` 6건.
- `skip` 사유:
  - 발송테스트용 1건
  - 원주 지역 후보 부재/연락처 불일치 1건
  - 이미 동일 고객사 row 324로 적용된 중복 1건
  - 빈 행 3건
- 이 단계는 보류 건 후속 적용을 위한 검토표 보강이며, 추가 DB 반영은 아직 수행하지 않았다.

## 보류 엑셀 사용자 회신 반영

- 백업: `output/portal-contact-update-20260525/contact-update-holds.before-user-reply-20260525_142708.xlsx`
- 최종 결정 결과: `apply` 19건, `skip` 5건.
- 사용자 지정/확인 반영:
  - `269 씨앤디자인 치과기공소(원주)`: `apply 2739`
  - `274 디지웍스`: `apply 223`
  - `283 경희의료원`: `apply 5945`
  - `478 예담치과기공소(부산)`: 주소지 우선 기준으로 `apply 6021`
  - `120 하이덴탈코리아(연성대학교)`: 배송지 근거 기준으로 `apply 242`
- 검증: `apply` 19개 company id는 모두 prod에 존재한다.
- 예외: `2739`는 이름에 `[구]씨앤디자인` 문자열이 있으나 현재 고객사명은 `주식회사 원주씨앤디`이고, 사용자가 URL로 직접 지정했으므로 적용 후보로 유지했다.
- 참고: `223 디지웍스`는 주문수 0건이지만 사용자가 기존 FG 고객사에 반영하도록 지정했다.
- 이 단계 역시 보류 건 후속 적용을 위한 검토표 보강이며, 추가 DB 반영은 아직 수행하지 않았다.

## 보류 19건 prod 적용

- 사용자 후속 지시에 따라 dev 적용은 중단하고 prod만 반영했다.
- 적용 전 prod dump: `output/portal-contact-update-20260525/prod-before-hold-contact-update-20260525_143229.dump`
- 적용 SQL: `output/portal-contact-update-20260525/contact-update-holds-prod.sql`
- 적용 로그: `output/portal-contact-update-20260525/prod-hold-contact-update-apply-20260525_143307.log`
- 적용 대상 JSON: `output/portal-contact-update-20260525/contact-update-holds-apply-final-prod.json`
- 검증 결과: `output/portal-contact-update-20260525/post-hold-apply-prod-verification.md`
- 적용 결과:
  - prod schema 보강 SQL 실행 완료. 기존 컬럼은 `IF NOT EXISTS`로 skip됨.
  - hold `apply` 19건 모두 `UPDATE 1`.
  - 검증 fetch 19건, missing 0, field mismatch 0, `contactMemo` marker 누락 0.
- dev DB에는 schema/data 변경을 수행하지 않았다.
