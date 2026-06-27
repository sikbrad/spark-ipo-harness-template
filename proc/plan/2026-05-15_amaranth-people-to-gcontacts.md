# 아마란스 명부 → 구글 연락처 등록

## 목표

`data/company/people/*_person_info.json` 의 임직원을 **구글 연락처에 신규 등록**.

- **dedup**: 전화번호 기준 — 동일 전화번호가 이미 구글 연락처에 있으면 skip
- **표시 이름**: `"{이름} 디오에프 {부서}"` 형태 (예: `"백인식 디오에프 AX"`)
- **mutation 범위**: create만. 기존 연락처 수정·삭제 일절 없음 (`/gcontacts` 스킬이 update/delete를 의도적으로 미지원)

## 입력 / 출력

| 항목 | 값 |
|---|---|
| 입력 | `data/company/people/*_person_info.json` (현재 86개, `_archived/` 제외) |
| 출력 | 구글 연락처 신규 N개 + `data/company/people/_gcontacts_sync.log` (이름·전화번호·match 여부·created `resourceName` 기록) |
| 대상 계정 | **bispro89@gmail.com** 또는 **sikbrad@gmail.com** ← **결정 필요** |

## 확정된 결정 (2026-05-15)

| 항목 | 값 |
|---|---|
| 타겟 계정 | **bispro89@gmail.com** |
| 이름 필드 dept 표기 | **(A) 회사명 프리픽스 떼고 끝 2단계** — `"백인식 디오에프 디오에프 AX"`, `"권경원 디오에프 연구소 웹"`, `"오진권 디오에프 영업본부"` |
| mobile 없는 사람 | **Skip** (전화 dedup 키 없는 row는 등록 안 함) |
| 필드 채움 전략 | **표준 필드는 다 채우고 잔여만 메모** (organization, birthday 등 풀 매핑) |
| `org.department` | **leaf 1개만** — 구조는 짧게, 부서 path 전체는 메모로 |
| dry-run | **먼저 실행 → 사용자 확인 → 본 실행** |

## Google Contacts 필드 매핑

| Google 필드 | Amaranth 출처 | 예시 |
|---|---|---|
| `names.givenName` | `name + " 디오에프 " + dept2`<br>(dept2 = 회사명 떼고 끝 2단계 공백 join) | `"백인식 디오에프 디오에프 AX"` |
| `phoneNumbers (type=mobile)` | `mobile` | `01067789489` 그대로. dedup 키 |
| `phoneNumbers (type=work)` | `ext_num`, `tel_num` 둘 다 있으면 다 추가 | (대부분 null) |
| `emailAddresses (type=work)` | `email` | `ins@doflab.com` |
| `organizations[0].name` | `company` | `"주식회사 디오에프"` |
| `organizations[0].department` | `dept` (leaf만) | `"AX"`, `"웹"`, `"국내영업"` |
| `organizations[0].title` | `position` | `"부장"`, `"책임연구원"` |
| `organizations[0].jobDescription` | `duty` | `"팀장"` (없으면 생략) |
| `addresses (type=work)` | `addr`, `zip_code` | (대부분 null이면 생략) |
| `biographies` (메모) | 잔여 — `login_id`, `birthday`, `join_day`, `main_work`, 전체 `dept_path` | 자세히는 아래 |

**구조화 안 하는 필드**:
- `birthday` — 사용자 요청으로 `birthdays` 필드 안 채우고 메모에만.
- `employee_number` (사번) — 메모에서도 제외.

**메모 본문 포맷** (있는 항목만 줄로 출력, 비면 그 줄 생략):

```
ID ins
생일 1989-03-18
입사일 2025-09-22
주업무: AI Transformation
부서 경로: 주식회사 디오에프>디오에프>AX
```

## 전화번호 정규화 정책

매칭 키는 **마지막 10자리 숫자**.

```python
def _norm_phone(s: str | None) -> str | None:
    if not s: return None
    digits = ''.join(ch for ch in s if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else None
```

이유:
- 아마란스 `mobile`: `"01067789489"` (하이픈 없는 11자리 포함 010)
- Google 저장 포맷: `"010-6778-9489"` / `"+82 10-6778-9489"` / `"+821067789489"` 등 다양
- 모두 `digits[-10:]` = `"1067789489"` 로 매칭됨
- 짧은 사내번호 (예: `extNum` 4~5자리)는 매칭 키 생성 안 됨 (`None` 반환) → 비교에서 자동 제외

`extNum`, `tel_num`은 dedup 키 아님 — `mobile` 만 비교 키.

## 알고리즘

```
1. 타겟 계정 g = GoogleClient('bispro89' or 'sikbrad') 인증
2. existing = list_contacts(g)
   existing_phones = { _norm_phone(p) for c in existing for p in c.phones } - {None}
3. people = load_all('data/company/people/*_person_info.json')  # _archived 제외
4. log_rows = []
   for person in people:
       key = _norm_phone(person['mobile'])
       if key is None:
           log_rows.append((person, 'no_mobile', None))
           continue
       if key in existing_phones:
           log_rows.append((person, 'dup_skip', None))
           continue
       display = f"{person['name']} 디오에프 {person['dept']}"
       result = create_contact(g, given=display, phones=[person['mobile']], ...)
       existing_phones.add(key)  # 한 batch 내 중복 방지
       log_rows.append((person, 'created', result['resourceName']))
5. log_rows → data/company/people/_gcontacts_sync.log (tsv 또는 json)
6. summary 출력: created N, dup_skip M, no_mobile K
```

## 안전장치

- **dry-run 먼저** — `--dry-run` 플래그 추가, 실제 create 호출 없이 어떤 사람이 created/skip 될지 list만 출력. 사용자가 확인 후 실제 실행.
- **rate limit** — People API 권장 250ms/req. 한 번에 80명 미만이라 큰 영향 없으나 `time.sleep(0.3)` 정도 보수적으로.
- **부분 실패** — 한 사람 create 실패해도 다음 진행. 실패한 row는 log에 `'error: <msg>'`로 기록.
- **재실행 idempotent** — dedup 키가 phone이므로 두 번 돌려도 두 번째는 모두 `dup_skip`이 되어야 정상.

## 구현 위치

- 신규 helper 함수: `proc/lib/people_to_gcontacts.py`
  - `_norm_phone(s)`, `_load_people(base_dir)`, `_existing_phone_index(g)`, `sync_to_gcontacts(account, dry_run=False, dept_fmt='leaf', include_email=False, name_mode='display_only')`
- CLI runner: 같은 파일의 `if __name__ == '__main__':` 블록. `--account`, `--dry-run`, `--include-email`, `--dept-fmt` 옵션.
- **스킬 신설 X** — 일회성에 가까운 작업. 호출 한 줄로 끝나므로 helper만 두고 호출자는 사람이 직접 명령.

## 작업 항목

- [x] 사전 결정 항목 사용자 확정 (위 표 참조)
- [x] `proc/lib/people_to_gcontacts.py` 작성 (정규화·로드·diff·sync 함수)
- [x] `--dry-run` 으로 1차 실행 → 사용자에게 created 후보 명단 보고
- [x] 사용자 OK 후 실제 실행 → 결과 log 저장
- [x] 결과 요약 보고 (created N / dup_skip M / no_mobile K / error E)
- [x] 동일 작업 재실행 시 모두 dup_skip 인지 검증 (idempotency 확인)

## 실행 기록

### 발생한 이슈 & 수정

1. **`gcontacts_api.parse_person()` phones는 dict** (`{'value','canonical','type'}`)였는데 string으로 가정하고 normalize한 결과 1526개 연락처 → 0개 정규화 키. 모든 dedup 실패. **수정**: `existing_phone_index()`에서 `value`와 `canonical` 둘 다에서 추출하도록 변경. → [feedback memory](../../../.claude/projects/-Users-gq-works-projs-dof-work-skills-dof-work-startpoint-04/memory/feedback_gcontacts_phones_shape.md)
2. **본인(백인식, loginId='ins') 미제외**. **수정**: `SELF_LOGIN_IDS = {'ins'}` 상수 도입 + `self_skip` 결과 버킷 추가. → [user memory](../../../.claude/projects/-Users-gq-works-projs-dof-work-skills-dof-work-startpoint-04/memory/user_identity_amaranth.md)

### Dry-run (2차, 버그 수정 후) — 2026-05-15

```
[dry-run] created=76 dup_skip=9 no_mobile=0 self_skip=1 errors=0

self_skip: 백인식
dup_skip (이미 있던 9명): 김규탁, 김상진, 나혜리, 박소정, 박은진, 박현수, 서해리, 심흥식, 이미연
```

### Apply (본 실행) — 2026-05-15

```
[apply] created=76 dup_skip=9 no_mobile=0 self_skip=1 errors=0
```

- 결과 log: [data/company/people/_gcontacts_sync_apply.json](../../data/company/people/_gcontacts_sync_apply.json) — 각 row에 `resource_name` 포함 (예: `people/c4181220018010222084`).
- 평균 1.0s/req (API 응답 + sleep 0.3s 포함).
- 에러 0건.

### Idempotency 검증 (apply 직후 재 dry-run)

```
[dry-run] created=0 dup_skip=85 no_mobile=0 self_skip=1 errors=0
```

76 신규 + 9 기존 = **85 dup_skip**으로 모두 매칭. 재실행해도 중복 등록 없음 ✓

## 최종 산출물

| 파일 | 역할 |
|---|---|
| [proc/lib/people_to_gcontacts.py](../lib/people_to_gcontacts.py) | helper + CLI |
| [data/company/people/_gcontacts_sync_dry.json](../../data/company/people/_gcontacts_sync_dry.json) | dry-run 결과 |
| [data/company/people/_gcontacts_sync_apply.json](../../data/company/people/_gcontacts_sync_apply.json) | apply 결과 (resource_name 포함) |

## 향후 운영

- ERP에 신규 입사자 추가 시: `/amaranth-people` 으로 명부 sync → `python3 proc/lib/people_to_gcontacts.py --apply --account bispro89` 재실행. 신입만 created, 기존자는 dup_skip.
- 부서/직급 변경된 사람은 **자동 갱신 안 됨** — `/gcontacts` 가 update를 의도적으로 미지원하기 때문. Google Contacts UI에서 수동 처리하거나, 필요해지면 별도 update helper 추가.
- 다른 계정에도 등록하려면: `--account sikbrad` (현재 미실행).
