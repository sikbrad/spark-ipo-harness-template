# 포탈 주문 속성 해시태그 분류 계획

## 목표
포탈 주문 데이터를 근거로 주문에 장비, 워런티패키지, 소모재 등 복수 속성 해시태그를 안정적으로 부여할 수 있는지 검증하고, 운영 반영 전 파일럿 기준을 만든다.

## 현재 판단
- 가능하다. 기존 `Hashtag` 모델은 `ORDER` 엔티티에 여러 태그를 붙일 수 있고, 현재 데이터에도 해시태그 2개 이상인 주문이 233건 있다.
- `orderType`은 `PAID | FREE | AS` 단일 회계 성격이므로 장비/소모재 같은 상품 속성을 넣기에는 맞지 않는다.
- 주문 속성은 주문 자체보다 `OrderProduct` 라인과 `Product` 마스터의 제품 트리/플래그에서 파생하는 것이 맞다.
- 오늘 읽은 활성 로컬/DEV DB는 동일 규모였다: 주문 26,717건, 주문제품 98,469건, 제품 4,802개, 제품패키지 10개, 주문 해시태그 2,801개.

## 데이터 신호
- `OrderProduct`: `productCode`, `productName`, `factory`, 금액/수량, 무상사유를 가진 주문 라인 스냅샷.
- `Product`: `parentProductCode`, `productType`, `serialYn`, `packageYn`, `factory`를 가진 제품 마스터.
- `ProductPackage`: 일부 패키지 제품의 `packageType`, `priceType`.
- `Hashtag`: `entityType='ORDER'`, `entityUk=<order.uk>`, `tag`, `type='hashtag'`, `orderUk=<order.uk>` 구조로 다중 태그 저장 가능.

## 1차 분류 초안
- `장비`: `serialYn=true`인 제품 또는 장비 대분류 제품. 예: Dental scanner, Milling machine, Intraoral, Industrial scanner, Sintering Furnace.
- `워런티패키지`: `Support / Warranty Pack`, `SU-WP-*`, 제품명 `Warranty`, 제품 패키지 중 워런티 성격.
- `프로모션패키지`: `CO-ET-* Promotion package` 계열. 워런티패키지와 혼합 금지.
- `소모재`: 제품 대분류 `Consumables` 및 no hierarchy 보강 대상 중 Tool, Block, Spray 등.
- `임플란트부품`: 제품 대분류 `Implant Components`.
- `소프트웨어`: 제품 대분류 `CAD Software`.
- `배송/서비스`: Shipping & Handling, Support 등 필요 시 별도 태그.

## 오늘 확인한 분포
- 제품 트리 기준 주요 주문 라인: Consumables/Milling Tool 41,478라인, Consumables/Zirconia Block 5,170라인, Milling machine/Milling accessory 7,823라인, Support/Warranty Pack 220라인.
- 1차 휴리스틱 주문 수: 소모재 11,784건, 장비 5,355건, 워런티패키지 2,572건, 소프트웨어 1,781건, 임플란트부품 1,509건.
- 복수 속성 주문 후보: 태그 2개 1,332건, 3개 730건, 4개 108건, 5개 2건.
- 미분류 후보 6,751건은 `no hierarchy` 제품과 예외 코드 보강이 필요하다.

## 작업 항목
- [ ] 운영 기준 데이터 원천을 확정한다. 현재 활성 `.env`는 로컬 `dof_portal`과 DEV `dof_portal_dev`이며, 운영 반영 전 prod DSN을 별도 확인한다.
- [ ] 읽기 전용 리포트 스크립트를 만든다: 주문별 추천 태그, 근거 제품 라인, confidence, 충돌 사유를 CSV/JSON으로 출력한다.
- [ ] 제품 트리 기반 기본 룰을 구현한다: 장비, 워런티패키지, 프로모션패키지, 소모재, 임플란트부품, 소프트웨어.
- [ ] `no hierarchy` 상위 제품을 수동 검토해 보강 룰을 만든다. 우선 후보: `DM-TO-*`, `DM-CR-*`, `SU-WP-*`, `MD-*`, `SC-*`, `DS-MA-*`.
- [ ] 워런티패키지와 프로모션패키지 오분류를 별도 검증한다. `CO-ET-* Promotion package`는 워런티로 넣지 않는다.
- [ ] 샘플 100건 이상을 수동 검수해 precision 기준을 세운다. 파일럿 반영은 확신도 높은 태그만 대상으로 한다.
- [ ] 운영 반영 스크립트는 idempotent upsert로 작성하고, 변경 전 대상 주문/기존 태그 백업 CSV를 남긴다.
- [ ] 반영 후 DB read-back과 `/api/orders?hashtags=<tag>` API read-back으로 태그별 주문 수를 검증한다.
- [ ] 포탈 목록/상세 화면에서 다중 태그 표시와 필터 조합이 업무적으로 충분한지 브라우저로 확인한다.

## 남은 리스크
- `no hierarchy` 제품이 많아 제품 마스터 정리 없이 100% 자동 분류는 어렵다.
- `패키지`라는 단어가 워런티, 프로모션, 가격/크레딧 패키지에 섞여 있어 태그명을 분리하지 않으면 오분류가 생긴다.
- 주문 하나가 장비와 소모재를 동시에 포함하는 경우가 많으므로 단일 속성 필드보다 다중 해시태그가 맞다.
