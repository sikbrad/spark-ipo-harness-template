# startpoint 문서 재배치 2차 실행 계획

작성일: 2026-06-09 KST

## 목적

2026-06-08 1차 이동 이후 `dof-work-startpoint-04`에 남은 `proc/plan`, `proc/research` 문서를 다시 훑고, 새로 생겼거나 1차에서 보류했던 문서 중 다른 workspace 프로젝트 소유권이 더 강한 항목을 이동한다.

## 판단

추가 이동 대상은 6개다.

| 현재 파일 | 대상 | 판단 |
|---|---|---|
| `proc/research/2026-06-08_logistics-tracking-alternatives.md` | `dof-order-web-3-az/proc/30_research/analysis` | 포털 코드/DB의 `carrier`, `trackingNumber`, 해외 주문/출고 데이터를 근거로 한 물류 추적 설계 리서치다. |
| `proc/research/2026-06-08_solapi-kakao-attachment-cost-research.md` | `dof-order-web-3-az/proc/30_research/analysis` | 포털 repo에 같은 날짜의 거래명세서/PI 카카오 링크 발송 아키텍처 문서가 있어, SOLAPI 비용/첨부 제한 리서치는 그 의사결정 보조자료로 보는 편이 맞다. |
| `proc/research/2026-06-08_channeltalk-support-phone-api-research.md` | `dof-order-web-3-az/proc/30_research/analysis` | 포털 업무규칙 문서에 Zendesk/채널톡/지원 접수 방식이 이미 연결되어 있고, 향후 support/case 통합 판단 자료다. |
| `proc/research/2026-06-08_kakao-cstalk-zendesk-matrixchat-research.md` | `dof-order-web-3-az/proc/30_research/analysis` | Zendesk/MatrixChat/상담톡 직접 구현 리서치는 포털 고객지원 통합 의사결정 문맥이 강하다. |
| `proc/research/2026-06-08_kakao-cstalk-dealer-api-only-research.md` | `dof-order-web-3-az/proc/30_research/analysis` | 상담톡 API-only 상세 보조 리서치로 위 문서와 같은 소유권이다. |
| `proc/plan/2026-06-08_domestic_dental_lab_report_260607.md` | `dental-tech-list-downloader/docs` | 전국 치과기공소 인허가 데이터와 localdata 원천을 다룬 문서라 dental-tech-list-downloader와 데이터 소유권이 가장 가깝다. |

## 유지 판단

- Android SMS forwarding 리서치: 아직 별도 Android/app 프로젝트가 없고 startpoint의 범용 조사 성격이 강해 유지.
- 국내 치과 후보/해외 유통사/Outline prospect 문서: 기존 dental 프로젝트는 지도/다운로드 도구에 좁게 맞춰져 있어 영업처 후보/Outline 발행 전체의 canonical 위치로는 부적절해 유지.
- Teams people/avatar 문서: startpoint의 `data/teams/peoples` 로컬 지식화 작업이며 Teams bot 구현 repo 문서는 아니므로 유지.
- Confluence AX reorg 문서: Atlassian/Confluence 운영 정리이며 별도 제품 repo가 없어 유지.

## 진행 기록

- 2026-06-09: 이동 전 대상 repo 상태와 후보 문서 확인.
- 2026-06-09: 실파일 6개 이동 완료.

## 이동 결과

| 대상 | 이동 수 | 파일 |
|---|---:|---|
| `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/30_research/analysis` | 5 | `2026-06-08_logistics-tracking-alternatives.md`, `2026-06-08_solapi-kakao-attachment-cost-research.md`, `2026-06-08_channeltalk-support-phone-api-research.md`, `2026-06-08_kakao-cstalk-zendesk-matrixchat-research.md`, `2026-06-08_kakao-cstalk-dealer-api-only-research.md` |
| `/Users/gq/works/projs/dental-analysis/dental-tech-list-downloader/docs` | 1 | `2026-06-08_domestic_dental_lab_report_260607.md` |

검증:

- 이동 pair 6개 모두 source에서 사라지고 target에 존재함.
- Android SMS, 국내/해외 prospect, Teams people/avatar, Confluence AX reorg 문서는 유지.
