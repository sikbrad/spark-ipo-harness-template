# 기술지원팀 OneNote 자료 덤프

## 목표
DOFSupport SharePoint 사이트의 OneNote 자료를 원본 보존용 raw와 검토 가능한 Markdown으로 내려받고, Markdown 렌더링 검토용 HTML 인덱스를 만든다.

## 작업 항목
- [x] DOFSupport 사이트와 OneNote notebook/section/page 접근 경로 확인
- [x] OneNote Graph raw 덤프와 SharePoint drive 원본 파일 덤프 스크립트 작성
- [x] 페이지 HTML을 Markdown과 로컬 asset 구조로 변환
- [x] `data/techsupport/onenote/raw`와 `data/techsupport/onenote/mdfiles`에 결과 생성
- [x] Markdown 검토용 HTML 리포트 생성
- [x] 산출물 개수와 샘플 렌더링을 검증

## 결과 메모
- 2026-05-31 KST: DOFSupport OneNote notebook 2개, section group 34개, section 100개, page index 913개를 수집했다.
- raw content HTML은 909개, Markdown은 placeholder 4개 포함 913개, 로컬 resource는 2,525개이며 resource error는 0개다.
- Graph content endpoint가 404를 반환한 4개 페이지는 metadata/OneNote 링크/error placeholder Markdown을 남겼고, 해당 섹션 원본 `.one` 파일 3개를 `raw/original_section_files/`에 내려받았다.
- HTML review는 `data/techsupport/onenote/review/index.html` 및 page HTML 913개로 생성했다.
- Puppeteer 검증 결과 index row 913개, 샘플 `NC 파일 이상문구 삽입현상 확인 방법` 페이지 이미지 3개 모두 로드, placeholder 페이지도 Graph error 안내와 원본 섹션 파일 링크가 표시됨을 확인했다.
