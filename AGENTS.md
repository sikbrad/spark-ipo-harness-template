
# SPARK + IPO

SPARK(Spec, Plan, Archive, Research, Knowhow) 명령 처리 규칙 체계와 IPO(Input, Proc, Output) 데이터 처리 흐름을 결합한 AI Agentic 만능 명령 및 데이터 처리 시스템이다.

이 문서(`AGENTS.md`)는 **Codex CLI · Gemini CLI**용 프로젝트 지침이다. Claude Code는 별도의 [`CLAUDE.md`](CLAUDE.md)를 읽는다.

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
- 사전 조사가 필요하면 `proc/research/`에 리서치 문서를 작성한다
- `input/`은 명시적 지시 없이 수정하지 않는다
- `proc/archive/`는 명시적 지시 없이 열람하지 않는다
- `proc/knowhow/`는 명시적 지시 없이 열람하지 않는다


## 기술 스택 (필수)

웹/JS·TS 작업 시 다음 스택을 사용한다. 임의 변경 금지.

- **패키지 매니저**: **Bun** — `npm` / `yarn` / `pnpm` 사용 금지. 모든 install/run/script는 `bun`으로 실행한다.
- **웹 프레임워크**: **Vite + React + TypeScript** (JS 아님)
- **스타일링**: **TailwindCSS** (v4 기준, `@tailwindcss/vite` 플러그인 사용)
- **스크립트 실행**: `bun <file>.ts` (Node 직접 실행 대신)

자주 쓰는 명령:
```bash
bun install              # 의존성 설치 (npm install 금지)
bun add <pkg>            # 런타임 의존성
bun add -d <pkg>         # 개발 의존성
bun run dev              # 개발 서버
bun run build            # 빌드
bunx <tool>              # 일회성 실행 (npx 대체)
```


## Agent Skills

이 프로젝트에서 사용 가능한 스킬은 아래와 같다. 각 CLI는 자기 위치만 읽는다.

| 플랫폼 | 스킬 위치 | 호출 방식 |
|--------|-----------|-----------|
| Codex CLI | `.codex/prompts/<name>.md` | `/<name>` (slash prompt), 본문에서 `$ARGUMENTS` 사용 |
| Gemini CLI | `.gemini/skills/<name>/SKILL.md` | `/<name>` 또는 자연어 트리거 |

> Claude Code의 스킬 정의(`.claude/skills/<name>/SKILL.md`)는 별도 위치에 있으며, 본 문서는 이를 다루지 않는다. Claude 측은 `CLAUDE.md` 참조.

### 제공 스킬

| 스킬 | 설명 |
|------|------|
| `/create-spec` | 명세(Spec)를 `proc/spec/`에 항목별 문서로 작성 |
| `/update-plan` | `proc/plan/`에 작업 계획 생성/업데이트 |
| `/update-spec` | 명세·업무규칙 변경 시 `proc/spec/` 문서 업데이트 (FSD/rules/architecture/nfr/user-flow/api/work-rules/decisions 카테고리 + ADR 처리) |
| `/update-research` | 구현 전 사전 조사·연구 문서를 `proc/research/`에 작성 (방안 비교 + 권장안 + 구현 제안) |
| `/test-server` | playwright-cli로 실행 중인 서버를 E2E 테스트, 산출물은 `output/test/` |

스킬 추가/수정 시 세 플랫폼(Codex `.codex/prompts/`, Gemini `.gemini/skills/`, Claude `.claude/skills/`)을 모두 동기화한다.
