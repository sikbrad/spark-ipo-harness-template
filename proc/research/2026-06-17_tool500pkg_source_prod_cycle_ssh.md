# 2026-06-17 TOOL 500PKG 자동화 소스/본섭 검증 및 SSH 배포 이슈

## 요약

`shop-order-auto-with-api`에서 `[툴 패키지] TOOL 500PKG` 주문은 기존 자동화가 상품 모델번호 없음으로 제외하던 케이스였다. 이번 작업으로 소스에는 `TOOL 500PKG` 전용 경로를 추가했다. 이 경로는 계약을 먼저 생성하고, 생성된 계약 `uk`를 주문 payload에 연결해 주문을 생성한다.

본섭 포탈 API lifecycle 검증도 수행했다. 테스트 계약/주문을 실제 본섭에 생성했고, readback 검증 후 테스트 주문과 계약을 soft delete로 정리했다.

초기에는 AX01 접속용 SSH private key가 없어 worker 배포가 실패했지만, 이후 `/home/gq/.ssh/id_ed25519`와 `/home/gq/.ssh/id_ed25519.pub`를 복사해 접속을 복구했다. 최종적으로 `package.json` version을 `1.3.0`으로 올리고, README/CHANGELOG 변경 이력을 추가한 뒤 AX01 본섭에 `v1.3.0 260617_230859`로 배포 완료했다. Teams 알림 빌드번호도 `(빌드번호 v1.3.0 260617_230859)`로 확인했다.

## 관련 경로

- 자동화 소스 repo:
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api`
- 주요 수정 파일:
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/scripts/submit-latest-order-to-portal.ts`
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/scripts/submit-latest-order-to-portal.test.ts`
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/scripts/tool500pkg-prod-cycle.ts`
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/package.json`
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/README.md`
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/CHANGELOG.md`
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/proc/plan/2026-06-17_tool500pkg_contract_order_auto.md`
- 본섭 lifecycle 결과 파일:
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/output/research/tool500pkg_prod_cycle_result_20260617_202737.json`
- 수동 생성 결과 기록:
  - `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/tool500pkg_prod_create_20260617173732.json`

## 업무 규칙 정리

`TOOL 500PKG`는 일반 온라인샵 주문처럼 상품코드 매핑 후 주문만 만드는 것이 아니라, 다음 순서로 처리해야 한다.

1. 계약 생성
2. 계약 `uk`를 주문에 연결
3. 주문 생성

계약 payload 핵심값:

- `contractName`: `{고객사명}_Tool Promotion 500PKG(1)`
- `companyUk`: 포탈 고객사 `uk`
- `customerUk`: `null`
- `managerUk`: `b1808747-6f97-5005-9f5e-7f78de738e97`
- `managerName`: `이미연`
- `contractDate`: 주문일
- `periodFrom`: 주문일
- `periodTo`: 주문일 + 1년
- `contractType`: `PREPAID`
- 제품:
  - `productCode`: `CO-ET-007`
  - `productName`: `Tool Promotion 500PKG`
  - `unitPrice`: `5,000,000`
  - `quantity`: `1`
  - `supplyAmount`: `4,545,455`
  - `taxAmount`: `454,545`
  - `totalAmount`: `5,000,000`
  - `note`: `온라인 주문 :  {shopOrderNo}`

주문 payload 핵심값:

- `orderName`: `{고객사명}_Tool Promotion 500PKG(1)`
- `orderType`: `PAID`
- `contractUk`: 방금 생성한 계약의 `uk`
- `companyUk`: 포탈 고객사 `uk`
- `customerUk`: 포탈 고객 `uk`
- `managerUk`: `b1808747-6f97-5005-9f5e-7f78de738e97`
- `managerName`: `이미연`
- `requestDate`, `performanceDate`: 주문일
- `externalOrderNo`: 쇼핑몰 주문번호
- `paymentTerms`: `002`
- `invoiceEmail`: 포탈 고객 이메일 우선
- 주소/연락처:
  - Makeshop 배송지보다 포탈 고객사 주소와 포탈 고객 연락처를 우선한다.
- 제품:
  - `productCode`: `CO-ET-007`
  - `productName`: `Tool Promotion 500PKG`
  - `unitPrice`: `0`
  - `quantity`: `1`
  - `supplyAmount`: `0`
  - `taxRate`: `10`
  - `taxAmount`: `0`
  - `totalAmount`: `0`
  - `freeReason`: `OTHER`
  - `freeReasonCode`: `3104`
  - `note`: `온라인 주문 :  {shopOrderNo}({YYYY-MM-DD})\n툴 프로모션 500PKG\n`
- 수금:
  - `status`: `SCHEDULED`
  - `collectionDueDate`: 주문월 말일
  - `amount`: `5,000,000`
  - `currency`: `KRW`
  - `collectionMethod`: Makeshop 결제수단 기준. 카드 케이스는 `CREDIT_CARD`
  - `note`: 빈 문자열

## 수동 생성 건

수동으로 생성한 운영 건은 보존해야 한다.

- 계약:
  - `CO202606170003`
  - URL: `https://portal.doflab.com/contracts/CO202606170003`
  - 고객사: `라라치과기공소(강남)`
  - 계약명: `라라치과기공소(강남)_Tool Promotion 500PKG(1)`
  - 상태 확인: `GET 200`, `deletedAt=null`
- 주문:
  - `OD202606171035`
  - URL: `https://portal.doflab.com/orders/OD202606171035`
  - 고객사: `라라치과기공소(강남)`
  - 주문명: `라라치과기공소(강남)_Tool Promotion 500PKG(1)`
  - 상태 확인: `GET 200`, `deletedAt=null`, `orderStatus=EXECUTIVE_APPROVED`

## 소스 변경 내용

`submit-latest-order-to-portal.ts`에 다음을 추가했다.

- `TOOL_500PKG_*` 상수
  - Makeshop UID: `12407549`
  - 포탈 제품코드: `CO-ET-007`
  - 제품명: `Tool Promotion 500PKG`
  - 금액: `5,000,000`
  - 주문 제품 무상 사유 코드: `3104`
  - 기본 담당자: `이미연 / b1808747-6f97-5005-9f5e-7f78de738e97`
- `isTool500PkgShopLine`
  - 상품 UID 또는 상품명 텍스트로 `TOOL 500PKG` 감지
- `isTool500PkgOrder`
  - 주문 전체가 `TOOL 500PKG` 단일 계열일 때만 전용 흐름 진입
  - 일반 상품과 섞인 주문은 자동 생성하지 않고 수동 검토 대상으로 중단
- `buildTool500PkgContractPayload`
  - 계약 payload 생성
- `buildTool500PkgOrderPayload`
  - 주문 payload 생성
- `run()`
  - `tool500PkgMode`면 `/contracts` POST 후 `/orders` POST
  - poller 호환을 위해 반환값의 `portal_url`, `readback_order_no`, `readback_status`는 주문 기준 유지

전용 담당자는 기본값을 하드코딩하되 다음 env로 override 가능하게 했다.

- `PORTAL_TOOL_500PKG_MANAGER_UK`
- `PORTAL_TOOL_500PKG_MANAGER_NAME`
- `TOOL_500PKG_MANAGER_UK`
- `TOOL_500PKG_MANAGER_NAME`

일반 온라인샵 주문의 담당자 규칙(`온라인샵`)은 유지했다.

## 테스트

로컬 테스트:

- `bun test scripts/submit-latest-order-to-portal.test.ts`
  - 24 pass
  - 116 assertions
- `bun run test`
  - 34 pass
  - 163 assertions
- Bun build check:
  - `submit-latest-order-to-portal.ts`
  - `tool500pkg-prod-cycle.ts`
  - `poll-order-emails.ts`
  - `teams-order-notifier.ts`
  - `serve-static.ts`
  - 성공

핵심 회귀 테스트:

- `TOOL 500PKG payloads match the manually created prod contract and order`
- 수동 생성 payload(`CO202606170003`, `OD202606171035`)와 소스 생성 payload가 동일해야 통과한다.

## 본섭 lifecycle 검증

`scripts/tool500pkg-prod-cycle.ts`를 추가해 실제 본섭 API lifecycle을 검증했다.

검증 순서:

1. 소스의 TOOL 500PKG payload builder로 테스트 계약 payload 생성
2. 본섭 `/contracts` POST
3. 생성된 계약 `uk`를 주문 payload에 연결
4. 본섭 `/orders` POST
5. 계약/주문 readback
6. readback assertion
7. 테스트 주문 soft delete
8. 테스트 계약 soft delete
9. 삭제 후 GET 404 확인

실행 결과:

- test external order no:
  - `TEST-TOOL500PKG-260617202737`
- 생성된 테스트 계약:
  - `CO202606170004`
  - create status: `201`
- 생성된 테스트 주문:
  - `OD202606171042`
  - create status: `201`
- readback assertion:
  - `passed`
- 테스트 주문 삭제:
  - `DELETE /orders/OD202606171042`
  - status: `204`
  - 삭제 후 `GET /orders/OD202606171042`: `404`, `주문을 찾을 수 없습니다`
- 테스트 계약 삭제:
  - `DELETE /contracts/CO202606170004`
  - status: `204`
  - 삭제 후 `GET /contracts/CO202606170004`: `404`, `계약을 찾을 수 없습니다`

테스트 레코드는 이름에 `(테스트)`를 붙여 만들었다.

## 삭제 API 확인

포탈 서버 코드 기준으로 주문/계약 삭제는 hard delete가 아니라 soft delete다.

주문:

- controller:
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/apps/server/src/orders/orders.controller.ts`
  - `apiContract.orders.deleteOrder`
- service:
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/apps/server/src/orders/orders.service.ts`
  - `softDelete(idOrNo, deletedBy)`
- 조건:
  - 이미 삭제된 주문이면 실패
  - `REGISTERED` 상태에서만 삭제 가능
  - 삭제 시 `ArchivedItem` 생성
  - 주문의 미완료 수금을 취소 처리
  - 계약 연결 주문이면 계약 잔액 재계산

계약:

- controller:
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/apps/server/src/contracts/contracts.controller.ts`
  - `apiContract.contracts.deleteContract`
- service:
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/apps/server/src/contracts/contracts.service.ts`
  - `softDelete(idOrNo, deletedBy)`
- 조건:
  - 이미 삭제된 계약이면 실패
  - 연관 주문이 있으면 실패
  - 따라서 테스트 정리는 주문 삭제 후 계약 삭제 순서가 맞다.

## AX01 배포 시도와 SSH private key 이슈

배포 명령:

```bash
bun run deploy:prod
```

배포 스크립트:

- `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/deploy_prod.sh`

배포 대상:

- `REMOTE_HOST=DOF-AX01`
- `REMOTE_PATH=/home/ax01/works/projs/shop-order-auto-with-api-01`
- frontend domain:
  - `dofshop-auto-mgmt.doflab.com`
- port:
  - `54300`

배포 실패:

```text
ax01@61.36.134.214: Permission denied (publickey,password).
```

원격 probe:

```bash
/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/.agents/skills/remote-instance/scripts/remote_probe.sh --target ax01 --check
```

결과:

```text
target=ax01
command=ssh -p 22 ax01@61.36.134.214
user=ax01
host=61.36.134.214
port=22
ax01@61.36.134.214: Permission denied (publickey,password).
```

SSH debug command:

```bash
ssh -vvv -o BatchMode=yes -o ConnectTimeout=8 DOF-AX01 'pwd'
```

debug 결과 핵심:

- SSH config는 현재 실행 환경에서 `/home/gq/.ssh/config`를 읽었다.
- `Host DOF-AX01` 설정:
  - host: `61.36.134.214`
  - user: `ax01`
  - port: `22`
- default private key 후보가 모두 없음:
  - `/home/gq/.ssh/id_rsa`
  - `/home/gq/.ssh/id_ecdsa`
  - `/home/gq/.ssh/id_ecdsa_sk`
  - `/home/gq/.ssh/id_ed25519`
  - `/home/gq/.ssh/id_ed25519_sk`
- 최종 메시지:

```text
No more authentication methods to try.
ax01@61.36.134.214: Permission denied (publickey,password).
```

ssh-agent 확인:

```bash
ssh-add -l
```

결과:

```text
Could not open a connection to your authentication agent.
```

확인한 SSH 관련 경로:

- 현재 SSH config/debug 기준:
  - `/home/gq/.ssh/config`
  - `/home/gq/.ssh/known_hosts`
- 추가로 존재 확인된 SSH 항목:
  - `/Users/gq/.ssh/aws-ax/`
  - `/Users/gq/.ssh/config`
  - `/Users/gq/.ssh/known_hosts`
  - `/Users/gq/.ssh/known_hosts.old`
  - `/Users/gq/.ssh/authorized_keys`
- EC2용 key 경로는 config에 존재:
  - `/Users/gq/.ssh/aws-ax/ax.pem`
  - 이 key는 `OrderPortal-ax-dev-ec2`, `OrderPortal-ax-prod-ec2`용으로 설정되어 있고, `DOF-AX01` host에는 `IdentityFile`이 지정되어 있지 않다.
- AX01용 private key는 현재 확인되지 않았다.

당시 결론:

- 본섭 포탈 API에 테스트 계약/주문 생성 및 삭제 검증은 완료했다.
- AX01 worker에 새 코드를 배포하는 것은 아직 완료하지 못했다.
- 원인은 현재 실행 환경에 `DOF-AX01` 접속용 SSH private key가 없거나 ssh-agent에 로드되어 있지 않기 때문이다.

## 후속 조치 완료: SSH key 복사 및 AX01 배포

이후 odung/ws1203 원격 환경에 필요한 SSH key가 복사되었다.

- 복사된 key:
  - `/home/gq/.ssh/id_ed25519`
  - `/home/gq/.ssh/id_ed25519.pub`
- 권한:
  - private key: `600`
  - public key: `644`
- fingerprint:
  - `SHA256:acD4yDk5fSZCsr1WJNHrMir6sz9c1QSwQB9m1tiHSmI`
- AX01 접속 확인:
  - 원격에서 `DOF-AX01` 접속 성공
  - 확인값: `/home/ax01`, host `ax01`, user `ax01`

배포 실행:

- 실행 위치:
  - `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api`
- 실행 명령:

```bash
bun run deploy:prod
```

배포 결과:

- `DEPLOY_EXIT:0`
- 배포 대상:
  - `DOF-AX01:/home/ax01/works/projs/shop-order-auto-with-api-01`
- 최종 배포 빌드:
  - `v1.3.0 260617_230859`
- version 문서화:
  - `package.json`: `1.3.0`
  - `README.md`: 현재 버전과 최근 변경 요약 추가
  - `CHANGELOG.md`: `v1.3.0`, `v1.2.0` 변경 이력 추가
- Teams 알림 빌드번호:
  - 알림 코드는 `SHOP_ORDER_AUTO_BUILD_VERSION`과 `SHOP_ORDER_AUTO_BUILD_ID`를 읽어 `(빌드번호 v{version} {buildId})` 형식으로 메시지에 넣는다.
  - `deploy_prod.sh`가 원격 `.env`에 `SHOP_ORDER_AUTO_BUILD_VERSION=${BUILD_VERSION}`와 `SHOP_ORDER_AUTO_BUILD_ID=${BUILD_ID}`를 기록한다.
  - `BUILD_VERSION` 기본값은 `package.json`의 `version`이라 현재 `v1.3.0`이다.
  - `BUILD_ID` 기본값은 배포 시각 기준 `YYMMDD_HHMMSS`라 배포 때마다 갱신된다.
  - PM2는 `pm2 startOrReload ecosystem.config.cjs --update-env`로 reload되어 새 `.env` 값을 반영한다.
  - 원격 `.env` 확인:
    - `SHOP_ORDER_AUTO_BUILD_VERSION=1.3.0`
    - `SHOP_ORDER_AUTO_BUILD_ID=260617_230859`
  - 원격 알림 함수 확인:
    - `(빌드번호 v1.3.0 260617_230859)`
- remote verification:
  - tests: `34 pass`, `163 assertions`
  - build check: 통과
  - seed run: `submitted=0`, `skipped=6`, `failed=0`
  - PM2 reload: 성공
  - `shop-order-auto-front`: `online`
  - `shop-order-auto-worker`: `online`
- health:
  - `{"ok":true,"service":"shop-order-auto-mgmt"}`
- status:
  - sqlite: `ready`
  - failed: `0`

## AX01 배포본 TOOL 500PKG lifecycle 재검증

배포 후 AX01 배포본에서도 `TOOL 500PKG` prod lifecycle을 재검증했다.

- 테스트 계약:
  - `CO202606170005`
- 테스트 주문:
  - `OD202606171044`
- readback:
  - `passed`
- 주문 삭제:
  - `204`
  - 삭제 후 `404`
- 계약 삭제:
  - `204`
  - 삭제 후 `404`
- 원격 결과 파일:
  - `/home/ax01/works/projs/shop-order-auto-with-api-01/output/research/tool500pkg_prod_cycle_result_20260617_deployed_retry.json`

최종 결론:

- 소스 구현 완료.
- 로컬 단위/통합 테스트 통과.
- 본섭 포탈 API lifecycle 검증 완료.
- AX01 worker 배포 완료.
- 버전 `v1.3.0` 상향 및 README/CHANGELOG 문서화 완료.
- Teams 알림 빌드번호 `v1.3.0 260617_230859` 반영 확인.
- AX01 배포본 lifecycle 재검증 완료.
- 수동 생성 운영 건 `CO202606170003` / `OD202606171035`는 보존 대상이며, 테스트 생성 건만 삭제 처리했다.
