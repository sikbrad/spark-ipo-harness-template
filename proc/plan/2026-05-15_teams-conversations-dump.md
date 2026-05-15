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
- 저장 규모: DM/그룹채팅 102개, 채팅 메시지 28,843건, 채널 conversation 27개, 채널 메시지 3,016건.
- Graph 504 반복으로 재시도 대상인 채널: `DOF Inc. / noti-order`, `DOF Inc. / General`, `DOF Inc. / 영업부`.
- 2026-05-15 11:53 재시도: `영업부`는 성공 상태 유지, `noti-order`와 `General`은 Graph 504/429 반복으로 계속 재시도 대상.
