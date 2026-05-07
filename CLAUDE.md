
# SPARK + IPO

SPARK(Spec, Plan, Archive, Research, Knowhow) 명령 처리 규칙 체계와 IPO(Input, Proc, Output) 데이터 처리 흐름을 결합한 AI Agentic 만능 명령 및 데이터 처리 시스템이다.

### SPARK — 명령 처리 규칙
```
proc/
├── spec/       # S — 설계 명세
├── plan/       # P — 작업 계획 (간결한 작업 메모)
├── archive/    # A — 비활성 문서 (AI 열람 금지)
├── research/   # R — AI 조사·분석 결과
└── knowhow/    # K — 재사용 프롬프트 (AI 열람 금지)
```

### IPO — 데이터 처리 흐름
```
project/
├── input/              # I — 입력 데이터, 참고 데이터
├── proc/               # P — 명령 처리 규칙
├── output/             # O — 출력 데이터
└── src/                # 소스 코드
```

---

## 규칙
- 복잡한 작업 요청 시 `proc/plan/`에 계획 문서를 작성하고, 업데이트하면서 개발한다
- 명세가 변경되면 `proc/spec/`의 관련 문서를 업데이트한다
- `input/`은 명시적 지시 없이 수정하지 않는다
- `proc/archive/`는 명시적 지시 없이 열람하지 않는다


## Agent Skills
Agent Skills 오픈 표준(agentskills.io) 기반.
위치: `.claude/skills/` 또는 `.gemini/skills/`

| 스킬 | 설명 |
|------|------|
| `/create-spec` | 명세(Spec)를 `proc/spec/`에 항목별 문서로 작성 |
| `/update-plan` | `proc/plan/`에 작업 계획 생성/업데이트 |
| `/update-spec` | 명세 변경 시 `proc/spec/` 문서 업데이트 |
| `/browser-harness` | 브라우저 자동화 — `agent_helpers.py`에 helper 누적시키는 사용 규칙 |
| `/amaranth-calendar` | 아마란스 ERP(erp.doflab.com) 일정/캘린더 데이터 추출 |
| `/amaranth-org` | 아마란스 ERP 조직도/임직원 정보 추출 |
| `/amaranth-resource` | 아마란스 ERP 자원(회의실/차량) 예약 조회 및 신규 예약 등록 |
| `/amaranth-approval` | 아마란스 ERP 전자결재 문서함 조회 (미결/기결, 본인 결재 이력) |
| `/amaranth-acc-ledger` | 아마란스 ERP 거래처계정내역(ACC3030) — 기간·계정과목별 거래처 원장(차변/대변/잔액) |
| `/amaranth-acc-balance` | 아마란스 ERP 거래처계정잔액(ACC3020) — 기준일·계정과목별 거래처 잔액(합계+코드별) |
| `/teams-activity` | Microsoft Teams web Activity 피드(알림) 조회·분석 — DOM 스크레이핑 기반, 가상스크롤 누적 수집 |
