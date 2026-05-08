# 아마란스 ERP 연차휴가신청서 상신 자동화

> 2026-05-08. playwright-cli (`S('amaranth')`) 기반.
> 목표: 임의 일자에 임의 제목으로 연차휴가신청서를 자동 상신.
> **결과**: 5/11(월) "자동화테스트"로 상신 성공 — 문서번호 `DOF-2605-0143`, 상태 `진행`.

## 컨텍스트

- 기존 `/amaranth-approval` 스킬은 결재함 **조회만** (eap105A04 list).
- 기안(상신)은 SPA 다이얼로그 + 다단계 폼을 거쳐야 함 (wehago-sign HMAC 헤더가 SPA 번들 내부에서 부착됨 → 외부 fetch 불가).
- ERP_URL: `https://erp.doflab.com`

## 워크플로우 (3단계)

### Step 1 — 결재작성 페이지에서 양식 선택
- URL: `/#/UB/UB/UBA0000?specialLnb=Y&moduleCode=UB&menuCode=UBA&pageCode=UBA6000`
- "자주 사용되는 양식" 섹션의 카드 중 **연차휴가신청서** 클릭.
- 클릭 후 `/#/HP/HPD0110/HPD0110?...&formDTp=HP_HPD0110_00011&formId=36` 로 이동.
  - 이건 결재 폼이 아니라 **HR 근태신청관리** 페이지. 휴가는 결재 모듈 직접이 아니라 **HR 자가신청** 경유.

### Step 2 — 근태신청서(HPD0110) 폼 작성
좌측 리스트에서 "연차휴가신청서" 선택된 상태. 우측 폼:

| 필드 | 셀렉터 / 위치 | 값 |
|---|---|---|
| 휴가구분 | `button[연차]` 등 (sub-type) | 연차 클릭 (시간 자동 세팅 트리거) |
| 시작일자 | `input.OBTDatePickerRebuild_inputYMD__PtxMy` (visible[0]) | YYYY-MM-DD (`focus + select + type`) |
| 종료일자 | 위와 동일 (visible[1]) | Tab 시 시작일과 동기화 |
| 시작시간 / 종료시간 | `OBTTimePicker2_input` (5개 input) | 자동 세팅 (06:00~22:00, 시간계 08시간) |
| 신청자 | `placeholder=사원코드도움` | 본인 자동 |
| 사유 | x≈774, y≈593, w≈1111 (마지막 input) | 임의 텍스트 (`focus + type`) |

핵심 trick:
- `input.OBTDatePickerRebuild_inputYMD__PtxMy`는 React-controlled — native value setter 안 통함. **`focus() + select() + playwright-cli type "YYYY-MM-DD"`** 후 `Tab` 으로 commit. range picker라 시작일만 입력해도 종료일이 동기화됨.
- 시간 필드는 **연차 sub-type 버튼을 한 번 클릭해야** 잔여시간 계산이 활성화됨. 클릭 안 하고 신청완료 누르면 토스트 "잔여시간 정보가 없습니다" + 시간계 "-".
- 토요일/일요일은 잔여시간 0으로 거절. **평일(월~금) only**.

폼 채운 뒤 우하단 **신청완료** 클릭 → Step 3.

### Step 3 — 신청내역 검토 + 결재상신
신청완료 후 같은 페이지에 **신청내역 테이블 + 결재상신 폼** 렌더:
- 자동 생성: 휴가구분 / 일자 / 시간 / 신청일수 / 사유 / 결재선
- 입력 필요: **제목** (textbox, ref via snapshot) — 권장: 사유와 동일 또는 의미 있는 한 줄.
- 우하단 **결재상신** 버튼 클릭.

### Step 4 — 결재 popup tab에서 최종 상신
**결재상신 클릭은 새 브라우저 탭을 띄움** (이게 사용자가 본 "팝업"):
- URL: `/#/popup?MicroModuleCode=eap&approkey=ERP_<uuid>&formId=36&callComp=UBAP001&popupUUID=...`
- Title: `연차휴가신청서`
- 정식 전자결재 문서 view (휴가신청서 양식, 결재라인 부장→대표이사 자동 세팅, 작성일자/기안부서/제목/사유/연차차감 등 표시).
- 우상단 3 버튼: `미리보기` / `보관` / **`상신`** (파란색).
- **상신** 클릭 → 결재 line으로 발송, popup tab 닫힘, 원 탭은 캘린더 view로 복귀.

`상신` 누르지 않고 popup만 띄우면 결재함에 들어가지 않음 — 첫 시도 실패의 원인.

## 함정 / 발견 사항

1. **OBT 버튼은 .click() 안 통함** — `OBTButton_root`/`OBTButton_typedefault` wrapper가 inner `<button>`을 가리고 native click 이벤트를 가로챔. **playwright-cli `click <ref>`** (snapshot ref) 또는 **mousedown/mouseup/click 합성 디스패치**로 우회. ref 기반이 가장 안정적.
2. **OBT DatePicker는 React-controlled** — `Object.getOwnPropertyDescriptor(...).value.set` 트릭 안 통함. focus + select + keyboard type 만 통함.
3. **연차 sub-type 버튼 click이 시간계산 트리거** — 안 누르면 폼이 invalid 상태 ("잔여시간 정보가 없습니다").
4. **결재상신은 popup 탭** — 같은 윈도우 내 modal이 아니라 새 브라우저 탭. tab-list 후 tab-select 1.
5. **popup 탭의 `상신` 버튼은 일반 `<div>` cursor=pointer** — `<button>`이 아니라 generic. snapshot ref로 클릭.
6. **5/9 (토요일)** — 시스템이 잔여시간 0 처리해서 거부. 평일(5/11)로 변경 후 성공.

## 검증 (eap105A04)

```
2026-05-08 16:09:31 | 연차휴가신청서 | 자동화테스트 | 진행 | DOF-2605-0143
```

## 헬퍼 작성 TODO (후속)

`proc/lib/pwc_amaranth.py` 에 `approval_*` 섹션 옆에 추가 후보:

```python
def submit_leave(s, start_date, end_date=None, reason='자동화', title=None, leave_type='연차'):
    """연차휴가신청서 전체 워크플로우 자동화.

    Args:
        s: S('amaranth')
        start_date / end_date: 'YYYY-MM-DD'. end_date None이면 start와 같음.
        reason: 사유 텍스트 (Step 2 폼)
        title: 제목 (Step 3). None이면 reason 사용.
        leave_type: '연차' / '오전반차' / '오후반차' / ...
    Returns:
        dict { 'doc_no': 'DOF-...', 'status': '진행', 'submitted_at': ... } or None
    """
    # 1. UBA6000 → 연차휴가신청서 클릭
    # 2. 연차 sub-type 클릭 (시간 활성화)
    # 3. 시작/종료일 focus+type, Tab
    # 4. 사유 focus+type
    # 5. 신청완료 click (ref)
    # 6. 제목 fill
    # 7. 결재상신 click (ref)
    # 8. tab-select 1
    # 9. 상신 click (ref e25)
    # 10. tab-close 1, verify via approval_docs(s)
    ...
```

지금은 ad-hoc하게 검증된 흐름 — 헬퍼 함수화는 다음 명세 변경 시 통합 권장. 본 작업은 **단발성 상신 + 흐름 문서화**가 목표였으므로 helper 미작성 (사용자 확인 후 추후 작업).
