# 2026-06-05 Night Routine

## Scope

- 기준일: `2026-06-05` Asia/Seoul.
- 목적: 하루 raw 수집, Jot/Task/standup 판정, kubit/Raindrop/Area 정리, `summary.md` 작성.
- 제외: KakaoTalk/kmsg, 외부 게시/메시지 전송.

## Plan

1. `data/daily/2026-06-05/raw/`를 준비하고 source error 기록을 시작한다.
2. Notion DailyJot/Task DB live snapshot을 수집한다.
3. Teams standup/chats/channels, Google Calendar/Gmail, Outlook, Atlassian, Amaranth approval을 수집한다.
4. kubit Slack conversation/people cache를 갱신한다.
5. voice/audio 후보를 확인하고, 실제 원본이 있으면 전사한다.
6. Raindrop dump/infer/untagged retag를 제한적으로 실행한다.
7. empty Areas 후보를 확인하고 필요하면 backfill 흐름을 실행한다.
8. raw를 읽어 `data/daily/2026-06-05/summary.md`를 작성한다.

## Progress

- Raw directory prepared: `data/daily/2026-06-05/raw/`.
- Main daily raw collection completed with 5 initial source errors.
- kubit `collect:conv` and `collect:people` completed; Slack scope gap remains.
- Amaranth pending approval checked: 0 docs.
- Raindrop infer limited run completed: 20 processed, 19 ok, 1 failed; no eligible retag target.
- Empty Areas discover found 1 placeholder Task; patched to `Uncategorizable`.
- `data/daily/2026-06-05/summary.md` written.
