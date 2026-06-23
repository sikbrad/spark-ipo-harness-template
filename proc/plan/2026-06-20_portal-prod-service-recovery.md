# 포탈 본섭 서비스 복구

## 목표
`https://portal.doflab.com/login?redirect=%2F`가 정상 로드되고, 본섭 백엔드 `/health`가 200을 반환하도록 복구한다.

## 작업 항목
- [x] 본섭 접속 경로와 복구 범위 확인
- [x] 본섭 현재 PM2/포트/헬스 상태 재확인
- [x] 최소 PM2 조치로 백엔드 리스너 복구
- [x] 외부 `/health`와 로그인 URL 정상 응답 검증
- [x] 원인과 후속 예방 조치 기록

## 진행 기록
- 2026-06-20 19:52 KST: 본섭 `OrderPortal-ax-prod-ec2`에서 PM2는 server/front 모두 online이나, LISTEN은 `54221`만 존재. `127.0.0.1:54222/health`는 connection refused, 외부 `/health`는 500/0 bytes.
- 2026-06-20 19:52 KST: `pm2 restart dof-order-portal-server --update-env` 실행 후 server pid가 `498506`으로 바뀌고, `*:54222` 리스너 및 내부 `/health` 200 확인.
- 2026-06-20 19:53 KST: 외부 `https://portal.doflab.com/health` 200/375 bytes, `https://portal.doflab.com/login?redirect=%2F` 200/602 bytes 확인.
- 2026-06-20 19:53 KST: Playwright로 로그인 URL 렌더링 확인. 제목 `DOF PORTAL`, 이메일/비밀번호 입력 및 로그인 버튼 표시, 콘솔 오류 0건, 네트워크 `/health` 200.

## 원인 메모
- 직전 장애 원인은 본섭 백엔드가 PM2상 online이지만 실제 `54222` HTTP 리스너가 없는 상태였기 때문이다.
- 서버 로그의 직접 원인은 2026-06-20 18:05 KST 무렵 `app.listen(54222)`의 `EADDRINUSE` 실패였다.
- `bootstrap()` 실패가 프로세스를 명시 종료하지 않아 PM2가 online으로 표시하는 false-positive 상태가 됐다.

## 후속 예방
- 백엔드 `bootstrap().catch(...)`에서 listen 실패 시 `process.exit(1)` 하도록 수정 필요.
- 배포/재시작 후 본섭 내부 `curl http://127.0.0.1:54222/health`와 외부 `/health`를 배포 게이트로 추가 필요.
