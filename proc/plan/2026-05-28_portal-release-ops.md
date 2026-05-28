# 2026-05-28 Portal Release Ops

## 요청
- 포탈 DB 덤프 생성
- 포탈 공지: 13:00-13:20 서버점검, 주문사항 업데이트 안내
- 오늘 커밋 사항 확인 후 릴리즈노트 작성/공지
- 실주(주문취소) 등 DB 수정 필요 여부 확인, 필요 시 prod DB 반영
- master 브랜치 13:00 push
- Teams `init-crm-renew` 오늘 게시글 중 이번 수정으로 해결되는 내용에 친절한 댓글 작성

## 진행
- 12:56 KST: 포탈 repo `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az` 확인. `master...origin/master [ahead 7]`.
- 12:57 KST: 13:00 KST `git push origin master` 예약 실행 시작.
- 12:58 KST: prod DB dump 생성 완료. `output/db-dumps/20260528_125845_portal_prod.dump` (64,371,086 bytes).
- 13:02 KST: prod DB 확인. `OrderStatus` enum에 `CLOSED_LOST` 존재, `CLOSED_LOST` 주문 992건, `REJECTED` 견적 0건, `DataView` 내 `실주` 잔존 0건. 라벨 변경은 code-only/display-only라 DB 수정 없음.
- 13:03 KST: prod 공지 등록 완료. 점검 공지 ID `63` (`2026-05-28T04:00:00Z`~`04:20:00Z`, active readback 확인), 릴리즈노트 공지 ID `64` (`업데이트 안내 (2026-05-28)`, readback 확인).
- 13:00 KST: push hook build 통과 후 `master -> origin/master` push 완료 (`7e7995c3..10c6dfcb`).
- 13:02 KST: Teams `DOF Inc. / init-crm-renew` 오늘 스레드 2건 확인. `실주`/수금탭 정책 스레드에 댓글 작성 및 readback 확인 (`reply_id=1779940923906`). 용어 표기 해결과 수금탭 정책 미해결 범위를 구분해 안내.
