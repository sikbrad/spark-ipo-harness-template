# Notion Task/Note DB — Empty Area Backfill (2026-05-19)

## 목표
Notion Task DB (`71c69a38…`) / Note DB(ds `06f18917…`)에서 **Areas relation이 비어 있는** 페이지를 찾아 Area를 부여한다.

## 주의사항 (사용자 명시)
- **Areas relation이 비어 있는 페이지만 처리한다.** 이미 Area가 부여된 페이지는 절대 수정/추가/건드리지 않는다.
- discover 단계의 필터(`relation_empty(page, "Areas")`)가 1차 가드. push 단계에서도 mapping에 들어간 페이지만 PATCH 대상으로 한다 (idempotent re-run 시 이미 부여된 페이지는 처리 안 됨).
- Area 후보는 상태 `Closed`만 제외. To-do / In progress 상태 area는 모두 사용 가능.

## 핵심 원칙
1. **Area 분류는 LLM이 직접 콘텐츠를 보고 의미적으로 판단**. 키워드 매칭 코드 금지.
   - 각 후보 Area의 실제 Tasks/Documents 6~8건 sample → 성격 파악 (이미 [daily-jot-to-tasks-2026-05-19.md](daily-jot-to-tasks-2026-05-19.md)에 정리된 요약 재사용 가능).
2. **Area 후보는 상태 ≠ Closed 인 것만** (Done/Closed는 사용 금지).
   - In-progress(Responsible / Occasional)뿐만 아니라 To-do(Todo)도 일단 후보.
   - 사용자 지시: "area 는 done 인거는 무시" → Closed만 제외.
3. **DB 별 area property 명칭**:
   - Task DB: `Areas` (relation, multi)
   - Note DB: `Areas` (relation, multi)
4. **mapping.json 패턴 재사용**: AI가 [페이지 → area_page_id] 매핑을 사람-검증 가능한 JSON으로 외부화 → push 스크립트는 그 매핑만 따라간다.
5. **plan 문서 작성하며 진행**.

## 진행 흐름

### Step 1 — empty-Areas 후보 페이지 수집
- Task DB ds `312bfde5…` query (filter: Areas is_empty=true)
- Note DB ds `06f18917…` query (filter: Areas is_empty=true)
- 결과: `proc/plan/backfill_areas_2026-05-19.candidates.json` (id, title, type, body 요약, status, dates)

### Step 2 — Area 후보 정리 (Closed 제외)
- Area DB ds `8a64fd60…` query (filter: 상태 ≠ Closed)
- 결과: 각 area의 page_id, 명칭, 상태, group(In-progress / To-do)
- 콘텐츠 샘플 (각 area 연결 Tasks/Notes 6~8건씩) → 사람말 요약

### Step 3 — 매핑 (AI 의미 판단)
- 각 후보 페이지의 title + body excerpt 읽고 의미적으로 가장 부합하는 area 1개 선택
- 모호/판단불가는 mapping에 `reason` 적고 사용자 검수로 패스
- `proc/plan/backfill_areas_2026-05-19.mapping.json` 작성

### Step 4 — push
- `proc/plan/backfill_areas_2026-05-19.py` mapping.json 읽고 `PATCH /pages/{id}` 로 Areas relation 추가
- 결과 `.result.json`에 기록

### Step 5 — 스킬화
- `.claude/skills/backfill-empty-areas/SKILL.md` 작성
- CLAUDE.md 스킬 표에 추가

## 키 ID
| 객체 | ID |
|---|---|
| Task DB | `71c69a38-772b-4ea0-b9e6-0bb23f64ac7c` |
| Task ds | `312bfde5-d1da-4f7d-94a6-b73c912eb042` |
| Note DB | (확인 필요 — note ds `06f18917-50a8-4d73-979f-b13a8c63f754`) |
| Area DB | `e71a7b62-a9fa-4a34-b5cf-1e5af5826d8e` |
| Area ds | `8a64fd60-124c-4ca0-9ab9-b10a4e4131ce` |

## Area 상태 (재확인)
- Todo, Responsible, Occasional, Closed
- Group: To-do=[Todo] / In progress=[Responsible, Occasional] / Complete=[Closed]
- 이번 작업 후보: To-do + In progress (Closed만 제외)

## 진행 상황
- [x] Plan 문서 생성
- [x] empty-Areas 후보 페이지 수집 (Task 21 / Note 2)
- [x] 후보 Area 목록 정리 (Closed 제외 → 활성 18개)
- [x] AI 매핑 작성 ([backfill_areas_2026-05-19.mapping.json](backfill_areas_2026-05-19.mapping.json))
- [x] push 스크립트 dry-run → apply 성공 (tasks 21 + notes 2 모두 PATCH)
- [x] idempotent guard 검증 — 재실행 시 23건 전부 `skipped_has_area`
- [x] 스킬 `/backfill-empty-areas` 생성 ([.claude/skills/backfill-empty-areas/SKILL.md](../../.claude/skills/backfill-empty-areas/SKILL.md))
- [x] CLAUDE.md 스킬 표 업데이트

## 사용자 보정 (2026-05-19, 추가 지시)
- 강호남 점심: Uncategorizable → **Suited**
- POC클리닉 기획안: Uncategorizable → **Lecturing**
- 카카오 GeoAI 시절 13건: Career → **GeoAI** (status Closed지만 사용자 명시 요청)
  - cli interface, 좌표계, laz 스케일, dam_datagen, 카카오 레지스터리, Grid size, Thomas 타일, pcd grid, DAM dataset, RandLaNet&Toronto3D, 영등포리눅스, RandLaNet SemanticKitti, Weight 계산식
- 적용: [backfill_areas_2026-05-19_corrections.py](backfill_areas_2026-05-19_corrections.py) (idempotent guard bypass — 명시적 reassignment 의도)
- 결과: [backfill_areas_2026-05-19_corrections.result.json](backfill_areas_2026-05-19_corrections.result.json)

## 매핑 요약 (실제 적용)
- **DOF (2)**: ps 개발부서 바이브코딩 가이드, 260514 개발부서세미나 강의중노트
- **Home(부부) (1)**: tk 아내 외장하드 수리
- **Lecturing (2)**: 쿠비트 첫번째모임 강의자료, 벤처경영 수업자료
- **Career (14)**: 영경교수님 관련 2건 + 카카오 GeoAI/DAM/LiDAR 시절 task 12건 (cli interface, 좌표계, laz 스케일, dam_datagen, 카카오 레지스터리, Grid size, Thomas 타일, pcd grid, DAM dataset, RandLaNet&Toronto3D, 영등포리눅스, RandLaNet SemanticKitti, Weight 계산식). GeoAI Area가 Closed라 직접 못 쓰고 Career로 묶음.
- **SelfAdmin(자기관리) (1)**: 계정찾기
- **Uncategorizable (2)**: 강호남 점심, POC클리닉 기획안 (맥락 모호 → 사용자 후속 분류 권장)

## 산출물
- [backfill_areas_2026-05-19_discover.py](backfill_areas_2026-05-19_discover.py) — discover 스크립트
- [backfill_areas_2026-05-19.candidates.json](backfill_areas_2026-05-19.candidates.json) — discover 결과
- [backfill_areas_2026-05-19.mapping.json](backfill_areas_2026-05-19.mapping.json) — AI 사람-검증 가능 매핑
- [backfill_areas_2026-05-19.py](backfill_areas_2026-05-19.py) — push 스크립트 (idempotent guard 내장)
- [backfill_areas_2026-05-19.result.json](backfill_areas_2026-05-19.result.json) — push 결과
