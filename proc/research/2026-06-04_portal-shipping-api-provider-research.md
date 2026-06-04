# 포털 배송조회 API 업체/플랜 검토

작성일: 2026-06-04
범위: 개발 없음. 포털 프로덕션 DB 읽기 전용 조회 + 공개 API/요금제 리서치.

## 결론

포털 배송조회 API를 새로 붙인다면 1순위는 **17TRACK API Basic**이다. 현재 포털 물량은 최근 12개월 출고 6,836건, 운송장 입력 6,681건이므로 17TRACK의 **10,000 quota / 12개월** Basic 플랜 안에 들어간다. 17TRACK은 등록된 송장 1개에 quota 1개를 쓰고, 이후 지속 추적/API 호출/자동 추적은 추가 quota를 차감하지 않는 구조라 현재 포털의 배송조회 용도와 가장 잘 맞는다.

국내 택배만 별도 안정화하거나 한국어 지원/국내 택배사 대응을 중시한다면 보조 후보는 **DeliveryAPI 월 9,900원 플랜**이다. 최근 12개월 국내 출고 5,716건 중 롯데택배 2,530건, 로젠택배 1,117건이 압도적이고, DeliveryAPI는 국내 택배 조회·웹훅에 강하다. 다만 국내+국외를 하나로 해결하려면 17TRACK이나 TrackingMore/Ship24 같은 글로벌 통합 API가 더 자연스럽다.

## 포털 데이터 근거

데이터 원천:
- 레포: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az`
- DB: `.env`의 주석 처리된 `DATABASE_URL_REMOTE` prod URL을 사용해 `BEGIN READ ONLY`로 조회
- 기준일: 2026-06-04, 미래 `shippingDate` 제외
- 스키마: `Order.shippingDate`, `Order.carrier`, `Order.trackingNumber`

스키마 확인:
- `apps/server/prisma/schema.prisma:527-535`에 배송지, 출고일, 운송업체, 운송장번호 필드가 있다.
- 현재 배송상태 서비스는 진행 중 주문을 조회하고 15분 캐시 주기로 갱신한다. `apps/server/src/shipping-status/shipping-status.service.ts:43`, `:365-390`
- 기존 지원 운송사 코드에는 `DHL`, `FEDEX`, `UPS`, `TNT`, `CJ`, `LOTTE`, `LOGEN`, `EPOST`, `KYUNGDONG`, `SF_EXPRESS`, `ARAMEX` 등이 있다. `packages/api-contract/src/schemas/shipping-status.ts:4-36`

### 전체/최근 물량

| 구분 | 값 |
|---|---:|
| 전체 활성 주문 rows | 26,218 |
| 전체 출고일 입력 주문 | 24,884 |
| 전체 운송사 입력 주문 | 25,055 |
| 전체 운송장 입력 주문 | 19,912 |
| 최근 12개월 출고 주문 | 6,836 |
| 최근 12개월 운송장 입력 주문 | 6,681 |
| 최근 12개월 출고일이 있는 일수 | 260일 |
| 최근 12개월 평균 출고/출고일 | 26.29건 |
| 최근 12개월 p95 출고/일 | 39건 |
| 최근 12개월 최대 출고/일 | 61건 |
| 최근 12개월 최대 출고/월 | 702건, 2025-12 |

월별 출고량:

| 월 | 출고 | 운송장 입력 |
|---|---:|---:|
| 2025-06 | 398 | 358 |
| 2025-07 | 477 | 414 |
| 2025-08 | 497 | 490 |
| 2025-09 | 588 | 587 |
| 2025-10 | 509 | 509 |
| 2025-11 | 535 | 535 |
| 2025-12 | 702 | 701 |
| 2026-01 | 636 | 634 |
| 2026-02 | 537 | 532 |
| 2026-03 | 680 | 678 |
| 2026-04 | 627 | 612 |
| 2026-05 | 581 | 575 |
| 2026-06, 6/4까지 | 69 | 56 |

### 국내/국외 비중

`country`가 `KR`/`KOR` 또는 한국명인 경우 국내로 분류했다.

| 구분 | 출고 | 운송장 입력 | 운송사 입력 | 원문 운송사 고유값 |
|---|---:|---:|---:|---:|
| 국내 | 5,716 | 5,602 | 4,914 | 877 |
| 국외 | 1,118 | 1,077 | 1,005 | 371 |
| 국외 추정 | 2 | 2 | 2 | 1 |

### 운송사 분포

최근 12개월 기준, 현재 코드의 `classifyCarrier`와 같은 정규식 계열로 접은 값이다. 원문 `carrier`에는 날짜/메모/복수 운송사 표기가 많아 원문 고유값은 1,000개 이상이다.

| 운송사군 | 출고 | 운송장 입력 | 국내 | 국외 |
|---|---:|---:|---:|---:|
| LOTTE | 2,530 | 2,527 | 2,523 | 7 |
| LOGEN | 1,117 | 1,117 | 1,116 | 1 |
| MISSING | 915 | 870 | 802 | 113 |
| UNKNOWN | 676 | 615 | 552 | 124 |
| DHL | 550 | 546 | 2 | 548 |
| MANUAL | 316 | 313 | 303 | 13 |
| DIRECT | 230 | 203 | 201 | 29 |
| KYUNGDONG | 106 | 106 | 96 | 10 |
| QUICK | 86 | 82 | 83 | 3 |
| ROHLIG | 62 | 61 | 0 | 62 |
| NOMI | 61 | 56 | 0 | 61 |
| FEDEX | 46 | 45 | 0 | 46 |
| EPOST | 26 | 26 | 25 | 1 |
| TNT | 23 | 23 | 0 | 23 |
| PNL | 22 | 21 | 0 | 22 |
| CJ | 15 | 15 | 12 | 3 |
| 기타 소량 | 59 | 59 | 1 | 58 |

핵심 해석:
- 국내는 롯데택배+로젠택배가 3,647건으로 전체 최근 12개월 출고의 약 53.4%, 국내 출고의 약 63.8%다.
- 국외는 DHL 548건이 가장 중요하다. FedEx/TNT/UPS는 합산 72건으로 작다.
- `MISSING`, `UNKNOWN`, `MANUAL`, `DIRECT`가 2,137건이라, API 도입보다 먼저 운송사/송장 정규화가 조회 성공률을 좌우한다.
- Rohlig, Nomi, PNL 등 포워더성 운송사는 글로벌 parcel API에서도 자동 상태 조회가 안 될 수 있다. 이들은 링크/수기확인 fallback이 필요하다.

## 업체/플랜 조사

### 17TRACK API

공식 근거:
- API는 HTTP + webhook push 구조를 제공한다.
- 3,300개 이상 주요 운송사를 지원하고 매주 추가된다고 설명한다.
- tracking number로 80% 이상 carrier auto-identification을 제공한다고 설명한다.
- 플랜: Basic `10,000 quota / ¥299`, Advanced `50,000 quota / ¥1,299`, Pro `500,000 quota / ¥7,299`, Enterprise `1,000,000 quota / ¥9,999`.
- Plan Details: 무료 100 quota/month, quota는 tracking number 등록 시 차감, 등록 성공 후 지속 추적/반복 API 호출/자동 추적에는 차감 없음, quota 유효기간 12개월, 자동 재구매 없음.

출처:
- https://www.17track.net/en/api
- https://help.17track.net/hc/en-us/articles/37575217580825-Plan-Details

포털 적합성:
- 최근 12개월 출고 6,836건, 운송장 입력 6,681건이므로 Basic 10,000 quota로 충분하다.
- 국내+국외 단일 API 후보 중 비용 구조가 가장 낮다.
- carrier auto-identification이 있어 `carrier` 원문 품질이 낮은 포털 데이터에 유리하다.
- 단, 자동 재구매가 없으므로 quota 잔량 모니터링이 필요하다.

추천 플랜:
- **기본 추천: Basic 10,000 quota / 12개월**
- 다음 조건이면 Advanced: 연 출고가 10,000건을 넘거나, 기존 과거 송장 전체 19,912건을 한 번에 백필해 대량 등록하려는 경우

### DeliveryAPI

공식 근거:
- 롯데택배, CJ대한통운, 우체국택배 등 주요 택배사를 단일 REST API로 조회한다고 설명한다.
- 계정 없이 송장번호 조회 가능, `POST /tracking/trace`, `POST /tracking/subscribe`, `GET /tracking/couriers` 제공.
- 요금: 무료 월 100회, 월 9,900원 월 10,000회, 월 39,000원 월 50,000회, 월 59,000원 월 100,000회, 월 139,000원 월 300,000회, 월 299,000원 월 1,000,000회.
- 각 유료 플랜은 10개 택배사 실시간 조회와 웹훅 지원.

출처:
- https://www.deliveryapi.co.kr/

포털 적합성:
- 국내 핵심 운송사인 롯데택배/로젠택배/경동택배/CJ/우체국 대응에 적합하다.
- 한국어 지원과 국내 택배 이슈 대응이 필요한 경우 운영 부담이 낮다.
- 국외 DHL/FedEx/포워더까지 모두 커버하는 단일 API로 보기에는 17TRACK/TrackingMore/Ship24보다 약하다.

추천 플랜:
- **국내 전용/보조 추천: 월 9,900원, 월 10,000회 API 호출**
- 단, 현재 포털의 15분 캐시 구조를 그대로 외부 API 호출로 치환하면 비용이 커진다. 진행 중 주문의 trackable 송장이 57건만 있어도 57건 x 96회/일 x 30일 = 월 164,160회가 된다. 이 방식이면 월 139,000원 300,000회 플랜 이상이 필요하다.
- 따라서 DeliveryAPI를 쓸 때도 `subscribe`/웹훅 중심으로 설계해야 월 9,900원 플랜이 맞다.

### TrackingMore

공식 근거:
- Free: 50 credits/month
- Basic: $9/month, billed $108/year, 2,400 credits/year, overage $0.04/credit
- Pro: $59/month, billed $708/year, 24,000 credits/year, Tracking API + Webhook 포함
- 1,608 couriers 통합, auto-detect carrier 제공

출처:
- https://www.trackingmore.com/en/pricing?tm_source=top-nav

포털 적합성:
- API/webhook이 Pro부터 포함되므로 포털 API 연동 후보는 Pro다.
- 24,000 credits/year는 현재 연 출고 6,836건 대비 충분하다.
- 17TRACK보다 비싸지만, 상용 SaaS 기능/대시보드/문서/브랜드 트래킹까지 같이 필요하면 검토할 만하다.

추천 플랜:
- **대안: Pro $59/month, 24,000 credits/year**

### Ship24

공식 근거:
- 1,524 connected couriers worldwide
- Free: 10 shipments/month
- Essential: $3.9/month, 50 shipments/month, AI courier auto-detection
- Pro: $59/month, 1,000 shipments/month, Tracking API & Webhook 포함, overage $0.05/shipment

출처:
- https://www.ship24.com/pricing

포털 적합성:
- 현재 월 최대 702건이므로 Pro 1,000 shipments/month 안에 들어간다.
- API/webhook이 Pro부터 포함된다.
- 글로벌 B2C tracking page/notification 성격이 강해, 포털 내부 업무용 배송조회에는 17TRACK/DeliveryAPI보다 비용 우위가 없다.

추천 플랜:
- **대안: Pro $59/month, 1,000 shipments/month**

### AfterShip Tracking

공식 근거:
- Essentials: $29/month, 6,000 shipments/year, extra $0.08/shipment
- Premium: $59/month, 6,000 shipments/year, extra $0.12/shipment
- API & webhooks는 Premium 항목에 포함
- 자동 carrier detection/correction 제공

출처:
- https://www.aftership.com/pricing/tracking

포털 적합성:
- API/webhook 때문에 Premium이 최소 후보인데, 포털은 최근 12개월 6,836건이라 6,000/year를 이미 초과한다.
- 대시보드/브랜드 트래킹/알림까지 필요하면 성숙한 후보지만, 단순 배송조회 API로는 비용 대비 우선순위가 낮다.

추천 플랜:
- 이번 용도에서는 비추천. AfterShip을 고른다면 Premium 이상.

## 추천 시나리오

### 1안: 단일 API로 국내+국외 처리

**17TRACK API Basic**을 사용한다.

근거:
- 현재 연간 등록 대상 6,681~6,836건 < 10,000 quota.
- 신규 송장 등록 후에는 지속 추적에 quota가 추가 차감되지 않는다.
- 국내/국외 carrier를 하나의 API와 webhook으로 묶을 수 있다.
- carrier 원문이 지저분한 포털 데이터에 auto-identification이 유리하다.

예상 비용:
- 17TRACK Basic: 10,000 quota / 12개월 / ¥299.
- 연 출고가 10,000건에 가까워지면 Advanced 50,000 quota로 전환.

### 2안: 국내 품질 우선 + 국외 별도

국내는 **DeliveryAPI 월 9,900원**, 국외는 17TRACK Basic 또는 직접 DHL/FedEx/UPS 공식 링크 fallback으로 처리한다.

근거:
- 국내는 롯데택배/로젠택배 비중이 매우 높고 DeliveryAPI가 한국 택배사 대응/웹훅/지원에 유리하다.
- 국외는 DHL이 핵심이지만 Rohlig/Nomi/PNL 같은 포워더가 있어 완전 자동화보다 fallback이 필요하다.

주의:
- DeliveryAPI는 API 호출량 기반이다. 15분 주기 폴링을 그대로 붙이면 월 10,000회가 금방 초과된다.
- 국내도 `subscribe` 웹훅 중심으로 설계해야 월 9,900원 플랜이 맞다.

### 3안: SaaS 운영 기능까지 포함

**TrackingMore Pro** 또는 **Ship24 Pro**를 검토한다.

근거:
- 포털 내부 조회를 넘어 branded tracking page, notification, dashboard, analytics까지 쓰려면 글로벌 SaaS가 낫다.
- 단순 API 연동만 보면 현재 물량에서는 17TRACK보다 비싸다.

## 구현 전에 정해야 할 정책

개발은 이번 범위가 아니지만, 업체 선택 전에 아래 정책은 정해야 한다.

1. 송장 등록 단위: 주문 1건에 송장 여러 개가 들어갈 수 있다. 현재 서비스도 최대 5개 후보를 추출한다.
2. 운송사 정규화: `롯데택배 12/17`, `메디덴: 로젠택배`, `본사: 롯데택배\n메디덴: 로젠택배`, `DHL 962294390` 같은 원문을 표준 carrier code로 정리해야 한다.
3. 웹훅 우선: 외부 API는 주기 폴링보다 송장 등록 + webhook update 방식으로 써야 한다.
4. 과거 데이터 백필: 전체 운송장 입력 주문 19,912건을 한 번에 등록하면 Basic 10,000 quota를 초과한다. 초기에는 최근 90일 또는 진행 중 주문만 등록하는 것이 안전하다.
5. 포워더 fallback: Rohlig, Nomi, PNL, Lucky, KNP 등은 API 자동조회 미지원 가능성이 높아 “수기확인/공식 링크/메모” 상태를 유지해야 한다.
6. 상태 보존: 외부 API 장애 시 기존 수동 상태와 공식 조회 링크 fallback이 깨지면 안 된다.

## 최종 추천

포털의 현재 물량과 운송사 구성을 기준으로는 **17TRACK API Basic을 1차 선택**으로 둔다. 국내 택배 조회 품질이나 국내 운영 지원이 더 중요하다는 판단이 서면 **DeliveryAPI 월 9,900원 플랜을 국내 보조 API**로 붙이는 하이브리드가 현실적이다.

바로 하나만 고르라면:
- **선택: 17TRACK API Basic**
- **이유: 국내+국외 단일 처리, 현재 연간 물량이 10,000 quota 안에 들어감, 지속 추적에 추가 quota가 차감되지 않음, webhook 구조가 포털에 맞음**

추후 성장 기준:
- 연 출고 10,000건 초과 또는 과거 전체 백필 필요: 17TRACK Advanced
- 국내만 15분 폴링 구조로 유지: DeliveryAPI 월 139,000원 이상 필요
- 브랜드 트래킹/고객 알림까지 제품화: TrackingMore Pro 또는 Ship24 Pro 재검토
