---
name: test-server
description: 실행 중인 서버를 브라우저로 테스트. "서버 테스트", "서버 띄워서 확인", "브라우저로 테스트", "playwright 테스트", "엔드투엔드 테스트", "E2E 테스트" 등 서버 동작 확인 요청 시 사용. playwright-cli(https://github.com/microsoft/playwright-cli)로 테스트한다.
argument-hint: "[테스트 대상 URL 또는 시나리오]"
---

# 서버 테스트 (playwright-cli)

실행 중인 서버를 브라우저 자동화로 테스트한다. 테스트 도구는 **playwright-cli** (https://github.com/microsoft/playwright-cli)로 고정한다.

## 0. 사전 점검 — playwright-cli 설치 확인

테스트 시작 전에 항상 설치 여부를 먼저 확인한다.

```bash
npx --no-install playwright-cli --version 2>/dev/null || command -v playwright-cli
```

설치되어 있지 않으면 **임의로 설치하지 말고**, 유저에게 다음 메시지로 설치를 요청한다.

```
playwright-cli가 설치되어 있지 않습니다. 아래 명령으로 설치해 주세요.

  npm install -g playwright-cli
  npx playwright install   # 브라우저 바이너리 설치

설치 후 다시 요청해 주세요.
```

설치가 확인된 뒤에만 다음 단계를 진행한다.

## 1. 테스트 대상 확인

- `$ARGUMENTS`에 URL/시나리오가 들어오면 그대로 사용한다.
- 비어 있으면 프로젝트의 dev 서버 URL을 추정한다 (`package.json`의 `dev` 스크립트, `.env`, 기본 `http://localhost:3000` 등). 추정이 모호하면 유저에게 묻는다.
- 서버가 떠 있는지 먼저 확인한다.

```bash
curl -sSf -o /dev/null -w "%{http_code}\n" <URL>
```

응답이 없으면 유저에게 서버를 먼저 실행하도록 알린다 (임의로 dev 서버를 띄우지 않는다).

## 2. playwright-cli 사용 패턴

| 목적 | 명령 |
|------|------|
| 브라우저 열어 페이지 확인 | `npx playwright-cli open <URL>` |
| 스크린샷 캡처 | `npx playwright-cli screenshot --full-page <URL> <file.png>` |
| 시나리오 코드 자동 생성 | `npx playwright-cli codegen <URL>` |
| PDF 출력 | `npx playwright-cli pdf <URL> <file.pdf>` |
| 디바이스 에뮬레이션 | `--device "iPhone 13"` 등 옵션 추가 |

스크린샷·PDF 같은 산출물은 `output/test/`에 저장한다 (없으면 생성).

## 3. 시나리오 테스트가 필요한 경우

단순 페이지 확인을 넘어서는 클릭/입력/검증 시나리오는 `npx playwright-cli codegen <URL>`로 스크립트를 생성한 뒤 `output/test/<YYYYMMDD>_<주제>.spec.ts`에 저장하고, 필요시 유저에게 실행 방법을 안내한다.

## 4. 결과 보고

테스트 종료 후 다음을 요약 보고한다.
- 사용한 명령
- HTTP 상태 / 페이지 타이틀
- 캡처/생성된 산출물 경로
- 발견된 에러·경고 (콘솔 로그가 있으면 포함)

## 규칙

- **설치 자동화 금지**: playwright-cli가 없으면 설치 명령만 안내한다. `npm install`을 임의로 실행하지 않는다.
- **서버 자동 실행 금지**: 서버가 꺼져 있으면 유저에게 알리고 종료한다. 임의로 dev 서버를 띄우지 않는다.
- 테스트 도구는 playwright-cli로 고정한다 (puppeteer, selenium, 일반 playwright test 러너 등으로 대체하지 않는다).
- 산출물은 `output/test/`에 저장한다.
- 한글로 보고한다.
- `$ARGUMENTS`에 테스트 대상 URL 또는 시나리오가 들어온다.
