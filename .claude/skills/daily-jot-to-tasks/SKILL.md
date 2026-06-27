---
name: daily-jot-to-tasks
description: 오늘(또는 지정 날짜) Notion Jot DB의 DailyJot 페이지에서 체크박스(할일)와 bullet(생각)을 뽑아 Task DB에 Task / Note DB에 Note로 등록한다. Area는 **AI가 각 Area의 콘텐츠를 직접 보고 의미적으로** 매핑 (키워드 매칭 절대 금지). 1주일 내 비슷한 Task가 이미 있으면 그 페이지를 link로 끌어오고 '끌올' 텍스트를 붙인다. 원본 Jot 블록 끝에는 노션 page-mention chip 부착. "데일리좃 보고 태스크 만들어", "오늘 메모에서 할일 만들어", "jot to tasks", "daily-jot-to-tasks" 등의 요청 시 사용.
---

# DailyJot → Task/Note Auto-Registration

오늘(또는 임의 날짜)의 DailyJot 페이지를 읽고 체크박스/bullet을 Task DB / Note DB에 등록한다.
**Area 매핑은 LLM이 직접 판단**(코드 키워드 매칭 금지). 매핑은 외부 JSON에 적어 단순 push.

## 핵심 룰
1. **체크박스 1개 = Task 1개**. 체크박스 하위의 bullet/체크박스는 그 Task의 body에 `bulleted_list_item`으로 embed (별도 Task/Note 만들지 않음).
2. **bullet (체크박스 아닌 것, 체크박스 하위도 아닌 것) = 생각** → Note DB. 다만 actionable 동사가 강하면 사용자에게 확인.
3. **Task title은 반드시 `ts ` prefix**, **Note는 없음**.
4. **Task body는 `tk` 템플릿 (`bdda3e4b-2727-49a0-adc9-e15a7c1b2c26`)** 본문 복사 (notion_task.py 기본).
5. **Area는 상태 `In progress` (group: Responsible / Occasional) 인 것만 사용.** Closed/Todo는 후보 제외.
6. **Area 매핑은 LLM 판단**:
   - 후보 Area 각각의 실제 Tasks/Documents 6~8건씩 sample → 성격 파악
   - 한 Jot 항목이 어느 Area에 속하는지 의미적으로 결정
   - 결과는 plan/mapping에 근거와 함께 기록
   - **키워드 사전·`if "회사" in title` 같은 코드 절대 금지**
7. **ActDate** = Jot 항목에 명시된 날짜 (없으면 Jot 페이지 생성일자)
8. **링크는 노션 page-mention chip** (`{type:"mention", mention:{type:"page", page:{id}}}`) — text-link / preview / embed 아님.
9. **1주일 내 비슷한 Task가 있으면 그걸 끌올**:
   - 처리 전, Task DB에서 `Created time ∈ [today-7d, today)` 인 Task 목록을 조회
   - LLM이 직접 (코드/키워드 아님) 의미적으로 비교하여 dup 후보 판단
   - dup이면 새 Task 만들지 말고 mapping의 해당 task 항목에 `existing_task_id: <past_task_id>` 적기
   - 스크립트는 그 항목을 보고: 생성 skip → Jot 블록에 page-mention chip + " 끌올" 일반텍스트 append
10. **plan 문서 작성하면서 진행** — 판단 근거(샘플링 결과 / dup 판단 이유)를 사람이 추적 가능하게 남길 것.

## 진행 흐름

### Step 1 — Jot 페이지 찾기 & dump
```python
# Jot DB: d16ebd32-1285-43a8-a9c1-355a91ab782b
# data source: 6c6fb239-012d-47e8-a20f-c614cb01fc0d
# Filter: 시작일자 == <YYYY-MM-DD>
```
페이지 본문 트리를 dump해서 체크박스/bullet과 hierarchy를 파악.

### Step 2 — Area 후보 추리기 (In-progress only)
```python
# Area DB: e71a7b62-a9fa-4a34-b5cf-1e5af5826d8e
# data source: 8a64fd60-124c-4ca0-9ab9-b10a4e4131ce
# 상태(status) options:
#   Todo, Responsible, Occasional, Closed
# 상태 group:
#   To-do      : [Todo]
#   In progress: [Responsible, Occasional]   ← 사용
#   Complete   : [Closed]
```
In-progress 17개를 후보로 좁힘. 각 Area를 `pages.retrieve` 한 뒤 연결된 Tasks/Documents 6~8건씩 sample → AI가 직접 읽고 영역 성격 정리.

### Step 3 — 1주일 dup 후보 수집
```python
# Task DB ds: 312bfde5-d1da-4f7d-94a6-b73c912eb042
# Filter: Created time >= today-7d AND Created time < today
```
지난주 Task 제목·area·내용 일부를 LLM이 읽음 → 오늘 항목과 의미적으로 비교.

### Step 4 — mapping.json 작성
```jsonc
{
  "act_date": "YYYY-MM-DD",
  "tasks": [
    {
      "jot_block": "<jot block id>",
      "title": "ts <title>",
      "area_page_id": "<area page id>",
      // optional: 체크박스 하위 sub-bullet의 jot block ids → 이 Task body에 embed
      "embed_children": ["<child block id>", ...],
      // optional: 1주일 내 dup일 때 — 기존 task id. 적으면 생성 skip, 끌올 처리.
      "existing_task_id": "<past task id>"
    }
  ],
  "notes": [
    {
      "jot_block": "<jot block id>",
      "title": "<note title>",
      "area_page_id": "<area page id>",
      "type": "아이디어"  // Note DB 유형 옵션 중 하나
    }
  ]
}
```

### Step 5 — 스크립트 실행
참조 구현: [proc/plan/jot_to_tasks_2026-05-19.py](../../../proc/plan/jot_to_tasks_2026-05-19.py)

```bash
python proc/plan/jot_to_tasks_<date>.py proc/plan/jot_to_tasks_<date>.mapping.json
```

스크립트 동작:
- task → 신규 생성 (template + Areas + ActDate) → Jot block에 chip mention append → embed_children 처리
- task with `existing_task_id` → 신규 생성 skip → Jot block에 chip mention + " 끌올" 텍스트 append
- note → 신규 생성 → Jot block에 chip mention append

## 키 ID
| 객체 | ID |
|---|---|
| Jot DB | `d16ebd32-1285-43a8-a9c1-355a91ab782b` |
| Jot DS | `6c6fb239-012d-47e8-a20f-c614cb01fc0d` |
| Task DB | `71c69a38-772b-4ea0-b9e6-0bb23f64ac7c` |
| Task DS | `312bfde5-d1da-4f7d-94a6-b73c912eb042` |
| Task 템플릿 `tk` | `bdda3e4b-2727-49a0-adc9-e15a7c1b2c26` |
| Note DB | `57fc4d6e-2d7b-4162-8b4e-87c3e45d79cd` |
| Note DS | `06f18917-50a8-4d73-979f-b13a8c63f754` |
| Area DB | `e71a7b62-a9fa-4a34-b5cf-1e5af5826d8e` |
| Area DS | `8a64fd60-124c-4ca0-9ab9-b10a4e4131ce` |

## DB 속성

### Task DB (user-settable)
| 속성 | 타입 | 비고 |
|---|---|---|
| 명칭 | title | **`ts ` prefix 필수** |
| TimeSpan | date range | |
| DueDate | date | |
| ActDate | date | Jot 항목 날짜 (없으면 Jot 페이지 생성일) |
| TaskType | select | Task / Project / Chore — default Task |
| Status | status | default Ready |
| Impact | select | ⭐ / ⭐⭐ / ⭐⭐⭐ |
| Areas | relation → Area DB | **반드시 In-progress Area만** |

### Note DB (user-settable)
| 속성 | 타입 | 비고 |
|---|---|---|
| 명칭 | title | prefix 없음 |
| 유형 | select | 아이디어/미팅노트/리서치/방법개선안/메뉴얼/학습자료/정보조각/작업기록/궁금증·호기심/물증/하지않은말/강의기록/diary/단상/기회opportunities/외부공개링크있음/개선수요 |
| Impact | select | ⭐ / ⭐⭐ / ⭐⭐⭐ |
| Areas | relation → Area DB | In-progress 권장 |

## 의존성
- `proc/lib/notion_api.py` — NotionClient
- `proc/lib/notion_auth.py` — OAuth 토큰
- `proc/lib/notion_task.py` — `create_task()` (template 본문 복사 포함)

## 안티 패턴 (절대 금지)
- 코드에 `AREAS = {"DOF": "...", ...}` 같은 키워드 매핑 사전.
- `if "회사" in title: area = "DOF"` 류의 키워드 기반 분류.
- "회사", "업무", "개인" 같은 자연어 카테고리를 그대로 Area로 쓰기 (그건 Jot의 그룹 bullet — Area DB의 entry와 다름).
- Closed/Todo 상태 Area 사용.
- Task title에 `ts ` prefix 누락.
- 텍스트 하이퍼링크 / preview 링크 / embed 링크 (오직 page-mention chip).

## 사용자 검수
모든 작업 완료 후 **반드시 사용자에게 매핑 표와 검증 결과를 보고하고 확인 요청**. 자동 종결 금지.
