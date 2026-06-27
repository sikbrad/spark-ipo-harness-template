# Teams 전체 대화 덤프

## 목표
내가 접근 가능한 Teams DM, 그룹 채팅, 팀/채널 게시물을 원본 JSON과 Markdown으로 `output/teams/conversations/` 아래 분류 저장한다.

## 작업 항목
- [x] Claude Teams skills와 기존 Graph helper 확인
- [x] 전체 페이지네이션 기반 덤프 스크립트 작성
- [x] SQLite 상태 DB 기반 증분 추출 설계 반영
- [x] rate limit/timeout 실패 항목은 완료 마킹하지 않아 다음 실행에서 재시도되는지 검토
- [x] 채널 reply 단위 실패를 `_replyFetchError`로 저장하고 다음 실행에서 해당 thread를 재시도하도록 보완
- [x] DM, groupchat, teams 분류별 raw JSON 및 Markdown 출력
- [x] Graph 인증/실행 검증
- [x] 결과 파일과 남은 한계 보고

## 결과
- 출력 경로: `output/teams/conversations/`
- 상태 DB: `output/teams/conversations/_state.sqlite3`
- 저장 규모: DM 58 / 그룹채팅 44 (chat 메시지 28,905건), 팀 4 / 채널 29 (thread 3,441 / reply 2,934).
- Graph 504 반복으로 재시도 대상인 채널: `DOF Inc. / noti-order`, `DOF Inc. / General`, `DOF Inc. / 영업부`.
- 2026-05-15 11:53 재시도: `영업부`는 성공 상태 유지, `noti-order`와 `General`은 Graph 504/429 반복으로 계속 재시도 대상.
- 2026-05-15 15:10 원인 확인 및 해결: `DOF Inc. / General`은 `$top=50` skiptoken에서 Graph 504가 반복됐고, `$top=20`으로 낮추면 root pagination이 완료됨. reply는 N+1 호출 대신 `$expand=replies`로 받아 저장 완료(root 697 / replies 611, 2018-07-24까지).
- 2026-05-16 00:06 전체 재실행(`--expand-replies --channel-page-size 20 --reply-refresh-threads 25`): 102 chat / 29 channel 모두 성공, `chat_errors`/`team_errors` 0, `_replyFetchError` 잔여 0. `noti-order` 포함 모든 4팀 정상 완료.
