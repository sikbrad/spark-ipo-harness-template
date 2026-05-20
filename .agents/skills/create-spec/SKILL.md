---
name: create-spec
description: 명세(Spec) 작성 스킬. 유저가 "기획해줘", "명세 만들어줘", "요구사항 문서 작성해줘", "SPEC", "PRD" 등 기획/명세 관련 요청을 할 때 사용한다. 핵심 항목을 체계적으로 사고하여 빠짐없는 명세서를 작성한다.
argument-hint: "[유저의 요구사항 또는 아이디어]"
---

# 명세(Spec) 작성 스킬

유저의 요구사항을 받아 `proc/spec/`에 항목별 명세 문서들을 체계적으로 작성한다.

## 핵심 원칙

- 절대 개발하지 마라. 요구사항 문서만 작성하라.
- 유저의 요구사항을 빠짐없이 반영하라. 의도를 파악하고 충실히 문서화하라.
- 한글로 작성하라.
- 깊게 생각하고, 오류를 줄이기 위해 스스로 검토하라.

## 작성 전 준비

1. `input/` 디렉토리에 유저가 제공한 참조 자료가 있는지 확인하라.
2. 샘플 콘텐츠 폴더가 있으면 반드시 읽고 반영하라.
3. 유저의 요구사항에서 명시적/암시적 기술 제약을 파악하라.

## 명세 핵심 항목 — 반드시 이 순서로 사고하고 작성하라

### 1. AI 명령지침 (Core Rules / System Prompt)
- 이 명세를 읽고 개발할 AI에게 전달할 행동 규칙
- 깊게 생각하고 스스로 검토할 것
- 유저의 요구사항 의도를 파악하고 충실히 구현할 것
- 배포 정책, 테스트 정책 등 제약 조건 명시

### 2. 제품 정의 (Scope Statement / Product Goal)
- Problem Statement: 해결하려는 핵심 문제 정의
- Product Goal: 이 제품이 달성하려는 것
- Persona: 타겟 사용자 정의 (역할별)

### 3. 핵심 기능 정의 (FSD / IA / Sitemap)
- MoSCoW: Must / Should / Could / Won't 기능 분류
- Sitemap: 전체 페이지 구조도
- IA (Information Architecture): 정보 구조
- Screen Spec: 화면별 기능 명세 (구성요소 + 설명 테이블)

### 4. 사용자 경험 설계 (UX Flow / Screen Flow / Use Case)
- 역할별 사용 시나리오 (일반 사용자, 관리자 등)
- Navigation Flow: 페이지 이동 경로도
- UI Components: 페이지별 구성 요소 정의
- RBAC: 권한별 접근/행위 차별화 매트릭스

### 5. 운영 로직 및 비즈니스 정책 (Business Rules / Validation / ERD)
- 핵심 비즈니스 규칙
- Auth / ACL: 인증 및 보안 규칙
- ERD / Schema: 데이터 모델 및 관계 정의
- Validation Rules: 입력값 제약 테이블

### 6. 콘텐츠 데이터셋 (Seed Data / Content Samples)
- 초기 데이터 정의 (어떤 콘텐츠가 표시되는지 구체적 예시)
- `input/` 내 샘플 콘텐츠 참조 경로 명시
- 데이터 분류 체계, 기본값 설정

### 7. 브랜딩 (Brand Identity / UX Writing / Tone & Voice)
- 서비스명, 슬로건
- Brand Personality: 서비스 성격
- Tone & Voice: 언어적 톤앤매너
- Microcopy: 상황별 문구 테이블

### 8. 디자인 시스템 (Design Token / Style Guide / UI Kit)
- Color Palette: 주요 색상
- Typography: 제목/본문/강조 스타일
- Layout: 레이아웃 규칙
- 시각적 컨셉

### 9. 기술 환경 및 개발 도구 (SDD / Tech Stack / DevEnv)
- 프론트엔드, 데이터 저장, 배포, 개발 환경
- 배포 정책

### 10. 단계별 개발 로드맵 (WBS / Milestones / Phased Rollout)
- Phase별 작업 범위
- 검증 기준 (체크리스트)

## 출력 규칙

- 출력 위치: `proc/spec/` 에 항목별로 분리된 문서를 생성한다
- 내용 규모에 따라 문서를 합치거나 더 분리할 수 있다
- 마크다운 형식, 한글 작성
- `$ARGUMENTS`에 유저의 요구사항이 들어온다. 이를 기반으로 명세를 작성하라.
