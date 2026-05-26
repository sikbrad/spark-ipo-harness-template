# Vibecoding latest PPT book

## 목표

Google Drive 백업 폴더의 바이브코딩 관련 자료 중 파일명에 `latest`가 붙은 PPT/PPTX를 로컬 산출물로 복사하고, 슬라이드 내용을 추출해 하나의 Markdown 책과 PDF 책으로 엮는다.

## 작업 항목

- [ ] 원본 Working 폴더에서 바이브코딩 관련 폴더 후보 확인
- [ ] 파일명에 `latest`가 포함된 PPT/PPTX 후보 선별
- [ ] 선별 파일을 `data/vibecoding-book/source-ppts/`로 복사
- [ ] 각 문서의 슬라이드 텍스트/노트/이미지 후보를 추출
- [ ] 추출 내용을 정리해 `book.md` 생성
- [ ] `book.md`를 보기 좋은 PDF로 렌더링
- [ ] 산출물 구조와 파일 무결성 검증

## 원칙

- 원본 Google Drive 백업 폴더는 읽기 전용으로 다룬다.
- `input/`과 `proc/archive/`는 건드리지 않는다.
- 복사본, 추출물, 중간 파일, 최종 책은 모두 `data/vibecoding-book/` 아래에 둔다.
