# Teams 전체 대화 수집 및 나이트루틴

## 목표
오늘 새로 초대된 Teams 채팅방이 누락되지 않도록 채팅방 목록을 최신화하고, Teams 대화 기록을 가능한 처음부터 로컬 아카이브에 반영한 뒤 2026-06-08 나이트루틴 raw/summary를 작성한다.

## 작업 항목
- [x] 최신 Teams 채팅방 목록을 `data/teams/chatrooms_list.*`에 dump
- [x] 기존 아카이브와 최신 채팅방 목록을 비교해 신규/누락 채팅방 확인
- [x] DM/그룹/회의 채팅 본문을 처음부터 재수집해 `output/teams/conversations/` 갱신
- [x] Teams 채널/팀 게시물 아카이브를 증분 갱신하고 실패 항목 기록
- [x] 나이트루틴 수집 소스 실행 및 실패 항목을 `source-errors.json`에 기록
- [x] `data/daily/2026-06-08/summary.md` 작성 또는 갱신
- [x] 수집 결과와 검증 근거 확인

## 검증 메모
- `data/daily/2026-06-08/raw/*.json` 25개 파싱 성공.
- `data/daily/2026-06-08/summary.md` 저장 확인.
- `output/teams/conversations/chatrooms.raw.json` 110개 채팅방 안에 신규 4개 채팅방 포함 확인.
- `output/teams/conversations/` raw JSON 190개 확인.
- 장기 Whisper 프로세스 종료 확인. 원본 오디오는 저장됐고 1개 transcript만 완료되어 `source-errors.json`에 부분 timeout 기록.
