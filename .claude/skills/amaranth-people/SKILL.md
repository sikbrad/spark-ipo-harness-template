---
name: amaranth-people
description: 아마란스 ERP(erp.doflab.com) 전체 임직원 명부를 `data/company/people/<이름>_person_info.json` 개별 파일로 dump. diff sync — ERP 현행자는 덮어쓰기/추가, 퇴사자는 `_archived/`로 이동. playwright-cli + 캡처 헤더 replay 기반. "회사 인적정보", "임직원 명부", "전체 사람 dump", "people 갱신", "퇴사자 정리", "people sync" 등 명부 일괄 수집 요청 시 사용. 특정 부서/소수 인원 ad-hoc 조회는 `/amaranth-org`.
---

# 아마란스 ERP 전체 임직원 명부 dump

전체 86명(2026-05 기준) 규모 회사의 인적정보를 사람별 JSON 파일로 떨어뜨린다. 매번 idempotent — ERP 명단과 폴더 내용이 한 번의 호출로 정확히 동기화된다.

## 전제

- `playwright-cli` + `-s=amaranth` 세션이 로그인된 상태. 아니면 먼저:
  ```bash
  playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed
  ```
- 헬퍼는 [proc/lib/pwc_amaranth.py](../../../proc/lib/pwc_amaranth.py)의 `fetch_all_employees`, `employee_info`, `sync_people_files`.

## 수집 메커니즘 (왜 단순 검색으로 안 되는가)

조직도 다이얼로그 검색(`gw102A02 selectedType=search`)은 부서 leaf 이름·이름·직급·담당업무만 substring 매칭이라 전원을 enumerate 못 한다. 트리 노드 선택(`gw102A02 selectedType=tree`)도 **직속 멤버만** 반환 (descendant 미포함). 그래서:

1. `gw102A01 isTreeAllOpen=True parentSeq=0` — 전체 부서 트리(현재 29 노드) 한 번에
2. 각 부서 노드마다 `gw102A02 selectedType=tree` — 직속 멤버
3. `empSeq`로 dedup

두 endpoint 모두 `wehago-sign` HMAC 헤더가 필수라 직접 fetch는 601. SPA가 한 번 fire한 요청의 헤더를 캡처해 replay (이미 헬퍼가 캡슐화).

## 표준 호출

### 전체 명부 dump (diff sync)

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import fetch_all_employees, sync_people_files
users = fetch_all_employees(S('amaranth'))
result = sync_people_files(users)  # default: data/company/people/
print(f\"written={len(result['written'])}, archived={len(result['archived'])}\")
for f in result['archived']:
    print('  archived:', f)
"
```

소요시간 ~10초 (트리 노드 29개 × 250ms). 결과:
- `data/company/people/이름_person_info.json` — 현행 86명
- `data/company/people/_archived/이름_person_info.json` — 퇴사자 (있다면)

### 원본 record가 필요한 경우

`employee_info()`로 정규화하지 않고 원시 gw102A02 응답을 그대로:

```python
users = fetch_all_employees(s)
# users[i]는 원본 dict — empName, comOptPath, positionName, mainWork, mobileTelNum, ...
```

`amaranth-org` 스킬 문서의 "응답 필드" 섹션 참조.

## person_info.json 형식

```json
{
  "name": "백인식",
  "login_id": "ins",
  "employee_number": "25090001",
  "emp_seq": "2205",
  "company": "주식회사 디오에프",
  "dept_path": "주식회사 디오에프>디오에프>AX",
  "dept": "AX",
  "dept_seq": "2206",
  "position": "부장",
  "duty": "팀장",
  "main_work": "AI Transformation",
  "email": "ins@doflab.com",
  "mobile": "01067789489",
  "ext_num": null,
  "tel_num": null,
  "birthday": "1989-03-18",
  "join_day": "2025-09-22",
  "addr": null,
  "zip_code": null
}
```

빈 문자열은 `null`로 정규화됨. 매핑은 `pwc_amaranth.py:_EMP_FIELD_MAP`.

## sync 동작

| 케이스 | 결과 |
|---|---|
| ERP에 있고 파일도 있음 | 덮어쓰기 (정보 갱신) |
| ERP에 있고 파일 없음 | 새로 생성 |
| ERP에 있는데 이름 바뀜 | 옛 파일 삭제 + 새 파일명으로 작성 (empSeq 매칭) |
| ERP에 없는데 파일 있음 (퇴사) | `_archived/`로 `os.replace` 이동 |
| 동명이인 (현재 0건) | 두 번째 사람부터 `<name>_<login_id>_person_info.json` |

`_archived/`는 git에 그대로 commit해도 되고, history만 따로 보고 싶으면 `git mv` 한 번 더 해서 다른 곳으로 옮겨도 무방.

## 트러블슈팅

- `gw102A01/gw102A02 인증 헤더 캡처 실패` → 세션 로그아웃 상태. 위 부트스트랩 명령으로 재로그인.
- `조직 트리(gw102A01)를 가져오지 못함` → `isTreeAllOpen` 요청은 통과했는데 응답이 비어있음. 보통 wehago-sign 만료 → 페이지 reload 후 재시도 (`s.reload(); time.sleep(2)` 후 다시).
- 트리 구조가 바뀌었을 때 — 부서 신설/통폐합은 자동 반영됨 (트리 결과를 그대로 iterate).
- 부서 노드 사이 250ms sleep은 SPA가 cgi rate limit이 있는지 명확하지 않아 보수적으로 잡은 값. 더 빨리 해도 보통 통과하나 처음 한 번은 그대로 두는 게 안전.

## 관련 스킬

- [/amaranth-org](../amaranth-org/SKILL.md) — 부서 트리 탐색, 특정 키워드 검색, 개발팀(`research_members`) 등 ad-hoc 조회.
- [/amaranth-calendar](../amaranth-calendar/SKILL.md) — 캘린더 (사람 events에서 본 스킬의 명부와 매칭).
