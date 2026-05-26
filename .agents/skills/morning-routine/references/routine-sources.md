# Routine Sources

## Rule

`kmsg` / KakaoTalk is excluded from both morning and night routines.

## Morning vs Night

| Source | Morning | Night |
|---|---|---|
| DailyJot -> Tasks | run first | may rerun/check result |
| Notion dump | read recent summaries; avoid heavy dump unless needed | incremental dump |
| Teams activity/chat/channel | action triage | full day raw collection via `daily-collect` |
| kubit Slack conversations | light recent check/cache | incremental/full collect |
| kubit people | read only if needed | update with `collect:people` |
| Google Calendar | today/tomorrow planning | archive day events |
| Gmail | response triage | archive day mail |
| Outlook | response triage | archive day mail |
| Jira/Confluence | current work and blockers | archive day activity |
| Google Drive | meeting/task supporting docs | archive modified files |
| OneDrive/SharePoint | supporting docs when linked from work | archive modified/relevant docs |
| Raindrop | only urgent revisit items | dump; infer when useful |
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
raw/gcal-*.json
raw/gmail-*.json
raw/outlook.json
raw/gdrive-*.json
raw/atlassian.json
raw/raindrop.json
raw/voice-*.txt
summary.md
```
