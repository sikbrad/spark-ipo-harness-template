# 2026-06-15 Night Routine

## 목표
2026-06-15 기준 raw를 수집하고, Jot/Task/Standup/Raindrop/메일/캘린더/Teams/Atlassian 자료를 읽어 `data/daily/2026-06-15/summary.md`를 작성한다.

## 작업 항목
- [x] 음성 후보 확인
- [x] 오늘 음성 다운로드 및 Qwen3-ASR CUDA 전사
- [x] Notion/Raindrop/Google/Teams/Outlook/Atlassian raw 수집
- [x] 빈 Areas 후보 확인 및 필요한 경우 backfill
- [x] kubit Slack conversation/people 갱신
- [x] raw 직접 읽기
- [x] summary.md 작성
- [x] 실패 source와 다음 액션 기록

## 결과
- `data/daily/2026-06-15/summary.md`를 새 음성 전사와 23:31 재수집 raw 기준으로 갱신.
- 오늘 음성 `260615_190616.m4a` 다운로드 및 전사 완료.
  - 모델: `Qwen/Qwen3-ASR-1.7B` CUDA
  - 길이: 2353.63초
  - 5분 청크 8개
  - 전사본: `data/daily/2026-06-15/raw/voice-260615_190616.txt`
- Note DB 빈 Area 1건(`260615 박소정팀장 미팅 은행자동조회`)은 이미 `DOF`로 보강되어 있었고, 재실행 시 `skipped_has_area`.
- Google/MS Graph/Outlook/Atlassian/Notion live/Raindrop/kubit raw 재수집 완료.
- 남은 오류:
  - Notion full dump는 기존 300초 timeout 이력으로 skip, live snapshot 사용.
  - Teams private channel 3개는 Graph 403.
  - kubit Slack은 scope 부족 경고가 있으나 conversation/people collect 자체는 완료.
