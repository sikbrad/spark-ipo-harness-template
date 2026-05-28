---
name: vibecoding-book
description: 바이브코딩/AX/말라카 강의 자료를 책으로 재기획·집필·렌더링하는 워크플로우. "바이브코딩 책", "책 다시 써", "출판기획서", "목차 팽창", "PPT/Notion/Daily/ChatGPT 기록으로 책 보강", "HTML/PDF 책 렌더", "말라카 강의와 회사 AX를 구분해 책 구성" 요청 시 사용한다. 로컬에 이미 내려받은 자료를 우선 사용하고, 자료집이 아니라 새 원고를 저술해야 하는 장문 출판 작업에 사용한다.
---

# Vibecoding Book

바이브코딩 책을 로컬 자료 기반으로 기획, 집필, HTML/PDF 렌더링하는 스킬이다. 자료 수집 결과물을 엮는 것이 아니라, 출판기획서와 목차를 먼저 만든 뒤 저자 목소리의 새 원고로 다시 쓴다.

## Core Rules

- 기본 출력 위치는 `data/vibecoding-book/` 아래의 새 하위 폴더로 둔다.
- 복잡한 재집필은 `proc/plan/`에 계획 문서를 만들거나 기존 책 계획 문서를 갱신하면서 진행한다.
- 새 API 스크랩은 기본값으로 하지 않는다. Daily, voice transcript, Notion dump, ChatGPT DB, PPT extracts 등 로컬에 이미 있는 자료를 먼저 쓴다.
- PPT/Notion/Daily/ChatGPT 추출물은 근거 자료다. 최종 책은 추출물 나열이나 슬라이드 페이지 결합이 아니라 새 문장으로 저술한다.
- 출판기획서와 목차를 먼저 만들고, 그 다음 원고를 쓴다.
- 독자가 궁금해하지 않는 한 책 쓰는 법, HTML 출판 루프, 원고 제작 과정 자체를 본문 주제로 넣지 않는다. 제작·검수 정보는 리포트에만 남긴다.
- 말라카 관련 내용은 외부 실습강좌/강사 운영 경험으로 다루고, 회사 사내교육·AX·업무 자동화는 회사 업무 파트로 분리한다.
- 개인 정보, 회사 내부 정보, 실명, 권리 이슈가 있는 이미지는 외부 공개 전 검수 대상으로 표시한다.

## Workflow

1. 최신 사용자 지시를 기존 책 방향보다 우선한다.
2. 계획 문서에 요청사항, 금지사항, 출력 위치, 검증 기준을 기록한다.
3. 로컬 자료 인벤토리를 만든다.
   ```bash
   python3 .agents/skills/vibecoding-book/scripts/inventory_sources.py \
     --root . \
     --out data/vibecoding-book/source-inventory-$(date +%F)
   ```
4. 인벤토리 리포트에서 다음 축별로 근거를 선별한다.
   - 말라카 외부 강의: latest PPT, 강의 voice transcript, KUBIT/POC clinic 자료, 강의 관련 Notion.
   - 회사 AX: Daily/voice의 `ax`/회사 업무 기록, Teams/Outlook/Gmail/GDrive raw, 거래원장/CRM/ERP 기록.
   - 저자 서사: Notion author profile evidence, career notes, Daily 회고.
   - 시장형 목차: `market-positioning-report.md`, 교보 조사, 기존 출간계획서.
   - 독자 질문/호기심: `data/db/chatgpt.sqlite`의 conversation titles와 필요 시 raw conversation dump.
5. 출판기획서와 확장 목차를 쓴다. 목차에는 각 장의 독자 효용, 원천 근거, 제외할 내용, 말라카/회사 구분을 적는다.
6. 원고를 새로 쓴다. 각 장은 `주장 -> 현장 장면 -> 방법 -> 검증 기준 -> 다음 행동` 흐름을 기본으로 둔다.
7. HTML/PDF를 렌더한다. 현재 프로젝트의 기존 렌더 스크립트를 재사용하되, 출력 폴더와 제목/목차를 새 판본에 맞춘다.
   - 시장형 최신 스크립트: `scripts/malaka_vibecoding_market_book.py`
   - daily-note 기반 구판 스크립트: `scripts/malaka_vibecoding_daily_rewrite_book.py`
   - Notion 근거 추출: `scripts/vibecoding_notion_research.py`
8. 검증한다.
   - `pdfinfo`로 200쪽 이상 여부와 제목 확인.
   - `pdftotext`와 `rg`로 금지 문구, raw metadata, 조사 오류, 반복 템플릿 잔여 표현 확인.
   - Browser로 HTML 표지, 목차, 파트, 1장, 뒷표지를 시각 검수하고 스크린샷을 저장한다.
   - `render-review.md`와 계획 문서에 검증 결과를 남긴다.

## Source Inventory

자료 보강 가능성을 먼저 확인해야 할 때는 `scripts/inventory_sources.py`를 실행한다. 결과는 `source-inventory.md`와 `source-inventory.json`으로 저장된다.

인벤토리에서 특히 봐야 할 신호:
- `data/daily/*/summary.md`: 하루 단위 맥락과 작업 흐름.
- `data/daily/*/raw/voice-*.txt`: 말투, 회고, 강의/회사 AX 현장감.
- `data/notion/md/**/*.md`와 `data/notion/hydrated/pages/*.json`: 저자 세계관, 강의 준비, 업무 기록.
- `data/db/chatgpt.sqlite`: 사용자가 실제로 궁금해했던 질문 흐름.
- `data/vibecoding-book/extracts/`: latest PPT 슬라이드 텍스트와 이미지 근거.
- `data/vibecoding-book/proposal/`, `final/`, `market-rewrite-*`: 이전 판본의 장점과 버릴 내용.

## Output Contract

완료 보고에는 다음을 포함한다.
- 새/수정된 스킬 또는 책 산출물 경로.
- 사용한 주요 로컬 자료 묶음과 보강 가능성 판단.
- PDF 페이지 수, HTML 구조, 브라우저 검수 여부.
- 본문에서 제외한 내용과 남은 리스크.
