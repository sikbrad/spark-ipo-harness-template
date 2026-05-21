# 카톡 데이터 데일리 백필 수집기

## 목표
`data/kmsg/<chat_id>__<slug>/YYYY-MM-DD.md` 형식으로 내 카톡 채팅방 전부(오픈채팅 제외)를 데일리로 끊어 저장. 재실행 idempotent. 매일 cron으로 어제 분 자동 수집까지 가능하게.

## 설계 결정
- **오픈채팅 식별**: `kmsg chats --verbose --json` 으로 type/openchat 필드 있는지 1차 확인 → 없으면 사용자 검수 가능한 exclude list (`proc/lib/kmsg_excludes.json`) 운영
- **백필 범위**: 각 채팅방 끝까지 스크롤 백필. kmsg `read --limit N` 의 실제 상한 측정 후 (예: 1000) `--limit` 점진 증가 시도. AX scroll-back이 막히면 거기까지가 한계 — 한계 기록 후 이후 일자별 incremental 모드로
- **폴더 키**: `data/kmsg/<chat_id>__<slugified-title>/YYYY-MM-DD.md` (chat_id가 안정성 핵심, slug은 사람용)
- **날짜 추론**: 메시지엔 `time_raw`("HH:MM")만 있고 절대시각 없음 → 카톡 UI의 날짜 divider 파싱 필요. `read` 가 system 메시지(날짜 구분선) 포함 못 하면 `watch --include-system` 패턴 차용해서 read 쪽도 확장 또는 fetch 시각 기준 + hour-rollover 추적 휴리스틱
- **상태 추적**: `data/kmsg/_state.sqlite` (chat_id별 last_fetched_at, last_message_hash, total_messages, oldest_seen_date)
- **GUI 침해 최소화**: 순차 실행만 (병렬 불가), 한 방당 30~60초 budget, 사용자 OS 작업 중일 땐 중단 가능하게 SIGINT 처리

## 작업 항목
- [x] **0. 준비**: 카톡 로그아웃 → `kmsg auth login` → `kmsg status` 그린
- [x] **1. discovery**: `kmsg chats --verbose --limit 200 --json` 으로 전체 채팅방 목록 dump → `data/kmsg/_index/chats-{ts}.json`
- [x] **2. 오픈채팅 식별**: verbose 필드 inspect → openchat 필터 룰 결정 → `data/kmsg/_index/excludes.json` 산출 (사용자 검수)
- [x] **3. read 한계 측정**: 1개 큰 방 골라 `read --limit 1000 / 5000 / 10000` 로 실제 반환 메시지 수 측정, 날짜 divider 출현 여부 확인 → `proc/plan/2026-05-21_kmsg-daily-backfill.md` 에 결과 기록
- [x] **4. 날짜 파서 작성**: divider 패턴 ("2026년 5월 11일 일요일" 등) + time_raw → 절대시각 변환기 (`proc/lib/kmsg_dates.py`)
- [x] **5. MD writer**: `data/kmsg/<chat_id>__<slug>/YYYY-MM-DD.md` 포맷 (헤더: chat title, date; 본문: `HH:MM @author\nbody\n\n` 반복). 같은 날짜 파일은 머지 (중복 제거 by msg_hash)
- [x] **6. backfill orchestrator**: `proc/lib/kmsg_backfill.py`
  - 전체 chats → exclude 제외 → 각 방마다 `read --limit max` → date-bucket → daily MD 쓰기/머지
  - state DB 업데이트
  - 한 방 실패해도 전체 안 멈추게 try/except 격리
- [x] **7. 1차 풀백필 실행**: 모든 방 끝까지 (kmsg limit 내에서)
- [ ] **8. incremental 모드**: `--since YYYY-MM-DD` 또는 default=어제. 매일 cron 후보
- [ ] **9. 사용자 검수**: 결과 폴더 트리 + 샘플 MD 보여드리고 포맷·필터 수정

## 산출물
- `data/kmsg/<chat_id>__<slug>/YYYY-MM-DD.md` × N
- `data/kmsg/_index/chats-{ts}.json`, `excludes.json`, `_state.sqlite`
- `proc/lib/kmsg_dates.py`, `proc/lib/kmsg_backfill.py`
- (선택) `.claude/skills/kmsg-daily-backfill/SKILL.md`

## 알려진 제약 (2026-05-21 측정 결과)
- kmsg는 GUI 점유 → 백필 도중 카톡 만지면 안 됨
- 단일 PC 로그인 — 모바일은 OK, 다른 데스크탑 카톡 켜면 끊김
- ⚠️ **kmsg read는 AX 현재 렌더 분량만 반환** (테스트: 쥬쥬월드 43개, 가족방 36개). `--limit 5000 --deep-recovery` 도 늘어나지 않음. 스크롤백 미지원
- ⚠️ **절대시각 없음 + 12h/24h 모호** ("5:15"가 오전/오후 불명). 메시지엔 `time_raw`만, 날짜 divider도 JSON에 안 들어옴
- ⚠️ **과거 풀백필 불가** — 가능한 건 "지금 시점 스냅샷 + 이후 일별 누적". 사용자가 카톡 사이드바를 직접 위로 스크롤해 둔 채 read 호출하면 그만큼 더 잡힐 가능성은 있음 (사람 협조)
- chat list `--limit 500` 은 UI 아티팩트 섞임, `--limit 2000` 은 깨끗 — `--limit 2000` 사용

## 수정된 전략
1. **오늘 스냅샷 (1회)**: 441개 채팅방 전체 read → 각 메시지를 오늘 날짜로 가정해 bucket (가장 안전). hour-rollover로 자정 넘는 메시지가 보이면 그 부분만 어제로 split
2. **데일리 incremental**: 매일 같은 시각 cron → 새 메시지(이미 저장된 해시 중복 제거 후) 누적
3. **장기적**: 사용자가 특정 방을 위로 스크롤한 뒤 수동 trigger 시 그 시점 read해서 과거분 더 채움 (옵션)
