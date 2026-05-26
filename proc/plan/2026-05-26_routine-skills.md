# 2026-05-26 Morning/Night Routine Skills

## Goal

Create two orchestration skills:

- `morning-routine`: turn current signals into a prioritized day brief.
- `night-routine`: collect and archive the day into `data/daily/<YYYY-MM-DD>/`.

## Decisions

- Exclude `kmsg` from both routines.
- Allow `night-routine` to re-collect sources also used by `morning-routine`.
- Prefer existing source skills and scripts over new implementation code.
- Keep kubit Slack collection in the sibling workspace:
  `/Users/gq/works/lecture/kubit/kubit-bitbot-slack-01`.
- Add Notion Task DB reads to both routines.
- Add Teams standup to both routines. There is no dedicated standup skill folder in this workspace today; use `teams-channel` or `data/daily/<date>/raw/teams-standup.json` until one exists.

## Source Placement

### Morning

- `daily-jot-to-tasks`: convert DailyJot items into Notion tasks/notes.
- Notion Task DB: read today/overdue/Doing/Ready/Wait tasks for planning.
- `teams-activity`, `teams-chat`, `teams-channel`: unanswered DMs, mentions, important threads.
- Teams standup: if morning standup is missing, propose content from Jot, Task DB, calendar, and previous next actions.
- kubit Slack light check: recent cached conversations / incremental conversation collect when needed.
- `gcal`, `gmail`, `outlook`: meetings, mail that needs response, links.
- `daily-collect` previous summaries: carry forward unresolved next actions.
- `daily_atlassian.py`: Jira/Confluence current work signals.
- `amaranth-approval`, `amaranth-calendar`, `amaranth-resource`: approval/schedule/resource checks when relevant.

### Night

- Voice transcripts into `data/daily/<date>/raw/voice-*.txt` first.
- `daily-collect`: full raw source collection and `summary.md`.
- Repeat morning sources as needed for complete archival.
- Re-read DailyJot and Notion Task DB to classify completed/progress/unfinished work.
- Compare Teams standup morning plan and evening recap against Jot/Task DB.
- kubit Slack full/incremental conversation collection and people update.
- `notion-dump`, `raindrop`, `raindrop-infer`, and bounded `raindrop-retag` for untagged bookmarks.
- `chatgpt`, `gdrive`, `onedrive`, `sharepoint` as end-of-day archival inputs.
- `amaranth-people` only as optional/periodic, not required every night.

## Implementation

- Add `.agents/skills/morning-routine/SKILL.md`.
- Add `.agents/skills/night-routine/SKILL.md`.
- Add shared source routing reference:
  `.agents/skills/morning-routine/references/routine-sources.md`.
- Link the night skill to the same reference.
- Update `CLAUDE.md` skill table.

## Verification

- Confirm new skill frontmatter exists and names match folder names.
- Confirm `kmsg` is not present in routine source lists except as an explicit exclusion.
- Confirm Notion Task DB and Teams standup are present in both routines.
- Confirm night routine includes untagged Raindrop retagging.
- Confirm `CLAUDE.md` lists both skills.
