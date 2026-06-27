# 효성 FMS CMS 영상 리서치 계획

작성일: 2026-06-17

## 목적

Confluence AX 페이지 `260618 효성CMS 자동주문등록 관련`에 연결된 영상 2건을 분석해, 효성 CMS+에서 CMS/카드 자동결제 회원을 등록하거나 기존 계좌를 변경할 때 어떤 화면에 어떤 값을 넣는지 업무 규칙으로 정리한다.

대상 페이지:
- <https://doflab.atlassian.net/wiki/spaces/AX/pages/881033357/260618+CMS>

## 작업 결과

- [x] Confluence API로 페이지 본문 확인
- [x] SharePoint 링크 2건을 Microsoft Graph `/shares/.../driveItem`으로 해석해 MP4 원본 다운로드
- [x] `ffmpeg`로 오디오 추출 및 5초 간격 화면 샘플링
- [x] Whisper `turbo`로 한국어 전사
- [x] 주요 화면 OCR 및 육안 확인
- [x] CMS/카드/계좌변경 업무 규칙 리서치 문서 작성

## 산출물

- 리서치 문서: `proc/research/2026-06-17_hyosung-fms-cms-registration-rules.md`
- 원자료/파생자료: `output/hyosung-fms-cms-research-20260617/`

## 검증 메모

- Confluence 페이지 제목: `260618 효성CMS 자동주문등록 관련`
- 영상 1: 기존 출금 건에서 계좌 변경, 약 13분 29초
- 영상 2: 카드 신규회원등록, 약 6분 28초
- 최초 ASR은 MPS fp16에서 `nan logits`로 실패했고, MPS fp32 재실행으로 두 영상 모두 전사 성공
- 숫자 식별자, 계좌번호, 카드번호, 사업자번호, 휴대전화 등은 리서치 본문에 원문 그대로 싣지 않고 규칙 중심으로 정리
