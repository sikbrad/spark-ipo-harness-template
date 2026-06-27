---
name: backfill-empty-areas
description: Notion Task DB / Note DB에서 **Areas relation이 비어 있는** 페이지만 골라 Area를 부여한다. Area 매핑은 **LLM이 각 Area의 콘텐츠와 각 페이지의 title/body를 직접 읽고 의미적으로 판단** (키워드 매칭 절대 금지). Area 상태가 `Closed`인 것은 후보에서 제외. **이미 Area가 부여된 페이지는 절대 건드리지 않음** (재실행 시에도 idempotent). "노션 area 비어있는 거 채워줘", "Task/Note area 부여", "backfill area", "빈 area 메꿔줘" 등의 요청 시 사용.
---

# Notion Empty-Area Backfill

Task DB / Note DB에서 Areas relation이 빈 페이지만 골라 Area를 부여한다.

## 주의사항 (사용자 명시, 절대 위반 금지)

1. **Areas가 이미 부여된 페이지는 절대 건드리지 않는다.**
   - discover 단계 필터(`Areas is_empty` 또는 `relation_empty`)가 1차 가드.
   - push 단계에서 PATCH 직전에 페이지를 재조회하여 Areas가 여전히 빈 경우에만 PATCH (idempotent guard). 재실행해도 안전.
2. **Area 후보는 상태 `Closed`만 제외.** To-do / In progress(Responsible, Occasional) 상태는 모두 사용 가능.
3. **Area 매핑은 LLM 의미 판단.** 코드 키워드 매칭 / `if "회사" in title` 같은 휴리스틱 금지.
4. **plan 문서 작성하며 진행.** 판단 근거(각 페이지 → area, 이유)를 mapping.json `reason` 필드에 적어 사람이 추적 가능하게.

## 진행 흐름

### Step 1 — discover
빈-Area Task / Note + 활성 Area 목록 수집.

참조 구현: [proc/plan/backfill_areas_2026-05-19_discover.py](../../../proc/plan/backfill_areas_2026-05-19_discover.py)

```bash
python proc/plan/backfill_areas_<date>_discover.py
# → backfill_areas_<date>.candidates.json
#   { tasks: [...], notes: [...], areas: [{id,name,status}] }
```

필터:
- Task ds `312bfde5…`: `Areas` relation 비어있는 행
- Note ds `06f18917…`: `Areas` relation 비어있는 행
- Area ds `8a64fd60…`: 상태 ≠ `Closed`

각 후보 페이지의 본문 excerpt(800자)도 함께 dump 해 LLM이 의미 판단할 때 단서로 쓴다.

### Step 2 — Area 성격 파악
각 후보 Area의 page를 retrieve해서 그 Area에 연결된 Tasks/Documents 6~8건 sample. 또는 [proc/plan/daily-jot-to-tasks-2026-05-19.md](../../../proc/plan/daily-jot-to-tasks-2026-05-19.md)의 Area 성격 요약 재사용.

대표 Area 성격:
| Area | 의미 |
|---|---|
| DOF | 디오에프(현 회사) 업무 — CRM, 거래원장, 사내 세미나 |
| Productivity | 개인 생산성 도구 활용 (노션, 워크스페이스) |
| Lecturing | 외부 강의/강연 (바이브코딩, 벤처경영, 책, 슬라이드) |
| Career | 커리어 — 이전 직장(카카오 GeoAI/DAM/LiDAR), 학계 협업, 외부 인맥 |
| SelfAdmin(자기관리) | 개인 행정/건강/계정 |
| Home(부부) | 부부 일상, 아내, 자녀/임신 |
| Family(고향) | 본가 |
| ProgMaster | 프로그래밍 마스터 (학습/스킬) |
| Kamo, Musician, ProPar, ConvBoard, Suited, WHYQ, TANKMON, Uncategorizable, RealEstate, Artisan | 그 외 영역 (각자 콘텐츠 확인) |

### Step 3 — mapping.json 작성 (LLM 의미 판단)
```jsonc
{
  "_meta": { "act_date": "YYYY-MM-DD", "area_descriptions": {...} },
  "tasks": [
    {
      "id": "<page id>",
      "title": "<title>",
      "area_page_id": "<area page id>",
      "area_name": "<area name>",
      "reason": "<why 이 area인지>"
    }
  ],
  "notes": [
    { "id": "...", "title": "...", "area_page_id": "...", "area_name": "...", "reason": "..." }
  ]
}
```

판단 모호하면 `Uncategorizable`로 두고 reason에 그 사실을 남김 (사용자가 나중에 재분류).

### Step 4 — push
참조 구현: [proc/plan/backfill_areas_2026-05-19.py](../../../proc/plan/backfill_areas_2026-05-19.py)

```bash
python proc/plan/backfill_areas_<date>.py --dry-run   # 먼저 검수
python proc/plan/backfill_areas_<date>.py             # 실제 PATCH
```

각 페이지 PATCH 직전에:
1. `GET /pages/{id}` 재조회
2. `properties.Areas.relation`이 비어있을 때만 PATCH 실행
3. 이미 차있으면 `skipped_has_area`로 기록 후 건너뜀

PATCH 페이로드:
```json
{ "properties": { "Areas": { "relation": [{"id": "<area_page_id>"}] } } }
```

결과는 `.result.json`에 dump.

## 키 ID

| 객체 | ID |
|---|---|
| Task DB | `71c69a38-772b-4ea0-b9e6-0bb23f64ac7c` |
| Task ds | `312bfde5-d1da-4f7d-94a6-b73c912eb042` |
| Note ds | `06f18917-50a8-4d73-979f-b13a8c63f754` |
| Area DB | `e71a7b62-a9fa-4a34-b5cf-1e5af5826d8e` |
| Area ds | `8a64fd60-124c-4ca0-9ab9-b10a4e4131ce` |

## Area 상태 (참고)

`상태` (status) options: `Todo`, `Responsible`, `Occasional`, `Closed`
Group: `To-do` = [Todo] / `In progress` = [Responsible, Occasional] / `Complete` = [Closed]

**이 스킬은 Closed만 후보에서 제외** (Todo, Responsible, Occasional 모두 사용 가능).
[daily-jot-to-tasks](../daily-jot-to-tasks/SKILL.md)와 정책이 다르니 주의 — daily-jot은 In-progress(Responsible/Occasional)만 사용.

## 참조

- [proc/plan/2026-05-19_backfill-area-empty-tasks-notes.md](../../../proc/plan/2026-05-19_backfill-area-empty-tasks-notes.md) — 첫 실행 plan + 판단 근거
- [daily-jot-to-tasks](../daily-jot-to-tasks/SKILL.md) — 유사한 mapping.json 외부화 패턴
- [notion-task](../notion-task/SKILL.md) — Task DB 스키마 & 키 ID
