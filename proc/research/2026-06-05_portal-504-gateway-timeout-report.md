# 포탈 504 Gateway Time-out 원인 분석 리포트

- 작성시각: 2026-06-05 10:28 KST
- 대상: https://portal.doflab.com/
- 대상 EC2: `OrderPortal-ax-prod-ec2` / private IP `172.31.82.19`

## 요약

2026-06-05 10:20 KST 전후 포탈 접속 시 504 Gateway Time-out 또는 무응답이 발생했다.
사용자가 AWS에서 EC2 재부팅을 수행한 뒤, 10:25 KST경 인스턴스가 새로 부팅되었고 PM2가 포탈 front/server를 자동 재기동하면서 서비스는 정상 복구되었다.

현재 확인 가능한 직접 원인은 게이트웨이 뒤 upstream인 포탈 EC2/app이 재부팅 전 정상 응답하지 못한 것이다. 세부 원인은 애플리케이션 단일 예외보다는 EC2 OS/userland 또는 런타임 hang 가능성이 높다.

## 현재 상태

- 외부 URL `/`: `HTTP/2 200`
- 외부 URL `/health`: `HTTP/2 200`
- `/health` 응답: `status=ok`, `database=connected`, app `DOF PORTAL v1.2.2`
- prod EC2 SSH: 정상 로그인 가능
- PM2:
  - `dof-order-portal-front`: `online`
  - `dof-order-portal-server`: `online`
  - `dof-bot-web`: `online`
- 리슨 포트:
  - `54221`: portal front
  - `54222`: portal server
  - `54224`: bot web
  - `54225`: uvicorn
- 리소스:
  - 메모리: 1913MB total / 905MB available
  - 디스크 `/`: 30GB 중 8.5GB 사용, 29%
  - failed systemd unit: 없음

## 관측 타임라인

- 10:19 KST: dev jump 서버는 정상 접속됨.
- 10:19-10:24 KST: prod private IP `172.31.82.19`의 TCP 22번은 열려 있었으나 SSH는 `Connection timed out during banner exchange`로 실패. 이는 키/권한 문제가 아니라 SSH 데몬 또는 OS userland가 정상 응답하지 못하는 상태에 가깝다.
- 10:22 KST: 외부 `https://portal.doflab.com/`는 8초 내 0 byte 응답으로 timeout.
- 10:25:23 KST: prod EC2 새 부팅 확인 (`system boot 2026-06-05 01:25 UTC`).
- 10:25:30 KST: PM2 daemon 새로 시작, portal front/server/bot online.
- 10:25:41 KST: Nest application started.
- 10:25:49 KST 이후: `/health`, dashboard/order API 요청들이 1-300ms 수준으로 정상 처리됨.
- 10:26-10:28 KST: 외부 `/` 및 `/health` 모두 `HTTP/2 200`.

## 근거

- 이전 부팅 journal 마지막 기록: `2026-06-05 01:15:39 UTC`
- 새 부팅 시작: `2026-06-05 01:25:23 UTC`
- 현재 부팅 로그: `system.journal corrupted or uncleanly shut down, renaming and replacing`
- 이전 부팅의 `journalctl -p err`에는 장애 직전 명확한 error entry 없음.
- PM2 로그에는 재부팅 직전 portal front/server의 crash loop나 PM2 restart 증거가 없음.
- 재부팅 후에는 PM2가 정상 복원했고, app health에서 DB 연결도 정상이다.

## 판단

### 직접 원인

게이트웨이가 포탈 upstream에서 정상 응답을 받지 못해 504 또는 timeout이 발생했다.

### 가능성이 높은 상위 원인

EC2 인스턴스 OS/userland 또는 런타임이 응답 불능에 빠진 것으로 보인다.

근거는 다음과 같다.

- TCP 22는 열려 있었지만 SSH banner exchange가 반복 timeout.
- 외부 포탈도 응답을 반환하지 못함.
- 이전 부팅의 system journal이 01:15:39 UTC 이후 끊겼고, 재부팅 후 journal unclean shutdown 메시지가 남음.
- 재부팅만으로 PM2/app/DB health가 즉시 정상화됨.

### 가능성이 낮은 원인

- DB 영구 장애: 재부팅 직후 `/health`에서 `database=connected`.
- 디스크 full: `/` 사용률 29%.
- PM2 설정 누락: 재부팅 후 PM2 서비스가 front/server를 자동 기동.
- 특정 주문 API 코드 예외: `value.toISOString is not a function` 예외가 2026-06-04 로그에 반복되지만, 이번 504의 직접 증거는 아님. 별도 버그로 추적 필요.

## 한계

정확한 커널/하이퍼바이저/메모리 pressure 원인은 현재 로그만으로 확정할 수 없다. 장애 핵심 시간대에 OS 로그 자체가 끊겨 있고, 로컬에 AWS CLI가 없어 EC2 status check / CloudWatch 지표를 즉시 조회하지 못했다.

## 후속 조치 제안

1. AWS 콘솔에서 2026-06-05 10:15-10:25 KST의 EC2 system status check, instance status check, CPU credit, NetworkIn/Out, EBS burst/latency를 확인한다.
2. CloudWatch Agent 또는 journal remote shipping을 붙여 hang 직전 CPU/memory/load/process 상태가 남도록 한다.
3. ALB/Route53/target health 5xx 알람과 `/health` synthetic check 알람을 설정한다.
4. 재발 시에는 단순 재부팅 전 가능하면 AWS console screenshot/status check와 EC2 serial console output을 먼저 확보한다.
5. 별도 작업으로 `orders.service.ts`의 `value.toISOString is not a function` 예외를 수정한다. 이번 504의 원인으로 단정되지는 않지만, 운영 오류 로그를 계속 만들고 있다.
