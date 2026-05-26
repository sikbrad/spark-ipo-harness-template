# C00354 SF 계약값 누락 확인 및 브라우저 보정 보고

작성: 2026-05-26 14:30 KST  
대상: `https://portal.doflab.com/contracts/C00354`  
접근 방식: Playwright MCP 브라우저, `admin-test--@doflab.com` 계정  
저장소 기준: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az`, SF 로더는 sibling `dofing-order-portal-data-3-az`

## 결론

`C00354`는 포털 PROD 화면에서 `출처: SF`로 표시되는 SF 이관 계약이었다. 확인 당시 계약일만 비어 있었고, SF 원천에는 대응 가능한 `ActivatedDate = 2022. 7. 15 PM 12:13` 값이 존재했다.

브라우저에서 계약일 최초 1회 입력 예외가 열린 상태였으므로, `2022-07-15`로 입력 후 저장했다. 저장 토스트 `계약이 수정되었습니다.`가 표시됐고, 저장 후 계약일 필드는 `2022-07-15`로 표시되면서 다시 비활성화되어 1회 입력 예외가 정상 동작했다.

## 브라우저 확인값

저장 전 C00354 화면:

| 항목 | PROD 화면 값 |
|---|---|
| 계약명 | `C00354 이담치과기공소(영등포)` |
| 계약번호 | `C00354` |
| 계약일 | 비어 있음 |
| 고객사 | `린치핀치과기공소(영등포) [구]이담치과기공소` |
| 고객 | 비어 있음 |
| 계약기간 | `2022-06-03` ~ `2026-06-02` |
| 출처 | `SF` |
| 계약 상태 | `활성화` |
| 계약유형구분 | 비어 있음 |
| 결제조건 | 비어 있음 |
| 계약금액 / 잔액 | `0` / `0` |
| 월 납입료 | `90000` |
| 하자보증기간 | `48` |
| 비고 | `SF 활성화: 김수련 Chloe / 2022-07-15` |

브라우저 근거:

- 저장 전 주요 필드: `output/portal-c00354-sf-contract-date/c00354-mainfields-snapshot.md`
- 저장 전 전체 화면: `output/portal-c00354-sf-contract-date/c00354-detail.png`
- 저장 직전 계약일 입력값: `output/portal-c00354-sf-contract-date/c00354-contractdate-filled-before-save.md`
- 저장 성공 토스트: `output/portal-c00354-sf-contract-date/c00354-after-save-snapshot.md`
- 저장 후 주요 필드: `output/portal-c00354-sf-contract-date/c00354-mainfields-after-save.md`
- 저장 후 전체 화면: `output/portal-c00354-sf-contract-date/c00354-after-contractdate-save.png`

## SF 원천값

`resources/sf-crm/contracts.jsonl:101`의 C00354 원천값:

| SF 필드 | 값 |
|---|---|
| `Id` | `8007F000005MPJmQAO` |
| `Contract_No__c` | `C00354` |
| `Status` | `Activated` |
| `ActivatedBy` / `ActivatedDate` | `김수련 Chloe` / `2022. 7. 15 PM 12:13` |
| `CreatedDate` | `2022. 5. 25 PM 4:05` |
| `StartDate` / `EndDate` | `2022. 6. 3` / `2026. 6. 2` |
| `ContractTerm` | `48` |
| `Monthly_payment__c` | `KRW 90,000` |
| `Sales_Number__c` | `Sales7752` |
| `Opportunity__c` | `0067F000015Pb5SQAS` |

관련 SF Quote도 존재한다.

- `resources/sf-crm/quotes.jsonl:5685`
- `QuoteNumber=00006976`
- `Grand_Total__c=KRW 3,000,000`
- `Payment_Condition__c=계약금 설치일 카드결제->계좌이체(6/3), 월렌탈료 9만원 CMS`

관련 SF Opportunity도 존재한다.

- `resources/sf-crm/opportunities.jsonl:7424`
- `Opportunity_ID__c=Sales7752`
- `StageName=Contraction Complete`
- `CloseDate=2022. 6. 3`

## 왜 계약일이 비었는가

현재 SF Contract 로더는 `ActivatedDate`를 읽기는 하지만 `contractDate`에 매핑하지 않는다.

- `src/loaders/sf-crm/loaders.ts:1232-1233`: `ActivatedBy`, `ActivatedDate` 입력 타입 존재
- `src/loaders/sf-crm/loaders.ts:1264-1276`: `ActivatedDate`를 비고 푸터 `활성화`로 조립
- `src/loaders/sf-crm/loaders.ts:1288`: `contractDate`는 명시적으로 `null`
- `src/loaders/sf-crm/loaders.ts:1289-1290`: `StartDate`, `EndDate`만 각각 `periodFrom`, `periodTo`에 매핑

필드 매핑 문서도 Contract 섹션에서 `ActivatedDate -> contractDate` 매핑을 정의하지 않는다. 문서상 매핑은 `StartDate -> periodFrom`, `EndDate -> periodTo`, `Monthly_payment__c -> monthlyFee`, `Sales_Number__c -> opportunityUk`, `CreatedDate -> createdAt`까지만 있다.

따라서 이번 누락은 “SF 원천값이 없어서 못 채운 것”이 아니라 “로더가 계약 활성화일을 계약일로 채우지 않도록 설계되어 있던 것”이다.

## 비어 있는 다른 값 판단

브라우저에서 보이는 빈 값 중 일부도 SF에는 근거가 있다.

| 포털 필드 | 현재 상태 | SF 근거 | 현재 로더 상태 | 판단 |
|---|---|---|---|---|
| 계약일 | 저장 전 비어 있었음, 지금 `2022-07-15` 적용 완료 | Contract `ActivatedDate` | `contractDate=null` | 이번에 수동 보정 완료. 자동 매핑 검토 필요 |
| 계약유형구분 | 비어 있음 | FO `OppRecordType__c=Rental Sales`, 월납입료 존재 | `contractType=null` | 렌탈 계약 추론 후보 |
| 고객 | 비어 있음 | Opportunity/Quote Contact `전종민`, SF Contact 존재 | `customerUk=null` | 계약-고객 연결 매핑 후보 |
| 견적 | 비어 있음 | Quote `00006976` 존재 | `quotationUk=null` | 계약-견적 연결 매핑 후보 |
| 결제조건 | 비어 있음 | Quote `Payment_Condition__c` 존재 | `paymentTerms=null` | 포털 enum과 자유 텍스트 정책 정리 필요 |
| 계약금액 | `0` | Quote `Grand_Total__c=KRW 3,000,000` | `totalAmount=0` | 렌탈 계약에서 총액 의미가 애매해 정책 결정 필요 |
| 계약제품 | `0개` | Opportunity Product 2건 존재 | ContractProduct 적재 아님 | 계약 제품으로 보여줄지 정책 결정 필요 |

위 항목들은 모두 “화면에서 비어 보인다”는 점은 맞지만, 로더가 일부러 `null` 또는 `0`을 넣는 설계라서 단순 데이터 사고로 보기는 어렵다. 사용자 불편을 직접 만든 값은 계약일이고, 나머지는 SF 계약 상세 completeness 개선 과제에 가깝다.

## 적용 내역

1. Playwright MCP로 `https://portal.doflab.com/contracts/C00354` 접속.
2. `admin-test--@doflab.com` 계정으로 로그인.
3. 저장 전 화면에서 `출처: SF`, `계약일` 빈 값, `비고`의 SF 활성화일 `2022-07-15` 확인.
4. `계약일`에 `2022-07-15` 입력.
5. 저장 버튼 클릭.
6. `계약이 수정되었습니다.` 토스트 확인.
7. 저장 후 계약일이 `2022-07-15`로 표시되고 계약일 필드가 비활성화된 것 확인.

## 권고

단기 조치는 완료됐다. `C00354`는 이제 계약일이 채워졌고 렌탈 갱신을 위한 기간 수정 저장을 막던 핵심 빈 값은 해소됐다.

후속으로는 SF 로더 정책을 결정해야 한다.

1. `ActivatedDate`를 `contractDate`로 자동 적재할지 결정한다.
2. 자동 적재한다면 과거 SF 계약 중 `importSource='sf' AND contractDate IS NULL AND note LIKE '%활성화:%'` 대상을 백필한다.
3. `contractType`, `customerUk`, `quotationUk`, `paymentTerms`, `totalAmount`, `ContractProduct`는 별도 매핑 정책을 잡는다. 특히 C00354처럼 렌탈 정황이 명확한 계약은 `계약유형구분=렌탈 계약`까지 자동화할 수 있는지 검토한다.
4. SF 로더가 계속 `contractDate=null`로 넣는다면 같은 유형의 계약일 빈 값이 다시 생길 수 있으므로, 최소한 연구/스펙 문서에 “SF Contract의 ActivatedDate는 현재 Contract.note에만 보존된다”고 명시한다.
