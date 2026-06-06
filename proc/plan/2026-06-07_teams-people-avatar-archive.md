# Teams 전체 백업 최신화와 인물별 업무 아바타 자료화

## 목표
기존 Teams 전체 대화 백업 위치를 확인하고 최신으로 업데이트한 뒤, 양승현, 김규탁, 조소연의 업무 기록을 직접 읽어 업무 영역별 문서로 정리한다.

## 작업 항목
- [x] 기존 Teams 전체 백업 산출물과 실행 스크립트 확인
- [x] 전체 방/채널/DM 대화 백업을 최신으로 업데이트
- [x] 최신화 결과의 범위, 실패, 누락 가능성 검증
- [x] `data/teams/peoples/양승현`, `data/teams/peoples/김규탁`, `data/teams/peoples/조소연` 폴더 생성
- [x] 각 인물 관련 DM/그룹/채널 자료를 직접 읽고 업무 영역 식별
- [x] 인물별 업무 영역 폴더와 가상 아바타용 요약 문서 작성
- [x] 작업 근거와 남은 리스크를 계획문서에 업데이트
- [ ] 인물별 업무이력을 주문/국가/업무 맥락에서 다시 읽고 사례 단위로 보강
- [ ] 각 인물의 반응·판단·행동 패턴을 `업무이력/` 문서로 분리
- [ ] 보강 문서 검증 및 남은 한계 기록

## 진행 메모
- 기존 전체 백업 위치는 `output/teams/conversations/`이고, 원본 JSON/Markdown과 `_state.sqlite3` 상태 DB가 함께 있다.
- 이전 결과는 2026-05-19 추출 기준 DM 59, 그룹채팅 44, 팀 4, 채널 29, 오류 0이었다.
- 최신 Graph 백업은 2026-06-07 01:24:51 +0900 기준으로 갱신되었다.
- Graph 백업 결과: DM 61, 그룹채팅 45, 채팅 메시지 31,176개, 신규 채팅 메시지 38개, 채팅 오류 0.
- Teams 채널 결과: 팀 4개, 채널 30개, 채널 스레드 2,877개, 신규/갱신 스레드 454개, 답글 2,816개.
- `이미연` DM은 최초 rescan 중 502 오류가 있었고, 스크립트에 502/네트워크 예외 retry와 `--only-chat` 필터를 추가한 뒤 단건 재실행으로 복구했다.
- Graph에서 실패한 `DOF Inc. / General`은 Teams 브라우저 내부 API fallback으로 최신 50개 posts / 40개 parsed threads를 별도 저장했다.
- 직접 읽은 주요 원문: 대상자 DM, `핑거세일즈 주문현황`, `init-crm-renew`, `noco-users`, `기업부설연구소`, `focus-ai-coders`, `data/company/people/*_person_info.json`.

## 산출물
- Teams 전체 백업: `output/teams/conversations/`
- Teams Graph 최신 요약: `output/teams/conversations/_summary.json`
- Teams 브라우저 fallback 요약: `output/teams/conversations/teams/DOF Inc-2318874eb31a4eb08e/_browser_fallback_summary.json`
- 인물별 업무 아바타 자료 루트: `data/teams/peoples/`
- 양승현: `README.md`, `avatar-context.md`, `source-index.md`, 업무영역 4개
- 김규탁: `README.md`, `avatar-context.md`, `source-index.md`, 업무영역 5개
- 조소연: `README.md`, `avatar-context.md`, `source-index.md`, 업무영역 6개

## 추가 요청 범위
- 2026-06-07 추가 요청: 특정 인물의 업무 기록을 단순 역할 요약이 아니라 "주문/국가/업무에 따라 어떻게 반응하고 동작했는지" 남긴다.
- 현재 문맥상 대상은 기존 3명(양승현, 김규탁, 조소연)으로 처리한다.
- 방식은 자동 키워드 분석이 아니라 원문 대화와 기존 정리 문서를 직접 읽고, 사례를 업무 맥락별로 사람이 읽을 수 있는 문서로 남긴다.

## 남은 리스크
- Graph와 브라우저 내부 API 모두에서 403 Forbidden인 채널 3개는 현재 계정 권한으로 본문 최신화가 불가능했다: `DOF Inc. / proj-출고-예외승인`, `DOF Inc. / 기술지원 운영`, `DOF Inc. / proj-월결산-생산재고회계`.
- `DOF Inc. / General`은 Graph 전체 pagination이 502/504 skiptoken 오류로 끝까지 재수집되지 않았다. 기존 2026-05-19 백업 파일은 유지했고, 브라우저 fallback 최신 50개 posts를 별도 보강했다.
- 따라서 이번 결과는 "Graph 접근 가능한 모든 DM/그룹/채널은 최신화, 접근 제한/서버 pagination 오류 채널은 증거 파일과 fallback 산출물 보존" 상태다. 100% 전체 최신화를 위해서는 해당 403 채널 권한 또는 관리자 export 경로가 필요하다.
