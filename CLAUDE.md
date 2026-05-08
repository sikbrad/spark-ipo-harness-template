
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


## 브라우저 자동화 아키텍처

사이트별 자동화는 [`@playwright/cli`](https://github.com/microsoft/playwright-cli) 기반:
- 공통 wrapper: `proc/lib/pwc.py` (`S(name)` 세션 클래스)
- 사이트별 helper: `proc/lib/pwc_teams.py`, `pwc_salesforce.py`, `pwc_amaranth.py`, `pwc_naver.py`
- 세션 격리: `-s=teams`, `-s=salesforce`, `-s=amaranth`, `-s=naver` — 서로 다른 사이트는 진짜 동시 실행 가능
- 첫 1회 부트스트랩: [proc/plan/playwright-cli-bootstrap.md](proc/plan/playwright-cli-bootstrap.md)
- 마이그레이션 배경: [proc/plan/playwright-cli-migration.md](proc/plan/playwright-cli-migration.md)

`browser-harness` (CDP REPL)는 legacy fallback — 사용자가 명시 지정 시만.

## Agent Skills
Agent Skills 오픈 표준(agentskills.io) 기반.
위치: `.claude/skills/` 또는 `.gemini/skills/`

| 스킬 | 설명 |
|------|------|
| `/create-spec` | 명세(Spec)를 `proc/spec/`에 항목별 문서로 작성 |
| `/update-plan` | `proc/plan/`에 작업 계획 생성/업데이트 |
| `/update-spec` | 명세 변경 시 `proc/spec/` 문서 업데이트 |
| `/browser-harness` | (Legacy) browser-harness CDP REPL 사용 규칙 — 명시 지정 시만 |
| `/amaranth-calendar` | 아마란스 ERP 일정/캘린더 데이터 추출 (playwright-cli) |
| `/amaranth-org` | 아마란스 ERP 조직도/임직원 정보 추출 (playwright-cli) |
| `/amaranth-resource` | 아마란스 ERP 자원(회의실/차량) 예약 조회·등록 (playwright-cli) |
| `/amaranth-approval` | 아마란스 ERP 전자결재 문서함 (미결/기결) (playwright-cli) |
| `/amaranth-leave-request` | 아마란스 ERP 연차휴가신청서 자동 작성·상신 (UBA6000 → HPD0110 → popup → 상신, playwright-cli) |
| `/amaranth-doc-recall` | 아마란스 ERP 상신문서함의 진행중 결재 문서 회수 (UBA1010 → popup → 회수 → 확인, playwright-cli) |
| `/amaranth-acc-ledger` | 아마란스 ERP 거래처계정내역(ACC3030) — 단일 기간 직접 query (playwright-cli) |
| `/amaranth-acc-period` | 거래처계정내역 — 전체 history 한번 fetch + 임의 기간 derive (이월잔액 코드 계산) |
| `/amaranth-acc-customer-ledger` | 거래처원장(ACC3010) — 거래처별 transaction-level + 월계/누계 marker (SPA 월별 chunked) |
| `/amaranth-acc-balance` | 아마란스 ERP 거래처계정잔액(ACC3020) (playwright-cli) |
| `/teams-chat` | Microsoft Teams 채팅(DM/그룹) **본문** 조회·전송 — **MS Graph API**. default. |
| `/teams-chat-browser` | (Fallback) 위와 동일 — playwright-cli + 내부 REST. 명시 지정 또는 Graph 실패 시. |
| `/teams-channel` | Microsoft Teams 채널 게시물 **조회·게시·답글** — **MS Graph API**. default. |
| `/teams-channel-browser` | (Fallback) 위와 동일 — playwright-cli + 내부 `/api/csa/.../posts`. |
| `/teams-activity` | Microsoft Teams DM 미답 / @멘션 분석 — **MS Graph API** (휴리스틱). default. |
| `/teams-activity-browser` | (Fallback) Activity 피드 자체(시스템 알림 포함) — Graph 미노출이라 본 fallback이 unique-feature. |
| `/outlook` | 회사 Outlook (Office 365) 메일 — 검색·본문·첨부·**발송·답장·이동·읽음/플래그·삭제** (MS Graph API). |
| `/sharepoint` | 회사 SharePoint Online 사이트·라이브러리·파일 검색·다운로드 (MS Graph API, read 전용). |
| `/onedrive` | 회사 OneDrive 개인 (`/me/drive`) — 검색·다운로드·**업로드·이동·복사·이름변경·공유·삭제** (MS Graph API). |
| `/gmail` | Google Gmail 검색·본문·첨부·**발송·라벨수정** — Google API + OAuth Desktop client. 두 계정(bispro89, sikbrad). |
| `/gcal` | Google 캘린더 일정·free/busy·**이벤트 생성/수정/삭제** — 동일 OAuth 토큰 공유. 모든 visible 캘린더 자동 aggregate. |
| `/gdrive` | Google Drive 파일·Docs/Sheets/Slides 검색·다운·업·**생성/수정/삭제** — full `drive` scope. |
| `/salesforce-record` | Salesforce Lightning 레코드(Opportunity/Quote/라인아이템) (playwright-cli) |
| `/naver-blog` | 네이버 블로그(blog.naver.com) 글쓰기·읽기·수정 + 마크다운 파일(frontmatter+이미지) 자동 발행 (playwright-cli) |
| `/chatgpt` | ChatGPT(chatgpt.com) 개인 계정 대화 토픽·본문 export — playwright-cli + Apple ID 로그인 + `/backend-api/conversations` 직호출. resume·429 백오프 내장. |
