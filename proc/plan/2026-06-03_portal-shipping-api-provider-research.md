# 포털 배송조회 API 업체/플랜 검토 계획

## 목표
- 포털 실제 주문 데이터에서 운송사, 운송장 입력률, 일/월 배송조회 예상 사용량을 읽는다.
- 국내/국외 배송조회 API 업체와 플랜을 조사한다.
- 포털에 적용할 추천 업체/플랜과 근거를 `proc/research/` 문서로 저장한다.
- 개발/코드 변경은 하지 않는다.

## 범위
- 대상 데이터: 포털 주문의 `carrier`, `trackingNumber`, `shippingDate`, 국가/통화/주문상태 등 배송조회 판단에 필요한 읽기 전용 데이터.
- 대상 기간: 가능한 전체 데이터와 최근 12개월/최근 90일 사용량을 함께 산출한다.
- 조사 대상: 국내 택배 조회 API, 해외/복수 운송사 Tracking API, 통합 Tracking API.

## 체크리스트
- [x] 포털 배송 관련 필드와 스키마 위치 확인
- [x] 실제 DB에서 운송사/운송장/배송일 사용량 추출
- [x] 국내/국외 API 업체와 플랜 최신 정보 조사
- [x] 데이터 기반 추천안 작성
- [x] 조사 문서 저장 및 산출물 검증

## 진행 메모
- 2026-06-03: 포털 본체 레포는 `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az`로 확인.
- 2026-06-03: 배송 관련 핵심 필드는 `apps/server/prisma/schema.prisma`의 `Order.shippingDate`, `Order.carrier`, `Order.trackingNumber`.
- 2026-06-04: 프로덕션 DB를 read-only로 조회. 최근 12개월 출고 6,836건, 운송장 입력 6,681건, 월 최대 702건, 일 최대 61건.
- 2026-06-04: 17TRACK Basic을 1차 추천, DeliveryAPI 월 9,900원 플랜을 국내 보조 후보로 정리.
- 2026-06-04: 최종 문서 저장: `proc/research/2026-06-04_portal-shipping-api-provider-research.md`.
