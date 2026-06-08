# 국내 치과기공소 인허가 기반 리포트260607

## 목표
- 국내 치과 후보 리포트에서 부족했던 치과기공소 후보를 별도 리포트로 보강한다.
- 공공/인허가 원천 데이터를 사용해 최소 2,000곳 이상의 국내 치과기공소를 확보한다.
- `리포트` Outline 문서 하위에 `리포트260607-국내-기공소` 문서를 생성 또는 갱신한다.
- 각 업체 표에는 연락처, 대분류/중분류/소분류, 어떤 곳인지, 포털 존재 여부, 인허가 근거, 영업상태, 신뢰도, 추천 이유를 포함한다.

## 실행 계획
- [x] 기존 국내 리포트와 Outline 발행 코드 확인
- [x] 공공데이터포털/지방행정 인허가 치과기공소 표준데이터 원천 확인
- [x] 원천 CSV 다운로드 경로와 컬럼/상태 분포 확인
- [x] 치과기공소 전용 정규화/리포트/Outline 발행 스크립트 작성
- [x] 원천 데이터에서 영업중 치과기공소 2,000곳 이상 산출
- [x] Markdown/JSON/CSV 산출물 저장
- [x] Outline `리포트260607-국내-기공소` 생성 또는 갱신
- [x] Outline readback으로 문서명, 행 수, 핵심 컬럼 검증

## 원천 데이터 판단
- 주 원천: 공공데이터포털 `전국치과기공소표준데이터`.
- 원천 설명: 전국 자치단체에서 관리하는 치과기공소 인허가 정보를 일괄 취합하여 사업장명, 인허가일자, 영업상태, 소재지주소 등을 제공.
- 현재 다운로드 확인: `file.localdata.go.kr/file/download/dental_labs/info`에서 CSV 수신 가능.
- 신뢰도: 정부 표준 인허가 데이터라 업체 존재/영업상태 신뢰도는 높음. 단, 홈페이지/담당자/실장비 보유 여부는 별도 웹검색 또는 전화 확인 필요.

## 산출물
- 스크립트: `proc/lib/dof_domestic_dental_labs_260607.py`
- 출력 폴더: `output/domestic-dental-labs-260607/`

## 2026-06-08 실행 결과
- 공공데이터포털/지방행정 인허가 CSV 다운로드 성공: `건강_치과기공소.csv`, 2,662,655 bytes.
- 파싱 결과: 전체 8,712행, `영업/정상` + `영업중` 4,648곳.
- Outline 표 반영: 3,000곳. 최소 목표 2,000곳 초과 달성.
- 표 컬럼: 우선순위, 대분류, 중분류, 소분류, 업체명, 어떤 곳인지, 포털 존재 여부, 인허가/인증 근거, 영업상태, 인허가일자, 주소, 전화, 장비 공개값, 검색/출처, 신뢰도, 추천 이유.
- 단발 `documents.create`는 3MB/2.4MB 본문에서 502 또는 장시간 무응답이 발생했다. 작은 문서 생성 후 200행 단위 append로 전환해 성공했다.
- Outline 문서: `리포트260607-국내-기공소`, doc id `1fcdc2e0-fdf6-4efd-a0b7-1680b2777441`, URL `https://outline.doflab.com/doc/260607-AMcMOzZyTv`.
- Outline readback: title 일치, table rows 3,000, text length 1,112,536, `포털 존재 여부` 컬럼 확인, `전국치과기공소표준데이터` 원천 설명 확인.
- 로컬 결과: `output/domestic-dental-labs-260607/report_260607_domestic_dental_labs_result.json`.
- 신뢰도 판단: 업체 존재/영업상태는 정부 표준 인허가 데이터라 높음. 전화/주소는 공개 원천 그대로이며, 홈페이지/담당자/실장비 보유 여부는 개별 웹검색 또는 전화 확인 필요.

## 2026-06-08 DB 정리 보정
- 문제: `리포트` 문서 하위에 `리포트260607-국내-기공소`가 3개 생성되어 있었다.
- 원인: Outline API `documents.list` 장애를 우회하면서 직접 create를 반복했고, 대용량 본문 create가 늦게 성공한 결과 중복 문서가 남았다.
- 원격: `DOF-AX01`의 `outline-postgres` DB를 직접 조회/수정했다.
- 백업: 수정 전후 `documents`와 수정 전 `revisions`를 로컬 `output/domestic-dental-labs-260607/db_fix/` 및 원격 `/home/ax01/works/utils/outline/backup-20260608-domestic-labs-fix/`에 저장했다.
- 상세 데이터 목적지: `국내 치과기공소` 문서 `https://outline.doflab.com/doc/6rwt64k0ioy5moqzvoq4soqzteygja-QcheOAYy0a/edit`.
- DB 확인 결과 위 문서는 수정 전 본문/자식/revision이 비어 있었고, 수정 후 업체별 상세 테이블 3,000행을 해당 문서로 이동했다.
- `리포트260607-국내-기공소`는 요약 문서로만 남기고 상세 데이터 문서 링크를 포함했다.
- 중복 리포트 문서 2개 soft-delete: `67241aef-14e2-4048-a0af-efd4e4d26c1d`, `ccd4374b-072b-4534-b48f-238a57c349b2`.
- 최종 DB/API 검증: `리포트` 하위 활성 `리포트260607-국내-기공소` 1개, 요약 문서 table rows 0, `국내 치과기공소` 상세 문서 table rows 3,000.
- Playwright 검증: 로그인 후 `리포트` 페이지에서 삭제된 중복 URL `G8mhyED80h`, `ukR4Njp3Km`가 DOM에 남아 있지 않음을 확인했다.

## 2026-06-08 Outline 트리/하위문서 보정
- 문제: `documents.deletedAt`와 API 목록은 정리됐지만, Outline 좌측 트리/하위 문서 UI가 `collections.documentStructure`의 stale node를 사용해 `리포트260607-국내-기공소` 3개를 계속 표시했다.
- 조치 스크립트: `proc/lib/dof_outline_fix_domestic_labs_tree_260607.py`.
- 백업: 수정 전 `collections.documentStructure`를 로컬 `output/domestic-dental-labs-260607/db_fix/collection_structure_before_tree_fix.json` 및 원격 `/home/ax01/works/utils/outline/backup-20260608-domestic-labs-tree-fix/collection_structure_before_tree_fix.json`에 저장했다.
- 상세 문서 구조: `국내 치과기공소` 하위에 시도별 17개 문서를 생성/갱신하고, 각 문서에 해당 지역 업체 표를 분산했다.
- 행 수: 서울 688, 경기 531, 부산 318, 대구 275, 경남 160, 광주 128, 대전 126, 경북 123, 충남 102, 전북 98, 강원 95, 인천 89, 전남 88, 충북 72, 울산 68, 제주 27, 세종 12. 합계 3,000.
- 링크 보정: Outline API의 `urlId` 단독 URL은 일부 문서에서 404가 발생해, `documents.info.url` canonical URL을 본문 링크와 `documentStructure` child node URL에 반영했다.
- DB 검증: `리포트` 트리의 `리포트260607-국내-기공소` 노드 1개, 삭제된 중복 트리 노드 0개, `국내 치과기공소` 트리 child 17개.
- API 검증: `리포트` parent 하위 국내 기공소 리포트 match 1개(`AMcMOzZyTv`), `국내 치과기공소` parent 하위 17개.
- Playwright 검증: `https://outline.doflab.com/doc/66as7ys7yq4-cJZ5YdyvPw`에서 삭제된 `G8mhyED80h`, `ukR4Njp3Km` 링크 없음. `https://outline.doflab.com/doc/7isc7jq47yq567oe7iuc-3dJZUM0CuY` 서울 문서가 정상 열리고 `표 반영: 688곳`, 행 패턴 688개 확인.
- 결과 JSON: `output/domestic-dental-labs-260607/tree_fix/tree_fix_result.json`.

## 2026-06-08 기준 문서 형식 재정정
- 문제: `국내 치과기공소` 하위가 시도별 대형 표 문서로만 구성되어 있어 `국내 치과의원 (A·B등급)`의 권역 -> 시도 -> 시군구 -> 업체 카드 형식과 맞지 않았다.
- 기준 확인: `https://outline.doflab.com/doc/ab-eGA5WmKiEM`은 상위 문서 아래 `수도권/영남/호남/강원/충청/제주` 권역 문서를 두고, 시도/시군구 문서의 표에서 업체명을 개별 카드 링크로 연결한다.
- 재구성 스크립트: `proc/lib/dof_outline_reformat_domestic_labs_like_ab.py`.
- `국내 치과기공소` 하위 구조: 권역 6개, 시도 17개, 시군구 203개, 업체 카드 3,000개.
- 업체 카드는 `영업처 카드`, `연락처`, `기공/장비 신호`, `판단 근거`, `검색/출처`, `영업 메모`, `백링크` 섹션으로 구성했다.
- 카드 본문은 Outline에서 줄 병합이 발생하지 않도록 항목/내용 표 형식으로 재작성했다.
- 카드 업데이트 결과: `output/domestic-dental-labs-260607/format_fix/card_table_update_result.json`, `updated=3000`.
- 리포트 `리포트260607-국내-기공소`는 `리포트260604-해외`와 같은 추천 기준/요약/추천 업체 테이블 형식으로 재작성했다. 표 컬럼은 우선순위, 포탈/주문 상태, 권역/시도, 업체, 어떤 회사인지, 확인된 취급품목, 왜 추천하는지, 연락/웹, 확인 출처, 신뢰도, 추가 확인 취급/브랜드, 최근 온라인 흔적, 링크/부가정보 신뢰도다.
- DB 검증: `국내 치과기공소` depth별 문서 수가 0:1, 1:6, 2:17, 3:203, 4:3000으로 확인됐다. 카드 관리번호도 3,000개 모두 유니크다.
- 컬렉션 트리 검증: leaf total 3,000, leaf unique 3,000, 중복 0. 상위 권역은 `수도권/영남/호남/강원/충청/제주`.
- Playwright 검증: `국내 치과기공소` 상위 문서에서 권역 구조와 `전체 반영: 3,000곳` 확인. `서울` 문서에서 `서울 (688곳)`, 표 25개, 업체명 링크 확인. 대표 카드 `덴탈랩동행치과기공소 (수원 2014)`에서 DOM table 4개와 관리번호 `PHMB320143740032062300003` 확인. 리포트 문서에서 추천 업체 수 300개, 전체 상세 카드 3,000개, 해외 리포트식 테이블 컬럼 확인.
