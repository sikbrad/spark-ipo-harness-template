# 메이크샵 주문자동생성 Teams 이슈 확인 및 개발계획

## 목표
Teams에 올라온 메이크샵(온라인샵) 주문자동생성 관련 두 이슈의 실제 현상을 확인하고, 원인 가설과 개발 계획을 정리한다.

## 작업 항목
- [x] Teams 링크 1 원문/스레드 확인
- [x] Teams 링크 2 원문/스레드 확인
- [x] 관련 주문자동생성 코드와 기존 산출물 위치 확인
- [x] 현상별 원인 가설 정리
- [x] 개발 계획과 검증 기준 작성

## 진행 메모
- 2026-06-11 시작. 입력 링크는 온라인주문 팀의 `샵주문-자동화-회계관련`, `샵주문-자동화-개발관련` 채널 메시지다.
- 2026-06-11 Teams 링크 1 확인. `샵주문 고객사 관련` 스레드의 핵심은 "페이크 id" 자체보다 자동생성 주문의 `영업실적담당자` 값이 승인 유효성 검사에서 유효한 `managerUk`로 인식되지 않는 문제다. 김채원님은 화면에 `온라인샵`이 보여도 승인 시 유효성 검사에 걸리고, 다시 `온라인샵`을 선택하면 승인된다고 설명했다.
- 2026-06-11 Teams 링크 2 확인. `온라인 자동 주문 시, 전자세금계산서 발행 주소 자동입력 가능여부` 요청으로, 자동생성 주문에서 `전자계산서주소`만 빠져 고객사 상세의 이메일을 수동 복사하고 있다는 내용이다.
- 2026-06-11 관련 자동화 repo는 `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api`로 확인했다. 현재 로컬 소스의 `scripts/submit-latest-order-to-portal.ts`는 `managerName: "온라인샵"`은 넣지만 `managerUk`는 환경변수에만 의존하고, `invoiceEmail`은 payload에 넣지 않는다.
- 2026-06-11 포탈 승인 검증 경로 확인. `validateApprovalRequestFields`는 승인요청 시 `managerId/managerUk`와 `invoiceEmail`을 필수로 본다. 즉 두 Teams 이슈는 모두 자동생성 payload가 승인 필수값을 안정적으로 채우지 못하는 문제로 수렴한다.
- 2026-06-11 현재 라이브 포탈 샘플도 read-only로 확인했다. 최신 자동생성 주문 일부는 `managerUk=7480a33a-826c-54f8-b0e3-841f8156dfd3`, `managerName=온라인샵`, `invoiceEmail`이 채워져 있었다. 따라서 바로 코드만 고치기 전에 운영 서버(ax01) 소스/환경변수와 로컬 repo 사이의 drift를 먼저 비교해야 한다.

## 현상별 판단
- 링크 1: 화면 표시명 `온라인샵`과 승인 검증용 식별자 `managerUk`가 분리되어 발생한 문제로 본다. 표시명만 있거나 빈/잘못된 UK가 저장된 주문은 승인 검증에서 `영업 실적담당자를 선택해주세요` 유형으로 막힐 수 있다.
- 링크 2: 자동화 payload가 `invoiceEmail`을 누락해, 포탈에서 수동 주문 생성 시 동작하는 고객사/고객 이메일 기본값 채우기를 자동화 경로가 재현하지 못하는 문제로 본다.

## 개발 계획 요약
- 실제 수정 대상 repo에 별도 계획 문서를 만들고, 구현 전 운영 서버와 로컬 소스/환경변수 차이를 먼저 확인한다.
- `온라인샵` 담당자는 환경변수 우선, 없으면 포탈 `/users?search=온라인샵` 조회로 단일 활성 사용자를 확인해 `managerUk`와 `managerName`을 함께 payload에 넣도록 한다.
- `invoiceEmail`은 포탈 고객 이메일, 고객사 이메일 순서로 채우고, API가 상세 조회에서만 이메일을 주면 상세 조회를 추가한다. 이메일이 없거나 형식이 틀리면 자동등록 성공으로 숨기지 말고 명확한 실패/알림 상태로 처리한다.
- 테스트는 payload 생성 단위 테스트와 누락값 실패 케이스를 추가하고, dry-run payload 및 포탈 readback으로 검증한다.

## 2026-06-11 수정 가능성 확인 및 반영
- 수정 가능하다. 실제 수정 지점은 `/Users/gq/works/projs/dofing-order-auto/shop-order-auto-with-api/scripts/submit-latest-order-to-portal.ts`로 확인했다.
- 로컬 코드에 1차 수정 반영:
  - `온라인샵 <dofshop@doflab.com>` 담당자 UK를 env 우선, 없으면 포탈 사용자 검색으로 resolve.
  - 포탈 고객 이메일 우선, 고객사 이메일 후순위로 `invoiceEmail` 주입.
  - `managerUk` 또는 `invoiceEmail`이 없으면 포탈 주문 생성 전 실패.
  - Teams 실패 댓글에서 전자계산서주소/담당자 설정 문제를 별도 안내.
- 검증:
  - `bun run test` 통과: 28 pass, 127 assertions.
  - 포탈 read-only API에서 `온라인샵 <dofshop@doflab.com>` 활성 사용자 1명과 고객사 이메일 필드 제공 확인.
  - 실제 Makeshop 주문번호 dry-run은 현재 API가 `makeshop_return_code=9009`를 반환해 payload 생성까지는 검증하지 못했다.

## 2026-06-11 포탈 데이터 변경 검토
- 즉시 포탈 데이터를 바꿔야 하는 건은 확인되지 않았다. 보고된 현상은 자동화 payload가 필수값을 안정적으로 넣지 못한 것이 핵심이라 코드 수정 대상이다.
- 기존 온라인샵/Makeshop 주문 16건 read-only 상세 조회 결과, 최신 주문들은 `managerUk`와 `invoiceEmail`이 채워져 있었다. 누락은 `OD202606021039` 1건(`COMPLETED`, `makeshop-auto-test`, `managerUk` 빈 값)으로, 승인 막힘 해결에는 필수 보정이 아니다.
- 미래 자동등록 관점에서는 구매 이력 있는 메이크샵 매핑 96개 중 2개(`dofmarketing`, `esther`)가 이메일 후보 없이 resolve될 수 있다. 최근 주문이 2025-02-27, 2024-11-05라 긴급하지 않으며, 실제 계속 주문하는 계정이면 포탈 고객/고객사 이메일 정리가 필요하다.

## 2026-06-11 주문완료 Teams 빌드번호 반영
- 주문완료 Teams 루트 메시지와 성공 댓글 맨 마지막에 `(빌드번호 v{version} {YYMMDD_HHmmss})` 형식의 시스템 정보를 표시하도록 수정했다.
- 로컬 검증: `bun run test` 통과(29 pass, 130 assertions), Bun build check 통과.
- 운영 배포 완료: ax01 배포 빌드번호 `v1.2.0 260611_130141`. 원격 `bun test` 29 pass / 130 assertions, Bun build, seed run, PM2 reload, `/healthz`, `/api/status` 모두 통과. 원격 메시지 생성 확인 결과 주문완료 루트 메시지와 성공 댓글 마지막 줄에 `(빌드번호 v1.2.0 260611_130141)`가 출력된다.

## 2026-06-11 주문완료 성공 댓글 mention 확인
- 사용자 제보 댓글 `1781156995573`을 Graph로 readback했다. 본문에는 `<at id="0">주문담당자</at>`가 있지만 `mentions=[]`라 실제 Teams mention entity가 없다.
- DD Bot 운영 DB의 `bot.api.send` 이벤트는 같은 댓글 activity `1781156995573`을 `mentions=1`로 기록했다. 즉 자동화가 mention을 안 보낸 것이 아니라 DD Bot text mention 경로에서 tag mention이 실제 Teams mention으로 고정되지 않았다.
- `주문담당자` Teams tag ID는 Graph `/teams/{team}/tags` 결과와 환경변수가 일치한다. tag 자체는 유효하며 구성원은 이미연, 김채원 2명이다.
- Adaptive Card `msteams.entities` 기반 tag mention도 운영에서 실험했지만 Bot Framework가 `Decoded tag id has invalid format` 또는 `Mentioned Tag ... does not exist in current Team`로 거부했다. 따라서 tag mention을 계속 밀지 않고 tag 구성원을 user mention으로 확장하는 방식으로 전환했다.
- shop-order 자동화는 `TEAMS_ORDER_HANDLER_USER_MENTIONS`가 있으면 `주문담당자` tag 대신 이미연, 김채원 user mention 2개를 보낸다. 본문에는 역할명 `주문담당자`를 남긴다.
- 운영 배포 완료: ax01 빌드번호 `v1.2.0 260611_151845`. 원격 `bun test` 30 pass / 135 assertions, Bun build, seed run, PM2 reload, `/healthz`, `/api/status` 통과.
- 제보 댓글 `1781156995573`도 in-place 업데이트했다. Graph readback 결과 `mentions`에 이미연, 김채원 AAD user mention 2개가 남고, 본문은 `<at id="0">이미연</at> <at id="1">김채원</at> 주문담당자 포탈에 온라인샵 주문이 등록되었습니다 ...`로 확인됐다.
