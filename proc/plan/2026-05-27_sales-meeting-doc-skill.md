# 영업정기회의 문서 생성 스킬

## 목표
Confluence AX 폴더의 최신 영업정기회의 문서를 복제해 지정 날짜 제목으로 만들고, DailyJot/Teams standup 중심의 회사 업무 이슈를 기존 `주제`별 `논의항목`에 개조식으로 채우는 스킬을 만든다.

## 작업 항목
- [x] Confluence 폴더와 최신 문서의 날짜 형식, 표 구조 확인
- [x] 스킬 지침 작성
- [x] Confluence 복제/표 갱신 스크립트 작성
- [x] Teams standup 보강 수집 스크립트 작성
- [x] dry-run으로 최신 문서/토픽/미리보기 검증
- [x] 최종 변경 파일과 남은 리스크 정리

## 2026-05-27 보정

- [x] storage body 재구성 방식이 icon/related/custom contents를 놓칠 수 있음을 확인
- [x] `POST /wiki/rest/api/content/{id}/copy` native copy 방식으로 스크립트 수정
- [x] 이미 생성된 `260527 영업정기회의+AX`는 `existing_page` replace로 원본 `260520` native copy 기반 재교체
- [x] 논의항목을 `{text, children}` 다단 개조식으로 렌더링하도록 보강
- [x] `260527 영업정기회의+AX`를 다단식 논의항목으로 다시 native copy replace
