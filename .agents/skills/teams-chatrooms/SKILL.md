---
name: teams-chatrooms
description: Microsoft Teams 내가 속한 모든 채팅방(DM·그룹·회의) **목록**을 한 번에 dump하여 마크다운 파일(기본 `data/teams/chatrooms_list.md`)로 저장. MS Graph `/me/chats` + `$expand=members,lastMessagePreview`. "내 팀즈 채팅방 목록", "DM/그룹 한 번에 정리", "Teams chatroom 목록 마크다운으로 저장", "내가 속한 모든 채팅방 dump", "팀즈 그룹채팅 멤버 누구있어", "chat_id 빠른 참조표" 등 채팅방 **목록·디렉토리** 요청 시 사용. (개별 채팅 **본문**은 `/teams-chat`, 미답·@멘션 분석은 `/teams-activity`)
---

# Microsoft Teams 채팅방 목록 dump

내가 속한 모든 채팅방을 한 번에 받아서 마크다운으로 정리한다. 누가/어떤 그룹과 대화 중인지 한 눈에 보고 싶을 때, 또는 chat_id를 빠르게 찾을 때 사용.

## 도구
- `proc/lib/msgraph.py` — `GraphClient` (MSAL device-code, 토큰 캐시 공유)
- `proc/lib/teams_graph.py` — `_kst`, `_strip_html` 유틸
- `.Codex/skills/teams-chatrooms/dump_chatrooms.py` — 본 스킬 entrypoint

## 전제
- `/teams-chat` 스킬과 동일한 인증 (`MSFT_MYAGENT_CLIENT_ID/TENANT_ID` + `python3 proc/lib/msgraph.py login` 1회).
- `Chat.Read` 권한이면 충분 (전송 X, 읽기 only).

## 표준 호출

```bash
# 기본: data/teams/chatrooms_list.md 로 저장
python3 .Codex/skills/teams-chatrooms/dump_chatrooms.py

# 다른 경로
python3 .Codex/skills/teams-chatrooms/dump_chatrooms.py --out output/teams_chats_2026-05.md

# 마크다운 + 원본 JSON 동시 저장
python3 .Codex/skills/teams-chatrooms/dump_chatrooms.py --json data/teams/chatrooms_list.json
```

## 출력 구조

1. **DM (1:1)** — 표 형식 (`상대 / 이메일 / 마지막 발신자 / 시각 / by_me`)
2. **그룹 채팅** — 방마다 멤버 수·전체 멤버·마지막 메시지·`chat_id`
3. **회의 채팅** — Teams 회의에서 자동 생성된 chat (멤버 다수일 수 있어 15명까지만)
4. **부록: chat_id 빠른 참조** — 한 줄 요약표 (DM/그룹/회의 모두)

정렬: 모든 섹션 모두 **최근 메시지 시각 내림차순**.

## ⚠️ 함정

- `$top` 상한 **50** — Graph 강제. 본 스킬은 `g.paged()`로 자동 페이지네이션 (102개+ OK).
- DM의 `name`(=`topic`)은 항상 비어있음 → `members`에서 본인 제외한 사람을 `partner`로 추출.
- DM 멤버가 비어있는 경우 (외부/탈퇴 계정): `(unknown)`으로 표기.
- `kind`: Graph는 `oneOnOne | group | meeting` — 본 스킬도 그대로 따름. (`teams-chat`의 `chat_list()`도 동일)
- 회의 채팅은 참가자 수십 명 일 수 있어 멤버 표기 15명 cap.

## 다른 Teams 스킬과의 분리

| 스킬 | 용도 |
|---|---|
| **`/teams-chatrooms`** (본 스킬) | 모든 채팅방 **목록**을 마크다운으로 dump |
| `/teams-chat` | 특정 채팅방 **본문** 조회·전송·수정·삭제 |
| `/teams-activity` | DM 미답·@멘션 분석 (휴리스틱) |
| `/teams-channel` | 채널(팀) 게시물 (chat과는 다른 자료구조) |

본 스킬의 출력에서 `chat_id`를 복사해 `/teams-chat`에 넣으면 본문 조회로 자연스럽게 이어진다.
