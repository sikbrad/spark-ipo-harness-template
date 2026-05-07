---
name: amaranth-org
description: 아마란스 ERP(erp.doflab.com) 조직도/임직원 정보 받기. playwright-cli 기반. "아마란스 조직도", "ERP 임직원", "개발부 인원", "연구소 멤버", "팀별 사람", "누가 어느 팀이야" 등 조직/사람 관련 요청 시 사용.
---

# 아마란스 ERP 조직 정보 추출

`@playwright/cli` 기반. `proc/lib/pwc_amaranth.py`의 org helper로 ERP 조직 데이터를 가져온다.

## 도구 스택

- `@playwright/cli` (전역 `playwright-cli` 명령) — 사이트별 격리 세션, 영속 프로필
- `proc/lib/pwc.py` — 세션 wrapper (`S('amaranth')`)
- `proc/lib/pwc_amaranth.py` — Amaranth ERP helper

## 전제

1. `playwright-cli` 설치 — 한 번만: `npm install -g @playwright/cli@latest`.
2. **Amaranth 세션 부트스트랩** (첫 1회):
   ```bash
   playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed
   ```
   브라우저 창이 뜨면 회사코드 `doflab` → ID(`.env ERP_PERSONAL_ID`) → PW(`.env ERP_PERSONAL_PW`) 로그인 → 출퇴근 체크 popup **취소**. 이후 `--persistent` 디스크 프로필이 로그인 유지.
3. `search_org()`는 조직도 다이얼로그가 닫혀 있어도 자동으로 연다.

## 핵심 helper (`proc/lib/pwc_amaranth.py`)

| 함수 | 용도 |
|---|---|
| `open_org_dialog(s)` | 우상단 조직도 아이콘(`span.btn.org`) 클릭 |
| `search_org(s, text)` | 조직도 다이얼로그 검색창에 `text` 입력 + Enter, `gw102A02` 응답 JSON 반환 |
| `research_members(s)` | `연구원` 검색 후 `comOptPath`에 `연구소` 또는 `선행기술` 포함자만 반환. dict keyed by 이름 |

## 응답 필드 (gw102A02 → resultData[i])

자주 쓰는 필드:
- `empName` (이름), `loginId` (사번 alias)
- `comOptPath` 예: `주식회사 디오에프>연구소>웹` (사용자에게 보여줄 부서경로)
- `comOptName` 부서 leaf 이름 (예: `웹`)
- `positionName` (전임연구원/책임연구원/수석연구원/...)
- `dutyName` (담당/파트장/팀장)
- `mainWork` 자유기입 담당업무 (`백엔드 개발`, `회로 설계` 등)
- `mobileTelNum`, `emailAddr`, `bday`, `joinDay`
- `deptSeq`, `path` (1000=회사, 2035=연구소, ...)

검색은 substring-of-anywhere 매칭이라 부서명/이름/직책/담당업무 모두 hit 가능. 결과를 자체 필터링해야 정확하다.

## 표준 호출

### 1) 개발부(연구소+선행기술) 27명 받기

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import research_members
s = S('amaranth')
members = research_members(s)
print(f'{len(members)} members')
print(json.dumps(members, ensure_ascii=False, indent=2)[:2000])
"
```

### 2) 임의 키워드 검색

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import search_org
s = S('amaranth')
data = search_org(s, '개발')
items = data.get('resultData', [])
print(f'{len(items)} hits for 개발')
for u in items[:10]:
    print(u['empName'], '-', u['comOptPath'], '-', u.get('mainWork',''))
"
```

### 3) 특정 부서 사람만 추리기

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import search_org
s = S('amaranth')
data = search_org(s, '연구원')
team = '소프트웨어기술'
hits = [u for u in data['resultData'] if u.get('comOptName') == team]
for u in hits:
    print(f\"{u['empName']}({u['loginId']}) - {u['positionName']}/{u['dutyName']} - {u.get('mainWork','')}\")
"
```

## 조직 트리 (2026-05 기준)

```
주식회사 디오에프 (86)
├── 디오에프 (6)
│   ├── 선행기술 (3)
│   └── AX (1)
├── 영업본부 (38)
├── 경영기획본부 (10)
├── 품질경영 (3)
├── 연구소 (24)
│   ├── 소프트웨어기술 (8)
│   ├── 시스템혁신 (5)
│   ├── 웹 (4)
│   ├── 제품기획 (5)
│   └── 프로젝트관리 (2)
└── 생산관리 (5)
```

**"개발부"라는 정식 부서명은 없다.** 사용자가 개발부를 언급하면 보통 다음 중 하나를 의미:
- 좁은 의미 (소프트웨어 개발만): 소프트웨어기술 + 웹 = 12명
- 넓은 의미 (R&D 전체): 연구소 + 선행기술 = 27명 ← `research_members()` 기본값
- 시스템혁신은 HW/FW 설계 (회로/기구/펌웨어)이라 SW 개발과는 결이 다름

모호하면 사용자에게 물어라.

## API 직접 호출 금지

`fetch('/gw/APIHandler/...')`로 직접 호출하면 `허용된 쿠키 인증 URL이 아닙니다` (601) 오류. 인증 헤더(`Authorization`, `wehago-sign`, `timestamp`, `transaction-id`)는 앱의 HTTP client만 자동 부착한다. 항상 UI 트리거 → XHR 캡처 방식을 쓴다 (`search_org`가 그렇게 구현됨).

## 조직도 다이얼로그 관련 핵심 endpoint

- `gw102A02` — 텍스트 검색
- `gw102A01` — 트리 노드 expand (`parentSeq`, `deptPath` 인자)
- `gw102A02` 응답 → `resultData: [User, ...]`
- `gw102A01` 응답 → 트리 (자식 부서 리스트)

## 주의

- **로그인 풀린 상태** → `playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed` 로 재로그인.
- **여러 탭** → `s.tab_list()` 로 확인, `s.tab_select(idx)` 로 전환. 다른 사이트 세션 간섭 없음.
