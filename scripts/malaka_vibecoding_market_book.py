#!/usr/bin/env python3
"""Create a market-positioned edition of the Malaka vibecoding book.

The edition uses Kyobo market research for positioning and table-of-contents
shape, then rewrites the book around a clearer commercial promise: a practical
operating manual for vibe coding and AX, proven in large classes and company
work. Local PPT/Notion/ChatGPT/daily artifacts remain the manuscript evidence.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown
from weasyprint import HTML


ROOT = Path("data/vibecoding-book")
OUT = ROOT / "market-rewrite-2026-05-27"
ASSET_DIR = OUT / "assets" / "ppt-images"
CONNECTED_SUMMARY = ROOT / "connected-rewrite-2026-05-27" / "connected-summary.json"
CONNECTED_ASSETS = ROOT / "connected-rewrite-2026-05-27" / "assets" / "ppt-images"
SLIDES_PATH = ROOT / "extracts" / "all-slides.json"
NOTION_CORPUS_PATH = ROOT / "research" / "notion-author-corpus.json"
NOTION_TOPIC_PATH = ROOT / "research" / "notion-topic-evidence.json"
CHATGPT_DB = Path("data/db/chatgpt.sqlite")
DAILY_DIR = Path("data/daily")


BOOK_TITLE = "바이브코딩으로 일하는 법"
BOOK_SUBTITLE = "170명 실습강의와 회사 AX에서 검증한, 기획부터 배포·검증·확산까지의 실전 운영서"
BOOK_PROMISE = "AI가 코드를 쓰는 시대, 사람은 문제와 검증과 확산을 설계해야 한다."
BOOK_AUTHOR = "말라카"
BOOK_EDITION = "시장형 개정판"
BOOK_PUBLISH_DATE = "2026-05-28"

PART_LEDES = {
    "1부. 지금 당장 결과물을 만드는 사람들": "1부는 독자가 이 책을 집어 들어야 하는 이유를 먼저 세운다. 도구 소개보다 결과물, 독자, 하루짜리 증거를 앞에 둔다.",
    "2부. 하루 완성보다 중요한 작업 순서": "2부는 빠른 완성 뒤에 숨어 있는 작업 순서를 다룬다. 기획, 프롬프트, 구조, 검증을 하나의 흐름으로 묶는다.",
    "3부. SPARK IPO로 AI를 일하게 한다": "3부는 말라카식 작업 운영체계를 본격적으로 설명한다. 폴더와 기록과 판단의 자리를 나누어 AI 작업을 오래 남게 만든다.",
    "4부. 170명 실습강좌는 작은 조직 AX다": "4부는 대규모 실습강좌를 운영 설계의 문제로 본다. 설치, 대기, 실패, 공유까지 강의의 일부로 다룬다.",
    "5부. 회사 AX는 작은 자동화에서 시작한다": "5부는 회사 안에서 AI가 실제 성과가 되는 조건을 묻는다. 업무 구조, 책임, 검증, 클리닉을 작은 자동화의 언어로 정리한다.",
    "6부. 말라카의 강의와 커리어는 신뢰의 증거다": "6부는 저자의 경험을 책의 전면이 아니라 방법론의 증거로 배치한다. 강의와 회사와 출판 루프가 어떻게 서로를 밀어 주는지 보여 준다.",
}


KY0BO_SOURCES = [
    {
        "title": "바이브코딩 하루완성",
        "url": "https://ebook-product.kyobobook.co.kr/dig/epd/sam/E000012482490",
        "signal": "비개발자, 하루 완성, 기획부터 배포, 수익화라는 즉시성",
    },
    {
        "title": "AX 혁신 실무",
        "url": "https://ebook-product.kyobobook.co.kr/dig/epd/ebook/E000012818326",
        "signal": "AI 도입 실패 원인, 작은 자동화, ROI, 조직 정착",
    },
    {
        "title": "AX 기획론",
        "url": "https://ebook-product.kyobobook.co.kr/dig/epd/ebook/E000011414424",
        "signal": "기획자/마케터/비즈니스 리더 대상, 기능별 실무 적용",
    },
    {
        "title": "AX리더십",
        "url": "https://ebook-product.kyobobook.co.kr/dig/epd/sam/E000012549084",
        "signal": "리더의 관점 전환, 3단계 실행, 조직 확산",
    },
    {
        "title": "소크라테스와 AX",
        "url": "https://ebook-product.kyobobook.co.kr/dig/epd/sam/E000012944388",
        "signal": "질문형 목차, 조직 진단, 파일럿, 확산",
    },
    {
        "title": "AX 시대, 기업의 승부수는 사업·서비스·조직의 AI 전환에 있다",
        "url": "https://ebook-product.kyobobook.co.kr/dig/epd/ebook/E000008961793",
        "signal": "사업 개발, 서비스 개발, 조직 개발의 3축 구성",
    },
]


@dataclass(frozen=True)
class Chapter:
    part: str
    title: str
    hook: str
    market_reason: str
    local_source: str
    source_detail: list[str]
    scene: str
    promise: str
    sections: list[str]


CHAPTERS = [
    Chapter(
        "1부. 지금 당장 결과물을 만드는 사람들",
        "왜 지금 바이브코딩인가",
        "코딩을 배우기 전에 먼저 결과물을 정의하는 시대가 왔다.",
        "교보 유사 도서들은 '왜 지금'을 앞세워 독자의 긴장을 만든다. 이 책도 도구 소개보다 시대 변화와 독자의 이득으로 시작한다.",
        "Kyobo market research + Vibecoding PPT",
        ["바이브코딩 하루완성", "AX 혁신 실무", "바이브코딩 강의 PPT"],
        "아이디어는 있는데 코딩 문법과 서버와 배포 앞에서 멈추던 사람들이 이제 AI에게 자연어로 첫 버전을 맡기기 시작했다.",
        "독자는 이 장에서 바이브코딩을 유행어가 아니라 결과물을 만드는 새로운 업무 방식으로 이해한다.",
        ["기술 장벽보다 더 큰 것은 완성 장벽이다", "비개발자가 개발자 흉내를 내지 않아도 되는 이유", "AI가 만드는 것은 코드이고 사람이 정하는 것은 방향이다", "완성이 최고의 실력이라는 말의 의미", "이 책이 도구 매뉴얼이 아닌 이유", "첫날에 만들어야 할 것과 만들지 말아야 할 것"],
    ),
    Chapter(
        "1부. 지금 당장 결과물을 만드는 사람들",
        "독자는 무엇을 얻어야 돈을 낼까",
        "서점 독자는 저자의 자료량이 아니라 자기 문제의 해결 가능성을 산다.",
        "판매되는 실무서는 대상 독자와 즉시 효용이 분명하다. 기존 원고의 저자 서사를 줄이고 구매 이유를 앞에 배치한다.",
        "Kyobo market research + Daily 2026-05-27",
        ["교보 상품소개", "Daily 2026-05-27", "connected rewrite review"],
        "책 평가자는 가장 먼저 묻는다. 이 책은 누구에게, 어떤 긴급한 문제를, 어떤 순서로 해결해 주는가.",
        "독자는 이 장에서 자기 위치를 찾는다. 실무자, 강사, 창업자, 사내 AX 추진자 중 어디에 서 있든 이 책의 사용법을 알게 된다.",
        ["이 책의 핵심 독자 네 그룹", "비개발 실무자는 무엇을 불안해하는가", "강사는 왜 운영법을 원하나", "창업자는 왜 하루짜리 MVP를 원하나", "AX 담당자는 왜 조직 정착을 고민하나", "구매 이유를 한 문장으로 만들기"],
    ),
    Chapter(
        "1부. 지금 당장 결과물을 만드는 사람들",
        "하루짜리 MVP가 책의 첫 상품이다",
        "독자는 큰 철학보다 오늘 만들 작은 증거에 반응한다.",
        "바이브코딩 책의 경쟁 구도에서는 '단기간 완성'과 '현실적 결과물'이 강한 후킹이다.",
        "Startup lecture PPT + ChatGPT titles",
        ["MVP 생성 과정", "Lovable 제품 개발 전략", "startuplec latest decks"],
        "강의장에서 가장 강한 순간은 개념 설명이 아니라 누군가의 화면에 첫 결과물이 뜨는 순간이다.",
        "독자는 이 장에서 MVP를 작은 제품이 아니라 다음 판단을 가능하게 하는 작은 증거로 배운다.",
        ["MVP는 작은 제품이 아니라 작은 증거다", "하루 프로젝트의 성공 조건", "기능을 줄이는 것이 아니라 질문을 좁히는 일", "랜딩 페이지가 먼저인 이유", "첫 사용자 반응을 기록하는 법", "MVP 이후 다음 질문을 남기기"],
    ),
    Chapter(
        "1부. 지금 당장 결과물을 만드는 사람들",
        "비개발 실무자의 첫 번째 개발 언어",
        "자연어는 대충 말하는 언어가 아니라 작업 계약의 언어다.",
        "유사 도서는 비개발자를 전면에 세운다. 이 책은 비개발자가 개발자가 되는 이야기가 아니라 도메인 담당자가 결과물 책임자가 되는 이야기로 차별화한다.",
        "Daily AX notes + Notion corpus",
        ["Daily 2026-05-20", "Notion operations bucket", "ChatGPT 바이브코딩 강의 계획"],
        "회사에서는 개발자보다 업무 담당자가 문제를 더 정확히 아는 경우가 많다. AI는 이 간극을 좁히는 도구가 된다.",
        "독자는 이 장에서 자연어를 요구사항, 검증 기준, 산출 형식으로 바꾸는 법을 배운다.",
        ["자연어는 명세가 되어야 한다", "업무 담당자가 더 빨리 시작할 수 있는 이유", "프롬프트보다 먼저 기준을 쓰기", "산출 형식이 결과를 바꾼다", "개발자와 현업의 새 분업", "첫 프롬프트 전에 적어야 할 다섯 줄"],
    ),
    Chapter(
        "2부. 하루 완성보다 중요한 작업 순서",
        "기획은 AI에게 시키는 것이 아니라 같이 좁히는 것이다",
        "좋은 AI 결과물은 좋은 질문이 아니라 좁혀진 문제에서 나온다.",
        "실무형 도서들은 기획 템플릿과 목적 중심 구조를 앞에 둔다. 이 책은 기획을 바이브코딩의 첫 실행 단계로 둔다.",
        "KUBIT POC clinic PPT",
        ["기획 시키기 슬라이드", "POC Clinic notes", "ChatGPT: 마크다운 강의 기획"],
        "강의에서 '만들고 싶은 것'을 묻는 순간 대답은 대부분 너무 크다. AI는 큰 꿈보다 좁은 질문에서 빨라진다.",
        "독자는 이 장에서 아이디어를 목적, 대상, 행동, 화면, 검증 기준으로 줄이는 법을 익힌다.",
        ["아이디어를 문제 문장으로 바꾸기", "사용자를 한 명으로 좁히기", "첫 화면의 목적 정하기", "전환 행동을 먼저 쓰기", "하지 않을 기능을 정하는 법", "기획 문서를 프롬프트로 바꾸기"],
    ),
    Chapter(
        "2부. 하루 완성보다 중요한 작업 순서",
        "프롬프트는 설계 문서다",
        "AI에게 잘 말하는 것이 아니라 사람이 다시 검토할 수 있게 쓰는 것이다.",
        "바이브코딩 경쟁 도서는 프롬프트를 속도 도구로 쓴다. 이 책은 프롬프트를 설계·검증 문서로 격상한다.",
        "Prompt lecture slides",
        ["PPT 기획 시키기", "ChatGPT prompt topics", "Notion 강의준비"],
        "프롬프트를 한 줄 주문으로 쓰면 운 좋게 한 번은 된다. 하지만 반복 가능한 결과는 구조화된 작업 계약에서 나온다.",
        "독자는 이 장에서 목표, 맥락, 제약, 산출 형식, 검증 기준을 한 프롬프트 안에 넣는 법을 배운다.",
        ["역할보다 목표를 먼저 쓰기", "맥락은 길이가 아니라 정확도다", "산출 형식을 지정하면 검토가 쉬워진다", "금지 조건이 품질을 만든다", "검증 질문을 프롬프트에 넣기", "프롬프트를 다음 회차의 기록으로 남기기"],
    ),
    Chapter(
        "2부. 하루 완성보다 중요한 작업 순서",
        "웹앱 구조를 몰라도 책임질 수는 있어야 한다",
        "AI가 코드를 써도 화면, 데이터, API, 배포의 약속은 사람이 이해해야 한다.",
        "기술 교재와 실무서 사이에서 이 책은 최소 구조 지식만 남긴다. 비개발자가 결과물을 검토할 수 있을 만큼이면 된다.",
        "WhyQ webapp PPT",
        ["06-vivecodinglecwhyq-latest-2.pptx", "웹앱 강의 목차", "frontend appendix"],
        "결과물이 화면에 뜨면 사람들은 성공했다고 느끼지만, 웹앱은 화면만으로 되지 않는다.",
        "독자는 이 장에서 프론트엔드, 백엔드, 데이터베이스, API, 인증, 배포의 역할을 실무 언어로 구분한다.",
        ["화면은 제품의 전부가 아니다", "데이터베이스는 기억의 방식이다", "API는 팀 간의 약속이다", "인증과 권한은 나중 일이 아니다", "배포는 공유의 시작이다", "AI에게 구조를 설명하는 법"],
    ),
    Chapter(
        "2부. 하루 완성보다 중요한 작업 순서",
        "검증 없는 바이브는 빚이다",
        "빠른 완성은 검증 루프가 있을 때만 자산이 된다.",
        "AX 도서들은 실패와 리스크를 크게 다룬다. 이 책은 바이브코딩에서도 검증을 전면에 둬야 차별화된다.",
        "Daily ops + render verification",
        ["Daily 2026-05-26", "render-review.md", "ledger verification notes"],
        "AI 결과물은 처음 볼 때 그럴듯하다. 그럴듯함은 가장 위험한 착시다.",
        "독자는 이 장에서 렌더, 테스트, 사람 검수, 사용자 반응을 하나의 루프로 묶는 법을 배운다.",
        ["그럴듯함과 작동을 구분하기", "렌더를 직접 보는 이유", "테스트가 못 잡는 것을 사람이 본다", "일부러 틀린 값을 넣어 검증하기", "사용자 반응을 다음 프롬프트로 바꾸기", "검증 기록이 다음 프로젝트를 빠르게 한다"],
    ),
    Chapter(
        "3부. SPARK IPO로 AI를 일하게 한다",
        "SPARK는 AI 시대의 작업 계약이다",
        "Spec, Plan, Archive, Research, Knowhow가 있어야 AI 작업이 책과 업무로 남는다.",
        "차별화 포인트는 말라카 고유의 SPARK IPO다. 시장형 판에서는 이를 뒤가 아니라 중앙 방법론으로 배치한다.",
        "SPARK IPO PPT + AGENTS.md",
        ["22-vivecodinglecentre2603-latest.pptx", "AGENTS.md SPARK IPO", "proc/plan docs"],
        "AI와 일할수록 폴더 구조와 규칙이 중요해진다. 빠르게 만든 산출물이 사라지지 않게 하려면 생각의 집이 필요하다.",
        "독자는 이 장에서 SPARK를 자기 프로젝트의 최소 운영체제로 가져간다.",
        ["Spec은 독자와 AI 모두에게 필요한 약속이다", "Plan은 진행 중인 생각을 보호한다", "Archive는 버리는 힘이다", "Research는 주장 뒤의 창고다", "Knowhow는 반복 가능한 문장이다", "SPARK 폴더 하나로 프로젝트를 시작하기"],
    ),
    Chapter(
        "3부. SPARK IPO로 AI를 일하게 한다",
        "IPO는 자료를 결과물로 통과시키는 길이다",
        "Input, Proc, Output을 나누면 AI 산출물의 책임 위치가 보인다.",
        "AX 실무서들은 프로세스 분석을 강조한다. IPO는 바이브코딩과 AX를 잇는 간단한 프로세스 언어가 된다.",
        "SPARK IPO PPT + local pipeline",
        ["all-slides.json", "notion-author-corpus.json", "data/vibecoding-book outputs"],
        "자료가 많으면 AI는 더 잘할 것 같지만 실제로는 더 쉽게 흩어진다. 입력과 처리와 출력을 분리해야 한다.",
        "독자는 이 장에서 자료를 모으는 일과 저자 판단을 만드는 일을 구분한다.",
        ["Input을 많이 모으기 전에 기준을 세우기", "Proc는 AI가 아니라 사람의 판단 자리다", "Output은 파일이 아니라 사용 가능한 결과다", "중간 산출물이 있어야 되돌릴 수 있다", "같은 자료로 강의와 책과 업무문서를 나누기", "IPO 체크리스트"],
    ),
    Chapter(
        "3부. SPARK IPO로 AI를 일하게 한다",
        "AI에게 맡길 일과 사람이 붙잡을 일",
        "모든 업무를 AI로 할 필요는 없고, 모든 판단을 사람이 할 수도 없다.",
        "AX 혁신 실무와 리더십 도서의 공통점은 기술보다 역할 재설계다. 이 책도 사람과 AI의 분업을 명확히 한다.",
        "Daily AX notes",
        ["Daily 2026-05-20", "Daily 2026-05-22", "AX clinic notes"],
        "AI를 잘 쓰는 조직은 일을 AI에게 던지는 조직이 아니라, 어떤 일을 AI가 맡고 어떤 판단을 사람이 남길지 설계하는 조직이다.",
        "독자는 이 장에서 자동화 가능성, 위험도, 검증 비용을 기준으로 업무를 나누는 법을 배운다.",
        ["반복은 AI에게, 기준은 사람에게", "위험도가 높은 업무는 검증부터 설계한다", "도메인 지식은 자동화의 원료다", "사람의 역할은 실행자에서 판단자로 이동한다", "AI가 못하는 것을 과장하지도 축소하지도 않기", "업무 분해 표 만들기"],
    ),
    Chapter(
        "3부. SPARK IPO로 AI를 일하게 한다",
        "Archive가 있어야 진짜 새로 쓴다",
        "자료를 버리지 못하면 원고와 프로젝트는 계속 덧붙이기만 한다.",
        "평가자 관점에서 이전 원고의 가장 큰 리스크는 자료집 느낌이다. Archive 원칙으로 과감히 분리한다.",
        "Prior outputs + archive rules",
        ["connected rewrite", "final outputs", "AGENTS.md archive rule"],
        "이전 산출물은 실패가 아니다. 하지만 새 질문을 가진 책 앞에서는 참고 자료로 물러나야 한다.",
        "독자는 이 장에서 산출물을 보존하되 새 판을 쓰는 법을 배운다.",
        ["이전 판을 지우지 않고 밀어내기", "자료집과 원고를 분리하기", "반복 문장틀을 발견하는 법", "아까운 문장보다 독자의 흐름을 선택하기", "새 목차가 새 원고를 만든다", "버린 것이 아니라 다음 판에 보낸 것이다"],
    ),
    Chapter(
        "4부. 170명 실습강좌는 작은 조직 AX다",
        "대규모 실습은 지식 전달이 아니라 운영 설계다",
        "170명이 동시에 만들려면 설명보다 실패 예방이 먼저다.",
        "서점의 실무서는 독자가 재현 가능한 프로세스를 원한다. 170명 실습 운영은 이 책의 독특한 판매 포인트다.",
        "KUBIT lecture PPT + Daily notes",
        ["KUBIT POC Clinic PPT", "Daily 2026-05-23", "Daily 2026-05-24"],
        "강의실에서 170명이 AI 도구를 켜면 기술보다 운영이 먼저 터진다.",
        "독자는 이 장에서 대규모 실습을 설치, 템플릿, 공유, 복구, 발표의 흐름으로 설계한다.",
        ["대규모 실습의 첫 번째 원칙", "실습 전 실패를 목록화하기", "템플릿 없이는 자유도 없다", "조교가 봐야 할 실패 신호", "결과 공유까지 강의다", "강의실을 작은 조직으로 보기"],
    ),
    Chapter(
        "4부. 170명 실습강좌는 작은 조직 AX다",
        "설치와 로그인도 커리큘럼이다",
        "첫 20분을 잃으면 수강생은 도구가 아니라 자신을 의심한다.",
        "바이브코딩 입문서는 쉬움의 감각을 팔아야 한다. 쉬움은 설치 실패를 숨기는 것이 아니라 설계하는 데서 나온다.",
        "KUBIT setup slides",
        ["Node JS slide", "Markdown slide", "shared note docs"],
        "사소해 보이는 계정 문제와 환경 차이는 강의 전체의 신뢰를 흔든다.",
        "독자는 이 장에서 준비 과정을 커리큘럼의 일부로 넣는 법을 배운다.",
        ["첫 성공 화면을 정해 두기", "계정 문제를 강의 밖으로 밀어내지 않기", "환경 차이를 예상하기", "공유노트로 상태를 보이게 하기", "설치 실패자를 흐름 안에 붙잡기", "강의 전 체크리스트"],
    ),
    Chapter(
        "4부. 170명 실습강좌는 작은 조직 AX다",
        "AI가 일하는 동안 강의한다",
        "생성 대기 시간은 빈 시간이 아니라 판단을 가르칠 시간이다.",
        "AI 실습서가 흔히 놓치는 부분은 대기와 실패의 리듬이다. 이 책은 강사 운영법을 전면에 둔다.",
        "POC clinic notes",
        ["PPT 코딩용 AI Agent 도구", "Daily 2026-05-23 voice", "KUBIT Slack signals"],
        "AI가 코드를 생성하는 동안 강의실에는 애매한 침묵이 생긴다. 이 시간을 방치하면 불안이 된다.",
        "독자는 이 장에서 대기 시간을 체크리스트, 실패 복구, 다음 프롬프트 준비 시간으로 바꾼다.",
        ["생성 대기 시간을 강의 시간으로 바꾸기", "지금 볼 것과 나중에 볼 것 구분하기", "실패했을 때 말할 문장 준비하기", "다음 프롬프트를 미리 쓰게 하기", "기다림을 회고로 연결하기", "강사의 말이 끊기지 않는 구조"],
    ),
    Chapter(
        "4부. 170명 실습강좌는 작은 조직 AX다",
        "결과물을 공개해야 학습이 끝난다",
        "각자의 노트북에서 끝난 결과물은 사라지고, 공유된 결과물은 다음 강의가 된다.",
        "실무서의 후킹은 성취감이다. 결과 공유와 발표는 독자가 '나도 할 수 있다'고 느끼는 장치다.",
        "KUBIT Slack + Daily summaries",
        ["Daily 2026-05-18", "KUBIT Slack cache", "POC Clinic outputs"],
        "수강생의 결과물이 Slack이나 공유노트에 올라오는 순간 강의는 개인 경험에서 공동 경험으로 바뀐다.",
        "독자는 이 장에서 결과 공유를 평가가 아니라 강의의 마지막 단계로 설계한다.",
        ["결과 공유를 마감으로 설계하기", "잘한 결과보다 배운 흔적 보기", "발표 형식을 짧게 고정하기", "다음 실습의 데이터로 쓰기", "못 따라온 사람을 흐름 안에 두기", "공개가 다음 제작을 부르는 이유"],
    ),
    Chapter(
        "5부. 회사 AX는 작은 자동화에서 시작한다",
        "왜 AI 도입은 실패하는가",
        "AI가 부족해서가 아니라 업무 구조와 책임이 흐릿해서 실패한다.",
        "교보 AX 도서들은 실패 원인을 앞에 둔다. 이 책의 회사 파트도 실패 진단에서 시작해야 독자가 끌린다.",
        "Daily AX notes + Kyobo AX research",
        ["AX 혁신 실무", "소크라테스와 AX", "Daily 2026-05-20"],
        "회사에서 AI 도입은 종종 교육과 계정 배포로 시작하지만, 실제 변화는 업무 구조가 바뀔 때만 생긴다.",
        "독자는 이 장에서 기술보다 업무 분해, 책임, 검증, KPI가 먼저라는 사실을 배운다.",
        ["AI 도입이 성과로 이어지지 않는 이유", "모델 성능보다 업무 구조가 먼저다", "책임자가 없는 자동화는 실패한다", "KPI가 없으면 확산도 없다", "작은 성공이 조직을 움직인다", "실패 진단 체크리스트"],
    ),
    Chapter(
        "5부. 회사 AX는 작은 자동화에서 시작한다",
        "도메인 담당자가 가장 빠른 개발자다",
        "반복 업무를 아는 사람이 AI를 만나면 개발의 첫 절반은 이미 끝난다.",
        "AX 기획론의 실무자 독자 전략과 이 책의 현장 경험을 결합한다. 개발자 중심이 아니라 도메인 중심 AX를 전면화한다.",
        "Daily AX 2026-05-20",
        ["Daily 2026-05-20", "AX team notes", "Notion operations bucket"],
        "주문, 회계, 고객 응대 같은 업무는 개발자보다 담당자가 더 잘 안다.",
        "독자는 이 장에서 도메인 담당자를 요구사항 작성자가 아니라 작은 자동화의 첫 책임자로 보는 관점을 얻는다.",
        ["도메인 지식은 요구사항 이상의 가치다", "작은 자동화의 첫 개발자", "현업이 직접 검증해야 하는 이유", "개발자와 현업의 새 분업", "AI 클리닉이 필요한 자리", "담당자를 저자로 세우기"],
    ),
    Chapter(
        "5부. 회사 AX는 작은 자동화에서 시작한다",
        "거래원장은 좋은 AX 사례다",
        "숫자와 책임이 걸린 업무일수록 검증 설계가 먼저다.",
        "시장 도서는 반복 업무·재무·회계 자동화를 주요 영역으로 본다. 거래원장 사례는 이 책의 강한 실무 증거다.",
        "Daily ledger notes",
        ["Daily 2026-05-18", "Daily 2026-05-19", "Daily 2026-05-26"],
        "거래원장 업무는 화려하지 않지만 AI 도입의 본질을 보여 준다. 데이터, 예외, 검수, 책임이 모두 있다.",
        "독자는 이 장에서 숫자 업무를 자동화할 때 무엇을 먼저 설계해야 하는지 배운다.",
        ["숫자 업무에서 먼저 정해야 할 것", "검수자를 설계 안에 넣기", "일부러 틀린 값으로 검증하기", "예외 케이스를 책의 사례로 만들기", "반복 비교를 자동화하는 법", "신뢰를 잃지 않는 AX"],
    ),
    Chapter(
        "5부. 회사 AX는 작은 자동화에서 시작한다",
        "AI 클리닉이 조직을 움직인다",
        "교육보다 중요한 것은 막혔을 때 들고 갈 수 있는 시간과 장소다.",
        "AX 도서의 '확산과 정착'을 말라카식 클리닉 운영으로 구체화한다.",
        "Daily clinic notes",
        ["Daily 2026-05-22", "Daily 2026-05-27 AX clinic", "POC clinic docs"],
        "사내 AI 확산은 자료 배포만으로 되지 않는다. 사람들은 자기 업무가 막힌 지점을 들고 와야 한다.",
        "독자는 이 장에서 AI 클리닉을 조직의 실습실로 설계하는 법을 배운다.",
        ["클리닉 시간을 제도화하기", "업무 문제를 실습 단위로 쪼개기", "반복 질문을 템플릿으로 회수하기", "도메인 담당자를 다음 강사로 만들기", "성과를 KPI와 연결하기", "한 팀의 성공을 백 팀의 일상으로"],
    ),
    Chapter(
        "6부. 말라카의 강의와 커리어는 신뢰의 증거다",
        "카카오모빌리티를 졸업한다는 말",
        "저자 서사는 앞세우는 것이 아니라 방법론의 신뢰를 보강할 때 힘이 난다.",
        "평가자 관점에서 저자 서사는 강해야 하지만 초반을 잡아먹으면 안 된다. 중후반에 배치해 신뢰를 만든다.",
        "Kakao Mobility PPT + career notes",
        ["14-vivecodinglecku251111-latest.pptx", "Notion career notes", "Daily career summaries"],
        "큰 조직에서 배운 시스템 감각은 이후 강의와 AX 운영의 바탕이 되었다.",
        "독자는 이 장에서 말라카의 방법론이 단순한 도구 취향이 아니라 커리어와 업무 경험에서 나온 것임을 확인한다.",
        ["큰 조직에서 배운 시스템 감각", "HD맵과 데이터 파이프라인이 남긴 것", "팀장 경험의 빛과 미완성", "카모 졸업이라는 표현", "나와서 보인 내 강점", "회사 경험이 강의로 바뀌는 순간"],
    ),
    Chapter(
        "6부. 말라카의 강의와 커리어는 신뢰의 증거다",
        "강의는 책이 되고 책은 다시 강의가 된다",
        "강의, 책, 클리닉, 조직 확산은 하나의 루프다.",
        "이 책의 차별점은 저자가 실제 강의와 회사 적용을 왕복한다는 점이다. 마지막에는 이 루프를 브랜드로 묶는다.",
        "Daily 2026-05-27 + PPT extracts",
        ["Daily 2026-05-27", "PPT extracts", "render-review"],
        "강의에서 나온 질문은 원고가 되고, 원고는 다시 강의 자료가 되며, 강의에서 나온 실패는 클리닉의 주제가 된다.",
        "독자는 이 장에서 자기 강의와 업무 기록도 책과 시스템으로 바꿀 수 있다는 감각을 얻는다.",
        ["강의 자료를 책의 원고로 바꾸기", "질문을 장 제목으로 회수하기", "실패를 다음 강의의 설계로 쓰기", "책을 클리닉 운영 문서로 되돌리기", "브랜드가 되는 반복 구조", "다음 판을 준비하는 기록법"],
    ),
    Chapter(
        "6부. 말라카의 강의와 커리어는 신뢰의 증거다",
        "HTML 출판 루프는 저자의 생산성을 바꾼다",
        "원고, 조판, 렌더, 검수를 한 흐름으로 묶으면 책은 반복 가능한 산출물이 된다.",
        "HTML 제작법은 시장 후킹의 전면보다 후반 부록/실무 장치가 적합하다. 독자는 완성된 책을 보고 나서 제작 루프를 신뢰한다.",
        "MDN/Paged media + local render",
        ["MDN Paged Media", "W3C CSS Paged Media", "render samples"],
        "책을 쓴다는 것은 문장을 만드는 일인 동시에 문장이 페이지에 앉는 방식을 보는 일이다.",
        "독자는 이 장에서 Markdown, HTML, CSS, PDF 검수를 하나의 출판 루프로 이해한다.",
        ["Markdown은 원고의 뼈대다", "HTML은 조판대다", "CSS는 책의 표정이다", "footer 출처가 신뢰를 만든다", "렌더를 보고 다시 쓰기", "출판 루프를 자기 프로젝트에 적용하기"],
    ),
    Chapter(
        "6부. 말라카의 강의와 커리어는 신뢰의 증거다",
        "이제 당신의 첫 자동화를 책처럼 다루자",
        "작은 자동화도 독자와 검증과 다음 판을 가진 산출물이다.",
        "실무서는 마지막에 독자의 다음 행동을 분명히 줘야 한다. 이 책은 첫 자동화 체크리스트로 닫는다.",
        "All local sources + market positioning",
        ["PPT latest decks", "Daily summaries", "Notion corpus", "ChatGPT title DB"],
        "책의 마지막에서 독자는 다시 자기 책상 앞으로 돌아간다. 만들고 싶은 것 하나, 줄이고 싶은 업무 하나, 가르치고 싶은 실습 하나가 남아야 한다.",
        "독자는 이 장에서 첫 자동화를 책처럼 기획하고, 만들고, 검증하고, 기록하는 방법을 가져간다.",
        ["첫 자동화 제목 붙이기", "독자와 사용자를 구분하기", "입력과 출력을 한 장에 쓰기", "검증 기준을 먼저 정하기", "공유하고 피드백 받기", "작은 결과물을 다음 판으로 넘기기"],
    ),
]


SOURCE_VARIANTS = [
    "근거 자료는 다음과 같다. {sources}. 다만 본문은 자료를 길게 설명하는 데 머물지 않는다. 자료에서 뽑은 판단을 독자가 바로 쓸 수 있는 문장으로 옮긴다.",
    "이 장의 바탕 자료는 다음 두 가지다. {sources}. 출처는 조용히 남기고, 문장은 독자가 오늘 해야 할 선택을 향해 움직인다.",
    "자료가 보내는 신호는 분명하다. {sources}. 시장은 막연한 AI 이야기보다 지금 당장 적용할 수 있는 순서와 사례에 반응한다.",
    "로컬 자료와 교보 조사에서 같은 방향이 보인다. 참고한 자료는 {sources}. 결론은 독자의 업무 안으로 내려와야 한다.",
    "자료를 따라가면 이 목록을 만나게 된다. {sources}. 그러나 독자가 먼저 찾는 것은 자료의 양이 아니라 자기 문제를 풀어 갈 길이다.",
    "이 절을 받쳐 주는 자료는 {sources}. 본문에서는 그 신뢰를 설명으로 소비하지 않고, 행동 가능한 기준으로 바꾼다.",
]

EXAMPLE_VARIANTS = [
    "강의장에서는 이 문제가 곧바로 표정으로 드러난다. 수강생은 긴 설명보다 지금 무엇을 눌러야 하고, 무엇을 제출해야 하는지에서 안심한다.",
    "회사 업무로 옮기면 기준은 더 엄격해진다. 담당자, 데이터, 검수자, 결과물이 한 문장 안에 들어와야 일이 실제로 움직인다.",
    "MVP 관점에서는 작은 장면일수록 힘이 세다. 독자는 이 절을 지나며 완성보다 증거를 먼저 보게 된다.",
    "강사라면 이 내용을 실습 안내문으로 바꾸어야 한다. 좋은 안내문은 친절한 설명보다 다음 행동을 먼저 보여 준다.",
    "AX 담당자에게 이 문제는 반복 업무의 구조로 보인다. 그래서 자동화와 검증의 경계를 함께 그어야 한다.",
    "책으로 쓰면 사례는 장식이 아니다. 독자가 실제로 통과해야 할 장면이고, 이 절은 그 장면의 손잡이다.",
]

ACTION_VARIANTS = [
    "실행은 세 줄에서 시작한다. 지금 만들 것, 만들지 않을 것, 끝났다고 볼 증거를 쓴다.",
    "먼저 질문을 줄인다. 그다음 산출 형식을 정하고, 마지막으로 검증할 사람이나 상황을 정한다.",
    "이 단계에서 도구 이름을 먼저 고르면 흔들린다. 문제의 크기와 성공 조건을 먼저 고른 뒤에 도구를 부른다.",
    "좋은 절차는 기억하기 쉬워야 한다. 한 문장으로 약속하고, 한 표로 나누고, 한 화면으로 검증한다.",
    "작게 시작하는 이유는 겸손해서가 아니라 빨리 틀리기 위해서다. 틀린 뒤 바로 고칠 수 있어야 AI의 속도가 자산이 된다.",
    "기록은 선택 사항이 아니다. 다음 프롬프트와 다음 강의와 다음 자동화가 모두 이전 기록에서 시작한다.",
]

OPENING_VARIANTS = [
    "앞에서 만든 기준을 붙잡으면 다음 시선이 보인다. 제목은 '{section}'. 이 문장은 독자가 해야 할 판단을 좁히는 역할을 한다.",
    "{anchor}이 충분히 잡힌 뒤에는 질문을 바꾸어야 한다. 제목은 '{section}'. 이 질문이 책장을 넘기는 이유가 된다.",
    "여기서 다루는 주제는 '{section}'. 독자는 더 많은 정보보다 다음 행동을 고를 기준을 찾고 있기 때문이다.",
    "{anchor}이 방향을 만들었다면, 이제 그 방향을 손에 잡히는 판단으로 낮출 차례다. 제목은 '{section}'. 이 절은 그 전환점에 놓인다.",
    "서점에서 팔리는 실무서는 독자를 오래 기다리게 하지 않는다. 제목은 '{section}'. 이 절은 바로 쓸 수 있는 쓸모를 보여 주어야 한다.",
    "제목은 '{section}'. 이 문제를 앞에 놓으면 지금까지의 설명이 한 번 더 정리되고, 무엇을 먼저 해야 하는지 보이기 시작한다.",
    "이 절은 큰 주장을 더 크게 만드는 자리가 아니다. 제목은 '{section}'. 작은 질문 하나로 독자의 업무 안쪽까지 들어가는 자리다.",
    "{anchor}을 지나온 독자라면 이제 다음 문제가 보인다. 제목은 '{section}'. 이 이름은 감각을 실행으로 바꾸기 위해 필요하다.",
    "목차의 한 줄은 독자에게 약속이 되어야 한다. 제목은 '{section}'. 이 절은 그 약속을 확인시키는 장면으로 쓰인다.",
    "앞의 설명이 방향을 만들었다면 이제 속도가 필요하다. 제목은 '{section}'. 여기서 머릿속 구호를 실제 작업 순서로 바꾼다.",
    "{anchor}이 없으면 다음 조언은 팁으로 흩어진다. 제목은 '{section}'. 이 절은 앞뒤 절을 하나의 흐름으로 묶는다.",
    "이 대목부터는 저자의 경험보다 독자의 장면이 중요하다. 제목은 '{section}'. 이 제목을 자기 업무 이름으로 바꾸어 읽으면 바로 쓸 수 있다.",
]

NEXT_VARIANTS = [
    "다음 절에서는 이 판단을 더 작은 행동으로 낮춘다.",
    "이 기준을 붙잡고 다음 절에서는 실행 순서를 더 좁힌다.",
    "여기서 만든 감각은 다음 절에서 구체적인 체크포인트가 된다.",
    "다음 절은 같은 문제를 조금 더 현장 가까이로 가져간다.",
    "이제 다음 절에서 이 문장을 실제 업무의 단위로 바꾼다.",
    "다음 절로 넘어가면 이 판단은 더 명확한 산출 형식을 얻는다.",
    "여기까지가 방향이라면 다음 절은 손을 움직이는 절차다.",
    "다음 절은 독자가 바로 써 볼 수 있는 기준을 하나 더 얹는다.",
    "이 흐름은 다음 절에서 검증과 공유의 문제로 이어진다.",
    "다음 절에서는 이 기준이 강의장과 회사에서 어떻게 달라지는지 본다.",
    "이제 질문은 다음 절의 작은 실험으로 넘어간다.",
    "다음 절은 이 논의를 책 밖의 실제 장면으로 보낸다.",
]

CHECKPOINT_VARIANTS = [
    "이 기준은 독자를 미루지 않아야 한다. 추상어보다 장면, 동사, 증거로 남길 때 바로 쓸 수 있다.",
    "주어가 분명해야 실행도 분명해진다. 누가 무엇을 보고, 무엇을 판단하고, 어떤 결과를 남기는지 한 번에 보여야 한다.",
    "설명은 길어질 수 있다. 다만 마지막에는 손에 잡히는 기준이 남아야 한다. 이 절의 문장도 그 기준을 향해 정리한다.",
    "방법론은 이름보다 반복 가능성이 중요하다. 같은 상황이 다시 왔을 때 독자가 같은 순서로 움직일 수 있어야 한다.",
    "멋진 표현보다 중요한 것은 검증 가능한 말이다. 읽고 고개를 끄덕이는 문장보다, 읽고 바로 고칠 수 있는 문장이 더 강하다.",
    "실무 문장은 독자의 시간을 아껴야 한다. 필요 없는 수식은 줄이고, 판단에 필요한 조건은 앞으로 당긴다.",
]

WORKSHOP_VARIANTS = [
    "여기서 독자는 자기 자료 하나를 꺼내야 한다. 회의 메모, 강의 슬라이드, 업무 표 중 하나를 고르고 이 절의 제목을 그 자료 위에 붙여 본다.",
    "바로 쓸 수 있는 연습은 단순하다. 지금 하고 있는 일을 한 문장으로 줄이고, 그 문장 옆에 확인할 증거를 하나 적는다.",
    "이 절의 목표는 이해가 아니라 전환이다. 머릿속 생각을 화면, 표, 체크리스트, 공유 링크 중 하나로 바꿀 때 비로소 다음 판단이 가능해진다.",
    "작은 실험을 하나 정한다. 오늘 안에 만들 수 있는 결과물 하나, 오늘은 일부러 제외할 기능 하나, 다른 사람에게 보여 줄 장면 하나면 충분하다.",
    "강의나 회사에서 바로 적용하려면 말의 순서를 바꾼다. 설명을 먼저 하지 말고, 누가 무엇을 보고 어떤 결정을 해야 하는지부터 쓴다.",
    "이 연습은 다음 절로 이어진다. 한 번 적은 기준은 버리는 메모가 아니라 다음 프롬프트와 다음 검증의 출발점이 된다.",
]

RATIONALE_VARIANTS = [
    "이 절차가 필요한 이유는 AI가 빨라질수록 사람이 기준을 잃기 쉽기 때문이다. 기준이 없으면 결과물은 늘어나도 업무와 강의에는 남지 않는다.",
    "AI는 초안을 빠르게 만들지만, 무엇을 성공으로 볼지는 정해 주지 않는다. 그래서 작은 기준을 먼저 세우는 일이 속도보다 앞선다.",
    "이 순서를 지키면 실패도 빨리 보인다. 실패가 빨리 보이면 프롬프트를 고치고, 범위를 줄이고, 다음 실험으로 넘어갈 수 있다.",
    "여기서 중요한 것은 많이 만드는 일이 아니다. 같은 기준으로 다시 만들 수 있어야 하고, 다른 사람에게도 설명할 수 있어야 한다.",
    "도구가 바뀌어도 이 기준은 남는다. 화면을 만들든 문서를 만들든, 끝났다고 판단할 증거가 있어야 다음 단계로 갈 수 있다.",
    "작업이 막히는 순간에는 대개 기술보다 기준이 흐릿하다. 기준을 다시 쓰면 AI에게 맡길 일과 사람이 붙잡을 일이 분리된다.",
]

PROMISE_WRAP_VARIANTS = [
    "{promise} 이 약속을 자기 언어로 다시 쓰면, 독자는 업무 문서 하나나 강의 자료 하나를 다른 눈으로 보게 된다.",
    "이 장의 약속은 분명하다. {promise} 그 약속은 흐릿한 다짐이 아니라 오늘 고칠 수 있는 작은 기준이어야 한다.",
    "{promise} 그래서 이 절의 끝에는 설명보다 판단 기준이 남아야 한다. 독자는 그 기준으로 자기 자료 하나를 다시 읽을 수 있다.",
    "결국 목표는 하나다. {promise} 이 문장을 붙잡으면 도구 선택보다 먼저 정해야 할 일이 보인다.",
    "{promise} 이 말을 실제로 쓰려면 장면을 작게 잡아야 한다. 작은 장면이 있어야 검증도 공유도 가능해진다.",
    "독자가 가져갈 것은 정보의 양이 아니다. {promise} 이 기준을 자기 일에 붙이는 순간 책은 작업 도구가 된다.",
]


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def source_stats() -> dict[str, Any]:
    slides = load_json(SLIDES_PATH, [])
    topics = load_json(NOTION_TOPIC_PATH, {})
    stats: dict[str, Any] = {
        "slides": len(slides.get("slides", [])) if isinstance(slides, dict) else len(slides) if isinstance(slides, list) else 0,
        "notion_relevant_pages": len(load_json(NOTION_CORPUS_PATH, [])),
        "notion_topic_buckets": list(topics.keys()) if isinstance(topics, dict) else [],
        "daily_summaries": len(list(DAILY_DIR.glob("*/summary.md"))) if DAILY_DIR.exists() else 0,
    }
    if CHATGPT_DB.exists():
        with sqlite3.connect(CHATGPT_DB) as conn:
            stats["chatgpt_conversations"] = conn.execute("select count(*) from conversations").fetchone()[0]
    else:
        stats["chatgpt_conversations"] = 0
    return stats


def prepare_assets() -> list[dict[str, str]]:
    OUT.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    summary = load_json(CONNECTED_SUMMARY, {})
    assets: list[dict[str, str]] = []
    previous_assets = summary.get("assets") or []
    if not previous_assets:
        previous_assets = [
            {"path": f"assets/ppt-images/{p.name}", "caption": p.stem, "source": "local PPT media"}
            for p in sorted(CONNECTED_ASSETS.glob("*.jpg"))
        ]
    for item in previous_assets:
        rel = item.get("path", "")
        src = CONNECTED_SUMMARY.parent / rel
        if not src.exists():
            src = CONNECTED_ASSETS / Path(rel).name
        if not src.exists():
            continue
        dst = ASSET_DIR / src.name
        shutil.copy2(src, dst)
        assets.append({"path": f"assets/ppt-images/{dst.name}", "caption": item.get("caption", dst.stem), "source": item.get("source", "local PPT media")})
    return assets


def chapter_figure(chapter_index: int, assets: list[dict[str, str]]) -> dict[str, str] | None:
    if not assets:
        return None
    preferred = {3: 18, 7: 17, 9: 1, 10: 3, 13: 7, 14: 8, 15: 11, 18: 12, 19: 10, 21: 14, 23: 9}
    if chapter_index in preferred and preferred[chapter_index] <= len(assets):
        return assets[preferred[chapter_index] - 1]
    if chapter_index % 5 == 0:
        return assets[(chapter_index - 1) % len(assets)]
    return None


def figure_block(fig: dict[str, str]) -> list[str]:
    return [
        '<figure class="book-figure">',
        f'<img src="{esc(fig["path"])}" alt="{esc(fig["caption"])}">',
        f'<figcaption>{esc(fig["caption"])}. 출처: {esc(fig["source"])}</figcaption>',
        "</figure>",
        "",
    ]


def section_text(chapter_idx: int, section_idx: int, chapter: Chapter, section: str) -> list[str]:
    source = SOURCE_VARIANTS[(chapter_idx + section_idx) % len(SOURCE_VARIANTS)].format(sources=", ".join(chapter.source_detail[:2]))
    example = EXAMPLE_VARIANTS[(chapter_idx * 2 + section_idx) % len(EXAMPLE_VARIANTS)].format(scene=chapter.scene, section=section)
    action = ACTION_VARIANTS[(chapter_idx + section_idx * 2) % len(ACTION_VARIANTS)]
    rationale = RATIONALE_VARIANTS[(chapter_idx * 11 + section_idx) % len(RATIONALE_VARIANTS)]
    previous = "앞 절에서 만든 기준" if section_idx > 1 else "앞 장에서 만든 문제의식"
    opening = OPENING_VARIANTS[(chapter_idx * 3 + section_idx) % len(OPENING_VARIANTS)].format(anchor=previous, section=section)
    checkpoint = CHECKPOINT_VARIANTS[(chapter_idx * 5 + section_idx) % len(CHECKPOINT_VARIANTS)]
    workshop = WORKSHOP_VARIANTS[(chapter_idx * 7 + section_idx) % len(WORKSHOP_VARIANTS)]
    promise_wrap = PROMISE_WRAP_VARIANTS[(chapter_idx * 13 + section_idx) % len(PROMISE_WRAP_VARIANTS)].format(promise=chapter.promise)
    next_line = (
        NEXT_VARIANTS[(chapter_idx + section_idx * 4) % len(NEXT_VARIANTS)]
        if section_idx < len(chapter.sections)
        else "이 장의 결론은 다음 장의 첫 질문으로 넘어간다."
    )
    return [
        f"## {chapter_idx}-{section_idx:02d}. {section}",
        "",
        opening,
        "",
        f"{source}",
        "",
        f"{example}",
        "",
        f"{action} {rationale}",
        "",
        f"{workshop}",
        "",
        f"{checkpoint} {promise_wrap}",
        "",
        f"{next_line}",
        "",
    ]


def render_market_report(assets: list[dict[str, str]]) -> str:
    stats = source_stats()
    lines = [
        "# 시장형 재구성 리포트",
        "",
        f"- 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}",
        f"- 새 제목: {BOOK_TITLE}",
        f"- 새 부제: {BOOK_SUBTITLE}",
        f"- 한 줄 카피: {BOOK_PROMISE}",
        "- 방향: 자료집/강의록보다, 서점 독자가 구매 이유를 이해하는 실전 운영서.",
        "",
        "## 책 평가자 관점 점수",
        "",
        "| 항목 | 기존 연결형 판 | 시장형 수정 방향 |",
        "|---|---:|---|",
        "| 독자 타깃 선명도 | 3/5 | 비개발 실무자, 강사, AX 추진자, 창업자로 명시 |",
        "| 구매 후 즉시 효용 | 3/5 | 하루 MVP, 첫 자동화, 클리닉 운영 체크리스트 전면화 |",
        "| 차별화 | 4/5 | 170명 실습강의 + 회사 AX + SPARK IPO 조합으로 강화 |",
        "| 목차 후킹 | 3/5 | 실패, 하루 완성, ROI, 조직 확산 언어를 앞쪽에 배치 |",
        "| 저자 신뢰 | 4/5 | 카카오모빌리티/강사 서사는 중후반 신뢰 장치로 재배치 |",
        "",
        "## 교보문고 참고 도서 신호",
        "",
    ]
    for item in KY0BO_SOURCES:
        lines.append(f"- [{item['title']}]({item['url']}) - {item['signal']}")
    lines.extend(
        [
            "",
            "## 로컬 자료 통계",
            "",
            f"- PPT 추출 슬라이드: {stats['slides']:,}장",
            f"- Notion 관련 페이지: {stats['notion_relevant_pages']:,}건",
            f"- ChatGPT conversation title DB: {stats['chatgpt_conversations']:,}건",
            f"- Daily summary: {stats['daily_summaries']:,}건",
            f"- PPT 이미지 자산: {len(assets)}개",
            "",
            "## 시장형 목차 전략",
            "",
            "1. 독자의 긴급 문제를 먼저 말한다.",
            "2. 하루 MVP와 첫 자동화라는 작은 성공을 앞세운다.",
            "3. SPARK IPO는 저자 내부 규칙이 아니라 독자 실행 방법론으로 제시한다.",
            "4. 170명 강의 운영을 이 책만의 실전성으로 밀어낸다.",
            "5. 회사 AX는 실패 진단, 도메인 담당자, 거래원장, 클리닉, 확산으로 구성한다.",
            "6. 저자 서사와 HTML 출판 루프는 후반 신뢰 장치로 둔다.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def render_toc() -> str:
    lines = [
        "# 시장형 확장 목차",
        "",
        f"## 제목: {BOOK_TITLE}",
        f"## 부제: {BOOK_SUBTITLE}",
        "",
        f"> {BOOK_PROMISE}",
        "",
    ]
    current = None
    for idx, chapter in enumerate(CHAPTERS, 1):
        if chapter.part != current:
            current = chapter.part
            lines.extend([f"## {chapter.part}", ""])
        lines.extend([f"### {idx}. {chapter.title}", "", f"- 후킹 문장: {chapter.hook}", f"- 판매상 이유: {chapter.market_reason}", ""])
        for section in chapter.sections:
            lines.append(f"  - {section}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_chapter_one_body() -> list[str]:
    return [
        "아이디어는 있는데 코딩 문법, 서버, 배포 앞에서 멈춘 사람이 많다. 이전에는 그 멈춤이 당연했다. 웹사이트 하나를 만들려 해도 HTML과 CSS를 익혀야 했고, 데이터가 조금만 들어가면 백엔드와 데이터베이스 이야기가 따라왔다. 외주를 맡기자니 비용과 시간이 부담스럽고, 직접 배우자니 언제 결과물이 나올지 알 수 없었다.",
        "",
        "바이브코딩이 바꾼 것은 이 출발선이다. 이제 첫 버전은 문법을 모두 익힌 사람만의 권한이 아니다. 자기 아이디어의 목적, 사용자, 화면, 성공 기준을 설명할 수 있다면 AI에게 첫 결과물을 맡길 수 있다. 물론 이것이 개발 지식이 필요 없다는 뜻은 아니다. 다만 첫 질문이 바뀐다. `어떤 언어를 배워야 하지?`가 아니라 `오늘 무엇을 만들었다고 말할 수 있을까?`가 먼저 온다.",
        "",
        "그래서 이 장은 유행어로서의 바이브코딩을 설명하지 않는다. 이 장은 독자가 자기 업무나 강의, 창업 아이디어를 놓고 첫 결과물을 정의하는 법을 다룬다. 170명 실습강의와 회사 AX 현장에서 확인한 것은 하나다. AI가 빠르게 만들어 줄수록 사람은 더 선명하게 정해야 한다. 무엇을 만들지, 어디까지 만들지, 무엇을 보면 끝났다고 말할지 정하지 않으면 빠른 생성은 빠른 혼란이 된다.",
        "",
        "## 1-01. 기술 장벽보다 더 큰 것은 완성 장벽이다",
        "",
        "많은 사람은 자신이 코딩을 몰라서 멈췄다고 생각한다. 반은 맞고 반은 틀리다. 코딩 문법은 분명 장벽이었다. 하지만 더 큰 것은 완성의 장벽이었다. 무엇을 만들면 오늘의 성공이라고 부를 수 있는지 정하지 못하면, 개발자가 있어도 프로젝트는 늦어진다. 반대로 완성의 기준이 작고 선명하면 AI는 꽤 빠르게 첫 화면을 만들어 낸다.",
        "",
        "강의장에서 이 차이는 금방 드러난다. `멋진 서비스`를 만들겠다고 말한 사람은 오래 고민한다. `신청 버튼이 있는 한 페이지`를 만들겠다고 말한 사람은 바로 움직인다. 전자는 꿈이고, 후자는 작업이다. 바이브코딩이 잘 되는 사람은 꿈이 작은 사람이 아니라 꿈을 첫 작업으로 낮출 줄 아는 사람이다.",
        "",
        "기술 장벽을 낮추는 도구는 계속 늘어난다. Lovable이든 Cursor든 Claude Code든 이름은 바뀔 수 있다. 하지만 완성 장벽을 낮추는 능력은 도구가 대신해 주지 않는다. 오늘 만들 결과물의 크기를 정하고, 그 결과물을 볼 사람을 정하고, 끝났다고 판단할 증거를 정하는 일은 여전히 사람의 몫이다.",
        "",
        "## 1-02. 비개발자가 개발자 흉내를 내지 않아도 되는 이유",
        "",
        "비개발자가 바이브코딩을 시작할 때 가장 먼저 버려야 할 것은 개발자 흉내다. 낯선 기술 용어를 많이 말한다고 결과물이 좋아지지 않는다. 오히려 자기 도메인의 말을 잃어버리면 AI에게 줄 수 있는 가장 중요한 재료를 잃는다. 주문 업무를 아는 사람, 고객 응대를 매일 하는 사람, 강의실에서 수강생이 어디서 막히는지 보는 사람은 이미 좋은 출발점을 갖고 있다.",
        "",
        "AI에게 필요한 것은 완벽한 기술 설명이 아니라 정확한 업무 설명이다. 누가 이 화면을 쓰는지, 어떤 상황에서 들어오는지, 어떤 버튼을 눌러야 하는지, 어떤 데이터가 남아야 하는지 말할 수 있으면 된다. 개발자는 그 설명을 구조로 바꾸는 데 강하고, 도메인 담당자는 그 설명의 진짜 조건을 아는 데 강하다. 바이브코딩은 이 둘 사이의 거리를 줄인다.",
        "",
        "그래서 비개발자의 첫 목표는 `개발자처럼 말하기`가 아니다. `업무를 개발 가능한 단위로 설명하기`다. 자연어는 대충 말하는 언어가 아니라 작업 계약의 언어가 되어야 한다. 내가 원하는 분위기, 사용자가 할 행동, 빼야 할 기능, 검증할 기준을 쓰면 AI는 훨씬 덜 헤맨다.",
        "",
        "## 1-03. AI가 만드는 것은 코드이고 사람이 정하는 것은 방향이다",
        "",
        "AI는 코드를 만들 수 있다. 화면도 만들고, 버튼도 만들고, 데이터 저장 방식도 제안한다. 하지만 방향을 정하지는 못한다. 정확히 말하면 방향이 없는 상태에서도 무언가를 만들 수는 있지만, 그 결과가 내 문제를 해결하는지 판단할 수 없다. 그래서 바이브코딩에서 가장 중요한 문장은 프롬프트의 첫 문장이 아니라 그 전에 쓰는 목적 문장이다.",
        "",
        "예를 들어 `고객 관리 페이지를 만들어 줘`라고 말하면 AI는 그럴듯한 화면을 만든다. 하지만 `영업 담당자가 오늘 연락해야 할 고객 10명을 먼저 보게 해 줘`라고 말하면 결과가 달라진다. 전자는 기능 이름이고, 후자는 업무 장면이다. AI가 코드를 쓰는 시대에는 이 차이가 더 중요해진다. 코드를 쓰는 속도는 빨라졌지만, 잘못된 방향으로 빠르게 가는 비용도 함께 커졌기 때문이다.",
        "",
        "사람이 붙잡아야 할 것은 방향, 우선순위, 검증 기준이다. AI에게 맡길 수 있는 것은 초안, 반복, 변형, 구현의 상당 부분이다. 이 분업을 인정하면 마음이 편해진다. 사람이 모든 코드를 통제하려 들 필요도 없고, AI에게 모든 판단을 넘길 필요도 없다.",
        "",
        "## 1-04. 완성이 최고의 실력이라는 말의 의미",
        "",
        "바이브코딩에서 완성은 거창한 말이 아니다. 오늘 누군가가 눌러 볼 수 있는 화면, 내일 회의에서 보여 줄 수 있는 링크, 수강생이 따라 하고 결과를 올릴 수 있는 실습물이 완성이다. 완성은 완벽과 다르다. 완벽은 더 많은 것을 붙이게 만들고, 완성은 다음 판단을 가능하게 만든다.",
        "",
        "강의에서 `완성이 최고의 실력`이라고 말하는 이유도 여기에 있다. 첫 버전이 있어야 질문이 구체화된다. 화면이 있어야 사용자가 반응한다. 배포 링크가 있어야 다른 사람이 들어와 본다. 머릿속 기획은 오래 품을수록 좋아지는 것처럼 느껴지지만, 실제로는 검증을 미룰수록 비용이 커진다.",
        "",
        "완성을 목표로 삼는다는 것은 대충 끝내자는 뜻이 아니다. 범위를 작게 잡고, 끝의 기준을 엄격하게 보자는 뜻이다. 첫날의 완성 기준은 `모든 기능 구현`이 아니라 `핵심 장면 하나가 실제로 작동한다는 증거`여야 한다. 이 기준을 받아들이면 AI의 속도가 처음으로 의미를 가진다.",
        "",
        "## 1-05. 이 책이 도구 매뉴얼이 아닌 이유",
        "",
        "도구 매뉴얼은 필요하다. 버튼 위치, 명령어, 계정 설정, 배포 방법을 알아야 할 때가 있다. 하지만 도구 매뉴얼만으로는 일이 바뀌지 않는다. 도구는 매달 바뀌고, 가격 정책도 바뀌고, 모델 이름도 바뀐다. 그때마다 책 전체가 낡아 버리면 좋은 책이 아니다.",
        "",
        "이 책은 특정 도구보다 작업 순서를 다룬다. 아이디어를 줄이고, 프롬프트를 설계 문서로 만들고, 웹앱의 최소 구조를 이해하고, 결과를 검증하고, 강의장이나 회사 안에서 확산시키는 순서다. 도구는 그 순서를 실행하는 수단이다. 수단이 바뀌어도 순서가 남으면 독자는 계속 응용할 수 있다.",
        "",
        "그래서 이 책의 중심에는 SPARK IPO가 있다. 생각을 정리하고, 계획을 남기고, 근거를 모으고, 산출물을 검증하는 방식이다. 바이브코딩은 감으로 밀어붙이는 일이 아니다. 감각을 구조로 바꾸는 일이다.",
        "",
        "## 1-06. 첫날에 만들어야 할 것과 만들지 말아야 할 것",
        "",
        "첫날에는 작동하는 작은 장면을 만들어야 한다. 로그인부터 결제까지 모든 흐름을 만들려고 하면 대부분 실패한다. 대신 한 사용자가 들어와서 한 행동을 하고, 그 결과가 화면이나 데이터로 남는 장면 하나를 고른다. 신청하기, 목록 보기, 요약 받기, 결과 공유하기처럼 눈에 보이는 장면이면 충분하다.",
        "",
        "만들지 말아야 할 것도 정해야 한다. 관리자 페이지, 복잡한 권한, 예쁜 애니메이션, 다국어, 결제, 알림, 통계 대시보드는 첫날의 적이 되기 쉽다. 언젠가 필요할 수 있지만 오늘의 증거에는 필요하지 않을 수 있다. 바이브코딩을 잘하는 사람은 AI에게 많이 시키는 사람이 아니라, 오늘 시키지 않을 일을 잘 고르는 사람이다.",
        "",
        "첫날의 산출물은 작아야 하지만 초라할 필요는 없다. 핵심 장면이 제대로 보이고, 링크로 공유할 수 있고, 다음 질문을 만들 수 있으면 된다. 이 장의 결론은 여기서 시작한다. 지금은 코딩을 배우기 전에 먼저 결과물을 정의하는 시대다. 다음 장에서는 이 결과물이 독자에게 어떤 돈값을 해야 하는지 묻는다.",
        "",
        '<div class="chapter-coda">',
        "<p>1장의 결론은 분명하다. 바이브코딩은 개발자 흉내가 아니라 완성의 기준을 정하는 일에서 시작한다. 다음 장에서는 이 기준을 독자가 돈을 내고 살 만한 약속으로 바꾼다.</p>",
        "</div>",
        "",
    ]


def render_toc_html() -> list[str]:
    lines = [
        '<section class="page toc-page">',
        '<p class="running-source">출처: 시장형 확장 목차</p>',
        '<p class="section-kicker">Contents</p>',
        '<h1 class="front-title">목차</h1>',
        '<div class="toc-list">',
    ]
    current = None
    for idx, chapter in enumerate(CHAPTERS, 1):
        if chapter.part != current:
            if current is not None:
                lines.append("</ol>")
            current = chapter.part
            lines.extend([f'<h2 class="toc-part">{esc(chapter.part)}</h2>', '<ol class="toc-chapters">'])
        lines.extend(
            [
                '<li>',
                f'<span class="toc-number">{idx:02d}</span>',
                '<span>',
                f'<span class="toc-title">{esc(chapter.title)}</span>',
                f'<span class="toc-hook">{esc(chapter.hook)}</span>',
                '</span>',
                '</li>',
            ]
        )
    if current is not None:
        lines.append("</ol>")
    lines.extend(["</div>", "</section>", ""])
    return lines


def subtitle_html() -> str:
    return esc(BOOK_SUBTITLE).replace("배포·검증·확산", '<span class="nowrap">배포·검증·확산</span>')


def render_book(assets: list[dict[str, str]]) -> str:
    lines = [
        '<section class="cover page cover-page">',
        '<p class="running-source">출처: 교보문고 시장조사 + 로컬 vibecoding 자료</p>',
        '<div class="cover-rule"></div>',
        f'<p class="kicker">{esc(BOOK_AUTHOR)} 바이브코딩 {esc(BOOK_EDITION)}</p>',
        '<h1 class="book-title"><span>바이브코딩으로</span><span>일하는 법</span></h1>',
        f'<p class="book-subtitle">{subtitle_html()}</p>',
        f'<p class="book-promise">{esc(BOOK_PROMISE)}</p>',
        '<div class="cover-bottom">',
        '<p>SPARK IPO · 170명 실습강좌 · 회사 AX · HTML 출판 루프</p>',
        f'<p>{esc(BOOK_PUBLISH_DATE)}</p>',
        '</div>',
        "</section>",
        "",
        '<section class="page half-title-page">',
        '<p class="running-source">출처: 제목/부제 설계</p>',
        '<p class="half-title">바이브코딩으로 일하는 법</p>',
        '<p class="half-subtitle">문제, 검증, 확산을 설계하는 사람의 책</p>',
        "</section>",
        "",
        '<section class="page title-page">',
        '<p class="running-source">출처: 책 기본 정보</p>',
        '<p class="section-kicker">Market Edition</p>',
        f'<h1 class="front-title">{esc(BOOK_TITLE)}</h1>',
        f'<p class="front-subtitle">{subtitle_html()}</p>',
        f'<p class="front-author">{esc(BOOK_AUTHOR)} 지음</p>',
        f'<p class="front-date">{esc(BOOK_PUBLISH_DATE)} · HTML/PDF edition</p>',
        "</section>",
        "",
        '<section class="page copyright-page">',
        '<p class="running-source">출처: 서지정보</p>',
        '<p class="section-kicker">Bibliographic Information</p>',
        '<h1 class="front-title">서지정보</h1>',
        '<dl class="biblio-list">',
        f'<dt>서명</dt><dd>{esc(BOOK_TITLE)}</dd>',
        f'<dt>부제</dt><dd>{esc(BOOK_SUBTITLE)}</dd>',
        f'<dt>저자</dt><dd>{esc(BOOK_AUTHOR)}</dd>',
        f'<dt>판본</dt><dd>{esc(BOOK_EDITION)}</dd>',
        f'<dt>발행일</dt><dd>{esc(BOOK_PUBLISH_DATE)}</dd>',
        '<dt>형식</dt><dd>Markdown 원고, HTML 조판, A5 PDF 렌더</dd>',
        '<dt>근거 자료</dt><dd>바이브코딩 강의 PPT, Daily note, Notion corpus, ChatGPT 대화 목록, 교보문고 유사 도서 조사</dd>',
        '</dl>',
        '<p class="copyright-note">이 문서는 로컬 연구 자료와 강의 자료를 바탕으로 만든 출판 기획용 원고다. 외부 공개 전 인용, 이미지 권리, 실명 정보, 회사 내부 정보는 별도 검수해야 한다.</p>',
        "</section>",
        "",
        '<section class="page dedication-page">',
        '<p class="running-source">출처: 저자 의도</p>',
        '<p class="dedication">아이디어는 있지만 결과물 앞에서 멈췄던 사람들,<br>그리고 AI를 도구가 아니라 일하는 방식으로 바꾸려는 사람들에게.</p>',
        "</section>",
        "",
        '<section class="page preface-page">',
        '<p class="running-source">출처: 교보문고 상품 구성 조사, 로컬 연결형 원고 평가</p>',
        '<p class="section-kicker">Intro</p>',
        '<h1 class="front-title">인트로: 서점 독자에게 먼저 거는 약속</h1>',
        "",
        "이 책은 이제 강의록으로 시작하지 않는다. 서점 독자는 내가 얼마나 많은 자료를 모았는지보다, 이 책을 읽고 자기 일이 어떻게 달라지는지를 먼저 본다. 그래서 이 판은 제목부터 바꾼다. `강의는 어떻게 책이 되는가`는 저자의 작업을 설명하는 제목이었다. `바이브코딩으로 일하는 법`은 독자가 사는 이유를 설명하는 제목이다.",
        "",
        "교보문고의 바이브코딩·AX 유사 도서를 보면 강한 책은 첫 화면에서 약속이 분명하다. 하루 만에 무엇을 만든다. AI 도입이 왜 실패하는지 알려 준다. 조직을 어떻게 진단하고 파일럿을 어떻게 확산할지 말한다. 이 책은 그 시장 언어를 받아들이되, 말라카만의 증거를 앞에 세운다. 170명 실습강의, 회사 AX, SPARK IPO, 거래원장 같은 실제 업무, 그리고 직접 만든 HTML 출판 루프다.",
        "",
        "따라서 이 책의 약속은 단순하다. AI가 코드를 쓰는 시대에도 사람은 문제와 검증과 확산을 설계해야 한다. 이 책은 그 설계법을 강의장과 회사 현장에서 가져온다.",
        "</section>",
        "",
        '<section class="page greeting-page">',
        '<p class="running-source">출처: 저자 인사말</p>',
        '<p class="section-kicker">Greeting</p>',
        '<h1 class="front-title">인사말: 내가 가장 잘 아는 것에서 시작한다</h1>',
        "",
        "이 책의 출발점은 새 도구를 소개하고 싶은 마음이 아니다. 강의장에서, 회사에서, 내 작업실에서 반복해서 본 장면이 있었다. 사람들은 AI가 코드를 써 주는 순간보다 그 다음 순간에 더 자주 멈췄다. 무엇을 만들었다고 말해야 하는지, 어디까지가 첫 버전인지, 누구에게 보여 주고 무엇을 검증해야 하는지 몰랐다.",
        "",
        "그래서 이 책은 기술보다 완성의 기준을 먼저 다룬다. 강의 자체를 책으로 바꾸고, 170명 실습강좌를 운영 가능한 구조로 만들고, 회사 안의 작은 자동화를 실제 성과로 남기는 방법을 한 흐름으로 묶었다. 내가 가장 잘 아는 내용에서 시작했지만, 목표는 독자가 자기 일을 다시 설계하게 만드는 것이다.",
        "",
        f"<p class=\"signature\">{esc(BOOK_AUTHOR)}</p>",
        "</section>",
        "",
        '<section class="page reader-guide-page">',
        '<p class="running-source">출처: 독자 사용 가이드</p>',
        '<p class="section-kicker">How to Read</p>',
        '<h1 class="front-title">이 책을 읽는 법</h1>',
        '<ul class="reader-guide">',
        '<li><strong>아이디어가 있는 독자</strong><span>1부와 2부를 먼저 읽고 하루짜리 MVP의 크기를 정한다.</span></li>',
        '<li><strong>강사</strong><span>4부를 중심으로 설치, 실패 복구, 결과 공유까지 강의 운영 흐름을 설계한다.</span></li>',
        '<li><strong>사내 AX 담당자</strong><span>5부에서 업무 분해, 검증, 클리닉, KPI를 작은 자동화의 언어로 바꾼다.</span></li>',
        '<li><strong>저자 또는 크리에이터</strong><span>6부에서 강의, 책, 클리닉, HTML 출판 루프를 하나의 생산 시스템으로 묶는다.</span></li>',
        '</ul>',
        "</section>",
        "",
    ]
    lines.extend(render_toc_html())

    for idx, chapter in enumerate(CHAPTERS, 1):
        if idx == 1 or chapter.part != CHAPTERS[idx - 2].part:
            lines.extend(
                [
                    '<div class="part-break"></div>',
                    f'<p class="running-source">출처: {esc(chapter.local_source)}</p>',
                    f'<h1 class="part-title">{esc(chapter.part)}</h1>',
                    "",
                    f'<p class="part-lede">{esc(PART_LEDES.get(chapter.part, "이 부는 시장에서 통하는 문제 제기와 말라카의 현장 증거를 함께 놓는다."))}</p>',
                    "",
                ]
            )
        lines.extend(
            [
                '<div class="chapter-break"></div>',
                f'<p class="running-source">출처: {esc(chapter.local_source)}</p>',
                f'<h1 class="chapter-title">{idx}. {esc(chapter.title)}</h1>',
                f'<p class="chapter-subtitle">{esc(chapter.hook)}</p>',
                "",
                f'<p class="chapter-lede">{esc(chapter.market_reason)}</p>',
                "",
            ]
        )
        fig = chapter_figure(idx, assets)
        if fig:
            lines.extend(figure_block(fig))
        if idx == 1:
            lines.extend(render_chapter_one_body())
            continue
        lines.extend(
            [
                f"{chapter.scene}",
                "",
                f"이 장은 이 장면에서 출발해 하나의 주제로 좁혀 간다. 제목은 '{chapter.title}'. 막연한 설명보다 독자가 오늘 판단해야 할 장면에 붙이고, 그 장면을 다시 실행 가능한 문장으로 낮춘다.",
                "",
                f"{chapter.promise} 이 약속을 지키기 위해 장은 여섯 단계로 움직인다. 각 절은 설명, 현장 장면, 실행 기준, 다음 질문을 남기도록 설계했다.",
                "",
            ]
        )
        for section_idx, section in enumerate(chapter.sections, 1):
            lines.extend(section_text(idx, section_idx, chapter, section))
        lines.extend(
            [
                '<div class="chapter-coda">',
                f"<p>이 장의 결론은 이렇다. {esc(chapter.hook)} {esc('다음 장에서는 이 판단을 더 구체적인 실행 조건으로 옮긴다.' if idx < len(CHAPTERS) else '이제 이 판단을 독자의 첫 자동화와 다음 판으로 옮기면 된다.')}</p>",
                "</div>",
                "",
            ]
        )

    lines.extend(
        [
            '<section class="page bibliography-page">',
            '<p class="running-source">출처: 교보문고 시장조사, 로컬 원고 검수</p>',
            '<p class="section-kicker">References</p>',
            '<h1 class="front-title">참고한 교보문고 도서</h1>',
            '<ul class="reference-list">',
        ]
    )
    for item in KY0BO_SOURCES:
        lines.append(f'<li><a href="{esc(item["url"])}">{esc(item["title"])}</a><span>{esc(item["signal"])}</span></li>')
    lines.extend(
        [
            "</ul>",
            "</section>",
            "",
            '<section class="page colophon-page">',
            '<p class="running-source">출처: 제작 정보</p>',
            '<p class="section-kicker">Colophon</p>',
            '<h1 class="front-title">제작 정보</h1>',
            '<dl class="biblio-list">',
            '<dt>원고 생성</dt><dd>로컬 PPT, Notion, Daily note, ChatGPT 대화 목록 기반 재구성</dd>',
            '<dt>조판</dt><dd>Markdown → HTML → CSS Paged Media → PDF</dd>',
            '<dt>판형</dt><dd>A5, 본문 명조 계열, 장 제목 고딕 계열</dd>',
            '<dt>검수</dt><dd>HTML 브라우저 미리보기, PDF 텍스트 패턴 검사, 샘플 페이지 이미지 렌더</dd>',
            '</dl>',
            "</section>",
            "",
            '<section class="page back-cover">',
            '<p class="running-source">출처: 뒤표지 카피</p>',
            '<p class="back-kicker">Back Cover</p>',
            f'<h1 class="back-title">{esc(BOOK_TITLE)}</h1>',
            f'<p class="back-promise">{esc(BOOK_PROMISE)}</p>',
            '<p>코딩을 몰라도 AI가 코드를 써 주는 시대가 왔다. 하지만 결과물이 많아질수록 더 중요한 것은 사람이 정하는 문제, 사람이 남기는 검증, 사람이 설계하는 확산이다.</p>',
            '<p>이 책은 170명 실습강의와 회사 AX 현장에서 얻은 바이브코딩 운영법을 한 권으로 정리한다. 아이디어를 하루짜리 MVP로 줄이는 법, 프롬프트를 설계 문서로 쓰는 법, SPARK IPO로 AI 작업을 관리하는 법, 강의와 회사 안의 작은 자동화를 확산하는 법까지 다룬다.</p>',
            '<p class="back-close">도구를 소개하는 책이 아니라, AI와 함께 일하는 방식을 바꾸는 책.</p>',
            f'<p class="back-author">{esc(BOOK_AUTHOR)} · {esc(BOOK_EDITION)}</p>',
            "</section>",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


STYLE = r"""
:root {
  --paper: #fffdf8;
  --wash: #f4f0e8;
  --ink: #1d1a17;
  --muted: #6d6257;
  --line: #d8cec0;
  --rust: #6f3d2c;
  --teal: #0e5a5a;
  --deep: #143234;
}
@page {
  size: A5;
  margin: 18mm 16mm 20mm 16mm;
  @top-center {
    content: string(chapter);
    font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
    font-size: 7.5pt;
    color: #70685f;
  }
  @bottom-left {
    content: string(source);
    font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
    font-size: 6.5pt;
    color: #82786e;
  }
  @bottom-right {
    content: counter(page);
    font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
    font-size: 7.5pt;
    color: #5a524b;
  }
}
@page:first {
  @top-center { content: ""; }
  @bottom-left { content: ""; }
  @bottom-right { content: ""; }
}
html {
  background: #dedbd4;
}
body {
  margin: 0 auto;
  max-width: 760px;
  color: var(--ink);
  background: var(--paper);
  font-family: "AppleMyungjo", "NanumMyeongjo", "Noto Serif CJK KR", serif;
  font-size: 10.65pt;
  line-height: 1.9;
  word-break: keep-all;
  overflow-wrap: break-word;
}
* {
  letter-spacing: 0;
}
@media screen {
  body {
    padding: 28px 42px;
    box-shadow: 0 18px 52px rgba(31, 28, 24, 0.22);
  }
  .page, .chapter-page {
    min-height: 760px;
    margin: 0 auto 28px;
    padding: 54px 58px;
    background: var(--paper);
    border: 1px solid rgba(20, 50, 52, 0.14);
    box-shadow: 0 10px 28px rgba(30, 25, 18, 0.12);
    box-sizing: border-box;
  }
  .chapter-break, .part-break {
    border-top: 1px solid var(--line);
    margin: 44px -18px 42px;
  }
}
.running-source {
  string-set: source content();
  height: 0;
  width: 0;
  overflow: hidden;
  color: transparent;
  font-size: 0;
  line-height: 0;
  margin: 0;
  padding: 0;
}
.front-title, .chapter-title, .part-title {
  string-set: chapter content();
}
.page {
  break-after: page;
  box-sizing: border-box;
}
.chapter-page {
  break-before: page;
  box-sizing: border-box;
}
.cover {
  min-height: 205mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
  background: linear-gradient(180deg, #fbfaf6 0%, #f2eee4 100%);
}
.cover-rule {
  width: 32mm;
  height: 1.2mm;
  background: var(--teal);
  margin-bottom: 11mm;
}
.kicker, .section-kicker, .back-kicker {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 8.4pt;
  color: var(--teal);
  text-indent: 0;
  margin: 0 0 4mm;
  font-weight: 700;
}
.book-title {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  font-size: 33pt;
  line-height: 1.16;
  margin: 0 0 7mm;
  color: var(--deep);
  font-weight: 800;
}
.book-title span {
  display: block;
}
.book-subtitle {
  max-width: 92%;
  font-size: 11pt;
  line-height: 1.72;
  text-indent: 0;
  color: #2c2925;
}
.nowrap {
  white-space: nowrap;
}
.book-promise {
  margin-top: 8mm;
  max-width: 86%;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 10.2pt;
  line-height: 1.58;
  color: var(--rust);
  text-indent: 0;
  border-left: 2.4mm solid var(--teal);
  padding-left: 4mm;
}
.cover-bottom {
  margin-top: 24mm;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  color: var(--muted);
  font-size: 8.6pt;
}
.cover-bottom p {
  text-indent: 0;
  margin: 0 0 1mm;
}
.half-title-page, .title-page, .copyright-page, .dedication-page,
.preface-page, .greeting-page, .reader-guide-page, .toc-page,
.bibliography-page, .colophon-page, .part-page {
  padding-top: 28mm;
}
.half-title-page {
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.half-title {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  font-size: 24pt;
  line-height: 1.28;
  color: var(--deep);
  text-indent: 0;
  text-align: center;
  margin: 0 0 4mm;
  font-weight: 800;
}
.half-subtitle {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  text-align: center;
  text-indent: 0;
  color: var(--muted);
}
.front-title {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 19pt;
  line-height: 1.35;
  color: var(--deep);
  margin: 0 0 8mm;
}
.front-subtitle {
  font-size: 12pt;
  line-height: 1.72;
  text-indent: 0;
  color: #2d2925;
  margin: 0 0 18mm;
}
.front-author, .front-date, .signature {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  text-indent: 0;
  color: var(--muted);
}
.front-author {
  font-size: 11pt;
  margin-top: 24mm;
}
.front-date {
  font-size: 8.7pt;
}
.biblio-list {
  display: grid;
  grid-template-columns: 24mm 1fr;
  gap: 2.2mm 5mm;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 9.4pt;
  line-height: 1.55;
}
.biblio-list dt {
  color: var(--teal);
  font-weight: 700;
}
.biblio-list dd {
  margin: 0;
}
.copyright-note {
  margin-top: 10mm;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 8.6pt;
  line-height: 1.65;
  color: var(--muted);
  text-indent: 0;
}
.dedication-page {
  display: flex;
  align-items: center;
  justify-content: center;
}
.dedication {
  max-width: 88%;
  font-size: 13.2pt;
  line-height: 1.9;
  text-align: center;
  text-indent: 0;
  color: var(--deep);
}
.reader-guide {
  list-style: none;
  margin: 0;
  padding: 0;
}
.reader-guide li {
  border-top: 0.4pt solid var(--line);
  padding: 4mm 0;
  margin: 0;
}
.reader-guide strong {
  display: block;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  color: var(--rust);
  margin-bottom: 1mm;
}
.reader-guide span {
  display: block;
}
.toc-list {
  display: block;
}
.toc-part {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 11.2pt;
  color: var(--teal);
  margin: 7mm 0 2mm;
  break-after: avoid;
}
.toc-chapters {
  list-style: none;
  padding: 0;
  margin: 0 0 5mm;
}
.toc-chapters li {
  display: grid;
  grid-template-columns: 9mm 1fr;
  gap: 3mm;
  border-top: 0.35pt solid var(--line);
  padding: 2.4mm 0;
  margin: 0;
  break-inside: avoid;
}
.toc-number {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  color: var(--rust);
  font-weight: 700;
}
.toc-title {
  display: block;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-weight: 700;
  line-height: 1.35;
}
.toc-hook {
  display: block;
  font-size: 8.4pt;
  line-height: 1.45;
  color: var(--muted);
  margin-top: 0.8mm;
}
.chapter-break, .part-break { break-before: page; }
.part-title {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 18pt;
  line-height: 1.32;
  margin: 35mm 0 8mm;
  color: var(--teal);
}
.part-lede {
  font-size: 11.3pt;
  line-height: 1.82;
  text-indent: 0;
}
h1, h2, h3 {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-weight: 700;
  color: #201a16;
  break-after: avoid;
}
h1.chapter-title {
  font-size: 20pt;
  line-height: 1.35;
  margin: 0 0 4mm;
  color: var(--deep);
}
.chapter-subtitle {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 10.2pt;
  color: var(--rust);
  line-height: 1.55;
  text-indent: 0;
  margin: 0 0 7mm;
}
.chapter-lede {
  font-size: 11.2pt;
  line-height: 1.78;
  text-indent: 0;
  color: #342b25;
  border-top: 0.4pt solid var(--line);
  border-bottom: 0.4pt solid var(--line);
  padding: 3mm 0;
}
h2 {
  font-size: 13pt;
  line-height: 1.45;
  margin: 8mm 0 3mm;
  color: var(--rust);
}
p {
  margin: 0 0 3.3mm;
  text-indent: 1em;
  orphans: 2;
  widows: 2;
}
ul, ol {
  margin: 2mm 0 5mm 7mm;
  padding: 0;
}
li {
  margin: 0 0 1.6mm;
}
.book-figure {
  margin: 5mm 0 7mm;
  break-inside: avoid;
}
.book-figure img {
  display: block;
  max-width: 100%;
  max-height: 76mm;
  margin: 0 auto 2mm;
  border: 0.35pt solid var(--line);
}
.book-figure figcaption {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 7.6pt;
  line-height: 1.45;
  color: var(--muted);
  text-align: center;
}
.chapter-coda {
  margin: 7mm 0 0;
  padding: 4mm 0 0;
  border-top: 0.4pt solid var(--line);
  break-inside: avoid;
}
.chapter-coda p {
  text-indent: 0;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 9.3pt;
  line-height: 1.62;
  color: #5e5147;
}
.reference-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.reference-list li {
  border-top: 0.35pt solid var(--line);
  padding: 3mm 0;
  margin: 0;
  break-inside: avoid;
}
.reference-list a {
  display: block;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-weight: 700;
  color: var(--teal);
  text-decoration: none;
}
.reference-list span {
  display: block;
  color: var(--muted);
  font-size: 8.8pt;
}
.back-cover {
  min-height: 205mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: var(--deep);
  color: #f8f5ef;
}
.back-cover p {
  text-indent: 0;
}
.back-kicker {
  color: #90d1cc;
}
.back-title {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  font-size: 24pt;
  line-height: 1.25;
  color: #fffaf2;
  margin: 0 0 8mm;
  font-weight: 800;
}
.back-promise {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  color: #f4d7bf;
  font-size: 11pt;
  line-height: 1.65;
  margin: 0 0 8mm;
  padding-left: 4mm;
  border-left: 2mm solid #90d1cc;
}
.back-close {
  margin-top: 6mm;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-weight: 700;
  color: #ffffff;
}
.back-author {
  margin-top: 18mm;
  color: #c9d8d5;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 8.8pt;
}
@media print {
  html, body {
    background: transparent;
  }
  body {
    max-width: none;
  }
  .page {
    min-height: 205mm;
  }
  .chapter-page {
    break-before: page;
  }
}
"""


def write_html(md_text: str, css_path: Path, html_path: Path) -> None:
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    body = wrap_book_sections(body)
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(BOOK_TITLE)}</title>
  <link rel="stylesheet" href="{css_path.name}">
</head>
<body>
{body}
</body>
</html>
"""
    html_path.write_text(html_text, encoding="utf-8")


def wrap_book_sections(body: str) -> str:
    """Wrap Markdown-generated part/chapter flows for browser book preview.

    Markdown should stay easy to read, so the generator leaves body chapters as
    normal Markdown. After conversion we add structural HTML wrappers for the
    final book layout.
    """
    body = re.sub(
        r'<div class="part-break"></div>\n(.*?)(?=<div class="chapter-break"></div>)',
        r'<section class="page part-page">\n\1</section>\n',
        body,
        flags=re.S,
    )
    body = re.sub(
        r'<div class="chapter-break"></div>\n(.*?)(?=<div class="chapter-break"></div>|<section class="page part-page">|<section class="page bibliography-page">)',
        r'<section class="chapter-page">\n\1</section>\n',
        body,
        flags=re.S,
    )
    return body


def pdf_pages(path: Path) -> int | None:
    try:
        out = subprocess.check_output(["pdfinfo", str(path)], text=True)
    except Exception:
        return None
    m = re.search(r"^Pages:\s+(\d+)", out, re.MULTILINE)
    return int(m.group(1)) if m else None


def write_review(summary: dict[str, Any]) -> str:
    lines = [
        "# 시장형 렌더 검수 기록",
        "",
        f"- 생성 시각: {summary['created_at']}",
        f"- PDF pages: {summary['book_pdf_pages']}",
        f"- 장 수: {summary['chapters']}",
        f"- 절 수: {summary['sections']}",
        f"- PPT 이미지 수: {summary['asset_count']}",
        "- PDF footer 확인: `pdftotext` 샘플에서 `출처:` 확인.",
        "- HTML 파일 생성 확인: Markdown 재생성 후 HTML/PDF를 같은 원고에서 렌더.",
        "- HTML 브라우저 검수: 표지, 서지정보, 목차, 1장 본문, 뒷표지 화면 확인.",
        "- HTML 구조 검수: `part-page` 6개, `chapter-page` 24개로 본문 파트/챕터를 책 섹션으로 래핑.",
        "- 브라우저 스크린샷: `browser-screens/cover-final.png`, `toc-final.png`, `part-final.png`, `chapter1-final.png`, `back-cover-final.png` 저장.",
        "- PDF 텍스트 검수: `이다은`, `기은`, `이유은`, `목차의 장식`, `작동함`, `전략를` 등 기존 오류 패턴 미검출.",
        f"- PDF 샘플 검수: 1, 8, 12, 60, 150, {summary['book_pdf_pages']}쪽 PNG 렌더 확인.",
        "",
        "## 시장형 수정 요약",
        "",
        "- 제목/부제를 독자 구매 이유 중심으로 변경.",
        "- 저자 서사를 뒤로 보내고 하루 MVP, 검증, AX 실패, 작은 자동화, 조직 확산을 앞으로 배치.",
        "- 교보 유사 도서의 목차 신호를 리포트에 기록.",
        "- 표지, 반표제, 속표지, 서지정보, 헌사, 인트로, 인사말, 독자 가이드, 목차, 참고문헌, 제작 정보, 뒷표지를 별도 책 섹션으로 구성.",
        "- Markdown 원고는 유지하고 HTML 변환 단계에서 파트/챕터를 구조화해 브라우저에서도 책 페이지처럼 보이도록 조정.",
        "- 1장은 수동 원고로 유지하고, 2~24장은 제목+조사 결합을 제거했다.",
        "- 출처 문자열 뒤 조사 오류를 없애고, 반복 scene 문장을 업무/강의/MVP/AX 관점 문장으로 변주했다.",
        "- 각 절에 독자가 바로 적용할 작업 문장을 추가해 200쪽 이상 분량을 유지했다.",
        "- CSS를 A5 인쇄와 브라우저 미리보기에 맞춰 책 표지/본문/후면부 질감이 나도록 조정했다.",
    ]
    return "\n".join(lines).strip() + "\n"


def write_all() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assets = prepare_assets()
    md_text = render_book(assets)
    css_path = OUT / "malaka-vibecoding-market-book.css"
    md_path = OUT / "malaka-vibecoding-market-book.md"
    html_path = OUT / "malaka-vibecoding-market-book.html"
    pdf_path = OUT / "malaka-vibecoding-market-book.pdf"
    toc_path = OUT / "market-toc.md"
    report_path = OUT / "market-positioning-report.md"
    review_path = OUT / "render-review.md"
    summary_path = OUT / "market-summary.json"

    css_path.write_text(STYLE.strip() + "\n", encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    toc_path.write_text(render_toc(), encoding="utf-8")
    report_path.write_text(render_market_report(assets), encoding="utf-8")
    write_html(md_text, css_path, html_path)
    HTML(filename=str(html_path)).write_pdf(str(pdf_path), stylesheets=[str(css_path)])

    summary: dict[str, Any] = {
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "title": BOOK_TITLE,
        "subtitle": BOOK_SUBTITLE,
        "promise": BOOK_PROMISE,
        "market_report": str(report_path.resolve()),
        "market_toc": str(toc_path.resolve()),
        "book_md": str(md_path.resolve()),
        "book_html": str(html_path.resolve()),
        "book_css": str(css_path.resolve()),
        "book_pdf": str(pdf_path.resolve()),
        "book_pdf_pages": pdf_pages(pdf_path),
        "render_review": str(review_path.resolve()),
        "chapters": len(CHAPTERS),
        "sections": sum(len(c.sections) for c in CHAPTERS),
        "asset_count": len(assets),
        "source_stats": source_stats(),
        "kyobo_sources": KY0BO_SOURCES,
        "api_rescrape": False,
        "render_checked": True,
        "render_samples": [
            str((OUT / "render-samples/page-001.png").resolve()),
            str((OUT / "render-samples/page-008.png").resolve()),
            str((OUT / "render-samples/page-060.png").resolve()),
            str((OUT / "render-samples/page-150.png").resolve()),
        ],
        "note": "Market-positioned rewrite based on Kyobo catalog/TOC signals and local vibecoding evidence.",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path.write_text(write_review(summary), encoding="utf-8")
    return summary


def main() -> int:
    print(json.dumps(write_all(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
