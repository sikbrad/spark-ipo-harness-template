# Routine Sources

## Rule

`kmsg` / KakaoTalk is excluded from both morning and night routines.

## Morning vs Night

| Source | Morning | Night |
|---|---|---|
| DailyJot -> Tasks | run first | may rerun/check result |
| Notion Task DB | today, overdue, Doing/Ready/Wait tasks for planning | completed/progress/unfinished review |
| Task/Note empty Areas | no, unless explicitly asked | run `backfill-empty-areas` after Notion review; only empty `Areas` relation pages |
| Notion dump | read recent summaries; avoid heavy dump unless needed | incremental dump |
| Teams standup | check whether today's morning standup exists; propose content if missing | compare morning plan and evening recap against Jot/Task DB |
| Teams activity/chat/channel | action triage | full day raw collection via `daily-collect` |
| kubit Slack conversations | light recent check/cache | incremental/full collect |
| kubit people | read only if needed | update with `collect:people` |
| Google Calendar | today/tomorrow planning | archive day events |
| Gmail | response triage | archive day mail |
| Outlook | response triage | archive day mail |
| Jira/Confluence | current work and blockers | archive day activity |
| Portal Feedback | active feedback/blocker spot-check | archive day feedback, notifications, and active snapshot as AX/user work signal |
| Portal Notices / Release Notes | latest release/maintenance notice spot-check if relevant | archive day notices, release notes, and published notice snapshot as AX/user work signal |
| Google Drive | meeting/task supporting docs | archive modified files |
| OneDrive/SharePoint | supporting docs when linked from work | archive modified/relevant docs |
| Raindrop | only urgent revisit items | dump; infer when useful; retag untagged bookmarks first |
| ChatGPT export | no, unless user asks | optional archival source |
| Amaranth approval | pending approvals | pending/processed approvals if relevant |
| Amaranth calendar/resource | schedule/resource checks | archive if relevant |
| Amaranth people | no | optional periodic people sync |

## kubit Slack Workspace

Path:

```text
/Users/gq/works/lecture/kubit/kubit-bitbot-slack-01
```

Useful commands:

```bash
npm run collect:conv
npm run collect:conv:dm
npm run collect:people
node src/collect-conversations.js --no-render
```

Important outputs:

```text
data/_conversations-index.json
data/_channel-cache/
data/_dm-cache/
data/_mpim-cache/
data/people/<person>/activity/
data/people/<person>/conversations/
data/people/<person>/future_self/
data/people/<person>/weekly_report/
```

## startpoint Daily Archive

Path:

```text
data/daily/<YYYY-MM-DD>/
```

Expected files:

```text
raw/notion-jot.json
raw/notion-edited.json
raw/teams-chats.json
raw/teams-channels.json
raw/teams-standup.json
raw/gcal-*.json
raw/gmail-*.json
raw/outlook.json
raw/gdrive-*.json
raw/atlassian.json
raw/portal-feedback.json
raw/portal-notices.json
raw/raindrop.json
raw/voice-*.txt
summary.md
```

## Portal Feedback

Night routine collects portal feedback with:

```bash
node proc/lib/portal_feedback_collect.mjs <YYYY-MM-DD>
```

Known daily raw path:

```text
data/daily/<YYYY-MM-DD>/raw/portal-feedback.json
```

Interpretation rule:

```text
포탈 Feedback은 AX팀이 작업한 포탈 업무 입력이므로, 나이트루틴 summary에서는 사용자/회사 업무 기록과 같은 신호로 취급한다.
```

The raw includes daily created/updated/notified feedback, current active feedback, and FEEDBACK notifications. If it fails, keep the rest of the routine running and record the failure in the daily summary.

## Portal Notices / Release Notes

Night routine collects portal notices and release notes with:

```bash
node proc/lib/portal_notice_collect.mjs <YYYY-MM-DD>
```

Known daily raw path:

```text
data/daily/<YYYY-MM-DD>/raw/portal-notices.json
```

Interpretation rule:

```text
포탈 공지사항의 릴리즈노트는 AX팀이 배포/운영한 산출물이므로, 나이트루틴 summary에서는 사용자/회사 업무 기록과 같은 신호로 취급한다.
```

The raw includes daily created/updated notices, a release-note snapshot, and currently published notices. If it fails, keep the rest of the routine running and record the failure in the daily summary.

## Notion Task DB

Task DB:

```text
71c69a38-772b-4ea0-b9e6-0bb23f64ac7c
```

Task data source:

```text
312bfde5-d1da-4f7d-94a6-b73c912eb042
```

Important properties:

```text
명칭, Status, ActDate, DueDate, Areas
```

Relevant statuses:

```text
Ready, Todo, Doing, Wait, Schedule, Done, Close, Someday
```

Morning reads Task DB for planning. Night reads Task DB for completion/progress review. Do not auto-update statuses unless the user explicitly asks.

## Teams Standup

Known daily raw path:

```text
data/daily/<YYYY-MM-DD>/raw/teams-standup.json
```

Known channel name from collected raw:

```text
standup-daily-ax
```

Use a dedicated standup skill/script if one appears later. Otherwise use `teams-channel` to fetch the channel thread/replies, or read the existing daily raw file.

## Raindrop Untagged Policy

Night routine should prioritize raindrops with empty `tags`:

```text
data/raindrop/dump/raindrops/<id>.json
```

Selection rule:

```python
not (raindrop.get("tags") or [])
```

Process:

1. Run `raindrop_dump.py dump`.
2. Run `raindrop_infer.py run`.
3. Select untagged ids from local dump.
4. Run `raindrop_retag.py run --id <id>` for a bounded batch.

Do not use `--force` or retag already-tagged bookmarks unless the user explicitly asks.
