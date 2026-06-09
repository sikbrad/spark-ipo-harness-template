# Threads 바이브코딩 예약 발행 스킬화

## 목표
로컬 바이브코딩 책/꼭지 자료를 바탕으로 개인정보와 회사 내부 정보를 제거한 Threads 연재 초안을 만들고, headful playwright-cli 세션으로 기간별 예약 발행하는 과정을 재사용 가능한 스킬로 만든다.

## 작업 항목
- [x] 기존 Threads 발행 스킬과 Vibecoding Book 스킬 구조 확인
- [x] 새 스킬 이름과 범위 결정
- [x] SKILL.md 작성
- [x] 초안 검증 스크립트 추가
- [x] Threads 예약 발행 스크립트 추가
- [x] `.agents`, `.claude`, `.gemini` 스킬 폴더 동기화
- [x] 스킬 파일 검증

## 산출물
- `.agents/skills/threads-vibecoding-scheduler/SKILL.md`
- `.agents/skills/threads-vibecoding-scheduler/scripts/validate_threads_posts.py`
- `.agents/skills/threads-vibecoding-scheduler/scripts/schedule_threads_posts.py`
- `.agents/skills/threads-vibecoding-scheduler/agents/openai.yaml`
- `.claude/skills/threads-vibecoding-scheduler/`
- `.gemini/skills/threads-vibecoding-scheduler/`

## 검증 결과
- 기존 `output/threads-vibecoding-2026-06` 21개 초안 검증 통과.
- 예약 스크립트 `--help` 실행 통과.
- `.agents`, `.claude`, `.gemini`의 `SKILL.md` mirror 일치 확인.

## 스킬 범위
- 포함: 로컬 자료 탐색, 공개 가능한 주제 선별, 3블록 Threads 체인 초안 작성, 개인정보/회사정보 스캔, 예약 발행 자동화, 결과 기록.
- 제외: 새 외부 API 스크랩, 회사/고객/실명 사례 직접 노출, 예약 전 사용자 확인 없는 원문 개인정보 사용.

## 검증 기준
- `SKILL.md` frontmatter에 `name`, `description` 포함.
- 초안 검증 스크립트가 기존 21개 파일을 통과.
- 예약 스크립트는 `--help` 실행 가능.
- mirror 폴더의 `SKILL.md` 내용이 `.agents`와 동일.
