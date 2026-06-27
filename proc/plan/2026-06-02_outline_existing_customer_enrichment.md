# Outline 기존고객 업체정보 보강 계획

대상 루트: `https://outline.doflab.com/doc/7jib7jef7lky7zue67o0-c0ae88mpyc`

## 목표
- 루트 하위 `기존고객` 업체 문서에 공개 웹 조사 기반 업체정보를 추가한다.
- 치과/치기공/유통 관련 활동, 제품/서비스, 언론·행사·협회·디렉터리 노출 여부를 확인한다.
- 정보 출처별 신뢰도를 업체 문서에 함께 적는다.

## 진행
- [x] 기존 게시 파이프라인과 Outline API 캐시 확인.
- [x] 기존고객 범위 확인: 포탈 연락처 완비 기존고객 493건.
- [x] 각 기존고객의 현재 Outline 문서 ID와 본문 확인.
- [x] 웹사이트, 검색 결과, 공개 디렉터리/언론 노출을 자동 수집.
- [x] 신뢰도 기준으로 조사 결과를 요약.
- [x] 업체별 Outline 문서에 `공개 조사 보강` 섹션 추가/갱신.
- [x] API readback으로 반영 건수와 샘플 본문을 검증.

## 신뢰도 기준
- 높음: 공식 홈페이지, 공식 소셜/행사 페이지, 정부·협회·공식 디렉터리, 포탈 주문 근거.
- 중간: 업계 디렉터리, 전시/세미나 참가 페이지, 제3자 회사 DB/지도 정보가 서로 맞는 경우.
- 낮음: 검색결과 스니펫만 있거나, 같은 이름의 업체가 여럿이라 동일성 확인이 약한 경우.

## 원칙
- 기존 본문은 보존하고 조사 섹션만 갱신한다.
- 공개 웹에서 확인된 내용만 쓰고, 동일성 불확실성은 명시한다.
- Facebook/LinkedIn 등 로그인·약관 리스크가 큰 대량 수집은 직접 크롤링하지 않고 공개 검색 결과나 업체 공식 링크 확인 수준으로 제한한다.

## 완료 결과
- 대상 문서: `기존고객` 업체 문서 498개.
- 조사 결과: 신뢰도 높음 26개, 중간 157개, 낮음 315개.
- 확인된 활동 유형: 치과 유통/장비 공급 140개, CAD/CAM·밀링 63개, 치기공/보철 제작 54개, 디지털 치과 워크플로우 14개, 치과 병·의원 진료 5개, 교육·세미나·행사 3개.
- 공식/자체 웹사이트 후보가 있는 문서: 183개.
- 명확한 언론 기사/행사 노출은 자동 공개 검색에서 확정 가능한 건으로는 잡히지 않아, 각 문서에 없으면 “확인하지 못함”으로 보수 표기했다.
- archived 상태였던 4개 기존고객 문서(BEGO Medical GmbH, Smileline Dental Lab, DENTAL DIREKT, Oral Design Picha)는 restore 후 보강 섹션을 반영했다.

## 산출물
- 실행 스크립트: `proc/lib/dof_outline_existing_customer_enrich.py`
- 조사 JSONL: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/existing_customer_enrichment/existing_customer_research.jsonl`
- 요약 JSON: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/existing_customer_enrichment/existing_customer_enrichment_summary.json`
- API 검증 JSON: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/existing_customer_enrichment/existing_customer_outline_verification.json`

## 검증
- `python3 -m py_compile proc/lib/dof_outline_existing_customer_enrich.py`
- Outline API readback 결과: 498/498개 문서에 `공개 조사 보강 (2026-06-02)` 섹션 존재.
- Outline API readback 결과: archived 문서 0개, errors 0개, missing section 0개.
