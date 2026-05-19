# DailyJot → Task/Note 자동화 (2026-05-19)

## 목표
오늘 Jot DB의 "DailyJot 2026-05-19 화" 항목에서
- **할일(TODO/체크박스)** → Task DB 페이지 생성 (Area + ActDate + 템플릿 `tk` 본문 + `ts ` title prefix)
- **생각(thought 성격 bullet)** → Note DB 페이지 생성 (Area + 유형=아이디어)
- 원본 Jot 블록 끝에 만든 페이지의 **노션 chip mention** (page reference) append

## 핵심 원칙 (사용자 피드백 통합)
1. **Area 분류는 키워드 매칭으로 코드에서 절대 하지 않는다.** 각 Area의 실제 콘텐츠를 사람이 보고 의미적으로 매핑. 매핑은 mapping.json에 외부화.
2. **Area는 상태 `In progress` (group: Responsible / Occasional) 인 것만 사용.** Closed/Todo Area는 후보에서 제외.
3. **Task title은 반드시 `ts ` prefix.** (Task DB 컨벤션)
4. **Task body는 `tk` 템플릿 (`bdda3e4b…`) 본문을 복사** (notion_task.py 기본값).
5. **링크는 Notion page-mention chip** (rich_text type=mention). text-link / preview / embed 아님.
6. **1 체크박스 = 1 Task. 체크박스 하위 bullet/체크박스는 별도 Task/Note로 만들지 않고 그 Task body에 embed.**
   mapping.json의 task 항목에 `embed_children: [jot_block_id, ...]` 로 명시. 스크립트는 그 자식들을 fetch해서 부모 Task body 끝에 `bulleted_list_item` 으로 append.
7. **plan 문서 작성·업데이트하며 진행.**

## In-progress Areas (사용 가능 후보)
**Responsible**: DOF, Productivity, Career, SelfAdmin(자기관리), Home(부부), ProgMaster, Family(고향), Kamo, RealEstate
**Occasional**: ProPar, Uncategorizable, Lecturing, ConvBoard, Suited, WHYQ, TANKMON, Musician

**제외(Closed/Todo)**: LW, DailyVibe, 교통안전제보단, GeoAI, MF, 자문역, 사테크모임, TAS(ZS), RoadNetwork, Artisan

## Area 성격 요약 (콘텐츠 샘플 기반)
| Area | 의미 | 대표 콘텐츠 |
|---|---|---|
| DOF | 회사(디오에프) 업무 | CRM 마이그, 거래원장, 전시회 |
| Productivity | 개인 생산성 도구 활용 | 노션 1.4 정리, 에지 워크스페이스 |
| Lecturing | 강의/강연 | 바이브코딩 강의, 슬라이드, 강연료 |
| Home(부부) | 부부+자녀 일상 | 임신용품, 부부여행, 운동, 아내 생일 |
| SelfAdmin(자기관리) | 개인 행정/건강 | 신세계클럽 해지, 마일리지, 치과 |

## 최종 Jot → Area 매핑 (사람 판단)
| jot_block_id | 내용 요약 | Area | 판단 근거 |
|---|---|---|---|
| `2918372d…d593` | 거래원장 다돌리고 검수 | DOF | DOF Tasks/Docs에 CRM·거래 흐름 다수 |
| `3e28372d…808c` | 음성 분석 돌리며 일하기 | Productivity | 도구 활용/워크플로 결 |
| `3648372d…4d06` | 데일리노트 돌리며 일하기 | Productivity | 노션 도구 활용 결 |
| `3648372d…5bba` | 책 (강의→책) **+ 4 sub-bullets embed** | Lecturing | 강의 콘텐츠 재가공 |
| `3658372d…bcfa` | 슬라이드 합치기 (top-level bullet, checkbox 아님) | Lecturing | 강의 자료 — 일단 Task 유지 (사용자 확인 대기) |
| `a0b8372d…0f0d` | 호텔 탐색 | Home(부부) | 부부+임신 맥락 일치 |
| `3648372d…c079` | 아기 계좌 신청 | Home(부부) | 자녀=부부단위 |
| `3648372d…68e1` | 유류비 지원금 (아기것도) | Home(부부) | 가족 단위 행정 |
| `3648372d…6f711` | 하드반납 연락 | SelfAdmin | 일상 행정 |
| `3658372d…b5ee` | 데일리좃→Task 자동화 만들기 | **SelfAdmin** | 사용자 지시 (LW는 Closed 상태라 제외) |

**(이전엔 별도 Note로 만들었으나 룰 변경으로 archived → T4 본문에 embed:)**
| `3658372d…f5eb` | 강의를 책으로 | → T4 body | 책 sub-bullet (embed) |
| `9238372d…8a16` | 170명 실습강좌 요령도 | → T4 body | 책 sub-bullet (embed) |
| `3658372d…6095` | 데일리보다 요령 툭툭 | → T4 body | 책 sub-bullet (embed) |
| `3658372d…624c9` | Ax도 | → T4 body | 책 sub-bullet (embed) |

## 진행 상황
- [x] 오늘 Jot 페이지 찾음: `3648372d-c5ca-81c0-8e6e-e80ea978607e`
- [x] Jot 본문 dump (TODO 10 + thought 4)
- [x] Note DB / Task DB / Area DB 스키마 확인
- [x] 각 Area 콘텐츠 직접 샘플링·요약
- [x] Area 상태 In-progress 필터링
- [x] 14개 페이지 생성 (Tasks 10, Notes 4)
- [x] Task title에 `ts ` prefix 추가 (PATCH)
- [x] `tk` 템플릿 본문 적용 (요약/실행계획/실행메모/액션/정리 섹션 확인)
- [x] T10 Areas → SelfAdmin (LW는 Closed 상태라 사용 불가)
- [x] 모든 원본 Jot 블록 끝에 page-mention chip append (텍스트 하이퍼링크에서 chip으로 변환 완료)
- [x] 스크립트에서 하드코드 키워드 매핑 제거, mapping.json 외부화
- [x] N1-N4 노트 archive 처리, T4 (책) body에 4 sub-bullets embed, 해당 Jot block의 chip 제거 — 1체크박스=1Task 룰 적용
- [x] mapping.json에 `embed_children` 필드 추가, 스크립트가 자식 임베드 처리하도록 업데이트
- [x] **1주일 dup 룰 적용**: Task DB의 `Created time ∈ [2026-05-12, 2026-05-19)` Task 2개 조회 → 오늘 T1~T10과 의미적으로 비교 → **dup 0건** (아래 판단 표 참조). 적용할 변경 없음
- [x] 스크립트에 `existing_task_id` + `suffix_text="끌올"` 지원 추가 (future runs용)
- [x] 새 스킬 `/daily-jot-to-tasks` 생성 (`.claude/skills/daily-jot-to-tasks/SKILL.md`) + CLAUDE.md 스킬 표에 추가
- [ ] T5 "슬라이드 합치기" — top-level bullet (checkbox 아님). 현재 Task 유지중. 사용자 확정 대기
- [ ] 사용자 검수

## 1주일 dup 판단 (오늘 적용 결과)
지난주 Task 2건:
- `ps 개발부서 바이브코딩 가이드 자료 만들기` (2026-05-14) — `3608372d…`
- `tk 아내 외장하드 수리` (2026-05-13) — `35f8372d…`

| 오늘 항목 | 후보 비교 | 결론 |
|---|---|---|
| T4 책 (강의→책) | A: 개발부서 바이브코딩 가이드 — 둘 다 콘텐츠 제작이지만 대상(내부 가이드 vs 책)과 형태 다름 | NOT dup |
| T5 슬라이드 합치기 | A: 개발부서 바이브코딩 가이드 — A에 슬라이드 포함 가능성 있지만 "합치기"라는 별개 액션 | NOT dup |
| T9 하드반납 연락 | B: 아내 외장하드 수리 — 같은 외장하드일 수 있으나 수리 vs 반납연락은 순차 단계 | NOT dup |
| 그 외 (T1, T2, T3, T6, T7, T8, T10) | 어느 후보와도 의미 겹침 없음 | NOT dup |

→ **dup 0건**, 새 chip/끌올 적용 없음.

## 산출물
- [jot_to_tasks_2026-05-19.mapping.json](jot_to_tasks_2026-05-19.mapping.json) — 사람-판단 매핑 (스크립트의 단일 입력)
- [jot_to_tasks_2026-05-19.py](jot_to_tasks_2026-05-19.py) — pusher (mapping.json 읽음, 키워드 매핑 없음)
- [jot_to_tasks_2026-05-19.result.json](jot_to_tasks_2026-05-19.result.json) — 생성된 페이지 ID/URL
