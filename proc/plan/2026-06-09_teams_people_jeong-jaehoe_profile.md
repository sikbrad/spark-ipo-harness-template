# Teams 정재회 업무 아바타 생성

## 목표
2026-06-08 Teams 수집분을 바탕으로 `data/teams/peoples/정재회/` 인물 아바타, 업무이력, 업무규칙을 신규 생성한다.

## 원칙
- 기존 `data/teams/peoples/` 문서 구조와 문장 스타일을 따른다.
- 원문 전체를 옮기지 않고 업무 재현에 필요한 판단 기준과 원천 경로만 남긴다.
- 전화번호, 계정, 개인식별값은 요약 문서에 쓰지 않는다.
- 직접 발화와 간접 언급을 분리한다.
- 번호가 붙은 중복 export는 최신 ID 포함 파일을 source of truth로 삼고 중복 반영하지 않는다.

## 대상 원천
- `data/company/people/정재회_person_info.json`
- `output/teams/conversations/groupchat/핑거세일즈 주문현황-19a8ba842042bd4ef0.md`
- `output/teams/conversations/groupchat/온라인 쇼핑몰 - DOF Shop-1967cd660576954fc8.md`
- `output/teams/conversations/groupchat/해외물류-1977376e2255df4d1a.md`
- `output/teams/conversations/dm/정재회-194bf9f38ab3f84f9b.md`
- 간접 근거: `중국Philden 수입관련`, `출고 - 생산/물류`, `init-crm-renew`

## 작업 항목
- [x] 기존 인물별 문서 구조 확인
- [x] 정재회 인사정보와 Teams 원천 범위 확인
- [x] 직접 발화와 간접 언급 분리
- [x] 정재회 인물 폴더, 업무이력, 업무규칙 작성
- [x] source-coverage와 공통 인덱스 갱신
- [x] 변경 내용 검증

## 증분 판단
- 정재회는 기존 `data/teams/peoples/`에 폴더가 없으므로 신규 인물로 생성한다.
- 핵심 직접 발화는 핑거세일즈 주문현황 606개, 온라인 쇼핑몰 123개, 해외물류 38개, DM 9개 메시지 블록이다.
- `중국Philden 수입관련`에서는 직접 발화는 없지만 물류(악세사리 출고) 담당으로 지정되어 보조 근거로 사용한다.
- `출고 - 생산/물류`와 `init-crm-renew`는 정재회 직접 발화가 거의 없거나 제한적이므로 역할 후보와 권한/인터뷰 맥락으로만 반영한다.

## 검증 메모
- `data/teams/peoples/정재회/`에 문서 20개가 생성되었음을 확인했다.
- 새 정재회 문서에서 전화번호, 이메일, login_id, 생일, chat_id 같은 민감 토큰이 검색되지 않음을 확인했다.
- 문서 내 `output/teams`, `data/company`, `data/teams` 원천 경로가 모두 실제 파일로 역추적됨을 확인했다.
- `git diff --check -- data/teams/peoples proc/plan/2026-06-09_teams_people_jeong-jaehoe_profile.md` 결과 공백/패치 오류가 없었다.
- `data/`는 `.gitignore` 대상이므로 Git diff에는 데이터 문서 변경이 표시되지 않는다.
