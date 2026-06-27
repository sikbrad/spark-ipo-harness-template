---
name: notion-task
description: Notion **Task DB**(Quick My Ocean / GQsReach)에 **할일·태스크** 등록. "할일 추가", "태스크 만들어줘", "노션에 할일", "Task DB에 추가", "노션 태스크" 등 "**할일**" 또는 "**태스크**" 단어가 들어간 경우에만 사용. **"캘린더"가 들어가면 `/gcal`로 라우팅**. **"일정"만 있고 모호하면 반드시 사용자에게 캘린더인지 노션 태스크인지 1줄로 물어볼 것** — 추측 금지.
---

# Notion Task DB 할일 등록

GQsReach 워크스페이스의 **Task DB** (`71c69a38…`)에 새 태스크 페이지 생성. 기본 템플릿 `tk-bdda3e4b…`의 본문 블록을 함께 복사한다.

## 키워드 분기 (중요)

이 스킬은 캘린더 스킬(`/gcal`)과 짝을 이룬다. 어느 쪽인지 명확하지 않으면 추측하지 말고 1줄로 묻는다.

| 사용자 표현 | 라우팅 |
|---|---|
| "할일", "태스크", "task", "Task DB", "노션에 ~ 추가" | **이 스킬** |
| "캘린더", "구글캘", "gcal", "구글 캘린더" | `/gcal` |
| "일정" (단독, 다른 단서 없음) | **사용자에게 질문**: "캘린더(gcal) / 노션 태스크 어느 쪽?" |

## 사용

```bash
python proc/lib/notion_task.py "강호남 점심" \
  --start 2026-05-28T12:00:00+09:00 \
  --end   2026-05-28T14:00:00+09:00
```

옵션:
- `--start` / `--end` — TimeSpan. start만 = 시점, end까지 = 구간.
- `--due` — DueDate (마감일).
- `--act` — ActDate (실제 실행일).
- `--task-type` — `Task` (default) / `Project` / `Chore`.
- `--status` — `Ready` (default) / `Todo` / `Doing` / `Wait` / `Schedule` / `Done` / `Close` / `Someday`.
- `--impact` — `⭐` / `⭐⭐` / `⭐⭐⭐`.
- `--template <id>` — 템플릿 페이지 ID (default: `bdda3e4b-2727-49a0-adc9-e15a7c1b2c26`).
- `--no-template` — 템플릿 본문 복사 생략.

Python에서 직접:
```python
import sys; sys.path.insert(0, "proc/lib")
from notion_task import create_task
res = create_task("강호남 점심",
                  time_span=("2026-05-28T12:00:00+09:00",
                             "2026-05-28T14:00:00+09:00"))
print(res["url"])
```

## 동작 순서

1. `POST /pages` — `parent.type=data_source_id`, properties (명칭/TimeSpan/TaskType/Status, optionally DueDate·ActDate·Impact).
2. 템플릿 본문 블록 재귀 fetch → sanitize → `PATCH /blocks/{new_id}/children`.
3. **Sanitize 규칙**:
   - `unsupported`, `child_database`, `child_page` 타입은 제외 (Notion API에서 create 불가).
   - 모든 `null` 값을 재귀적으로 제거 (예: `paragraph.icon: null` 거부됨 → key 자체를 빼야 함).
   - block-payload의 `children` key를 한 번 제거 후, has_children=True면 재귀 fetch한 결과를 다시 끼워 넣음.

## 시간 표현

- 한국 시간(KST)이면 ISO 끝에 `+09:00` offset. Notion이 시청자 timezone으로 자동 변환.
- 시간 없이 날짜만이면 `2026-05-28` 형식.

## 키 ID

| 객체 | ID |
|---|---|
| Task DB        | `71c69a38-772b-4ea0-b9e6-0bb23f64ac7c` |
| Data source    | `312bfde5-d1da-4f7d-94a6-b73c912eb042` |
| 기본 템플릿 (tk) | `bdda3e4b-2727-49a0-adc9-e15a7c1b2c26` |

## DB 속성 명칭 (User-settable)

| 속성 | 타입 | 비고 |
|---|---|---|
| 명칭 | title | 페이지 제목 |
| TimeSpan | date range | 시작·종료 (시간 포함 가능) |
| DueDate | date | 마감 |
| ActDate | date | 실제 실행 |
| TaskType | select | Project / Task / Chore |
| Status | status | Ready / Todo / Doing / Wait / Schedule / Done / Close / Someday |
| Impact | select | ⭐ / ⭐⭐ / ⭐⭐⭐ |
| URL | url | 외부 링크 |
| 목표수치 / 현재수치 / 초기수치 | number | 진척률 계산용 |

Formula/relation 속성(Child, Parent, NextTask, PrevTask, Areas, Documents, 달성률, TimeAnalysis, DueRemainDays, ng)은 create 시 건드리지 않음.

## 의존성

- `proc/lib/notion_api.py` — `NotionClient` (REST + 429 backoff).
- `proc/lib/notion_auth.py` — OAuth 토큰 캐시 (`~/.cache/dof-notion/token.json`) 또는 `.env`의 `NOTION_INTEG_ACCESS_TOKEN_*`.
- 첫 인증: `python proc/lib/notion_auth.py login`.
