# Teams 전체 대화 덤프

## 목표
내가 접근 가능한 Teams DM, 그룹 채팅, 팀/채널 게시물을 원본 JSON과 Markdown으로 `output/teams/conversations/` 아래 분류 저장한다.

## 작업 항목
- [x] Claude Teams skills와 기존 Graph helper 확인
- [x] 전체 페이지네이션 기반 덤프 스크립트 작성
- [x] SQLite 상태 DB 기반 증분 추출 설계 반영
- [x] rate limit/timeout 실패 항목은 완료 마킹하지 않아 다음 실행에서 재시도되는지 검토
- [ ] DM, groupchat, teams 분류별 raw JSON 및 Markdown 출력
- [ ] Graph 인증/실행 검증
- [ ] 결과 파일과 남은 한계 보고
