# 2026-06-18 Night Routine

## Goal

2026-06-18 하루 raw를 수집하고, Jot/Task/Standup/커뮤니케이션/포탈/kubit/Raindrop/음성 신호를 읽어 `data/daily/2026-06-18/summary.md`를 작성한다.

## Checklist

- [x] 기존 raw 확인 및 기본 수집 실행
- [x] 포탈 feedback/notices 보강
- [x] Teams daily raw와 archive 상태 확인
- [x] Drive/로컬 음성 원본 확인 및 전사
- [x] Notion Jot/Task/Standup 판정
- [x] kubit Slack conversation/people 갱신
- [x] Raindrop 당일 항목 infer/retag
- [x] Empty Areas backfill 필요 여부 확인
- [x] `summary.md` 작성
- [x] 필요 시 skill 문서 업데이트
- [x] 검증 완료

## Notes

- 기본 수집 raw는 `data/daily/2026-06-18/raw/`에 저장했다.
- Portal Feedback/Notice는 DB timeout으로 실패 payload만 남겼다.
- Teams daily raw는 standup/chat/activity 모두 당일 신호 0건이다. full archive 증분 갱신은 60초 timeout으로 종료되어 stale/partial 상태를 summary에 기록했다.
- 음성 후보와 Raindrop 당일 항목은 0건이라 전사/infer/retag 대상이 없었다.
- Notion DailyJot은 템플릿만 있고 새 액션이 없었다. Task DB는 Doing 4건, Ready 41건, Schedule 2건, Wait 2건, Todo 5건이었다.
- Empty Areas 후보는 Task/Note 모두 0건이라 Notion 변경은 하지 않았다.
- `night-routine` skill에는 이미 timeout/partial을 기록하고 계속 진행하는 규칙이 있어 오늘 추가 업데이트는 하지 않았다.
