# playwright-cli 세션 부트스트랩

각 사이트별로 **첫 1회만** 실행. 이후 `--persistent` 디스크 프로필이 로그인을 유지.

## 전제

```bash
# 1회만
npm install -g @playwright/cli@latest
playwright-cli --version  # 0.1.12+
```

## 세션 부트스트랩

### Teams (`-s=teams`)

```bash
playwright-cli -s=teams open https://teams.cloud.microsoft/ --persistent --headed
```

브라우저 창이 뜨면:
1. 이메일: `.env`의 `MSFT_TEAMS_PERSONAL_ID` 입력 → Next
2. SSO 자동 처리 후 비밀번호 prompt 시 `MSFT_TEAMS_PERSONAL_PW` 입력
3. **Microsoft Authenticator 푸시 알림** 핸드폰에서 표시된 숫자 입력 → 승인
4. "Stay signed in?" → Yes
5. Teams 메인 화면 로드되면 끝

### Salesforce (`-s=salesforce`)

```bash
playwright-cli -s=salesforce open https://d7f000002bofzuay.lightning.force.com/ --persistent --headed
```

1. ID: `.env` `SF_ACCOUNT_ID`
2. PW: `.env` `SF_ACCOUNT_PW`
3. MFA(TOTP) 화면 — 사용자 처리 (Authenticator/SMS)
4. Lightning Home 진입되면 끝

### Amaranth ERP (`-s=amaranth`)

```bash
playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed
```

1. 회사코드: `doflab`
2. ID: `.env` `ERP_PERSONAL_ID`
3. PW: `.env` `ERP_PERSONAL_PW`
4. 출퇴근 체크 popup → 취소
5. ERP 메인 화면 진입되면 끝

## 검증

각 세션 살아있는지 확인:

```bash
playwright-cli list
```

기대 출력:
```
### Browsers
- amaranth: status: open, browser-type: chrome, headed: true
- salesforce: status: open, browser-type: chrome, headed: true
- teams: status: open, browser-type: chrome, headed: true
```

## 일상 사용

부트스트랩 후에는 각 스킬이 알아서 세션 사용. 세션을 종료하려면:

```bash
playwright-cli -s=teams close       # 단일
playwright-cli close-all            # 전체
```

`close` 후에도 `--persistent` 프로필은 디스크에 남아 다음 `open` 때 로그인 상태 그대로 살아남.

## 시각 모니터링

여러 세션이 동시 동작 중일 때 한눈에 보려면:

```bash
playwright-cli show
```

라이브 그리드 + 단일 세션 줌인 + 원격 조작 가능.

## 동시성 모델

- **다른 `-s=`**: 완전 격리. 다른 브라우저 인스턴스, 동시 호출 OK.
- **같은 `-s=`**: 한 브라우저, 직렬화 필요. 두 명령을 동시에 보내면 race.
- 한 사이트에서 진짜 동시 worker가 필요하면 `-s=teams-1`, `-s=teams-2` 식으로 별도 세션을 부트스트랩(각각 별도 로그인 필요).

## 함정

- **`--persistent` 빠뜨리면** 첫 부트스트랩 후 close 시 로그인 정보 휘발 — 매번 다시 로그인. 첫 `open` 시 반드시 `--persistent` 명시.
- **`--headed` 빠뜨리면** headless로 떠서 사용자가 로그인 폼을 볼 수 없음. 첫 부트스트랩에서는 반드시 `--headed`. 이후 일반 사용은 headless 가능 (CI/cron).
- **MFA 갱신**: 일정 기간 후 SSO 토큰 만료 시 다시 헤디드로 열어서 재인증해야 할 수 있음.
- **프로필 손상**: `playwright-cli delete-data -s=<name>` 으로 프로필 초기화 가능.
