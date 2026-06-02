# Outline 오늘 추가 잠재고객 보강 결과

대상 루트: `https://outline.doflab.com/doc/7jib7jef7lky7zue67o0-c0ae88mpyc`

## 목표
- 루트 하위 `잠재고객-*` 업체 문서 중 2026-06-02 KST에 생성된 업체만 식별한다.
- 해당 업체들에 대해 headless 웹검색 기반 보강 섹션이 실제 Outline 본문에 들어가 있는지 검증한다.
- 누락 시 기존 문서를 덮어쓰지 않고, 기존 영업처 카드/연락처/데이터 취득/영업 메모를 유지한 채 보강 섹션만 병합한다.
- 사후 캐시와 readback 검증 결과를 남긴다.

## 진행
- [x] Outline API live `documents.list`로 잠재고객 국가 폴더 하위 업체 문서 16,019개 스캔.
- [x] `createdAt` 기준 2026-06-02 KST 생성 업체 8,855개 식별.
- [x] 오늘 추가 업체 8,855개가 headless 웹검색 결과 캐시에 모두 매칭되는지 확인.
- [x] 오늘 추가 업체 8,855개 전체에 `공개 웹검색 보강 (2026-06-02)` 섹션이 존재하는지 Outline API readback 검증.
- [x] 섹션 누락 0건 확인. 별도 repair 불필요.
- [ ] 사용자 정정 반영: 기존 캐시 검증이 아니라 오늘 추가 업체명 + 국가/현지어 치과 키워드로 headless 웹검색을 새로 실행하고 Outline 문서 본문을 즉시 갱신.

## 결과
- 오늘 추가 잠재고객 업체: 8,855개.
- 상태 분포: 잠재고객-치과 6,060개, 잠재고객-치기공 1,499개, 잠재고객-유통사 870개, 잠재고객-교정치과 426개.
- 신뢰도 분포: 높음 3,926개, 중간 7개, 낮음 4,922개.
- 공식/자체 웹사이트 본문 확인: 3,926개.
- 언론·행사성 신호 후보: 140개.
- Outline readback: 8,855개 확인, 섹션 누락 0개, 요청 실패 0개.

## 산출물
- 오늘 추가 업체 목록: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/prospect_headless_search_update/today_added_prospect_docs_2026-06-02.json`
- 오늘 추가 업체 검증 결과: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/prospect_headless_search_update/today_added_prospect_verification_2026-06-02.json`
- 사후 병합 검색 결과 캐시: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/prospect_headless_search_update/outline_first_search_updates.merged.jsonl`

## 판단
- 직전 결과는 오늘 추가 업체가 기존 보강 섹션을 갖고 있는지 확인한 것이어서 사용자 의도와 다르다.
- 이번 보정 실행은 캐시를 결론으로 쓰지 않고, 오늘 추가 업체 8,855개를 대상으로 업체명, 국가명, 현지어 치과 키워드를 조합해 새로 headless 웹검색한다.
- Outline 업데이트 성공 기준은 `documents.update` 응답이 아니라, 업데이트 직후 `documents.info` readback에서 새 문구 `현지어 치과 키워드`가 실제 본문에 남아 있는지로 판단한다.
- 신뢰도 `높음`은 공식/자체 웹사이트 본문을 headless로 열어 확인한 경우, `중간`은 공개 검색 결과에서 업체명과 치과 관련성이 함께 확인되지만 공식 본문 확인이 제한적인 경우, `낮음`은 동일 업체 확정 근거가 약해 기존 공개 출처 중심으로 보수 해석한 경우다.
