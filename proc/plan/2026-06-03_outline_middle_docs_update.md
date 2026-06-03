# Outline 중간 문서 현황 갱신

대상 루트: `https://outline.doflab.com/doc/7jib7jef7lky7zue67o0-c0ae88mpyc`

## 목표
- 루트 하위에서 업체 카드가 아닌 지역/상태/국가/분류 문서를 live Outline 기준으로 식별한다.
- `남유럽`, `기타`, `아프리카`, `남유럽/기존고객`, `그리스` 같은 중간 문서가 현재 하위 구조와 업체 수를 반영하는지 확인한다.
- 기존 문서 본문은 보존하고, 자동 현황 섹션만 추가/교체한다.
- 업데이트 후 live `documents.info` readback으로 섹션 반영을 확인한다.

## 진행
- [x] root 문서 live 확인: `영업처후보`, collection `ccc57505-9f9d-411f-b3c3-12d30aac65cc`, root child 14개.
- [x] 이전 잠재고객 업체 보강 실행 세션 종료 확인.
- [x] 오늘 추가 잠재고객 업체 보강 전수 readback 완료 확인.
- [x] live `documents.list` 전체 컬렉션 목록 수집.
- [x] `parentDocumentId` 관계로 업체 문서/중간 문서 구분.
- [x] 중간 문서 현황 섹션 생성 및 Outline 본문 병합 업데이트.
- [x] 업데이트된 중간 문서 readback 검증.

## 결과
- live 컬렉션 문서 수: 17,929개.
- root 하위 reachable 문서 수: 17,817개.
- 업체 문서: 17,345개.
- 업체가 아닌 중간 문서: 472개.
- root 직속 지역 문서: CIS, 남미, 남아시아, 남유럽, 동남아, 동북아, 동유럽, 북미, 서유럽, 아프리카, 오세아니아, 인니, 중동, 중유럽.
- `기타` 문서는 현재 live root 직속 지역 문서에 없음. 이전 구조에서 제외/재분류된 것으로 보고 업데이트 대상에서 제외.
- 중간 문서 업데이트: 최초 467/472 성공, 5개 일시 실패.
- 실패 5개 재시도: 5/5 성공.
- 최종 verify-only readback: 472/472 성공, 실패 0.

## 예시 확인
- `남유럽`: 하위 업체 23건, 하위 중간 문서 9건. 기존고객 4건, 잠재고객-교정치과 1건, 잠재고객-유통사 6건, 잠재고객-치과 12건.
- `남유럽 / 기존고객`: 하위 업체 4건, 하위 중간 문서 1건.
- `남유럽 / 기존고객 / 그리스`: 하위 업체 4건, 업체 예시 4건 링크 반영.
- `아프리카`: 하위 업체 515건, 하위 중간 문서 37건. 오늘 추가 잠재고객 485건 포함.

## 판단
- 이전 `outline_category_tree_verification.json`은 7,663개 업체 기준이라 현재 live 컬렉션 17,929개와 맞지 않는다.
- 이번 작업은 기존 캐시의 중간 문서 상태를 신뢰하지 않고 live Outline 목록으로 새 집계를 만든다.
- 중간 문서 업데이트는 기존 수기/생성 본문을 삭제하지 않고 `## 현재 하위 현황 (자동 갱신)` 섹션만 교체한다.

## 산출물
- live scan: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/middle_docs_update/middle_docs_scan_2026-06-03.json`
- sample sections: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/middle_docs_update/middle_docs_sample_sections_2026-06-03.json`
- update log: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/middle_docs_update/middle_docs_update_2026-06-03.jsonl`
- retry log: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/middle_docs_update/middle_docs_update_retry_2026-06-03.jsonl`
- verify log: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/middle_docs_update/middle_docs_verify_2026-06-03.jsonl`
