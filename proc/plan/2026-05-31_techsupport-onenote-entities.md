# 기술지원 OneNote 고객응대 지식 엔티티화

## 목표
`data/techsupport/onenote/mdfiles`의 OneNote Markdown을 고객응대/기술지원 지식 엔티티로 정리해 `data/techsupport/onenote/entities`에 저장한다. 회사 전산자원관리규칙, 사내 행정/운영 규칙, 계정/비밀번호성 문서는 포함하지 않는다.

## 작업 항목
- [x] 고객응대 포함/사내규칙 제외 기준을 코드로 고정
- [x] Markdown 913개를 파싱해 구조화 엔티티와 제외 목록 생성
- [x] 제품/영역/유형별 인덱스와 요약 리포트 생성
- [x] 누락/오분류 가능성이 높은 샘플을 검증

## 결과 메모
- 2026-05-31 KST: `scripts/build_techsupport_onenote_entities.py`로 `data/techsupport/onenote/entities`를 생성했다.
- source Markdown 913개 중 고객응대/기술지원 엔티티 881개를 포함했고, 사내 행정/전산자원/계정성 문서 등 32개를 제외했다.
- 포함 결과는 `entities.jsonl`, `entities.json`, `records/<product_area>/*.md`, `indexes/by_product_area.json`, `indexes/by_support_type.json`, `summary.json`으로 저장했다.
- 제외 결과는 `excluded.jsonl`, `excluded.json`에 제외 사유와 함께 저장했다.
- 금지 성격 키워드(`다오우오피스`, `자산관리`, `일일보고`, `쏘카`, `지출품의`, `통장사본`, `AJ파크`, `ID/PASS`, `ID_PASS`, `비밀번호` 등)가 포함 엔티티에 남지 않았음을 `rg`로 확인했다.
