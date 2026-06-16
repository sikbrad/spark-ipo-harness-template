# Confluence AX 최신글 기반 임팩트 리서치 계획

작성일: 2026-06-16
대상:
- <https://doflab.atlassian.net/wiki/spaces/AX/pages/878379121/260615>
- <https://doflab.atlassian.net/wiki/spaces/AX/pages/870055948/260609+AX>
- <https://doflab.atlassian.net/wiki/spaces/AX/overview?homepageId=611058224>

## 목적

AX 스페이스의 최근 2주 이내 글과 지정 문서를 읽고, 사용자가 지금 무엇을 하면 가장 임팩트가 큰지 판단한다. 결과는 `proc/research/`에 리서치 문서로 남긴다.

## 범위

- 기준일: 2026-06-16 KST
- 최근 범위: 2026-06-02 00:00 KST 이후 생성 또는 수정된 AX 스페이스 문서
- Confluence 읽기 전용 API 사용
- Confluence 문서 생성, 수정, 이동, 삭제는 하지 않음

## 작업 순서

- [x] 로컬 Confluence API 클라이언트와 인증 변수 확인
- [x] 과거 AX 스페이스 정리 문서와 회의록 문서 규칙 확인
- [x] 지정 페이지 2개 원문/메타데이터 수집
- [x] AX 스페이스 최신 문서 목록 수집
- [x] 최근 문서 본문을 읽고 주제별로 묶기
- [x] 임팩트/실행가능성/레버리지 기준으로 행동 후보 평가
- [x] 리서치 문서 작성
- [x] 산출물 경로와 핵심 결론 검증

## 판단 기준

- 임팩트: 매출, 현장 운영, 반복 업무 절감, 조직 확산에 미치는 효과
- 실행가능성: 사용자가 지금 바로 움직일 수 있는가
- 레버리지: 한 번의 행동이 여러 팀/문서/업무에 재사용되는가
- 리스크: 권한, 데이터 신뢰, 보안, 운영 저항이 큰가

## 산출물

- 리서치 문서: `proc/research/2026-06-16_confluence_ax_latest_impact_research.md`
- 원자료 JSON: `output/confluence-ax-latest-research/`

## 결과

- 최근 2주 범위: 2026-06-02 00:00 KST 이후
- AX 스페이스 최근 페이지: 23개 확인
- 스페이스 홈: `AX` 허브 페이지와 최근 업데이트 매크로 구조 확인
- 리서치 결론: 수금/미수/거래원장/고객 발송/입금확인 루프를 2주짜리 대표 AX 성과로 닫는 것이 가장 임팩트 큼
- 민감정보 처리: 생성 JSON에는 고객/금액/계정/접속 세부 본문을 redaction 처리
