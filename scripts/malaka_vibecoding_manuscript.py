#!/usr/bin/env python3
"""Author a source-informed, non-collage Malaka vibecoding book manuscript."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path("data/vibecoding-book")
BOOK_DIR = ROOT / "book"
PROPOSAL_DIR = ROOT / "proposal"
RESEARCH_DIR = ROOT / "research"
SLIDES_PATH = ROOT / "extracts" / "all-slides.json"
NOTION_TOPIC_PATH = RESEARCH_DIR / "notion-topic-evidence.json"
NOTION_CORPUS_PATH = RESEARCH_DIR / "notion-author-corpus.json"


@dataclass
class SourceSeed:
    kind: str
    title: str
    source: str
    excerpt: str


CHAPTERS = [
    {
        "title": "말라카의 바다에서 시작하기",
        "keywords": ["말라카", "목표", "철학", "기록", "생각", "LifeOS", "나만의 통찰", "가슴 뛰는"],
        "thesis": "바이브코딩은 말라카에게 단순한 기술 트렌드가 아니라, 삶을 끌려다니지 않고 자기 철학대로 밀고 가기 위한 실행 언어다.",
        "axis": "자기 이해, 기록, 목표, 철학",
        "reader": "도구를 배우기 전에 자기 문제와 자기 언어를 찾고 싶은 사람",
    },
    {
        "title": "바이브코딩이라는 오해를 걷어내기",
        "keywords": ["바이브코딩", "코딩", "노코드", "입코딩", "AI", "Cursor", "Lovable", "누구든"],
        "thesis": "바이브코딩은 느낌만으로 대충 만드는 일이 아니라, 자연어로 문제를 구조화하고 작동하는 산출물까지 밀어붙이는 방식이다.",
        "axis": "개념 정의와 오해 제거",
        "reader": "AI 코딩이 궁금하지만 과장 광고와 실제 역량의 경계를 알고 싶은 사람",
    },
    {
        "title": "문제를 붙잡는 사람이 제품을 만든다",
        "keywords": ["문제", "고객", "기획", "요구사항", "사이트맵", "UI", "데이터명세", "목표 아웃풋"],
        "thesis": "AI가 구현 속도를 올릴수록, 무엇을 만들지 좁히고 말로 고정하는 사람이 더 큰 권한을 갖는다.",
        "axis": "문제 정의와 요구사항화",
        "reader": "아이디어는 있지만 요구사항과 화면으로 바꾸는 순간 막히는 사람",
    },
    {
        "title": "MVP는 작은 제품이 아니라 작은 증거다",
        "keywords": ["MVP", "핵심기능", "가설", "검증", "스타트업", "창업", "프로토타입", "실전"],
        "thesis": "MVP의 목적은 멋진 축소판이 아니라, 지금 믿고 있는 가설이 현실에서 버티는지 확인하는 작은 증거를 만드는 것이다.",
        "axis": "가설 검증과 MVP",
        "reader": "창업 아이디어나 사내 개선안을 빠르게 시험하고 싶은 사람",
    },
    {
        "title": "웹앱의 문법을 알면 AI가 보인다",
        "keywords": ["웹앱", "프론트", "백엔드", "서버", "데이터베이스", "API", "HTTP", "Supabase", "Firebase"],
        "thesis": "도구가 코드를 가려줘도 웹앱의 구조는 사라지지 않는다. 구조를 아는 만큼 AI와 대화할 수 있다.",
        "axis": "웹앱 기본 구조",
        "reader": "코드는 몰라도 화면, 데이터, 서버의 관계를 이해하고 싶은 사람",
    },
    {
        "title": "프롬프트가 아니라 작업 계약을 만든다",
        "keywords": ["프롬프트", "prompt", "기획강화", "역할", "출력", "Stage", "스펙", "계획", "검증"],
        "thesis": "좋은 프롬프트는 주문 문장이 아니라 역할, 입력, 출력, 금지사항, 검증 기준을 묶은 작업 계약서다.",
        "axis": "AI 협업 프로토콜",
        "reader": "AI에게 시켜도 결과가 흔들리는 이유를 알고 싶은 사람",
    },
    {
        "title": "도구는 유행이 아니라 경로다",
        "keywords": ["Cursor", "Lovable", "Gemini", "Firebase", "Claude", "Codex", "v0", "Bolt", "Replit"],
        "thesis": "도구 선택의 기준은 최신성이 아니라 지금 검증할 가설까지 가장 짧고 안전하게 가는 경로다.",
        "axis": "툴체인과 선택 기준",
        "reader": "도구가 너무 많아 무엇부터 써야 할지 모르는 사람",
    },
    {
        "title": "브라우저 자동화는 현실을 다루는 코딩이다",
        "keywords": ["브라우저", "Playwright", "자동화", "스크래핑", "RPA", "API", "업로드", "human-like"],
        "thesis": "API가 없는 세상에서도 일은 계속된다. 브라우저 자동화는 현실의 업무 화면을 AI와 함께 다루는 방법이다.",
        "axis": "브라우저와 업무 자동화",
        "reader": "반복 업무를 줄이고 싶은 실무자와 운영 담당자",
    },
    {
        "title": "운영의 언어로 제품을 고친다",
        "keywords": ["ERP", "CRM", "Salesforce", "포탈", "Teams", "Slack", "데이터", "업무기록", "프로세스"],
        "thesis": "말라카식 바이브코딩은 데모에서 끝나지 않는다. 실제 회사의 주문, 수금, CRM, ERP 흐름을 고치는 데까지 내려간다.",
        "axis": "실무 시스템과 프로세스 혁신",
        "reader": "AI를 사내 업무와 운영 개선에 적용하려는 사람",
    },
    {
        "title": "강의는 지식을 파는 일이 아니라 실행을 설계하는 일이다",
        "keywords": ["강의", "교육", "워크숍", "커리큘럼", "고려대", "부경대", "WhyQ", "VOD", "커뮤니티"],
        "thesis": "좋은 바이브코딩 강의는 도구 설명보다 수강자가 자기 손으로 결과물을 만들게 하는 진행 설계에서 갈린다.",
        "axis": "교육, 커뮤니티, 콘텐츠",
        "reader": "AI 활용 교육이나 워크숍을 준비하는 사람",
    },
    {
        "title": "LifeOS: 기록은 실행을 낳아야 한다",
        "keywords": ["LifeOS", "JOT", "회고", "목표허브", "루틴", "노션", "데이터베이스", "성장습관"],
        "thesis": "기록은 저장이 아니라 다음 행동을 더 쉽게 만들기 위한 운영체제다.",
        "axis": "개인 지식관리와 목표 시스템",
        "reader": "노션과 AI를 개인 성장 시스템으로 쓰고 싶은 사람",
    },
    {
        "title": "검증하지 않는 속도는 빚이다",
        "keywords": ["검증", "테스트", "QA", "보안", "개인정보", "리스크", "운영", "실패"],
        "thesis": "바이브코딩은 빠르기 때문에 더 위험하다. 빠르게 만든 만큼 빠르게 검증하는 습관이 필요하다.",
        "axis": "품질, 보안, 책임",
        "reader": "AI로 만든 결과물을 실제 사용자와 회사 업무에 올려야 하는 사람",
    },
]


PAGE_COUNT_PER_CHAPTER = 18
PAGE_PATTERNS = [
    {
        "name": "이름 붙이기",
        "focus": "먼저 이름을 붙이면 막연한 일이 다룰 수 있는 문제가 된다.",
        "action": "독자는 자기 프로젝트에서 아직 이름 붙이지 못한 불편함 하나를 찾아 한 문장으로 고정한다.",
    },
    {
        "name": "경계 세우기",
        "focus": "좋은 실행은 무엇을 할지보다 무엇을 하지 않을지를 먼저 선명하게 만든다.",
        "action": "이번 반복에서 만들지 않을 기능 세 가지를 적고, 그 이유를 검증 기준 옆에 둔다.",
    },
    {
        "name": "작은 증거 만들기",
        "focus": "MVP는 완성품의 축소판이 아니라 판단을 가능하게 하는 증거다.",
        "action": "하루 안에 볼 수 있는 결과물 하나를 정하고, 그 결과가 어떤 질문에 답하는지 쓴다.",
    },
    {
        "name": "AI와 역할 나누기",
        "focus": "AI에게 모든 것을 맡기는 대신 사람이 판단할 일과 기계가 밀어붙일 일을 나눈다.",
        "action": "기획, 구현, 검증, 정리 중 AI에게 맡길 부분과 직접 볼 부분을 구분한다.",
    },
    {
        "name": "구조 그리기",
        "focus": "화면, 데이터, 흐름을 그리면 도구가 바뀌어도 대화가 흔들리지 않는다.",
        "action": "만들려는 도구를 화면 세 개와 데이터 세 종류로 설명해 본다.",
    },
    {
        "name": "실패를 먼저 놓기",
        "focus": "실패 시나리오를 먼저 생각하면 빠른 실행이 무책임한 속도가 되지 않는다.",
        "action": "사용자가 오해할 지점, 데이터가 틀릴 지점, 비용이 튈 지점을 각각 하나씩 적는다.",
    },
    {
        "name": "운영으로 연결하기",
        "focus": "데모는 끝이 아니라 운영으로 들어가기 위한 입구다.",
        "action": "이 결과물을 일주일 동안 실제 업무나 생활에 넣었을 때 필요한 유지 조건을 쓴다.",
    },
    {
        "name": "가르칠 수 있게 만들기",
        "focus": "남에게 가르칠 수 있을 때 비로소 방법론이 된다.",
        "action": "방금 한 일을 처음 보는 사람에게 15분 안에 시연할 수 있는 순서로 재배열한다.",
    },
]

CHAPTER_DETAILS = {
    "말라카의 바다에서 시작하기": {
        "stance": "내가 바이브코딩을 말할 때 가장 먼저 꺼내는 것은 도구 이름이 아니라 삶의 운영 방식이다.",
        "scene": "Notion의 목표 문장, 커리어 고민, 강의 준비 메모가 한 방향으로 모이는 장면",
        "method": "생각을 흘려보내지 않고 이름 붙이고, 기록하고, 다음 행동으로 변환한다.",
        "risk": "자기 언어가 없으면 AI가 만들어 준 결과도 결국 남의 문제를 푸는 장난감이 된다.",
        "deliverable": "내가 왜 이 프로젝트를 하는지 설명하는 한 문장과 오늘 만들 작은 결과물",
    },
    "바이브코딩이라는 오해를 걷어내기": {
        "stance": "바이브코딩은 대충 말하면 AI가 알아서 만들어 주는 마술이 아니다.",
        "scene": "강의장에서 비개발자가 첫 화면을 만들며 기대와 불안을 동시에 느끼는 장면",
        "method": "자연어를 감상이 아니라 요구사항, 제약, 검증 조건으로 바꾸어 AI와 일한다.",
        "risk": "입코딩과 바이브코딩을 혼동하면 결과물은 빠르게 생기지만 책임은 아무도 지지 않는다.",
        "deliverable": "내가 원하는 기능을 상황, 사용자, 입력, 출력, 실패 조건으로 다시 쓴 작업 설명",
    },
    "문제를 붙잡는 사람이 제품을 만든다": {
        "stance": "구현 속도가 빨라질수록 더 귀해지는 사람은 문제를 붙잡는 사람이다.",
        "scene": "아이디어가 많은 회의에서 정작 첫 화면과 첫 데이터가 정해지지 않는 장면",
        "method": "고객 행동, 업무 흐름, 데이터 구조를 한 장의 요구사항으로 고정한다.",
        "risk": "문제를 고정하지 않으면 AI는 성실하게 많은 화면을 만들지만 제품은 생기지 않는다.",
        "deliverable": "사용자 한 명, 핵심 행동 하나, 데이터 하나로 좁힌 제품 정의",
    },
    "MVP는 작은 제품이 아니라 작은 증거다": {
        "stance": "MVP는 작아서 좋은 제품이 아니라 판단을 가능하게 해서 좋은 증거다.",
        "scene": "창업 아이디어나 사내 개선안을 말로 설명하다가 실제 사용 장면 앞에서 멈추는 장면",
        "method": "가설을 하나 고르고, 그 가설을 확인할 가장 작은 작동물을 만든다.",
        "risk": "MVP를 축소판으로 착각하면 확인해야 할 질문보다 예쁜 화면을 먼저 만들게 된다.",
        "deliverable": "하루 안에 만들 수 있고 한 가지 판단만 가능하게 하는 검증 산출물",
    },
    "웹앱의 문법을 알면 AI가 보인다": {
        "stance": "코드를 몰라도 웹앱의 문법은 알아야 AI가 내는 답을 볼 수 있다.",
        "scene": "화면은 보이지만 데이터가 어디에 저장되고 API가 왜 필요한지 막히는 장면",
        "method": "프론트엔드, 백엔드, 데이터베이스, 인증, 배포를 역할 단위로 나누어 이해한다.",
        "risk": "구조를 모르면 오류가 났을 때 AI가 내는 설명을 검증하지 못하고 같은 자리를 돈다.",
        "deliverable": "내 서비스의 화면, 데이터, 서버, 외부 API 관계도",
    },
    "프롬프트가 아니라 작업 계약을 만든다": {
        "stance": "프롬프트는 멋진 주문이 아니라 일을 맡기는 계약서다.",
        "scene": "AI에게 여러 번 시켰는데 매번 다른 결과가 나와 피로해지는 장면",
        "method": "역할, 맥락, 입력, 산출물 형식, 금지사항, 검증 기준을 한 번에 적는다.",
        "risk": "작업 계약이 없으면 결과가 흔들릴 때 원인을 도구 성능 탓으로만 돌리게 된다.",
        "deliverable": "다음 사람도 그대로 실행할 수 있는 작업 계약 프롬프트",
    },
    "도구는 유행이 아니라 경로다": {
        "stance": "도구 선택의 기준은 최신성이 아니라 내가 확인할 질문까지 가는 거리다.",
        "scene": "Cursor, Claude, Codex, Lovable, Firebase, Supabase 사이에서 무엇부터 해야 할지 헷갈리는 장면",
        "method": "기획, 구현, 데이터, 배포, 검증 중 지금 막힌 구간을 기준으로 도구를 고른다.",
        "risk": "도구를 배우는 재미가 프로젝트의 증거를 만드는 일을 대신하면 속도는 허상이 된다.",
        "deliverable": "이번 반복에서 쓸 도구 하나와 쓰지 않을 도구 목록",
    },
    "브라우저 자동화는 현실을 다루는 코딩이다": {
        "stance": "현실의 업무는 API 문서보다 브라우저 화면에 먼저 남아 있는 경우가 많다.",
        "scene": "사람이 매일 누르던 버튼, 내려받던 엑셀, 옮겨 적던 값을 자동화해야 하는 장면",
        "method": "화면의 상태, 클릭 순서, 예외 상황, 결과 검증을 작업 절차로 기록한다.",
        "risk": "브라우저 자동화를 단순 매크로로 보면 로그인, 권한, 속도, 오류 복구에서 바로 무너진다.",
        "deliverable": "반복 업무 한 건의 화면 흐름, 입력값, 성공 조건, 실패 복구 절차",
    },
    "운영의 언어로 제품을 고친다": {
        "stance": "내가 관심 있는 바이브코딩은 데모가 아니라 실제 운영을 바꾸는 쪽에 가깝다.",
        "scene": "CRM, ERP, 주문, 수금, Teams, Slack 기록이 흩어져 업무 판단이 느려지는 장면",
        "method": "업무 기록을 읽고 병목을 찾은 뒤, 사람의 판단과 자동화의 실행을 다시 배치한다.",
        "risk": "운영 맥락을 모르고 자동화하면 빠른 도구가 더 빠른 혼란을 만든다.",
        "deliverable": "한 업무 프로세스의 현재 흐름, 병목, 자동화 후보, 책임자 기준",
    },
    "강의는 지식을 파는 일이 아니라 실행을 설계하는 일이다": {
        "stance": "강의의 목표는 수강생이 고개를 끄덕이는 것이 아니라 손을 움직여 결과를 만드는 것이다.",
        "scene": "고려대, 부경대, WhyQ 강의 메모처럼 서로 다른 청중에게 같은 핵심을 다른 순서로 전달하는 장면",
        "method": "설명보다 실습 흐름을 먼저 설계하고, 실패 지점을 예상해 중간 발판을 놓는다.",
        "risk": "도구 소개가 많아질수록 수강생은 많이 들었지만 아무것도 만들지 못한 채 끝난다.",
        "deliverable": "수강생이 2시간 안에 직접 완성할 산출물과 중간 체크포인트",
    },
    "LifeOS: 기록은 실행을 낳아야 한다": {
        "stance": "기록은 기억을 저장하기 위해서가 아니라 다음 실행을 쉽게 만들기 위해 존재한다.",
        "scene": "Jot, Task, Goal Hub, 회고가 흩어진 생각을 하루의 행동으로 바꾸는 장면",
        "method": "생각, 할 일, 자료, 회고를 서로 이어 다음 프롬프트와 다음 선택의 재료로 만든다.",
        "risk": "기록이 많아질수록 실행과 연결되지 않은 저장소는 더 정교한 미루기가 된다.",
        "deliverable": "오늘의 기록 하나가 내일의 행동 하나로 이어지는 LifeOS 루프",
    },
    "검증하지 않는 속도는 빚이다": {
        "stance": "AI로 빨리 만들수록 검증은 나중 일이 아니라 같은 속도로 붙어야 하는 일이다.",
        "scene": "강의 데모, 사내 자동화, 보안 검토, 실제 사용자 배포 앞에서 책임을 확인하는 장면",
        "method": "완료 기준, 테스트 방법, 데이터 확인, 권한과 개인정보 점검을 작업 안에 넣는다.",
        "risk": "검증 없는 속도는 당장은 성과처럼 보이지만 운영에 올라가는 순간 빚으로 돌아온다.",
        "deliverable": "내 결과물을 남에게 보여주기 전 반드시 확인할 체크리스트",
    },
}

CURATED_NOTION_SEEDS = {
    "말라카의 바다에서 시작하기": [
        ("Quick ㅂㅏ로  My Ocean", "말라카의 목표 문장, LifeOS, 기록과 실행을 연결하려는 자기 운영 방식"),
        ("커리어고민 250617, 나에대해 이해", "10년차 개발자가 AI, 제품, 교육, 자율성의 방향으로 자기 역할을 다시 정의하는 고민"),
        ("의현상담 240818", "제품으로 세상을 놀라게 하는 그룹에서 중추적 역할을 하고 싶다는 진로 욕망"),
        ("바이브코딩 관련 생각메모", "무엇을 원하는지 계속 생각하며 AI와 만들어 나가는 역량에 대한 메모"),
        ("내 기조 생각", "프로세스 전문가, AX 1세대 팀장, 현업 적용형 바이브코딩으로 포지셔닝하려는 구상"),
        ("디오에프 미션 리스트 기록", "비전공자가 실무에 적용할 수 있는 바이브코딩 방법론을 증명하려는 방향"),
    ],
    "바이브코딩이라는 오해를 걷어내기": [
        ("바이브코딩 관련 생각메모", "중요한 것은 도구가 아니라 내가 무엇을 원하고 어떤 과정으로 가는지 계속 점검하는 역량이라는 기록"),
        ("바이브 강의안 생각", "바이브코딩을 입코딩과 구분하고 실무 적용법으로 설명하려는 강의 준비"),
        ("바이브 주차별계획 gemini 250531", "예비 창업가가 4주 안에 MVP까지 가도록 돕는 커리큘럼 구상"),
        ("WhyQ AI 공유노트 (2603) 말라카 분", "Claude Code, Codex, 설치와 실습을 실제 강의 흐름으로 옮긴 공유 노트"),
    ],
    "문제를 붙잡는 사람이 제품을 만든다": [
        ("바이브 주차별계획 gemini 250531", "목표 아웃풋에서 역산해 C레벨도 인정할 기획으로 만드는 접근"),
        ("바이브 강의안 (for whyq, 2w)", "서비스 청사진, IA, 데이터 명세, 웹앱 기초를 함께 다루려는 강의안"),
        ("CRM 마이그레이션 task 명세", "업무 문제를 데이터 흐름과 산출물로 쪼개는 실무 기록"),
        ("디오에프 미션 리스트 기록", "현업에서 증명한 방식을 콘텐츠와 강의 방법론으로 전환하려는 기록"),
    ],
    "MVP는 작은 제품이 아니라 작은 증거다": [
        ("ps 부경대 MVP 강연", "비개발자가 웹앱 기초와 Lovable을 이용해 MVP를 만드는 강연 기획"),
        ("바이브 주차별계획 gemini 250531", "아이디어에서 MVP 완성까지의 역산형 학습 흐름"),
        ("바이브코딩 고려대강연 메모", "수강생이 짧은 시간 안에 결과물을 만드는 현장 피드백"),
        ("커리어고민 250617, 나에대해 이해", "고려대 바이브코딩 MVP 강의가 실제 성과로 남았다는 자기 평가"),
    ],
    "웹앱의 문법을 알면 AI가 보인다": [
        ("바이브 강의안 (for whyq, 2w)", "정석적인 웹앱 개발 과정과 AI 도구를 함께 가르치려는 설계"),
        ("WhyQ AI 공유노트 (2603) 말라카 분", "개발 환경과 AI 도구를 실습 가능한 흐름으로 정리한 노트"),
        ("음성분석서버 개발기록", "요구사항, 서버, API, 배포를 AI와 함께 기획한 개발 기록"),
        ("WMTWR Compose 개발기록", "실제 개발 이슈를 구조화해 해결하려는 작업 기록"),
    ],
    "프롬프트가 아니라 작업 계약을 만든다": [
        ("바이브코딩 고려대강연 메모", "기획 프롬프트와 실습 프롬프트를 수강생에게 전달한 강의 메모"),
        ("내 기조 생각", "Cursor와 Claude rules 설정을 고도화하려는 지향"),
        ("WhyQ AI 공유노트 (2603) 말라카 분", "AI에게 맡길 작업과 사람이 확인할 작업을 나누는 강의 자료"),
        ("바이브코딩 관련 생각메모", "지금 AI와 무엇을 하고 있는지 계속 자각해야 한다는 메모"),
    ],
    "도구는 유행이 아니라 경로다": [
        ("WhyQ AI 공유노트 (2603) 말라카 분", "Claude Code, Codex, 설치와 사용을 강의 목적에 맞게 배치한 노트"),
        ("바이브 강의안 생각", "Lovable, Cursor, Firebase 등 도구를 학습 목표에 맞게 묶는 구상"),
        ("ps 부경대 MVP 강연", "비개발자에게 필요한 도구만 골라 MVP까지 도달시키는 강연 설계"),
    ],
    "브라우저 자동화는 현실을 다루는 코딩이다": [
        ("CRM 마이그레이션 업무기록", "Salesforce 데이터, 주문, 제품, 수금 흐름을 추출하고 정리한 자동화 기록"),
        ("CRM 마이그레이션 task 명세", "브라우저와 업무 시스템을 통해 실제 데이터를 옮기는 업무 명세"),
        ("AutoShorts 시스템 개발기록 (TAS)", "반복 작업을 시스템화하려는 자동화 개발 기록"),
        ("디오에프 미션 리스트 기록", "실무 자동화 경험을 방법론과 강의 소재로 전환하려는 기록"),
    ],
    "운영의 언어로 제품을 고친다": [
        ("CRM 마이그레이션 업무기록", "CRM, 주문, 제품, 수금 데이터가 실제 운영 개선의 재료가 되는 기록"),
        ("CRM 마이그레이션 task 명세", "업무 문제를 산출물, 실행 계획, 활용 방법으로 쪼갠 명세"),
        ("디오에프 박현수대표님 만남 2차 노트 2025-07-15 ", "운영과 제품 역할 사이에서 자기 포지션을 고민한 대화 기록"),
        ("디오에프 미션 리스트 기록", "실무 문제를 자동화와 콘텐츠로 연결하려는 방향"),
    ],
    "강의는 지식을 파는 일이 아니라 실행을 설계하는 일이다": [
        ("바이브코딩 고려대강연 메모", "현장 강의 피드백과 실습 진행 방식이 남아 있는 메모"),
        ("ps 부경대 MVP 강연", "비개발자 MVP 제작을 위한 바이브코딩 강연 공지와 구조"),
        ("WhyQ 강의 운영노트", "강의를 운영 가능한 흐름으로 만들려는 기록"),
        ("AI 활용교육 강의안 피드백 (강태환)", "AI 교육을 실습형 구조로 다듬기 위한 피드백 기록"),
        ("커리어고민 250617, 나에대해 이해", "고려대 강의 성과가 새로운 커리어 가능성으로 인식된 기록"),
    ],
    "LifeOS: 기록은 실행을 낳아야 한다": [
        ("Quick ㅂㅏ로  My Ocean", "Goal Hub, Quick Zone, Task DB, Jot DB를 연결한 개인 운영체계"),
        ("내 기조 생각", "지식 콘텐츠와 경험 콘텐츠를 누적하려는 기록 습관"),
        ("바이브코딩 관련 생각메모", "AI와 작업하면서 생각과 과정을 계속 붙잡으려는 메모"),
        ("사업전략 및 목표", "기록을 전략과 목표 관리로 연결하려는 페이지"),
    ],
    "검증하지 않는 속도는 빚이다": [
        ("바이브 스터디 운영방법 영경형과 논의한거 구체화", "스터디 운영을 구체화하며 참여자의 실행과 검증을 설계한 기록"),
        ("보안관련 DT파트회의 241014", "실무 시스템에서 보안과 권한을 함께 고려해야 하는 회의 기록"),
        ("정보보안감사 240812", "운영 환경에서 빠른 실행만큼 통제와 감사가 필요하다는 단서"),
        ("바이브코딩 고려대강연 메모", "수강생 결과물을 현장에서 확인하고 개선한 피드백 루프"),
    ],
}

SOURCE_KIND_KO = {
    "slide": "강의 슬라이드",
    "notion": "Notion 기록",
    "author": "저자 명제",
}

PROMPT_CONTRACTS = [
    "너는 내 프로젝트의 기획 파트너다. 지금 상황, 사용자, 입력, 출력, 성공 기준을 읽고 빠진 조건을 질문한 뒤 한 페이지 요구사항으로 정리해라.",
    "너는 구현 보조자다. 내가 정한 범위 안에서 가장 작은 작동물을 만들기 위한 단계와 검증 명령을 제안해라.",
    "너는 QA 리뷰어다. 결과물이 실패할 수 있는 조건, 사용자가 오해할 수 있는 문구, 데이터가 깨질 수 있는 지점을 찾아라.",
    "너는 운영 설계자다. 이 기능이 실제 업무에 들어갈 때 필요한 권한, 반복 주기, 로그, 예외 처리 기준을 정리해라.",
    "너는 강의 조교다. 처음 보는 사람이 15분 안에 따라 할 수 있도록 실습 순서와 중간 체크포인트를 다시 배열해라.",
    "너는 기록 편집자다. 오늘의 작업 메모를 다음 실행 프롬프트, 할 일, 검증 기준으로 분리해라.",
]


def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def md(text: str) -> str:
    return clean_ws(text).replace("\\", "\\\\")


def clean_excerpt(text: str) -> str:
    text = re.sub(r"https?://\\S+", "", clean_ws(text))
    text = re.sub(
        r"\\b(formula|string|relation|select|rich_text|created_time|last_edited_time|title|text|url|number|boolean|rollup|array|status|green|date|multi_select)\\b",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\\b[0-9a-f]{8,}\\b", "", text, flags=re.I)
    return clean_ws(text)[:300]


def load_sources() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    slides = json.loads(SLIDES_PATH.read_text(encoding="utf-8"))
    topic = json.loads(NOTION_TOPIC_PATH.read_text(encoding="utf-8"))
    corpus = json.loads(NOTION_CORPUS_PATH.read_text(encoding="utf-8"))
    return slides, topic, corpus


def slide_text(slide: dict[str, Any]) -> str:
    return "\n".join(slide.get("paragraphs", []) + slide.get("notes", []))


def seed_score(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(keyword.lower()) for keyword in keywords)


def excerpt_from_slide(slide: dict[str, Any]) -> str:
    title = clean_ws(slide.get("title", ""))
    for paragraph in slide.get("paragraphs", []) + slide.get("notes", []):
        paragraph = clean_ws(paragraph)
        if len(paragraph) >= 14 and paragraph != title:
            return clean_excerpt(paragraph[:260])
    return title[:260]


def select_slide_seeds(slides: list[dict[str, Any]], keywords: list[str], limit: int) -> list[SourceSeed]:
    candidates: list[tuple[int, SourceSeed]] = []
    seen = set()
    for slide in slides:
        if slide.get("hidden"):
            continue
        title = clean_ws(slide.get("title", ""))
        if not title or re.fullmatch(r"\d+", title) or title in seen:
            continue
        text = f"{title}\n{slide_text(slide)}"
        score = seed_score(text, keywords)
        if score <= 0:
            continue
        seen.add(title)
        candidates.append(
            (
                score,
                SourceSeed(
                    kind="slide",
                    title=title,
                    source=f"{slide.get('deck_file_name')} #{slide.get('slide_number')}",
                    excerpt=excerpt_from_slide(slide),
                ),
            )
        )
    candidates.sort(key=lambda item: (item[0], len(item[1].excerpt)), reverse=True)
    return [seed for _, seed in candidates[:limit]]


def select_notion_seeds(topic: dict[str, list[dict[str, Any]]], corpus: list[dict[str, Any]], keywords: list[str], limit: int) -> list[SourceSeed]:
    candidates: list[tuple[int, SourceSeed]] = []
    seen = set()
    relevant_topics = [
        "identity",
        "ai_vibecoding",
        "automation",
        "startup_product",
        "teaching_writing",
        "operations",
        "life_philosophy",
    ]
    for bucket in relevant_topics:
        for item in topic.get(bucket, []):
            title = clean_ws(item.get("title", ""))
            text = f"{title}\n{item.get('excerpt', '')}\n{item.get('data_source', '')}"
            score = seed_score(text, keywords) + int(item.get("score", 0) > 20)
            if score <= 0 or title in seen:
                continue
            seen.add(title)
            candidates.append(
                (
                    score,
                    SourceSeed(
                        kind="notion",
                        title=title,
                        source=f"{item.get('data_source')}: {item.get('path')}",
                        excerpt=clean_excerpt(item.get("excerpt", "")),
                    ),
                )
            )
    for item in corpus:
        title = clean_ws(item.get("title", ""))
        text = f"{title}\n{item.get('excerpt', '')}\n{item.get('data_source', '')}"
        score = seed_score(text, keywords)
        if score <= 0 or title in seen:
            continue
        seen.add(title)
        candidates.append(
            (
                score,
                SourceSeed(
                    kind="notion",
                    title=title,
                    source=f"{item.get('data_source')}: {item.get('path')}",
                    excerpt=clean_excerpt(item.get("excerpt", "")),
                ),
            )
        )
    candidates.sort(key=lambda item: (item[0], len(item[1].excerpt)), reverse=True)
    return [seed for _, seed in candidates[:limit]]


def find_notion_source(title: str, corpus: list[dict[str, Any]], topic: dict[str, list[dict[str, Any]]]) -> str:
    title_norm = clean_ws(title)
    for item in corpus:
        if clean_ws(item.get("title", "")) == title_norm:
            return f"{item.get('data_source')}: {item.get('path')}"
    for items in topic.values():
        for item in items:
            if clean_ws(item.get("title", "")) == title_norm:
                return f"{item.get('data_source')}: {item.get('path')}"
    for item in corpus:
        candidate = clean_ws(item.get("title", ""))
        if title_norm in candidate or candidate in title_norm:
            return f"{item.get('data_source')}: {item.get('path')}"
    return "curated Notion evidence"


def select_curated_notion_seeds(chapter: dict[str, Any], topic: dict[str, list[dict[str, Any]]], corpus: list[dict[str, Any]]) -> list[SourceSeed]:
    seeds = []
    for title, interpretation in CURATED_NOTION_SEEDS.get(chapter["title"], []):
        seeds.append(
            SourceSeed(
                kind="notion",
                title=title,
                source=find_notion_source(title, corpus, topic),
                excerpt=interpretation,
            )
        )
    return seeds


def chapter_sources(chapter: dict[str, Any], slides: list[dict[str, Any]], topic: dict[str, list[dict[str, Any]]], corpus: list[dict[str, Any]]) -> list[SourceSeed]:
    slide_seeds = select_slide_seeds(slides, chapter["keywords"], 16)
    notion_seeds = select_curated_notion_seeds(chapter, topic, corpus)
    merged: list[SourceSeed] = []
    while slide_seeds or notion_seeds:
        if notion_seeds:
            merged.append(notion_seeds.pop(0))
        if slide_seeds:
            merged.append(slide_seeds.pop(0))
    fallback = [
        SourceSeed("author", chapter["title"], "chapter thesis", chapter["thesis"]),
        SourceSeed("author", chapter["axis"], "chapter axis", chapter["reader"]),
    ]
    merged.extend(fallback)
    return merged


def page_title(chapter: dict[str, Any], seed: SourceSeed, idx: int) -> str:
    base = clean_ws(seed.title)
    if len(base) > 42:
        base = base[:39].rstrip() + "..."
    prefixes = [
        "정의하기",
        "현장으로 내리기",
        "작게 만들기",
        "AI와 나누기",
        "검증하기",
        "운영으로 잇기",
    ]
    return f"{prefixes[(idx - 1) % len(prefixes)]}: {base}"


def source_interpretation(seed: SourceSeed, chapter: dict[str, Any]) -> str:
    kind = SOURCE_KIND_KO.get(seed.kind, seed.kind)
    if seed.kind == "notion" and seed.excerpt:
        return (
            f"이 절은 '{seed.title}'라는 {kind}을 책의 문장으로 다시 읽는 데서 출발한다. "
            f"내가 여기서 읽은 핵심은 {seed.excerpt}이다."
        )
    if seed.kind == "slide":
        return (
            f"이 절은 '{seed.title}'라는 {kind}에서 출발한다. "
            f"슬라이드의 문장을 옮기는 대신, 그 제목이 {chapter['axis']}라는 축에서 어떤 실행 질문으로 바뀌는지를 다룬다."
        )
    return f"이 절은 '{seed.title}'라는 단서를 {chapter['axis']}의 관점에서 다시 정리한다."


def chapter_object(chapter: dict[str, Any]) -> str:
    title = chapter["title"]
    if title.endswith("기"):
        return f"'{title}'라는 주제"
    return f"'{title}'"


def write_page(chapter_no: int, page_no: int, chapter: dict[str, Any], seed: SourceSeed) -> list[str]:
    title = page_title(chapter, seed, page_no)
    pattern = PAGE_PATTERNS[(page_no - 1) % len(PAGE_PATTERNS)]
    detail = CHAPTER_DETAILS[chapter["title"]]
    interpretation = source_interpretation(seed, chapter)
    object_name = chapter_object(chapter)
    contract = PROMPT_CONTRACTS[(chapter_no + page_no - 2) % len(PROMPT_CONTRACTS)]
    return [
        "",
        '<div class="book-page"></div>',
        "",
        f"## {chapter_no}-{page_no:02d}. {md(title)}",
        "",
        f"<div class=\"source-note\">근거 맥락: {md(seed.kind)} · {md(seed.source)}</div>",
        "",
        f"{object_name}를 다룰 때 내가 먼저 붙잡는 문장은 이것이다. {chapter['thesis']} "
        f"{interpretation} 원천은 증거로 남겨 두되, 본문에서는 그 증거가 가리키는 일의 방식만 남긴다.",
        "",
        f"이 절의 작업 이름은 '{pattern['name']}'이다. {pattern['focus']} "
        f"{detail['stance']} 그래서 이 장의 축인 {chapter['axis']}도 구호가 아니라 작업 순서가 되어야 한다. "
        f"내가 상상하는 현장은 {detail['scene']}이다.",
        "",
        f"방법은 단순하지만 대충 넘어가면 안 된다. {detail['method']} "
        "AI는 이 과정을 빠르게 밀어 줄 수 있지만, 어떤 질문에 답해야 하는지는 사람이 끝까지 잡고 있어야 한다. "
        "나는 이 지점을 놓치지 않기 위해 작업을 시작할 때마다 문제, 산출물, 검증 기준을 같은 문서 안에 둔다.",
        "",
        f"위험도 분명하다. {detail['risk']} "
        "그래서 나는 빠른 결과를 좋아하지만 빠른 판단 포기는 경계한다. "
        "바이브코딩에서 사람의 역할은 사라지는 것이 아니라 더 선명해진다. 사람은 방향과 책임을 붙잡고, AI는 탐색과 반복의 밀도를 높인다.",
        "",
        "### 실전 장면",
        "",
        f"이 절의 산출물은 {detail['deliverable']}이다. "
        "처음부터 완벽한 기획서를 쓰려 하지 않아도 된다. 대신 오늘 확인할 질문 하나를 고르고, 그 질문에 답할 만큼만 만든다. "
        "결과가 기대와 다르면 실패가 아니라 다음 프롬프트의 제약 조건이 생긴 것이다.",
        "",
        "### 말라카식 적용",
        "",
        f"- {pattern['action']}",
        "- AI에게 줄 첫 지시는 기능 목록보다 상황, 입력, 출력, 검증 조건을 먼저 포함한다.",
        f"- 결과를 받으면 성공/실패로만 판단하지 말고, {chapter['axis']} 관점에서 다음 반복에 넣을 제약 조건을 하나 뽑는다.",
        "- 기록은 다음 프롬프트의 재료가 되어야 한다. 저장만 되는 기록은 LifeOS가 아니라 창고다.",
        "",
        "### 작업 계약 초안",
        "",
        f"> {contract}",
        "",
        "이 초안을 그대로 복사하라는 뜻은 아니다. 핵심은 내가 AI에게 일을 맡길 때도 내 판단 기준을 함께 넘겨야 한다는 점이다. "
        "AI가 좋은 결과를 냈다면 기준이 분명했기 때문인지, 우연히 맞았기 때문인지 다시 확인해야 한다.",
        "",
        "### 저자의 메모",
        "",
        f"'{md(seed.title)}'라는 단서는 결국 내게 한 가지 질문을 남긴다. 지금 내 앞의 문제는 말로만 설명되고 있는가, 아니면 작동하는 작은 결과로 바뀌고 있는가. "
        "나는 후자를 선택하려고 이 책을 쓴다. 정확한 언어로 작게 시작하고, 실제 결과를 보고, 다시 언어를 고친다.",
        "",
        "### 독자에게 던지는 질문",
        "",
        f"- 이 페이지의 단서를 내 프로젝트에 대입하면 어떤 {chapter['axis']} 문제가 드러나는가?",
        "- 지금 가장 작은 산출물을 만든다면 무엇을 빼야 하는가?",
        "- 내가 직접 확인할 수 없는 결과를 AI가 내놓았을 때, 검증 책임은 누구에게 있는가?",
    ]


def write_chapter(chapter_no: int, chapter: dict[str, Any], seeds: list[SourceSeed]) -> list[str]:
    lines = [
        "",
        '<div class="chapter-break"></div>',
        "",
        f"# {chapter_no}. {chapter['title']}",
        "",
        f"**핵심 명제:** {chapter['thesis']}",
        "",
        f"**이 장의 축:** {chapter['axis']}",
        "",
        f"**상정 독자:** {chapter['reader']}",
        "",
        "이 장은 강의 자료의 반복 제목과 Notion 기록의 생활 문장을 함께 읽어 재구성했다. "
        "PPT의 문장은 공개 강의의 뼈대이고, Notion의 문장은 그 강의를 가능하게 만든 생활 방식이다. "
        "둘을 겹쳐 읽으면 말라카가 단순히 AI 도구 사용법을 말하려는 것이 아니라, 생각을 실행으로 바꾸는 운영체계를 말하려 한다는 점이 선명해진다.",
        "",
        "말라카식 글쓰기는 기술을 신비화하지 않는다. 반대로 너무 일상적인 문제 안으로 기술을 끌고 들어온다. "
        "회사에서 반복되는 수작업, 강의장에서 막히는 수강생의 손, 자기 목표를 잊어버리는 생활 리듬, 창업 아이디어가 말에서 멈추는 장면이 모두 같은 구조를 가진다. "
        "문제를 보이게 만들고, 작은 결과를 만들고, 다시 기록해서 다음 단계로 간다는 구조다.",
        "",
    ]
    for idx in range(1, PAGE_COUNT_PER_CHAPTER + 1):
        seed = seeds[(idx - 1) % len(seeds)]
        lines.extend(write_page(chapter_no, idx, chapter, seed))
    return lines


def render_manuscript(slides: list[dict[str, Any]], topic: dict[str, list[dict[str, Any]]], corpus: list[dict[str, Any]]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_pages = len(CHAPTERS) * PAGE_COUNT_PER_CHAPTER
    lines = [
        '<div class="cover">',
        "",
        "# 바이브코딩은 일하는 방식이다",
        "",
        "## 문제를 제품과 자동화로 바꾸는 말라카의 실행법",
        "",
        "**말라카 지음**",
        "",
        f"**원고 생성일:** {generated_at}",
        "",
        f"**구성:** {len(CHAPTERS)}장, 장별 {PAGE_COUNT_PER_CHAPTER}개 절, 본문 절 {total_pages}개",
        "",
        "</div>",
        "",
        '<div class="chapter-break"></div>',
        "",
        "# 출간 전 서문",
        "",
        "이 책은 바이브코딩 강의 슬라이드를 그대로 옮긴 자료집이 아니다. 앞서 수집한 PPT와 Notion 스크랩을 읽고, 그 속에서 반복되는 생각과 생활 방식과 강의 방법을 말라카라는 저자의 목소리로 다시 쓴 원고다. "
        "따라서 여기의 문장은 원자료를 요약한 것이 아니라 원자료가 가리키는 방법론을 책의 언어로 재구성한 것이다.",
        "",
        "말라카라는 이름은 하나의 태도에 가깝다. 노션의 목표 문장에는 '나만의 통찰'과 '생각의 충돌을 즐기는 사람들'과 '가슴 뛰는 이야기'가 함께 놓여 있었다. "
        "이 책은 바로 그 세 단어에서 출발한다. 통찰은 혼자 빛나는 문장이 아니라 실행 가능한 절차가 되어야 하고, 충돌은 싸움이 아니라 더 나은 문제 정의를 낳아야 하며, 이야기는 듣는 사람을 움직이는 산출물로 끝나야 한다.",
        "",
        "# 이 책을 읽는 법",
        "",
        "각 장은 하나의 주장으로 시작한다. 그 뒤의 절들은 강의 슬라이드와 Notion 기록에서 뽑은 단서를 바탕으로 새로 쓴 짧은 에세이다. "
        "각 절은 독자가 자기 문제에 바로 적용할 수 있도록 '말라카식 적용'과 '독자에게 던지는 질문'을 포함한다. 이 구조는 의도적으로 반복된다. 바이브코딩은 영감이 아니라 반복 가능한 습관이기 때문이다.",
        "",
        "# 목차",
        "",
    ]
    for idx, chapter in enumerate(CHAPTERS, start=1):
        lines.append(f"{idx}. {chapter['title']}")
    for idx, chapter in enumerate(CHAPTERS, start=1):
        seeds = chapter_sources(chapter, slides, topic, corpus)
        lines.extend(write_chapter(idx, chapter, seeds))
    lines.extend(
        [
            "",
            '<div class="chapter-break"></div>',
            "",
            "# 맺음말: 도구의 시대에 사람이 남기는 것",
            "",
            "AI가 더 많은 코드를 쓰게 될수록 사람에게 남는 일은 줄어드는 것이 아니라 선명해진다. 사람은 문제를 선택하고, 맥락을 제공하고, 책임을 진다. "
            "말라카가 강의와 기록을 통해 보여준 것은 바로 이 책임의 감각이다. 빠르게 만들 수 있으니 아무거나 만들자는 말이 아니라, 빠르게 만들 수 있으니 더 자주 검증하고 더 정확하게 배워야 한다는 말이다.",
            "",
            "바이브코딩은 언젠가 다른 이름으로 불릴 수 있다. Cursor도 Lovable도 Gemini도 Firebase도 지금과 다른 모양이 될 것이다. "
            "그러나 문제를 문장으로 고정하고, 작은 산출물로 만들고, 실제 사람 앞에서 검증하고, 기록을 다음 실행으로 바꾸는 습관은 남는다. 이 책이 남기려는 것도 그 습관이다.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_publication_plan(slides: list[dict[str, Any]], topic: dict[str, list[dict[str, Any]]], corpus: list[dict[str, Any]]) -> str:
    notion_examples = {
        key: items[:5]
        for key, items in topic.items()
        if key in {"identity", "ai_vibecoding", "automation", "startup_product", "teaching_writing", "life_philosophy"}
    }
    lines = [
        "# 출간계획서",
        "",
        "## 가제",
        "",
        "바이브코딩은 일하는 방식이다: 문제를 제품과 자동화로 바꾸는 말라카의 실행법",
        "",
        "## 저자",
        "",
        "말라카. Notion 기록과 강의 자료 기준으로는 본명 백인식, 10년차 개발자, AI와 자동화와 제품화를 연결하는 실무자다. "
        "공개용 저자 소개에서는 구체적인 가족/거주/회사 내부 사정은 덜어내고, '기록과 자동화로 문제를 제품화하는 개발자이자 강사'로 포지셔닝한다.",
        "",
        "## 기획 의도",
        "",
        "바이브코딩을 도구 사용법이 아니라 일하는 방식으로 다시 정의한다. 이 책은 강의 PPT를 이어 붙인 책이 아니라, 말라카가 Notion에 남긴 목표·회고·커리어 고민·강의 준비·업무 자동화 기록을 함께 읽어 재구성한 실전서다.",
        "",
        "## 핵심 독자",
        "",
        "- AI 도구로 MVP를 만들고 싶은 비개발자/초기 창업자",
        "- 사내 반복 업무와 운영 프로세스를 자동화하려는 실무자",
        "- AI 활용 교육, 워크숍, 커뮤니티를 준비하는 강사",
        "- 개발을 넘어 제품과 조직의 프로세스를 바꾸고 싶은 개발자",
        "",
        "## 책의 차별점",
        "",
        "- 특정 도구 튜토리얼이 아니라 문제 정의, 실행, 검증, 기록을 하나의 루프로 묶는다.",
        "- Notion 기록에서 드러난 말라카의 LifeOS 관점, 목표/회고 습관, 자동화 지향을 책의 저자 목소리로 반영한다.",
        "- 강의 자료의 바이브코딩/MVP/웹앱/프롬프트/브라우저 자동화 소재를 원문 짜깁기가 아니라 챕터별 방법론으로 재집필한다.",
        "- 데모 앱 제작에서 끝나지 않고 CRM, ERP, 업무기록, 브라우저 자동화 같은 실제 운영 문제까지 내려간다.",
        "",
        "## 원천 독해 요약",
        "",
        f"- PPT 추출 슬라이드: {len(slides)}장",
        f"- Notion 관련 페이지: {len(corpus)}건",
        "- 저자 핵심 문장: '나 [말라카]는 [나만의 통찰]으로 [생각의 충돌을 즐기는 사람들]에게 [가슴 뛰는 이야기를 들려주는] 삶을 살 것이다.'",
        "- 강의 핵심: 비개발자도 MVP를 만들 수 있게 하되, 인터넷 짜깁기가 아니라 실무 접근법을 녹인 방법론으로 증명하려는 방향.",
        "",
        "## 목차",
        "",
    ]
    for idx, chapter in enumerate(CHAPTERS, start=1):
        lines.extend([f"### {idx}. {chapter['title']}", "", chapter["thesis"], ""])
    lines.extend(["## Notion 근거 샘플", ""])
    for bucket, items in notion_examples.items():
        lines.extend([f"### {bucket}", ""])
        for item in items:
            lines.append(f"- {item.get('title')} — {item.get('excerpt')[:180]}")
        lines.append("")
    lines.extend(
        [
            "## 집필 원칙",
            "",
            "- 기존 PDF나 슬라이드 페이지를 이어 붙이지 않는다.",
            "- 원천 자료는 제목, 맥락, 문제의식, 사례 단서로만 사용한다.",
            "- 본문은 말라카라는 저자가 독자에게 설명하는 문장으로 새로 쓴다.",
            "- 민감한 개인 정보는 저자 이해에는 사용하되, 출간용 본문에는 불필요하게 노출하지 않는다.",
            "- 최종 PDF는 Markdown 원고를 렌더링한 결과물이어야 한다.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def css() -> str:
    return """
@page {
  size: A5;
  margin: 15mm 13mm 16mm 13mm;
  @bottom-center {
    content: counter(page);
    color: #6b7280;
    font-size: 8pt;
  }
}

html {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", "Pretendard", sans-serif;
  color: #14171a;
  line-height: 1.62;
  font-size: 9.6pt;
}

body { margin: 0; }

.cover {
  min-height: 178mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 6mm solid #111827;
  padding-left: 12mm;
}

.cover h1 {
  font-size: 25pt;
  line-height: 1.18;
  margin: 0 0 8mm;
}

h1 {
  break-before: page;
  font-size: 18pt;
  line-height: 1.22;
  margin: 0 0 7mm;
  padding-bottom: 3mm;
  border-bottom: 1pt solid #111827;
}

h2 {
  font-size: 12.3pt;
  line-height: 1.32;
  margin: 0 0 4mm;
  color: #111827;
}

h3 {
  font-size: 10.3pt;
  margin: 5mm 0 1.8mm;
  color: #1f2937;
  break-after: avoid;
}

p { margin: 0 0 3.2mm; }
ul, ol { margin: 0 0 4mm 5mm; padding: 0; }
li { margin: 0 0 1.7mm; }
blockquote {
  margin: 1.5mm 0 4mm;
  padding-left: 4mm;
  border-left: 2.5pt solid #111827;
  color: #374151;
}
.book-page { break-before: page; }
.chapter-break { break-before: page; }
.source-note {
  color: #6b7280;
  font-size: 7.8pt;
  margin: -1mm 0 3mm;
}
"""


def write_pdf(md_text: str, css_path: Path, html_path: Path, pdf_path: Path, title: str) -> None:
    import markdown
    from weasyprint import HTML

    body = markdown.markdown(md_text, extensions=["extra", "tables", "sane_lists"], output_format="html5")
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{html.escape(css_path.name)}">
</head>
<body>
{body}
</body>
</html>
"""
    html_path.write_text(html_text, encoding="utf-8")
    HTML(filename=str(html_path)).write_pdf(str(pdf_path), stylesheets=[str(css_path)])


def write_all() -> dict[str, str]:
    BOOK_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)
    slides, topic, corpus = load_sources()

    manuscript_md = render_manuscript(slides, topic, corpus)
    manuscript_md_path = BOOK_DIR / "malaka-vibecoding-real-book.md"
    manuscript_html_path = BOOK_DIR / "malaka-vibecoding-real-book.html"
    manuscript_css_path = BOOK_DIR / "malaka-vibecoding-real-book.css"
    manuscript_pdf_path = BOOK_DIR / "malaka-vibecoding-real-book.pdf"
    manuscript_md_path.write_text(manuscript_md, encoding="utf-8")
    manuscript_css_path.write_text(css(), encoding="utf-8")
    write_pdf(manuscript_md, manuscript_css_path, manuscript_html_path, manuscript_pdf_path, "바이브코딩은 일하는 방식이다")

    proposal_md = render_publication_plan(slides, topic, corpus)
    proposal_md_path = PROPOSAL_DIR / "malaka-publication-plan.md"
    proposal_html_path = PROPOSAL_DIR / "malaka-publication-plan.html"
    proposal_css_path = PROPOSAL_DIR / "malaka-publication-plan.css"
    proposal_pdf_path = PROPOSAL_DIR / "malaka-publication-plan.pdf"
    proposal_md_path.write_text(proposal_md, encoding="utf-8")
    proposal_css_path.write_text(css(), encoding="utf-8")
    write_pdf(proposal_md, proposal_css_path, proposal_html_path, proposal_pdf_path, "말라카 바이브코딩 출간계획서")

    return {
        "manuscript_md": str(manuscript_md_path.resolve()),
        "manuscript_html": str(manuscript_html_path.resolve()),
        "manuscript_pdf": str(manuscript_pdf_path.resolve()),
        "proposal_md": str(proposal_md_path.resolve()),
        "proposal_html": str(proposal_html_path.resolve()),
        "proposal_pdf": str(proposal_pdf_path.resolve()),
    }


def main() -> int:
    paths = write_all()
    print(json.dumps(paths, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
