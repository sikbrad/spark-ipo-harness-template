# Vibecoding latest PPT book

## 목표

Google Drive 백업 폴더의 바이브코딩 관련 자료 중 파일명에 `latest`가 붙은 PPT/PPTX를 로컬 산출물로 복사하고, 슬라이드 내용을 추출해 하나의 Markdown 책과 PDF 책으로 엮는다.

## 작업 항목

- [x] 원본 Working 폴더에서 바이브코딩 관련 폴더 후보 확인
- [x] 파일명에 `latest`가 포함된 PPT/PPTX 후보 선별
- [x] 선별 파일을 `data/vibecoding-book/source-ppts/`로 복사
- [x] 각 문서의 슬라이드 텍스트/노트/이미지 후보를 추출
- [x] 전체 추출 내용을 검토해 출판기획서 작성
- [x] 출판기획서를 반영해 `book.md` 생성
- [x] `book.md`를 보기 좋은 PDF로 렌더링
- [x] 산출물 구조와 파일 무결성 검증

## 원칙

- 원본 Google Drive 백업 폴더는 읽기 전용으로 다룬다.
- `input/`과 `proc/archive/`는 건드리지 않는다.
- 복사본, 추출물, 중간 파일, 최종 책은 모두 `data/vibecoding-book/` 아래에 둔다.

## 발견 기준

- 기준 폴더: `/Users/gq/Library/CloudStorage/GoogleDrive-bispro89@gmail.com/Other computers/내PC백업/Dropbox_local_231107/Working`
- 포함 조건: 파일명에 `latest` 포함, 확장자 `.ppt/.pptx/.pptm`, 경로에 `vibe`/`vibecoding`/`vivecoding`/`바이브` 계열 포함
- 제외 조건: PowerPoint 임시 잠금 파일 `~$...`
- 1차 후보: 30개, 총 약 5.7 GiB

## 진행 메모

- 일반 파일 복사는 Google Drive File Provider가 PPTX 내부 대용량 미디어까지 전량 스트리밍해 지나치게 느렸다.
- 텍스트/노트 추출은 PPTX XML만 읽으면 되므로, `source-ppts/`에는 원본을 가리키는 symlink를 만들고 추출·기획서·책 제작을 먼저 진행한다.
- 전체 바이트 복사가 꼭 필요하면 `manifest.json` 기준으로 별도 materialize/full-copy를 후속 실행한다.

## 결과

- 선별 PPTX: 30개 (`data/vibecoding-book/source-ppts/`, symlink)
- 추출 슬라이드: 9,312장
- 숨김 슬라이드: 4,359장
- 추출 텍스트 단락: 74,048개
- 덱별 추출물: `data/vibecoding-book/extracts/<deck>/slides.json`, `slides.md`
- 전체 추출물: `data/vibecoding-book/extracts/all-slides.json`, `decks.json`, `slide-inventory.json`
- 콘텐츠 검토 메모: `data/vibecoding-book/proposal/content-review.md`
- 출판기획서: `data/vibecoding-book/proposal/publication-proposal.md`, `publication-proposal.pdf` (10쪽)
- 편집 원고: `data/vibecoding-book/book/vibecoding-practical-book.md`, `vibecoding-practical-book.pdf` (193쪽, 8장/160개 레슨 페이지 확장판)
- 원문 소스북: `data/vibecoding-book/book/book.md`, `vibecoding-latest-ppt-sourcebook.pdf` (3,620쪽)
- 추출 오류: 0건

## 150쪽 이상 확장

- 사용자 추가 목표: 편집 원고 책을 150페이지 이상으로 확장
- 확장 방식: 8개 장 x 장별 20개 레슨 = 160개 레슨 페이지
- 각 레슨 구성: 원천 슬라이드, 레슨 초점, 해설, 슬라이드 단서, 적용 절차, 프롬프트 스타터, 검증 질문
- 검증 결과: `vibecoding-practical-book.pdf` 193쪽
