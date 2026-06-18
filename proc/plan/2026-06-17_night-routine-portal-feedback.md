# 2026-06-17 Night Routine Portal Feedback

## Goal

나이트루틴에서 포탈 `Feedback`과 공지사항 릴리즈노트 raw를 함께 수집하고, AX팀이 처리한 포탈 피드백/릴리즈노트를 사용자 업무 기록과 같은 업무 신호로 요약하도록 보강한다.

## Checklist

- [x] 기존 나이트루틴/데일리 수집 흐름 확인
- [x] 포탈 `Feedback` / `Notification` 스키마와 DB 접근 패턴 확인
- [x] 날짜별 `portal-feedback.json` 수집기 추가
- [x] `night-routine`, `daily-collect`, 공통 routine source 문서 업데이트
- [x] 도움말/수집기 실행 검증
- [x] 포탈 공지사항/릴리즈노트 `portal-notices.json` 수집기 추가
- [x] 포탈 공지사항/릴리즈노트 문서와 나이트 수집 래퍼 반영
- [x] 공지사항 수집기 실행 검증

## Notes

- 포탈 운영 DB는 읽기 전용 조회만 수행한다.
- 날짜별 created/updated/notificationSentAt 변경분과 현재 open feedback snapshot을 같이 보관한다.
- 요약 시 포탈 피드백과 공지사항 릴리즈노트는 단순 외부 소음이 아니라 AX팀 업무/사용자 업무 맥락으로 취급한다.
- `node --check`와 `--help`는 통과했다. 현 환경에서 `DATABASE_URL_REMOTE` 직접 연결은 15초 timeout이지만, 실패 시에도 `portal-feedback.json` error payload가 생성되는 것을 확인했다.
- `portal_notice_collect.mjs`도 `node --check`와 `--help`가 통과했다. 현 환경에서 `DATABASE_URL_REMOTE` 직접 연결은 15초 timeout이지만, 실패 시에도 `portal-notices.json` error payload가 생성되는 것을 확인했다.
