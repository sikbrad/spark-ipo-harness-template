# SPARK + IPO 하네스 템플릿

AI 에이전트(Claude Code · Codex CLI · Gemini CLI)와 함께 사용하는 **컨텍스트 엔지니어링 하네스 템플릿**입니다.

## 구조

```
project/
├── input/       # 입력·참고 데이터
├── proc/        # 명령 처리 규칙 (SPARK: Spec, Plan, Archive, Research, Knowhow)
│   ├── spec/        # 설계 명세
│   ├── plan/        # 작업 계획
│   ├── archive/     # 비활성 문서
│   ├── research/    # 조사·분석 결과
│   └── knowhow/     # 재사용 프롬프트
├── output/      # 출력 데이터
└── src/         # 소스 코드
```

## 사용법

1. 이 템플릿을 복사하여 새 프로젝트를 시작합니다.
2. 참고자료 또는 입력데이터가 있는 경우 `input/`에 넣고, AI에게 작업을 요청합니다.
3. AI는 `proc/spec/`에 명세를, `proc/plan/`에 계획을, `proc/research/`에 사전 조사를 작성하며 개발을 진행합니다.
4. 결과물이 있는 경우 `output/`에 저장하고, 소스코드는 `src/`에 생성됩니다.
5. AI가 적절한 skill을 호출하여 작업을 진행합니다.

## 기술 스택

- **패키지 매니저**: **Bun** (npm/yarn/pnpm 대신 bun 사용)
- **웹 개발**: Vite + React + **TypeScript** + TailwindCSS
- **데이터 처리**: Bun 스크립트 (`src/`)

## 멀티 에이전트 지원

세 플랫폼이 동일한 스킬 세트를 공유합니다. 각 플랫폼은 자기 위치만 읽으므로 변경 시 세 곳을 모두 동기화하세요.

| 플랫폼 | 스킬 위치 | 진입 문서 |
|--------|-----------|-----------|
| Claude Code | `.claude/skills/<name>/SKILL.md` | `CLAUDE.md` |
| Gemini CLI | `.gemini/skills/<name>/SKILL.md` | `AGENTS.md` |
| Codex CLI | `.codex/prompts/<name>.md` | `AGENTS.md` |

## 주요 스킬

| 명령 | 설명 |
|------|------|
| `/create-spec` | 명세(Spec) 작성 — `proc/spec/`에 항목별 문서 생성 |
| `/update-plan` | 작업 계획 생성·업데이트 — `proc/plan/` |
| `/update-spec` | 명세·업무규칙 업데이트 — FSD/rules/architecture/nfr/user-flow/api/work-rules/decisions 카테고리, ADR 지원 |
| `/update-research` | 사전 조사·연구 문서 작성 — `proc/research/`, 방안 비교 + 권장안 + 레이어별 구현 제안 |
| `/test-server` | playwright-cli E2E 테스트 — 산출물은 `output/test/` |

# 활용 방안

## 웹서비스 개발
* 이 템플릿이 있는 input/auction-item 폴더를 지우세요.
* input 에 필요한 참고 자료를 넣고, AI에게 작업을 요청하세요.
* AI가 작업을 진행하며, proc 폴더에 명세와 계획을 작성합니다.
* AI는 웹서버를 개발하며 src 에 소스코드를 생성합니다.
* 웹서비스를 실행하여 개발하세요.

## 이 프로젝트가 생성된 방법

1. 다른방식으로 프로젝트를 생성합니다.

   폴더를 새로 만들고 Vite + React + TypeScript 프로젝트를 한개 생성합니다 (bun 사용).

   ```bash
   bun create vite@latest . --template react-ts
   bun install
   # TailwindCSS 추가 (v4 기준)
   bun add -D tailwindcss @tailwindcss/vite
   ```

2. IPO(Input/Process/Output) 폴더 구조를 복사합니다.
3. SPARK(Spec/Plan/Archive/Research/Knowhow) 구조를 복사합니다.
4. AI 에이전트 설정 파일을 복붙합니다.
   - Claude Code: `.claude/` 디렉토리 + `CLAUDE.md`
   - Gemini CLI: `.gemini/` 디렉토리 + `AGENTS.md`
   - Codex CLI: `.codex/` 디렉토리 + `AGENTS.md`

## 로깅 훅

`.claude/hooks/log_user_input.sh` — 유저가 프롬프트를 입력할 때마다 `proc/archive/prompts/` 에 날짜별(`YYYY-MM-DD.md`)로 자동 기록합니다. 이를 통해 AI와의 대화 이력을 아카이브에 보존할 수 있습니다.

## 다른 용도로 이전 하는 방법

다른 프로젝트의 경우는 위의 1 단계 대신 아래와 같이 진행합니다.


### 데이터처리용 Bun(JS/TS) 프로젝트용
```bash
bun init -y
```

### 데이터처리용 Python 프로젝트용
```bash
uv init
```

### 모바일 어플리케이션용(React Native)
```bash
bunx @react-native-community/cli init .
```

### 데스크탑 어플리케이션용(electrobun)
```bash
bunx electrobun init
```

# Author
ins@doflab.com

# License
MIT License
