# Teams 전체 대화 수집 및 나이트루틴

## 목표
오늘 새로 초대된 Teams 채팅방이 누락되지 않도록 채팅방 목록을 최신화하고, Teams 대화 기록을 가능한 처음부터 로컬 아카이브에 반영한 뒤 2026-06-08 나이트루틴 raw/summary를 작성한다.

## 작업 항목
- [x] 최신 Teams 채팅방 목록을 `data/teams/chatrooms_list.*`에 dump
- [x] 기존 아카이브와 최신 채팅방 목록을 비교해 신규/누락 채팅방 확인
- [x] DM/그룹/회의 채팅 본문을 처음부터 재수집해 `output/teams/conversations/` 갱신
- [x] Teams 채널/팀 게시물 아카이브를 증분 갱신하고 실패 항목 기록
- [x] 나이트루틴 수집 소스 실행 및 실패 항목을 `source-errors.json`에 기록
- [ ] `data/daily/2026-06-08/summary.md` 작성 또는 갱신
- [ ] 수집 결과와 검증 근거 확인
