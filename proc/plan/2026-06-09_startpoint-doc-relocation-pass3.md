# startpoint 문서 재배치 3차 재검토

작성일: 2026-06-09 KST

## 목적

`dof-work-startpoint-04`의 `proc/plan`, `proc/research`에 남은 문서 중 다른 워크스페이스 프로젝트가 더 자연스러운 문서가 추가로 있는지 재검토한다.

## 결론

추가 이동 대상은 없다.

1차와 2차에서 강한 후보 44개는 이미 이동했다. 3차 검토에서 남은 문서는 startpoint-04가 실행 허브, 개인 업무 데이터 허브, 외부 서비스 스킬 허브, 또는 Outline/Teams/Confluence 운영 기록의 canonical 위치인 경우가 대부분이었다.

## 재검토 근거

- 남은 `proc/research`는 Android SMS 전달 앱 조사, Confluence AX 공간 정리 조사, Naver blog lifecycle test, macOS shortcut, Teams pending 자료처럼 전용 코드 저장소가 없거나 startpoint의 외부 서비스 운영 맥락이 강하다.
- 남은 Teams 인물/아바타/전수장부 관련 plan은 `output/teams/conversations`, `data/teams/peoples`, `data/company/people`를 직접 산출물로 삼는다. `teams-bot-dofi-01`이나 `dof-teams-bot`는 bot 제품/배포 프로젝트라서 현재 문서의 소유권과 다르다.
- 남은 국내/해외 치과 후보와 Outline prospect 문서는 포털 데이터를 일부 참조하지만 본질은 영업처 후보 발굴, 웹 보강, Outline 리포트 발행이다. `dental-tech-list-downloader`는 인허가 데이터 다운로드 문서 1개를 이미 받았고, 후보/리포트 운영 전체를 담기에는 범위가 좁다.
- SIDEX, daily/night/morning routine, Gmail/Calendar/Notion/Raindrop/ChatGPT/KakaoTalk/Threads/Naver/Amaranth 비회계 스킬 문서는 startpoint-04의 범용 실행 스킬 체계와 직접 연결된다.
- Confluence AX reorg 문서는 대상이 Atlassian 공간 구조이고, 로컬 산출물도 `output/confluence-ax-reorg` 아래라서 별도 repo 이동 후보가 아니다.

## 확인한 명령

```bash
rg -n '(/Users/gq/works/(projs|lecture)/|dof-order-web|portal-ledger|portal-data|shop-order|teams-bot|dof-teams|openclaw|kubit|vibe-coding-book|dental|sidex|confluence|channel|kakao|solapi|logistics|tracking|android|sms)' proc/plan proc/research -g '*.md'
find /Users/gq/works/projs /Users/gq/works/lecture -path '*/.git' -prune -o -path '*/node_modules' -prune -o -path '*/proc/archive' -prune -o -path '*/proc/90_archive' -prune -o \( -type d \( -name plan -o -name research -o -name 50_plan -o -name 30_research -o -name docs \) \) -print | sort
find proc/plan proc/research -maxdepth 1 -type f \( -name '*.md' -o -name '*.py' \) | sort
```

## 결과

- 3차 실파일 이동 수: 0개.
- 누적 실파일 이동 수: 44개.
- 기존 이동 결과 문서:
  - `proc/plan/2026-06-08_startpoint-doc-relocation-execution.md`
  - `proc/plan/2026-06-09_startpoint-doc-relocation-pass2.md`
  - `proc/research/2026-06-08_startpoint-doc-relocation-review.md`

## 남은 판단

현재 남은 후보 중 강제 이동할 곳은 없다. 다만 영업처 후보/Outline 리포트 계열이 계속 커지면 기존 dental 분석 프로젝트로 억지 이동하기보다 `dof-sales-prospecting` 같은 별도 SPARK/IPO 프로젝트를 만드는 편이 더 자연스럽다.
