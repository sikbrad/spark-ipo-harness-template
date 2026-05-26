# Vibecoding latest PPT book

## 목표

Google Drive 백업 폴더의 바이브코딩 관련 자료 중 파일명에 `latest`가 붙은 PPT/PPTX를 로컬 산출물로 복사하고, 슬라이드 내용을 추출한다. 이후 Notion 스크랩까지 함께 읽어 말라카라는 저자의 관점과 관심사를 파악한 뒤, 자료집이 아닌 200쪽 이상 신규 저술 원고와 출간계획서를 만든다.

## 작업 항목

- [x] 원본 Working 폴더에서 바이브코딩 관련 폴더 후보 확인
- [x] 파일명에 `latest`가 포함된 PPT/PPTX 후보 선별
- [x] 선별 파일을 `data/vibecoding-book/source-ppts/`로 복사
- [x] 각 문서의 슬라이드 텍스트/노트/이미지 후보를 추출
- [x] 전체 추출 내용을 검토해 1차 출판기획서 작성
- [x] 1차 자료집/실용서 초안 생성
- [x] Notion 스크랩을 읽어 말라카 저자상과 관심사 재정리
- [x] 기존 PDF를 최종본이 아닌 자료수집 산출물로 격하
- [x] 새 출간계획서 작성
- [x] 새 원고 Markdown 직접 저술
- [x] 새 원고를 보기 좋은 PDF로 렌더링
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

위 `book/` 및 `proposal/` 하위 산출물은 원천 추출/자료수집/1차 초안 성격이다. 사용자 피드백에 따라 최종 책 후보는 새로 작성한 `final/` 하위 산출물로 분리한다.

## 150쪽 이상 확장

- 사용자 추가 목표: 편집 원고 책을 150페이지 이상으로 확장
- 확장 방식: 8개 장 x 장별 20개 레슨 = 160개 레슨 페이지
- 각 레슨 구성: 원천 슬라이드, 레슨 초점, 해설, 슬라이드 단서, 적용 절차, 프롬프트 스타터, 검증 질문
- 검증 결과: `vibecoding-practical-book.pdf` 193쪽

## 200쪽 이상 신규 저술본

- 사용자 최신 목표: 기존 PDF는 자료수집에 가깝기 때문에 처음부터 새로 기획하고 말라카의 책으로 다시 쓸 것.
- 저자 파악 근거: PPT 추출 9,312장, Notion 관련 페이지 2,107건, 주제 버킷 `ai_vibecoding`/`automation`/`identity`/`life_philosophy`/`operations`/`startup_product`/`teaching_writing`.
- 저자상 요약: 말라카는 기록과 자동화로 문제를 제품화하는 개발자이자 강사로 포지셔닝한다. Notion에서는 나만의 통찰, 생각의 충돌, 가슴 뛰는 이야기, AI/제품/교육/자율성, LifeOS, 실무 자동화 관심사가 반복된다.
- 새 출간계획서: `data/vibecoding-book/final/malaka-vibecoding-publication-plan.md`, `malaka-vibecoding-publication-plan.pdf` (6쪽)
- 새 저술 원고: `data/vibecoding-book/final/malaka-vibecoding-authored-book.md`
- 새 PDF: `data/vibecoding-book/final/malaka-vibecoding-authored-book.pdf` (477쪽)
- 구성: 6부, 12장, 216개 절
- 검증: `pdfinfo` 기준 477쪽, 원고 343,013자, raw Notion/PPT 메타데이터 패턴(`rich_text`, `created_time`, `formula string`, `000Z` 등) 본문 미검출
- 주의: PDF 렌더링에는 스크립트를 사용했지만, 기존 PDF/PPT를 병합하거나 페이지를 짜깁기하지 않았다. 원천은 독해 범위와 목차 설계의 근거로만 사용하고 본문은 새 Markdown 원고로 조판했다.
