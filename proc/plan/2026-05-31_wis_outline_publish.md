# WIS 2026 Outline 방문 요약 게시 계획

## 목표
- `https://outline.doflab.com/doc/wis-2026-6oNZMSV1gd` 문서를 WIS 2026 방문 요약 문서로 업데이트한다.
- Confluence `박람회방문 WIS2026 (월드아이티쇼)`의 사용자 메모와 이미지, 참가사 리스트 PDF를 근거로 업체별/주제별 하위 문서를 만든다.
- SIDEX와 같은 방식으로 사진을 직접 VQA 판독하고, 최종 Outline에는 내부 처리 용어를 노출하지 않는다.

## 입력
- Confluence: `https://doflab.atlassian.net/wiki/spaces/AX/pages/823984130/WIS2026`
- Outline target: `https://outline.doflab.com/doc/wis-2026-6oNZMSV1gd`
- 참가사 리스트/도면 PDF: `/Users/gq/Downloads/2026 WIS 참가사 리스트 (국문).pdf`
- 이미지 zip: `/Users/gq/Downloads/vFlatwis26.zip`

## 작업 항목
- [x] SIDEX 커밋/계획/스크립트 구조 확인.
- [x] Confluence 본문, 업체/주제 그룹, 첨부 이미지 목록 수집.
- [x] vFlat zip 이미지 해제 및 누락 Confluence 첨부 이미지 다운로드.
- [x] 참가사 PDF를 이미지/OCR 기준으로 참조 자료화.
- [x] WIS 이미지별 VQA JSON 생성.
- [x] Confluence 메모 + VQA + 참가사 참조를 병합해 업체별 분석 JSON/MD 생성.
- [x] Outline parent 문서와 업체별 child 문서 게시.
- [x] Outline API로 최종 문서와 이미지 첨부 반영 확인.

## SIDEX에서 재사용할 원칙
- 사진 판독 결과와 사람 메모를 분리해 저장하되, 최종 문서는 방문 요약/업체 요약 중심으로 쓴다.
- 이미지 asset/document id를 캐시해 재실행이 안전하도록 한다.
- 업체명이 정확히 공식 참가사와 안 맞아도, 사진에 보이는 브랜드와 사용자 메모를 근거로 별도 그룹을 유지한다.
- 최종 문서에는 Qwen/VQA/OCR/파이프라인 같은 내부 처리 설명을 쓰지 않는다.

## 진행 메모
- Confluence 페이지에서 42개 관람 그룹과 137개 이미지 참조를 추출했다.
- `vFlatwis26.zip` 124장에 더해 Confluence 첨부에서 누락 이미지 23장을 다운로드해 로컬 원본 147장을 확보했다.
- 참가사 PDF는 텍스트 레이어가 없어 1쪽 이미지를 렌더링하고 `kor+eng` OCR 결과를 `output/wis-2026/reference/wis_participants_ocr.txt`에 저장했다.
- 그룹 단위 이미지 판독을 완료했고, `output/wis-2026/qwen-vqa/wis_qwen_vendor_analysis.json` 기준 42개 그룹, 137/137장 판독, 누락 0장이다.
- `https://outline.doflab.com/doc/wis-2026-6oNZMSV1gd` 부모 문서와 42개 업체/주제별 하위 문서를 게시했다.
- Outline API 검증 결과 부모 본문 길이 5194자, 자식 문서 42개, 이미지 첨부 캐시 138개(사진 137장 + 참가사 리스트/도면 1장), `백인식 메모` 섹션 포함을 확인했다.
- 이름이 같은 23/24번 `기업자료 ai 로 찾아준다` 그룹은 그룹번호를 포함한 키로 재게시해 부모 문서에 두 하위 문서 링크가 모두 따로 들어간 것을 확인했다.
