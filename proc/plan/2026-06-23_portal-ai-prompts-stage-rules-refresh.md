# 포탈 AI 프롬프트 단계별 업무규칙 갱신

- 날짜: 2026-06-23
- 대상: 포탈 본섭 `AiValidationPrompt` / `/admin/ai-prompts`
- 범위: 주문 단계별 ORDER 프롬프트 9개를 국내/해외 기준, 주의기준, 불허기준 포함 본문으로 신규 버전 생성

## 진행 계획

1. `.code-workspace` 전체 폴더를 관련성 기준으로 스캔하고 포탈 코드의 프롬프트 버전 선택 규칙을 확인한다.
2. Outline 인수인계서, Teams 업무규칙/퇴사자 인수인계 산출물, 포탈 유효성검사 코드, 운영 DB의 기존 프롬프트를 근거로 수집한다.
3. `data/portal-ai-prompts/2026-06-23/` 아래에 주문단계별 근거 문서와 업로드용 프롬프트 본문을 분리 작성한다.
4. 운영 DB의 `AiValidationPrompt`를 백업한 뒤 단계별 신규 버전을 생성하고 기존 active 플래그를 내린다.
5. 운영 DB/API와 `https://portal.doflab.com/admin/ai-prompts` 화면에서 반영 여부를 확인한다.

## 진행 로그

- 2026-06-23: 코드상 `createPromptVersion`은 같은 `entityType + stage`의 최신 version + 1을 생성하고 기존 active를 false로 내리는 구조임을 확인했다.
- 2026-06-23: `resolveActivePrompt(stage)`는 `entityType='ORDER'`, `stage`, `isActive=true`, `deletedAt=null`, `version desc` 기준으로 활성 프롬프트를 선택함을 확인했다.
- 2026-06-23: Outline 원문 URL은 본문이 비어 있는 상위 문서이고, 하위 문서 5개(`DOF 포털관련`, `해외영업 참고사항`, `해외법인 미수금`, `하이퍼덴트`, `엑소캐드`)를 실제 근거로 수집했다.
- 2026-06-23: Teams 업무규칙 산출물 `output/teams-business-rules/2026-06-17/`의 사람별 SOP/인수인계/근거 JSON을 근거로 사용하기로 했다.
- 2026-06-23: 산출물 루트 `data/portal-ai-prompts/2026-06-23/` 생성.
- 2026-06-23: 주문단계별 근거 문서 9개는 `data/portal-ai-prompts/2026-06-23/stages/`에, 본섭 업로드용 출처 제거 본문 9개는 `data/portal-ai-prompts/2026-06-23/upload/`에 생성했다.
- 2026-06-23: 업로드용 본문 검증 결과 9개 모두 `국내 주문 기준`, `해외 주문 기준`, `이 단계의 주의기준`, `이 단계의 불허기준`을 포함하고, 출처/Teams/Outline/사람명/파일경로 문자열은 포함하지 않는다.
- 2026-06-23 11:11 KST: 본섭 `AiValidationPrompt` 백업 완료: `data/portal-ai-prompts/2026-06-23/source/prod-AiValidationPrompt-before-20260623T021142Z.dump`.
- 2026-06-23 11:12 KST: 본섭 ORDER 프롬프트 9개 신규 버전 생성 및 기존 active 플래그 해제 완료. 생성 버전은 `REGISTERED/APPROVAL_REQUESTED/TEAM_LEAD_APPROVED/RELEASE_APPROVED/SHIPPED/COMPLETED/RELEASE_HOLD/CLOSED_LOST = v3`, `EXECUTIVE_APPROVED = v6`.
- 2026-06-23 11:12 KST: DB read-back 검증 완료: `data/portal-ai-prompts/2026-06-23/source/prod-ai-prompts-after-readback-summary.json`의 `ok=true`, 각 단계 active row 1개, 로컬 업로드 본문과 MD5 일치.
- 2026-06-23 11:22 KST: `playwright-cli` 브라우저 세션으로 `https://portal.doflab.com/admin/ai-prompts` 접속 검증 완료. 관리자 화면 DOM에 9개 단계와 v3/v6 버전이 노출되고, 같은 브라우저 세션의 `/api/admin/ai-prompts?entityType=ORDER` 응답 9개가 로컬 업로드 본문과 SHA-256까지 일치했다.

## 최종 산출물

- 근거 인덱스: `data/portal-ai-prompts/2026-06-23/index.md`
- 주문단계별 근거 문서: `data/portal-ai-prompts/2026-06-23/stages/*.md`
- 본섭 업로드용 출처 제거 본문: `data/portal-ai-prompts/2026-06-23/upload/*.md`
- 업로드 JSON: `data/portal-ai-prompts/2026-06-23/upload/prompts.json`
- 본섭 백업: `data/portal-ai-prompts/2026-06-23/source/prod-AiValidationPrompt-before-20260623T021142Z.dump`
- DB 반영 결과: `data/portal-ai-prompts/2026-06-23/source/prod-ai-prompts-apply-result.csv`
- DB read-back 검증: `data/portal-ai-prompts/2026-06-23/source/prod-ai-prompts-after-readback-summary.json`
- 브라우저 검증: `data/portal-ai-prompts/2026-06-23/source/prod-ai-prompts-admin-ui-verification.json`
- 브라우저 스크린샷: `data/portal-ai-prompts/2026-06-23/source/prod-ai-prompts-admin-ui-verification.png`

## 검증 결과

- 생성 스크립트 문법 확인: `node --check proc/plan/generate_portal_ai_prompt_docs_2026_06_23.js`
- 업로드 본문 품질 확인: 9개 모두 국내/해외/주의기준/불허기준 포함, 출처성 문자열 없음.
- 본섭 DB 확인: 9개 단계 모두 활성 row 1개, 예상 버전 및 본문 해시 일치.
- Playwright 관리자 화면 확인: `/admin/ai-prompts` 진입, 9개 단계 및 최신 버전 노출, 관리자 API 응답 200/9개/본문 SHA-256 일치.
