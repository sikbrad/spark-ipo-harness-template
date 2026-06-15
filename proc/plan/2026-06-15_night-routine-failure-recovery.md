# 2026-06-15 Night Routine Failure Recovery

## 목표
Linux 환경에서 2026-06-15 나이트루틴 중 실패한 source를 다시 동작시킨다.

## 실패 원인
- Google Calendar/Gmail/Drive: Python `google` 계열 패키지 없음.
- Outlook/Teams: Python `msal` 없음.
- Atlassian: `.env`에 키는 있으나 `python-dotenv`가 없어 `.env` 로딩 실패.
- kubit Slack: `node` / `npm` 없음.
- Raindrop infer: `youtube_transcript_api` 없음.
- Notion full dump: 300초 timeout. live Jot/Task snapshot은 수집됨.

## 설치 범위
- OS: `python3-pip`, `nodejs`, `npm`, `yt-dlp`, `ffmpeg`
- Python: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`, `msal`, `python-dotenv`, `youtube-transcript-api`
- Node: kubit workspace의 기존 `package-lock.json` 기준 `npm ci`

## 제외
- 음성인식 모델, Whisper, 오디오 전사 모델 설치/변경 제외.
- Notion Task/Note 상태/날짜 수정 제외.

## 작업 항목
- [x] apt로 Python/Node 런타임 보강
- [x] Python API 의존성 설치
- [x] kubit Node 의존성 설치
- [x] `yt-dlp` / `ffmpeg` 설치
- [x] import smoke test
- [x] Google OAuth cached-token scope 처리 수정
- [x] 실패 source 재수집
- [x] Raindrop infer/retag 재처리
- [x] kubit Slack collect 재처리
- [x] raw/source-errors 및 summary 보강

## 결과
- 설치 완료: `python3-pip`, `nodejs`, `npm`, `yt-dlp`, `ffmpeg`.
- Python import 확인 완료: `msal`, `google.auth`, `google_auth_oauthlib`, `googleapiclient`, `youtube_transcript_api`, `dotenv`.
- `proc/lib/google_auth.py` 수정: 기존 캐시 토큰이 가진 scope를 존중해 refresh하도록 변경. `sikbrad`의 `invalid_scope` 해결.
- Google 재수집 완료:
  - `gcal-bispro89.json`: 3건
  - `gmail-bispro89.json`: 8건
  - `gdrive-bispro89.json`: 5건
  - `gcal-sikbrad.json`: 0건
  - `gmail-sikbrad.json`: 9건
  - `gdrive-sikbrad.json`: 1건
- MS Graph 재수집 완료: Outlook, Teams chats, standup, 공개/접근 가능 채널.
- Atlassian 재수집 완료: Confluence created 2 / updated 4.
- kubit Slack 수집 완료:
  - `collect:conv`: 13 files updated, 18 messages processed.
  - `collect:people`: 124 files updated, 18 new messages.
- Raindrop 오늘 3건 infer/retag 완료.

## 남은 이슈
- Notion full dump는 300초 timeout 이력이 있어 이번 복구 패스에서는 skip. live Jot/Task snapshot은 정상.
- Teams private channel 3개는 Graph 403:
  - `proj-출고-예외승인`
  - `기술지원 운영`
  - `proj-월결산-생산재고회계`
