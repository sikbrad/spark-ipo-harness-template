# 바이브코딩 책 제작 스킬화 및 자료 보강 인벤토리

- 시작: 2026-05-28 KST
- 목표: 바이브코딩 책 제작 과정을 재사용 가능한 Agent Skill로 만들고, 워크스페이스에 남아 있는 로컬 자료로 책을 더 보강할 수 있는지 확인한다.

## 사용자 요청

- "이 책 만드는 것을 스킬로 만들자."
- daily note, recording transcribe, Notion 다운로드, ChatGPT 질문 기록 등 워크스페이스 전체의 더 많은 자료로 보강할 수 있는지 확인한다.

## 작업 원칙

- 새 API 스크랩이 아니라 로컬에 이미 내려받은 자료를 먼저 쓴다.
- 책 제작 스킬에는 자료집 결합 금지, 출판기획서/목차 선행, 저자 목소리로 새 원고 작성, HTML/PDF 검수 절차를 포함한다.
- 독자 본문에는 책 쓰는 법 자체를 기본 주제로 넣지 않는다.
- 말라카 외부 강의와 회사 사내교육·AX 업무를 구분한다.

## 진행 기록

- [x] `skill-creator` 지침 확인.
- [x] `.agents/skills/vibecoding-book/` 스킬 생성.
- [x] `SKILL.md`에 바이브코딩 책 제작 워크플로우와 금지/분리 규칙 작성.
- [x] `references/source-map.md`에 로컬 자료 위치와 검색어 정리.
- [x] `scripts/inventory_sources.py` 작성.
- [x] 스킬 validator 통과.
- [x] 로컬 자료 인벤토리 생성.
- [x] PDF 보관 후보 검토 및 선별 리포트 작성.
- [x] 공개 책 제작에 바로 참고 가능한 PDF를 symlink 아카이브로 구성.
- [x] PDF/Notion 의도 자료를 현재 시장형 책 원고의 1~6부에 보강 반영.

## 자료 보강 인벤토리 결과

- 인벤토리 리포트: `data/vibecoding-book/source-inventory-2026-05-28/source-inventory.md`
- JSON: `data/vibecoding-book/source-inventory-2026-05-28/source-inventory.json`
- PPT extract deck dirs: 30
- PPT extracted slides: 9,312
- Daily summaries: 361
- Daily Notion Jot raw files: 327
- Voice transcripts: 251
- Notion markdown files: 3,327
- Notion hydrated pages: 3,352
- ChatGPT conversations: 4,326

## 보강 가능성 판단

- 가능하다. 현재 책은 이미 PPT/Notion/Daily/ChatGPT 일부를 썼지만, 워크스페이스 전체 기준으로는 아직 활용 가능한 자료가 훨씬 많다.
- 특히 `voice-*.txt` 251개는 저자 말투, 회고, AX 현장감, 강의 장면을 보강하는 데 좋다.
- ChatGPT conversation title DB에는 바이브코딩 강의 계획, MVP 강의, Why 중심의 바이브코딩 등 독자의 질문 구조로 바꾸기 좋은 기록이 남아 있다.
- Notion markdown/hydrated dump는 저자 세계관, 커리어, 강의 준비, 업무 자동화 기록을 보강하는 데 쓸 수 있다.

## 산출물

- Skill: `.agents/skills/vibecoding-book/SKILL.md`
- Skill source map: `.agents/skills/vibecoding-book/references/source-map.md`
- Inventory script: `.agents/skills/vibecoding-book/scripts/inventory_sources.py`
- Inventory report: `data/vibecoding-book/source-inventory-2026-05-28/source-inventory.md`
- PDF archive candidates: `data/vibecoding-book/pdf-archive-2026-05-28/pdf-archive-candidates.md`
- PDF symlink archive: `data/vibecoding-book/pdf-archive-2026-05-28/{deliverables,source,references}/`
- Supplement evidence report: `data/vibecoding-book/market-rewrite-2026-05-27/supplement-evidence-2026-05-28.md`
- Updated manuscript/PDF: `data/vibecoding-book/market-rewrite-2026-05-27/malaka-vibecoding-market-book.{md,html,pdf}`

## 검증

- `python3 /Users/gq/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/vibecoding-book` 통과.
- `python3 .agents/skills/vibecoding-book/scripts/inventory_sources.py --root . --out data/vibecoding-book/source-inventory-2026-05-28 --candidate-limit 100` 실행 완료.
- `data/notion/assets/**/*.pdf`, `data/vibecoding-book/**/*.pdf` 기준으로 PDF 후보를 검토했고, 책 산출물/원천자료/참고자료/비공개 제외 자료로 분류했다.
- 공개 원고에 바로 연결하기 어려운 비공개/민감 PDF는 아카이브 symlink에서 제외했다.
- `python3 scripts/malaka_vibecoding_market_book.py` 재실행 완료. PDF 236쪽, 24장, 155절.
- 새 소제목 11개가 `market-toc.md`, Markdown 원고, PDF 텍스트에 모두 존재함을 확인했다.
- `책 쓰는 법`, `책쓰기`, `HTML 출판`, `IR Confidential`, `Frost`, `공유 금지`, `개인정보취급주의`, `수강생 리스트`, 계좌번호, 원본 Slack URL, `kakaomobility` 문자열은 PDF 텍스트에서 검출되지 않았다.
