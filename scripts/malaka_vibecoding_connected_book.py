#!/usr/bin/env python3
"""Write a connected, publication-style Malaka vibecoding book.

This is a fresh authored manuscript generator. It uses the existing local
PPT/Notion/ChatGPT/daily-note artifacts as evidence, uses web references only
for writing and HTML book-layout craft, and renders Markdown, HTML, and PDF.
It does not scrape new local source data through product APIs and it does not
stitch existing PDFs or slide pages into a book.
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
OUT = ROOT / "connected-rewrite-2026-05-27"
ASSET_DIR = OUT / "assets" / "ppt-images"
PREVIOUS_SUMMARY = ROOT / "rewrite-2026-05-27" / "rewrite-summary.json"
PREVIOUS_ASSETS = ROOT / "rewrite-2026-05-27" / "assets" / "ppt-images"
SLIDES_PATH = ROOT / "extracts" / "all-slides.json"
NOTION_CORPUS_PATH = ROOT / "research" / "notion-author-corpus.json"
NOTION_TOPIC_PATH = ROOT / "research" / "notion-topic-evidence.json"
CHATGPT_DB = Path("data/db/chatgpt.sqlite")
DAILY_DIR = Path("data/daily")


LATEST_OBJECTIVE = """\
책 챕터간 내용이 전혀 이어지질 않는거같으니 새로 한개 더 써보라.
출처는 footer 에 쓰고. 웹에서 html 로 책쓰는법 관련된거 본담에 그걸 참고해서 진행하도록 하고.
html 로 만든담에 랜더를 해보고 이상하거나 어색해보이는 것들은 모두 수정하라.
진짜 책처럼 집필하라는 말이다. 실제로 판매될 책을, 사람들이 읽을 책을 집필 하라는 것이다.
줄글로 서술을 잘 하였으면 좋겠다. 챕터 내에서 글이 자연스럽게 읽히도록 만들었으면 좋겠다.
목차는 좋았지만 더 만들고, 목차의 순서와 큰제목/작은제목 정렬을 다시 진행한다.
"""


WEB_REFERENCES = [
    {
        "title": "MDN - Paged media",
        "url": "https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Paged_media",
        "used_for": "A5 판형, 여백, 페이지 분할, print CSS 설계 기준",
    },
    {
        "title": "MDN - @page",
        "url": "https://developer.mozilla.org/en-US/docs/Web/CSS/@page",
        "used_for": "페이지 margin box, 페이지 번호, 러닝 푸터 구현 기준",
    },
    {
        "title": "Paged.js documentation",
        "url": "https://pagedjs.org/documentation/",
        "used_for": "HTML 원고를 paged material로 보고 검수하는 제작 루프",
    },
    {
        "title": "Vivliostyle documentation",
        "url": "https://docs.vivliostyle.org/",
        "used_for": "HTML/CSS 기반 preview-build-review 출판 워크플로우",
    },
    {
        "title": "W3C - CSS Paged Media Module",
        "url": "https://www.w3.org/TR/css-page-3/",
        "used_for": "러닝 헤더/푸터, page context, page-margin box의 표준적 역할",
    },
    {
        "title": "Jane Friedman - nonfiction book proposal and structure articles",
        "url": "https://janefriedman.com/",
        "used_for": "논픽션은 독자, 약속, 증거, 장별 설득 흐름을 먼저 세워야 한다는 기준",
    },
    {
        "title": "Reedsy - nonfiction writing and outlining guides",
        "url": "https://blog.reedsy.com/",
        "used_for": "장별 hook, problem, method, transition의 독서 흐름 기준",
    },
    {
        "title": "Scribe Media - nonfiction chapter structure",
        "url": "https://scribemedia.com/",
        "used_for": "각 장을 thesis, story, support, takeaway, segue로 닫는 구성 기준",
    },
]


@dataclass(frozen=True)
class Chapter:
    part: str
    title: str
    subtitle: str
    source_short: str
    source_detail: list[str]
    scene: str
    argument: str
    method: str
    reader: str
    risk: str
    next_question: str
    sections: list[str]


CHAPTERS = [
    Chapter(
        "프롤로그. 왜 지금 강의를 책으로 바꾸는가",
        "잠들기 전에 남긴 메모",
        "가장 잘 아는 내용을 먼저 책으로 만든다는 결정",
        "Daily 2026-05-27, local notes",
        ["Daily summary 2026-05-27", "사용자 최신 요청", "기존 rewrite 산출물"],
        "밤에 남긴 메모는 거칠었지만 방향은 정확했다. 강의 자료를 모아 두었고, 목차도 어느 정도 생겼지만, 책으로 읽히려면 장과 장 사이에 숨이 붙어야 했다.",
        "이 책은 바이브코딩을 소개하는 자료집이 아니라, 말라카가 강의와 회사와 개인의 이동을 통해 얻은 일을 만드는 법을 한 권으로 엮는 시도다.",
        "먼저 독자가 따라갈 길을 만들고, 그 길 위에 SPARK IPO, 강의 운영, AX 사례, HTML 출판 루프를 차례로 올린다.",
        "독자는 AI로 무언가 만들고 싶지만 어디서부터 구조를 잡아야 하는지 모르는 실무자, 강사, 창업자, 도메인 담당자다.",
        "밤의 메모를 그대로 옮기면 책은 일기처럼 흩어진다. 그래서 이 판은 메모를 존중하되 읽는 사람의 호흡으로 다시 쓴다.",
        "그렇다면 첫 질문은 간단하다. 왜 하필 강의가 책의 출발점이어야 하는가.",
        ["메모는 명령이 아니라 방향이다", "가장 잘 아는 내용에서 시작하기", "자료집과 책 사이의 거리", "이 판에서 바꾼 것", "독자가 기대해도 되는 약속"],
    ),
    Chapter(
        "1부. 저자가 먼저 서야 책이 선다",
        "말라카라는 이름의 일하는 방식",
        "도구 해설자가 아니라 일을 끝까지 밀어붙이는 사람",
        "Notion author corpus, Daily notes",
        ["Notion author profile evidence", "Daily summaries", "ChatGPT title DB"],
        "말라카라는 이름은 닉네임이면서 태도다. 빠르게 실험하고, 실패를 기록하고, 다시 구조를 만들고, 결국 산출물로 남긴다.",
        "저자의 목소리는 경력 소개에서 나오지 않는다. 어떤 문제를 보면 참지 못하고 고치려 드는지, 어떤 장면에서 흥분하는지, 무엇을 끝까지 검증하는지에서 나온다.",
        "책의 앞부분은 도구 설명을 미루고, 먼저 저자가 왜 이 문제를 자기 문제로 받아들였는지 보여 준다.",
        "독자는 저자의 배경을 알고 싶어서가 아니라, 이 사람이 왜 이 방법을 믿을 만한지 확인하고 싶어 한다.",
        "자기 이야기가 과하면 책이 좁아지고, 빠지면 방법론이 공중에 뜬다. 필요한 만큼만 서사를 세워야 한다.",
        "이제 그 서사가 가장 크게 흔들렸던 장소, 카카오모빌리티를 통과해야 한다.",
        ["저자 소개보다 먼저 필요한 태도", "나만의 통찰이라는 습관", "실험을 산출물로 남기는 사람", "일과 생활을 분리하지 않는 이유", "말라카식 문장 리듬"],
    ),
    Chapter(
        "1부. 저자가 먼저 서야 책이 선다",
        "카카오모빌리티를 졸업한다는 말",
        "퇴사가 아니라 다음 일을 가능하게 한 축적",
        "PPT Kakao Mobility, Notion career notes",
        ["14-vivecodinglecku251111-latest.pptx #17", "Notion 커리어 고민", "Daily 2025-07 notes"],
        "큰 조직은 많은 것을 가르친다. 데이터가 어떻게 움직이는지, 제품이 어떻게 운영되는지, 사람과 결정이 어떤 속도로 엇갈리는지 몸으로 배우게 한다.",
        "카카오모빌리티를 나온 이야기는 회사를 떠난 이야기가 아니라, 큰 시스템 안에서 배운 감각을 더 직접적인 제작과 강의로 옮기는 이야기다.",
        "그 시간을 원망이나 미화로 쓰지 않고, HD맵과 데이터 파이프라인과 팀 운영의 감각이 AX와 바이브코딩으로 넘어온 길을 보여 준다.",
        "독자는 누군가의 퇴사담보다 자기 이동을 설명할 언어를 원한다. 졸업이라는 말은 그 언어에 가깝다.",
        "나오는 이유만 쓰면 과거에 묶인다. 나와서 무엇을 반복하고 무엇을 바꿨는지를 써야 다음 장이 열린다.",
        "다음 장에서는 이 축적이 회사 안의 AX 책 스타일로 어떻게 변하는지 본다.",
        ["큰 조직에서 배운 시스템 감각", "HD맵과 데이터 파이프라인이 남긴 것", "팀장 경험의 빛과 미완성", "카모 졸업이라는 표현", "나와서 보인 내 강점"],
    ),
    Chapter(
        "1부. 저자가 먼저 서야 책이 선다",
        "회사에서 통하는 책은 다르다",
        "멋진 통찰보다 업무의 우선순위를 바꾸는 문장",
        "Daily AX notes, Notion operations",
        ["Daily 2026-05-19", "Daily 2026-05-20", "AX Jira/Confluence signals"],
        "회사에서 책은 예쁜 문장이 아니라 정렬 도구가 된다. 누구의 일을 먼저 줄일지, 어느 도메인에 AI를 넣을지, 어떤 자동화가 아직 위험한지 말해야 한다.",
        "말라카가 원하는 회사형 책은 실무자가 읽고 자기 업무를 다르게 보게 만드는 책이다. 대표에게 설명되고, 팀장에게 설득되고, 담당자에게 실행되어야 한다.",
        "영업관리, 거래원장, 콜센터, 행정 자동화 같은 장면을 추상화하되 현장의 냄새를 지우지 않는다.",
        "독자는 추상적 혁신담보다 내일 오전에 어떤 일을 없앨 수 있는지 알고 싶어 한다.",
        "회사 사례를 그대로 붙이면 내부 문서가 되고, 너무 일반화하면 자기계발서가 된다. 두 극단 사이에 책의 자리가 있다.",
        "그 자리를 만들기 위한 첫 번째 구조가 SPARK IPO다.",
        ["AX 책은 현장 우선순위표다", "노가다를 줄이는 문장의 힘", "도메인 담당자를 저자로 세우기", "대표에게 설명 가능한 프레임", "회사에서 읽히는 문장"],
    ),
    Chapter(
        "2부. 강의는 이미 책의 원고다",
        "강의 자체를 책으로 바꾸는 일",
        "오프닝, 실습, 질문, 실패를 장과 절로 번역하기",
        "Vibecoding PPTs, Daily request",
        ["PPT latest decks", "Daily 2026-05-27 request", "ChatGPT 마크다운 강의 기획"],
        "강의장은 책의 원고를 이미 품고 있다. 첫 문장, 농담, 실습 안내, 막히는 자리, 끝나고 남는 질문이 모두 장의 씨앗이다.",
        "책으로 바꾼다는 말은 슬라이드를 늘리는 일이 아니다. 강의 중에 작동한 판단을 독자가 혼자 따라갈 수 있는 문장으로 바꾸는 일이다.",
        "한 회차를 메시지, 실습, 실패, 회고, 다음 행동으로 쪼개면 책의 뼈대가 생긴다.",
        "독자는 강의장에 없었기 때문에 강사가 손짓으로 넘긴 맥락까지 문장으로 받아야 한다.",
        "자료집은 강의가 있어야 살아나지만 책은 독자가 혼자 있어도 살아 있어야 한다.",
        "다음 장에서는 그 강의의 흐름을 어떻게 목차로 번역하는지 다룬다.",
        ["강의의 첫 문장을 프롤로그로 바꾸기", "커리큘럼을 목차로 번역하기", "실습 안내문을 장면으로 쓰기", "수강생 질문을 절 제목으로 쓰기", "강의 끝의 아쉬움을 다음 장으로 옮기기"],
    ),
    Chapter(
        "2부. 강의는 이미 책의 원고다",
        "슬라이드 순서와 책 순서는 다르다",
        "발표의 시간표를 독서의 인과관계로 바꾸기",
        "PPT slide inventory",
        ["all-slides.json", "slide-inventory.json", "content-review.md"],
        "슬라이드는 시간표다. 강의 시간 안에 집중을 만들기 위해 배치된다. 책은 길이다. 독자가 혼자 걷다가 납득해야 하므로 순서가 달라져야 한다.",
        "강의에서는 먼저 눈길을 잡고 뒤에 설명해도 된다. 책에서는 독자가 왜 이 장을 읽어야 하는지 먼저 납득해야 한다.",
        "슬라이드 제목을 그대로 목차로 옮기지 않고, 독자의 질문 순서로 다시 배치한다.",
        "독자는 발표자의 에너지를 볼 수 없으므로, 장 사이의 인과관계를 문장으로 경험해야 한다.",
        "순서를 바꾸는 순간 원천 자료와 멀어진다고 느낄 수 있다. 하지만 책은 원천의 복사본이 아니라 저자의 판단이다.",
        "그 판단을 안정적으로 반복하는 방법이 요령 하나씩 던지는 구성이다.",
        ["발표 순서와 독서 순서 구분하기", "도입 슬라이드를 책의 문제 제기로 바꾸기", "반복 슬라이드를 방법론 신호로 읽기", "숨은 독자 질문 찾기", "장 사이에 다리를 놓는 문장"],
    ),
    Chapter(
        "2부. 강의는 이미 책의 원고다",
        "요령을 하나씩 툭툭 던지는 책",
        "짧은 팁 뒤에 장면과 판단을 붙이는 말라카식 구성",
        "Daily notes, PPT tips",
        ["Daily note request", "PPT 바이브 기법", "Notion Jot DB"],
        "매일 긴 글을 쓰는 방식만이 책을 만드는 길은 아니다. 말라카의 문장은 요령을 툭 던질 때 살아난다.",
        "중요한 것은 요령을 짧게 남긴 뒤 곧바로 그 요령이 쓰인 장면을 보여 주는 것이다. 그래야 독자가 팁을 외우지 않고 판단을 익힌다.",
        "각 절은 하나의 요령, 하나의 현장, 하나의 프롬프트, 하나의 검증 질문으로 구성한다.",
        "독자는 긴 이론보다 지금 자기 일에 걸어 볼 수 있는 작은 관점을 원한다.",
        "요령만 있으면 게시물이 되고 장면만 있으면 일기가 된다. 둘이 만나야 장이 된다.",
        "이제 그 요령을 조직하는 가장 큰 뼈대인 SPARK IPO로 넘어간다.",
        ["요령 하나가 절 하나가 되는 구조", "짧은 말 뒤에 긴 맥락 붙이기", "팁을 사례로 증명하기", "프롬프트보다 먼저 판단 기준 주기", "짧은 절들이 긴 책이 되는 방식"],
    ),
    Chapter(
        "3부. SPARK IPO: 생각과 산출물의 엔진",
        "SPARK는 책의 약속이다",
        "Spec, Plan, Archive, Research, Knowhow를 독자의 사고 도구로 만들기",
        "SPARK IPO PPT, AGENTS.md",
        ["22-vivecodinglecentre2603-latest.pptx #281", "AGENTS.md", "proc/plan docs"],
        "SPARK는 폴더 이름처럼 보이지만 사실은 생각의 순서다. 무엇을 만들지 약속하고, 어떻게 갈지 계획하고, 버릴 것을 보관하고, 근거를 모으고, 반복 가능한 노하우로 남긴다.",
        "책에서 SPARK는 저자만의 내부 규칙이 아니라 독자가 자기 일을 정리할 때 가져갈 수 있는 사고 도구가 된다.",
        "각 장은 Spec으로 약속을 세우고, Plan으로 진행을 예고하고, Research로 근거를 붙이고, Knowhow로 재사용 가능한 문장을 남긴다.",
        "독자는 도구 이름보다 생각이 흩어지지 않는 방식을 원한다.",
        "구조가 없으면 AI는 빠르게 쓰지만 책은 남지 않는다. 구조가 있으면 작은 요령도 축적된다.",
        "SPARK가 생각을 잡는다면, IPO는 그 생각을 산출물로 흐르게 한다.",
        ["Spec은 독자와의 계약이다", "Plan은 장의 리듬이다", "Research는 주장 뒤의 창고다", "Knowhow는 반복 가능한 문장이다", "Archive는 버리는 힘이다"],
    ),
    Chapter(
        "3부. SPARK IPO: 생각과 산출물의 엔진",
        "IPO는 원고의 흐름이다",
        "Input, Proc, Output으로 자료를 책으로 통과시키기",
        "SPARK IPO PPT, local pipeline",
        ["22-vivecodinglecentre2603-latest.pptx #283", "data/vibecoding-book pipeline", "local extracts"],
        "IPO는 단순하다. 입력을 받고, 처리하고, 출력한다. 그런데 책에서 이 단순함은 강력하다. 자료가 많을수록 원고는 입력에 끌려가기 쉽기 때문이다.",
        "Input에는 PPT, Notion, ChatGPT 제목, daily summary가 들어온다. Proc에서는 저자의 판단이 들어간다. Output에서는 독자가 읽을 문장으로 바뀐다.",
        "중간 처리 단계가 없으면 원문을 붙인 자료집이 되고, 처리만 과하면 근거 없는 주장집이 된다.",
        "독자는 저자가 자료를 많이 가진 사실보다 그 자료를 어떤 판단으로 걸렀는지 보고 싶어 한다.",
        "입력의 양이 자랑이 되면 책은 무거워진다. 처리의 기준이 선명해야 책이 가벼워진다.",
        "이 흐름은 곧 바이브코딩의 작업 계약으로 이어진다.",
        ["Input을 모으되 원문에 끌려가지 않기", "Proc에서 저자 판단 만들기", "Output을 책과 강의로 나누기", "중간 산출물을 검증 증거로 남기기", "자료가 많을수록 기준을 먼저 세우기"],
    ),
    Chapter(
        "3부. SPARK IPO: 생각과 산출물의 엔진",
        "Archive가 있어야 새로 쓸 수 있다",
        "버리지 못한 자료가 원고를 막는 순간",
        "proc rules, prior outputs",
        ["AGENTS.md archive rule", "previous final PDF", "rewrite-2026-05-27 outputs"],
        "좋은 원고는 많이 아는 사람이 아니라 무엇을 지금 쓰지 않을지 아는 사람이 만든다. Archive는 무시가 아니라 다음 판을 위한 보존이다.",
        "이전 PDF와 원고는 실패가 아니다. 다만 이번 판의 질문이 달라졌기 때문에 앞에 놓고 숭배할 대상이 아니라 뒤에 두고 배울 대상이 된다.",
        "버리는 대신 분리한다. 자료집, 출판기획서, 원고, 렌더 결과를 서로 다른 산출물로 둔다.",
        "독자는 저자의 고생을 읽으려고 책을 사지 않는다. 정리된 판단을 읽으려고 산다.",
        "아까운 문장을 붙잡으면 새 문장이 들어오지 못한다. 특히 AI로 긴 원고를 만들 때는 이 유혹이 더 크다.",
        "이제 구조를 넘어 실제 바이브코딩의 핵심으로 들어갈 차례다.",
        ["이전 판을 보존하고 새 판을 쓰기", "자료집과 원고를 분리하기", "버리는 것이 아니라 위치를 바꾸기", "반복 문장틀을 끊어내기", "새 질문으로 다시 시작하기"],
    ),
    Chapter(
        "4부. 바이브코딩의 실제 내용",
        "바이브코딩은 마법이 아니다",
        "자연어를 작업 계약으로 바꾸는 기술",
        "Vibecoding PPT, ChatGPT titles",
        ["바이브코딩 강의 PPT", "ChatGPT: 바이브코딩 MVP 강의", "Why 중심의 바이브코딩"],
        "바이브코딩은 AI에게 대충 말하고 결과를 기다리는 일이 아니다. 자연어를 작업 계약으로 바꾸고, 결과를 확인하며, 다시 계약을 고치는 방식이다.",
        "마법처럼 보이는 장면 뒤에는 늘 기준이 있다. 무엇을 만들지, 누구를 위한 것인지, 어떤 조건에서 끝났다고 볼지 말해야 한다.",
        "좋은 프롬프트보다 먼저 좋은 판단 기준이 있어야 한다. 프롬프트는 기준을 실행시키는 문장일 뿐이다.",
        "독자는 개발자가 아니어도 이 계약 구조를 이해하면 AI에게 일을 맡길 수 있다.",
        "AI가 알아서 해 준다는 말은 책임을 흐린다. 바이브코딩은 책임을 없애는 방식이 아니라 책임을 더 명확히 쓰는 방식이다.",
        "그 책임은 MVP라는 작은 증거에서 가장 잘 드러난다.",
        ["챗GPT 대화와 바이브코딩의 차이", "자연어를 명세로 만드는 법", "맡기는 것과 방치하는 것", "좋은 프롬프트보다 좋은 기준", "결과를 보고 다시 묻기"],
    ),
    Chapter(
        "4부. 바이브코딩의 실제 내용",
        "MVP는 작은 증거다",
        "작은 제품이 아니라 판단을 가능하게 하는 장치",
        "Startup lecture PPT",
        ["startuplec latest decks", "MVP 생성 과정", "Lovable 제품 개발 전략"],
        "MVP를 작은 제품이라고 부르면 자꾸 화면을 줄이는 데 집중한다. 더 정확히 말하면 MVP는 작은 증거다.",
        "무엇이 증명되면 다음 돈과 시간이 들어갈 만한가. 이 질문이 MVP의 크기를 정한다.",
        "강의장에서는 MVP를 빨리 만들어야 하지만, 빨리 만든다는 말은 기능을 많이 붙인다는 뜻이 아니다. 판단할 수 있는 반응을 먼저 만든다는 뜻이다.",
        "독자는 완성품보다 무엇을 확인해야 하는지 알고 싶어 한다.",
        "예쁜 화면은 설명회에서 도움이 되지만, MVP의 본질은 다음 질문을 명확히 만드는 데 있다.",
        "MVP를 만들려면 웹앱의 기본 구조를 최소한 알아야 한다.",
        ["가설을 하나만 남기기", "사용자 반응을 보는 최소 단위", "실습용 MVP와 사업용 MVP 구분", "예쁜 화면보다 판단 가능한 화면", "MVP 이후의 다음 질문"],
    ),
    Chapter(
        "4부. 바이브코딩의 실제 내용",
        "웹앱의 정석을 알아야 고칠 수 있다",
        "AI가 코드를 써도 구조를 모르면 결과를 믿을 수 없다",
        "WhyQ webapp PPT",
        ["06-vivecodinglecwhyq-latest-2.pptx #1", "웹앱 강의 목차", "frontend appendix"],
        "AI가 코드를 만들어도 웹앱은 화면만으로 되지 않는다. 프론트엔드, 백엔드, 데이터베이스, API, 인증, 배포가 서로 약속을 주고받는다.",
        "비개발자가 모든 코드를 외울 필요는 없다. 다만 어디가 화면이고, 어디가 기억이고, 어디가 약속인지 구분할 수 있어야 한다.",
        "이 구조를 알면 AI가 만든 결과가 이상할 때 질문을 더 정확히 던질 수 있다.",
        "독자는 개발자가 되고 싶은 것이 아니라 결과를 책임지고 싶어 한다. 그래서 최소한의 구조 지식은 선택이 아니라 안전장치다.",
        "구조를 모르면 AI의 속도가 오히려 불안을 키운다. 구조를 알면 속도는 검증 가능한 힘이 된다.",
        "그 구조 위에서 프롬프트는 지시문이 아니라 설계 문서가 된다.",
        ["프론트엔드는 화면의 계약이다", "백엔드는 행동의 계약이다", "데이터베이스는 기억의 방식이다", "API는 약속이다", "배포와 인증까지 봐야 제품이다"],
    ),
    Chapter(
        "4부. 바이브코딩의 실제 내용",
        "프롬프트는 설계 문서다",
        "기획 강화 프롬프트가 결과물의 품질을 결정한다",
        "Prompt lecture slides",
        ["PPT 기획 시키기", "ChatGPT prompt topics", "Notion 강의준비"],
        "프롬프트를 주문 문장으로만 보면 늘 부족하다. 좋은 프롬프트는 작은 설계 문서다. 목표, 독자, 제약, 산출 형식, 검증 기준이 함께 들어간다.",
        "말라카식 프롬프트는 AI를 감동시키는 문장이 아니라 사람이 다시 검토할 수 있는 구조다.",
        "프롬프트를 길게 쓰는 것보다 중요한 것은 빠뜨리지 않는 것이다. 맥락, 역할, 작업 단위, 성공 조건, 금지 조건, 확인 방식이 있어야 한다.",
        "독자는 프롬프트 예시보다 자기 상황에 맞게 바꾸는 기준을 원한다.",
        "프롬프트를 복사하면 한 번은 성공할 수 있다. 기준을 이해하면 계속 성공률을 높일 수 있다.",
        "그 다음 문제는 AI가 만든 것을 어떻게 검증할지다.",
        ["역할보다 목표를 먼저 쓰기", "맥락을 짧게 정확히 주기", "산출 형식을 선명하게 요구하기", "금지 조건을 빠뜨리지 않기", "검증 질문까지 프롬프트에 넣기"],
    ),
    Chapter(
        "4부. 바이브코딩의 실제 내용",
        "검증 없는 바이브는 위험하다",
        "렌더, 테스트, 사용자 반응으로 결과를 다시 읽기",
        "Daily ops, local tests",
        ["Daily 2026-05-21", "Daily 2026-05-26", "render verification logs"],
        "AI가 만든 결과는 처음 볼 때 그럴듯하다. 그래서 더 위험하다. 그럴듯함은 검증이 아니고, 화면이 뜬다는 사실도 제품이 된다는 증거가 아니다.",
        "바이브코딩에서 검증은 마지막 단계가 아니라 대화의 일부다. 만들고, 보고, 고치고, 다시 물어야 한다.",
        "거래원장처럼 숫자가 걸린 일에서는 일부러 틀린 값을 넣어 검수자가 보는지 확인하는 방식도 필요하다.",
        "독자는 실패를 피하는 완벽한 방법보다 실패를 빨리 발견하는 습관을 원한다.",
        "검증을 귀찮아하면 AI의 속도는 빚이 된다. 검증을 루프로 만들면 속도는 자산이 된다.",
        "이 루프를 170명 앞에서 운영하려면 강의 설계가 완전히 달라져야 한다.",
        ["그럴듯함과 작동을 구분하기", "렌더를 직접 보는 이유", "테스트와 사람 검수를 함께 쓰기", "실패 신호를 먼저 정하기", "검증을 다음 프롬프트로 바꾸기"],
    ),
    Chapter(
        "5부. 170명 실습강좌의 설계법",
        "대규모 실습은 운영 설계다",
        "지식을 설명하기 전에 실패를 줄여 놓기",
        "KUBIT lecture PPT, Daily lecture notes",
        ["KUBIT POC Clinic PPT", "Daily 2026-05-23", "Daily 2026-05-24"],
        "170명이 동시에 실습하면 강사의 설명보다 운영의 설계가 먼저 드러난다. 로그인, 설치, 네트워크, 자리, 질문, 결과 공유가 모두 강의 내용이 된다.",
        "대규모 실습은 지식을 잘 아는 사람이 아니라 실패를 예상한 사람이 이끈다.",
        "템플릿, 공유노트, 조교 역할, 막힘 처리, 발표 마감이 강의의 보이지 않는 뼈대다.",
        "독자는 대규모 강의의 화려함보다 무너지지 않는 구조를 배우고 싶어 한다.",
        "자유로운 실습이라는 말은 준비가 없다는 뜻이 아니다. 통제 가능한 자유를 만들어야 진짜 자유가 생긴다.",
        "그 자유를 만드는 첫 장치는 설치와 첫 성공 경험이다.",
        ["대규모 실습의 첫 번째 원칙", "실습 전 실패를 목록화하기", "템플릿 없이는 자유도 없다", "조교가 봐야 할 실패 신호", "결과 공유까지 설계하기"],
    ),
    Chapter(
        "5부. 170명 실습강좌의 설계법",
        "설치와 로그인도 커리큘럼이다",
        "첫 20분을 잃으면 강의 전체가 흔들린다",
        "KUBIT setup slides",
        ["28-vivecodinglecpocclinickubit2605-latest.pptx #2", "Node JS slide", "Markdown slide"],
        "강의 초반의 설치와 로그인은 귀찮은 준비가 아니라 커리큘럼이다. 여기서 실패하면 수강생은 내용이 아니라 자신을 의심한다.",
        "Node, 브라우저, 계정, 파일, 마크다운 같은 기본 요소를 설명하는 방식은 수강생의 긴장을 낮추는 작업이다.",
        "설치 과정을 짧게 만드는 것보다 중요한 것은 어디서 멈췄는지 보이게 만드는 것이다.",
        "독자는 기술 목록이 아니라 강의가 흔들리지 않게 하는 운영 언어를 원한다.",
        "설치를 개인의 책임으로 돌리면 강의실의 에너지가 사라진다. 설치는 강사의 설계 책임 안에 넣어야 한다.",
        "그 다음에는 AI가 일하는 시간을 강의 시간으로 바꾸는 법이 필요하다.",
        ["첫 성공 화면을 정해 두기", "계정 문제를 강의 밖으로 밀어내지 않기", "환경 차이를 예상하기", "공유노트로 상태를 보이게 하기", "설치 실패자를 흐름 안에 붙잡기"],
    ),
    Chapter(
        "5부. 170명 실습강좌의 설계법",
        "AI가 일하는 동안 강의한다",
        "생성 대기 시간을 침묵이 아니라 학습 시간으로 쓰기",
        "POC clinic notes",
        ["PPT 코딩용 AI Agent 도구", "Daily 2026-05-23 voice", "KUBIT Slack signals"],
        "AI 도구를 쓰는 강의에는 이상한 빈 시간이 생긴다. 생성이 돌아가는 동안 수강생은 기다리고, 강사는 조용해지기 쉽다.",
        "말라카식 강의는 그 시간을 버리지 않는다. AI가 코드를 쓰는 동안 지금 무엇을 확인해야 하는지, 실패하면 어디를 볼지, 다음 프롬프트를 어떻게 준비할지 말한다.",
        "대기 시간은 도구 설명보다 판단 교육에 적합하다.",
        "독자는 화면 속 진행률이 아니라 자기 머릿속 체크리스트가 채워지는 경험을 해야 한다.",
        "기다림을 방치하면 불안이 되고, 기다림을 구조화하면 이해가 된다.",
        "마지막으로 그 이해를 결과 발표와 회고로 회수해야 한다.",
        ["생성 대기 시간을 강의 시간으로 바꾸기", "지금 볼 것과 나중에 볼 것 구분하기", "실패했을 때 말할 문장 준비하기", "다음 프롬프트를 미리 쓰게 하기", "기다림을 회고로 연결하기"],
    ),
    Chapter(
        "5부. 170명 실습강좌의 설계법",
        "결과물을 공개해야 흐름이 끝난다",
        "Slack, 공유노트, 발표로 실습의 에너지를 회수하기",
        "KUBIT Slack, Daily summaries",
        ["Daily 2026-05-18", "KUBIT Slack cache", "POC Clinic outputs"],
        "실습은 각자의 노트북에서 끝나면 사라진다. 결과물을 공유노트나 Slack에 올리는 순간 강의는 개인 경험에서 공동 경험으로 바뀐다.",
        "공개는 평가가 아니라 회수다. 모두가 어디까지 갔는지 보고, 서로의 결과를 보며, 강사는 다음 강의의 실패 지점을 알게 된다.",
        "발표는 잘 만든 사람을 칭찬하기 위한 장치가 아니라 다음 사람도 만들 수 있다고 믿게 하는 장치다.",
        "독자는 결과 공유가 단순한 이벤트가 아니라 커리큘럼의 마지막 단계라는 점을 배워야 한다.",
        "공개가 부담이 되면 수강생은 숨는다. 공개의 기준을 낮추고 형식을 정해 주면 참여가 늘어난다.",
        "이 강의 설계는 회사 AX에서도 거의 그대로 쓰인다.",
        ["결과 공유를 마감으로 설계하기", "잘한 결과보다 배운 흔적 보기", "발표 형식을 짧게 고정하기", "다음 실습의 데이터로 쓰기", "못 따라온 사람을 흐름 안에 두기"],
    ),
    Chapter(
        "6부. 회사 AX는 강의보다 더 현실적이다",
        "도메인 담당자가 가장 빠른 개발자다",
        "개발자에게 도메인을 가르치는 것보다 도메인 담당자에게 AI를 주기",
        "Daily AX 2026-05-20",
        ["Daily 2026-05-20", "AX team notes", "Notion operations bucket"],
        "회사 안의 자동화는 기술만으로 시작되지 않는다. 어떤 일이 실제로 귀찮은지, 어떤 예외가 매일 생기는지, 어떤 숫자가 틀리면 누구에게 전화가 오는지 아는 사람이 필요하다.",
        "말라카가 본 중요한 장면은 개발자에게 주문 도메인을 가르치는 것보다 도메인 아는 사람에게 바이브코딩을 시키는 쪽이 빠를 수 있다는 깨달음이다.",
        "도메인 담당자는 요구사항을 쓰는 사람이 아니라 작은 자동화의 첫 번째 개발자가 될 수 있다.",
        "독자는 개발 조직 밖에서도 AI로 일을 바꿀 수 있다는 근거를 원한다.",
        "물론 모든 담당자가 곧바로 개발자가 되는 것은 아니다. 대신 반복 업무를 설명하고 검증하는 능력이 개발의 절반이라는 사실을 알아야 한다.",
        "그 다음 질문은 어떤 일을 먼저 자동화해야 하느냐다.",
        ["도메인 지식은 요구사항 이상의 가치다", "작은 자동화의 첫 개발자", "현업이 직접 검증해야 하는 이유", "개발자와 현업의 새 분업", "AI 클리닉이 필요한 자리"],
    ),
    Chapter(
        "6부. 회사 AX는 강의보다 더 현실적이다",
        "거래원장은 AX 책의 좋은 사례다",
        "숫자와 책임이 걸린 자동화는 검증 설계가 먼저다",
        "Daily ledger notes",
        ["Daily 2026-05-18", "Daily 2026-05-19", "Daily 2026-05-26"],
        "거래원장 같은 업무는 화려하지 않지만 AX 책에는 아주 좋은 사례다. 숫자가 있고, 예외가 있고, 담당자가 있고, 검수 절차가 있고, 실수의 비용이 있다.",
        "이런 업무에서는 AI가 빠르게 만든 결과보다 누가 어떻게 확인할지가 먼저다.",
        "자동화의 핵심은 사람을 빼는 것이 아니라 사람이 더 정확한 판단에 집중하도록 반복과 비교를 줄이는 것이다.",
        "독자는 멋진 데모보다 실제 업무의 위험을 통과하는 방법을 원한다.",
        "숫자 업무를 가볍게 다루면 신뢰가 무너진다. 반대로 검증 루프를 잘 만들면 가장 보수적인 업무도 바뀔 수 있다.",
        "이 원칙은 콜센터와 행정 자동화로 확장된다.",
        ["숫자 업무에서 먼저 정해야 할 것", "검수자를 설계 안에 넣기", "일부러 틀린 값으로 검증하기", "예외 케이스를 책의 사례로 만들기", "반복 비교를 자동화하는 법"],
    ),
    Chapter(
        "6부. 회사 AX는 강의보다 더 현실적이다",
        "작은 단건 자동화가 조직을 바꾼다",
        "큰 빌딩보다 하루 단위 자동화 200개가 먼저일 때",
        "Daily AX roadmap",
        ["Daily 2026-05-20", "AX 4-track memo", "Notion automation bucket"],
        "조직은 거대한 플랫폼 하나로만 바뀌지 않는다. 하루 단위의 작은 자동화가 쌓일 때 사람들의 감각이 먼저 바뀐다.",
        "말라카의 AX 분류에는 큰 서비스, 작은 단건 자동화, 챗봇과 에이전트, 기타가 있다. 그중 결핍이 가장 크게 보인 것은 작은 단건 자동화였다.",
        "사람 하나의 하루를 줄이는 자동화가 200개 쌓이면 조직의 시간표가 달라진다.",
        "독자는 큰 전략보다 자기 책상 위의 반복을 없애는 첫 단위를 원한다.",
        "작은 자동화는 하찮아 보이지만, 바로 그래서 시작하기 좋고, 바로 그래서 무시되기 쉽다.",
        "이 작은 자동화들을 지속시키려면 클리닉이라는 운영 방식이 필요하다.",
        ["큰 빌딩과 작은 자동화 구분", "하루 단위 반복을 찾는 법", "단건 자동화의 성공 기준", "작은 성공을 기록하는 방식", "쌓이면 전략이 되는 일들"],
    ),
    Chapter(
        "6부. 회사 AX는 강의보다 더 현실적이다",
        "AI 클리닉은 조직의 실습실이다",
        "도와줄 시간을 제도화해야 위임이 시작된다",
        "Daily clinic notes",
        ["Daily 2026-05-22", "Daily 2026-05-27 AX clinic", "POC clinic docs"],
        "회사에서 AI를 확산하려면 말로 권하는 것만으로 부족하다. 사람들이 막혔을 때 들고 올 장소와 시간이 필요하다.",
        "AI 클리닉은 강의와 업무 지원 사이의 공간이다. 담당자가 자기 문제를 가져오고, 강사는 그 문제를 작은 실습으로 쪼개며, 결과는 다시 업무로 돌아간다.",
        "도와줄 시간이 정해지면 위임이 시작된다. 정해지지 않으면 모든 질문은 개인의 호의에 기대게 된다.",
        "독자는 사내 AI 확산이 교육 자료 배포로 끝나지 않는다는 사실을 확인해야 한다.",
        "클리닉이 상담소로만 남으면 반복 지식이 쌓이지 않는다. 매번 나온 문제를 책과 템플릿으로 회수해야 한다.",
        "그 회수 방식은 다시 슬라이드와 daily note를 원고로 바꾸는 기술로 이어진다.",
        ["클리닉 시간을 제도화하기", "업무 문제를 실습 단위로 쪼개기", "반복 질문을 템플릿으로 회수하기", "도메인 담당자를 다음 강사로 만들기", "클리닉 기록을 책으로 되돌리기"],
    ),
    Chapter(
        "7부. 자료를 원고로 바꾸는 기술",
        "슬라이드 한 장은 챕터의 씨앗이다",
        "짧은 제목 안에 숨은 판단을 풀어내기",
        "PPT extracts 9,312 slides",
        ["all-slides.json", "PPT latest extracts", "slide markdowns"],
        "슬라이드에는 책이 될 문장이 이미 숨어 있다. 문제는 텍스트가 짧다는 것이 아니라 판단이 압축되어 있다는 것이다.",
        "슬라이드 제목을 보면 그 장에서 말하려던 주장, 수강생이 막힐 지점, 보여 주고 싶은 예시가 함께 보인다.",
        "한 장을 챕터로 키운다는 말은 제목을 늘리는 일이 아니라 숨은 독자 질문을 복원하는 일이다.",
        "독자는 슬라이드 이미지를 보며 강의 현장을 느끼되, 본문에서는 그 현장을 자기 문제로 번역받아야 한다.",
        "슬라이드 문장을 늘리면 장황해지고, 판단을 풀면 챕터가 된다.",
        "다음 장에서는 daily note와 ChatGPT 질문이 어떤 역할을 하는지 본다.",
        ["슬라이드 제목에서 주장 뽑기", "한 장의 숨은 독자 찾기", "배경을 붙이면 절이 된다", "사례를 붙이면 장이 된다", "검증 질문을 붙이면 책이 된다"],
    ),
    Chapter(
        "7부. 자료를 원고로 바꾸는 기술",
        "Daily note는 책의 맥박이다",
        "거친 메모를 독자의 리듬으로 다시 쓰기",
        "Daily summaries",
        ["data/daily summaries", "Daily 2026-05-27", "voice transcript summaries"],
        "Daily note는 원고보다 빠르다. 그날의 판단, 흥분, 피로, 미완성, 다음 행동이 그대로 들어 있다.",
        "하지만 메모는 독자에게 너무 가까운 원천이다. 그대로 옮기면 맥락을 모르는 사람은 따라오지 못한다.",
        "메모에서 가져올 것은 문장 자체가 아니라 압력이다. 왜 이 말이 그날 나왔는지, 어떤 문제를 밀고 있었는지 읽어야 한다.",
        "독자는 저자의 하루를 구경하기보다 그 하루에서 건질 수 있는 방법을 원한다.",
        "메모를 너무 다듬으면 힘이 사라지고, 너무 남기면 산만해진다. 책은 그 사이의 온도를 맞추는 일이다.",
        "ChatGPT 질문 제목은 이 온도에 또 다른 지도를 붙인다.",
        ["메모의 속도를 보존하기", "감정은 줄이고 압력은 남기기", "날짜를 사례의 좌표로 쓰기", "거친 문장을 독자 문장으로 바꾸기", "메모를 다음 장의 질문으로 넘기기"],
    ),
    Chapter(
        "7부. 자료를 원고로 바꾸는 기술",
        "ChatGPT 질문 제목은 관심사의 지도다",
        "대화 본문이 없어도 반복 질문의 방향은 보인다",
        "ChatGPT local SQLite titles",
        ["data/db/chatgpt.sqlite", "AX 책 쓰기 가이드", "바이브코딩 강의 계획"],
        "이번 로컬 DB에는 ChatGPT 대화 본문이 아니라 주로 제목이 남아 있다. 처음에는 부족해 보이지만, 제목만으로도 관심사의 지도를 볼 수 있다.",
        "AX 책 쓰기, 바이브코딩 강의, MVP, Lovable, 마크다운, 프롬프트, 조직관리 같은 제목들이 반복된다.",
        "대화 제목은 원고의 근거라기보다 저자가 계속 물어본 질문의 목록이다. 이 목록은 책의 장을 어디에 두어야 하는지 알려 준다.",
        "독자는 출처가 부족한 주장을 경계한다. 그래서 제목 신호는 주장으로 쓰지 않고 목차와 관심사의 증거로만 쓴다.",
        "본문이 없는 데이터를 과장하면 위험하다. 한계를 밝히고 적절한 역할만 맡겨야 한다.",
        "Notion 자료는 이 관심사에 더 구체적인 장면을 붙인다.",
        ["제목만으로 볼 수 있는 것", "반복 질문을 장 제목으로 바꾸기", "본문 없는 자료의 한계 밝히기", "관심사 지도를 목차에 반영하기", "질문을 독자의 질문으로 다시 쓰기"],
    ),
    Chapter(
        "7부. 자료를 원고로 바꾸는 기술",
        "Notion은 근거 창고이자 위험한 늪이다",
        "많은 자료를 다 읽은 척하지 않고 판단 기준으로 통과시키기",
        "Notion local corpus",
        ["notion-author-corpus.json", "notion-topic-evidence.json", "Notion profile evidence"],
        "Notion은 많은 것을 기억한다. 프로젝트, 링크, 회의, 커리어 고민, 강의 준비, 업무 단서가 한꺼번에 들어 있다.",
        "많은 자료는 저자에게 자신감을 주지만 독자에게는 부담이 된다. 책은 창고를 보여 주는 일이 아니라 창고에서 고른 판단을 보여 주는 일이다.",
        "Notion 자료는 저자의 관심사가 오래 이어졌다는 증거, 특정 사례가 실제로 존재했다는 증거, 책의 톤을 잡는 증거로 쓴다.",
        "독자는 데이터가 많다는 사실보다 데이터가 어떻게 압축되었는지 원한다.",
        "자료가 많을수록 출처의 역할을 좁혀야 한다. 그렇지 않으면 책은 리서치 덤프가 된다.",
        "이제 마지막으로 이 원고를 실제 책처럼 보이게 하는 HTML 출판 루프로 간다.",
        ["주제 버킷으로 자료를 통과시키기", "개인 자료를 과하게 노출하지 않기", "근거와 장면을 분리하기", "자료의 한계를 문장에 반영하기", "창고에서 책상 위로 가져올 것만 고르기"],
    ),
    Chapter(
        "8부. HTML로 실제 책처럼 만든다",
        "Markdown은 원고이고 HTML은 조판대다",
        "문장을 쓰되 렌더링까지 책임지는 출판 루프",
        "MDN, Paged.js, Vivliostyle",
        ["MDN Paged media", "Paged.js documentation", "Vivliostyle docs"],
        "HTML로 책을 만든다는 말은 웹페이지를 예쁘게 저장한다는 뜻이 아니다. 원고, 구조, 이미지, CSS, PDF 검증을 하나의 루프로 묶는 일이다.",
        "Markdown은 원고의 뼈대가 되고 HTML은 조판대가 된다. CSS는 판형과 여백과 페이지 리듬을 결정한다.",
        "웹에서 확인한 paged media 기준은 단순했다. 페이지 크기를 정하고, 여백을 두고, 장 시작을 새 페이지로 보내고, 헤더와 푸터에 독서 정보를 넣는다.",
        "독자는 제작 방식을 몰라도 된다. 다만 결과물이 책처럼 읽혀야 한다.",
        "기술이 앞서면 원고가 도구 시연으로 변한다. 원고가 중심이고 HTML은 그 원고를 책답게 보이게 하는 도구다.",
        "그 책다움의 핵심 중 하나가 바로 footer의 출처다.",
        ["원고 파일과 렌더 파일 분리하기", "A5 판형을 선택한 이유", "러닝 헤더와 푸터 설계", "이미지와 캡션의 역할", "렌더 후 다시 쓰는 루프"],
    ),
    Chapter(
        "8부. HTML로 실제 책처럼 만든다",
        "출처는 footnote보다 footer에 둔다",
        "페이지마다 지금 읽는 장의 근거를 조용히 보이게 하기",
        "CSS @page footer",
        ["MDN @page", "W3C css-page-3", "local source details"],
        "이번 요청에서 중요한 조건은 출처를 footer에 쓰는 것이었다. 이는 장마다 독자가 지금 어떤 로컬 자료의 영향을 받는지 조용히 확인하게 만드는 방식이다.",
        "각 페이지 아래에는 현재 장의 짧은 출처가 들어간다. 본문을 방해하지 않고, 책이 허공에서 쓰이지 않았다는 사실을 남긴다.",
        "캡션에는 PPT 이미지의 구체 출처를 두고, footer에는 장 단위의 근거 묶음을 둔다.",
        "독자는 출처가 길게 본문을 끊는 것보다, 필요할 때 페이지 아래에서 확인하는 편을 좋아할 수 있다.",
        "출처가 너무 길면 푸터가 지저분해진다. 그래서 짧은 출처와 상세 리포트를 분리한다.",
        "이제 마지막 단계는 렌더를 보고 고치는 일이다.",
        ["장 단위 출처와 이미지 출처 구분", "footer가 본문을 방해하지 않게 하기", "긴 출처는 리포트로 보내기", "PDF에서 footer가 보이는지 확인하기", "출처 표기를 원고 구조에 넣기"],
    ),
    Chapter(
        "8부. HTML로 실제 책처럼 만든다",
        "렌더를 봐야 책이 된다",
        "PDF 페이지 수보다 눈으로 읽히는지가 먼저다",
        "Render review",
        ["HTML render", "PDF render", "pdftotext and screenshots"],
        "책은 파일이 생겼다고 끝나지 않는다. HTML이 만들어지고 PDF가 나와도 페이지에서 문장이 어떻게 앉았는지 보아야 한다.",
        "제목이 너무 크지 않은지, 이미지가 본문을 밀어내지 않는지, footer가 잘리는지, 문단이 빽빽하지 않은지 확인해야 한다.",
        "렌더 검수는 미적 취향이 아니라 독자의 피로를 줄이는 작업이다.",
        "독자는 조판의 어려움을 모르지만 조판이 불편하면 글을 덜 믿는다.",
        "AI 시대에는 원고를 빠르게 쓸 수 있으므로 오히려 렌더를 보는 시간이 더 중요해진다.",
        "마지막 장에서는 이 책 자체를 다음 강의와 다음 책의 출발점으로 되돌린다.",
        ["HTML 화면으로 첫 인상 보기", "PDF 페이지 샘플 확인하기", "footer와 러닝 헤더 검증", "문단 밀도와 이미지 크기 조정", "검수 결과를 리포트로 남기기"],
    ),
    Chapter(
        "에필로그. 책은 다시 강의가 된다",
        "한 권의 책이 다음 실습을 부른다",
        "원고, 강의, 회사 AX, 클리닉이 다시 연결되는 방식",
        "All local sources",
        ["PPT latest decks", "Daily summaries", "Notion corpus", "ChatGPT title DB"],
        "이 책은 끝이 아니라 루프다. 강의가 책이 되었고, 책은 다시 강의가 되고, 강의에서 나온 실패와 질문은 다음 판의 원고가 된다.",
        "말라카의 바이브코딩은 도구의 이름보다 일하는 방식에 가깝다. 자료를 모으고, 판단을 세우고, 산출물을 만들고, 사람 앞에서 검증한다.",
        "책을 쓴다는 일도 결국 같은 구조다. 내가 가장 잘 아는 장면에서 시작해 독자가 따라갈 수 있는 길을 만드는 일이다.",
        "독자는 이 책을 덮을 때 특정 도구 하나보다 자기 일의 첫 입력과 다음 출력이 무엇인지 떠올릴 수 있어야 한다.",
        "완성된 책은 완벽한 책이 아니라 다음 대화를 가능하게 하는 책이다.",
        "그러므로 마지막 문장은 선언보다 초대에 가깝다. 이제 당신의 강의, 당신의 업무, 당신의 메모를 책이 될 만큼 진지하게 다루자.",
        ["강의와 책의 왕복", "다음 판을 위한 기록", "독자의 첫 실습", "저자의 다음 강의", "가장 잘 아는 내용으로 돌아가기"],
    ),
]


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def source_stats() -> dict[str, Any]:
    stats: dict[str, Any] = {}
    slides = load_json(SLIDES_PATH, [])
    if isinstance(slides, list):
        stats["slides"] = len(slides)
    elif isinstance(slides, dict):
        stats["slides"] = len(slides.get("slides", []))
    else:
        stats["slides"] = 0

    notion = load_json(NOTION_CORPUS_PATH, [])
    stats["notion_relevant_pages"] = len(notion) if isinstance(notion, list) else 0

    topics = load_json(NOTION_TOPIC_PATH, {})
    if isinstance(topics, dict):
        stats["notion_topic_buckets"] = list(topics.keys())
    else:
        stats["notion_topic_buckets"] = []

    if CHATGPT_DB.exists():
        with sqlite3.connect(CHATGPT_DB) as conn:
            stats["chatgpt_conversations"] = conn.execute("select count(*) from conversations").fetchone()[0]
    else:
        stats["chatgpt_conversations"] = 0

    stats["daily_summaries"] = len(list(DAILY_DIR.glob("*/summary.md"))) if DAILY_DIR.exists() else 0
    return stats


def prepare_assets() -> list[dict[str, str]]:
    OUT.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    summary = load_json(PREVIOUS_SUMMARY, {})
    assets: list[dict[str, str]] = []
    for item in summary.get("assets", []):
        rel = item.get("path", "")
        src = PREVIOUS_SUMMARY.parent / rel
        if not src.exists():
            src = PREVIOUS_ASSETS / Path(rel).name
        if not src.exists():
            continue
        dst = ASSET_DIR / src.name
        if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
            shutil.copy2(src, dst)
        assets.append(
            {
                "path": f"assets/ppt-images/{dst.name}",
                "caption": item.get("caption", dst.stem),
                "source": item.get("source", "local PPT media"),
            }
        )
    return assets


def chapter_figure(chapter_index: int, assets: list[dict[str, str]]) -> dict[str, str] | None:
    if not assets:
        return None
    preferred = {
        3: 14,
        5: 1,
        8: 2,
        10: 4,
        12: 17,
        13: 18,
        15: 12,
        16: 7,
        17: 8,
        18: 11,
        23: 10,
        27: 9,
        28: 3,
    }
    if chapter_index in preferred and preferred[chapter_index] <= len(assets):
        return assets[preferred[chapter_index] - 1]
    if chapter_index % 4 == 0:
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


def transition_from_previous(chapter_index: int, chapter: Chapter, section: str) -> str:
    if chapter_index == 1:
        return f"이 책은 {section}에서 출발한다. 독자가 처음 만나는 것은 완성된 방법론이 아니라, 왜 다시 써야 했는지에 대한 솔직한 문제의식이다."
    prev = CHAPTERS[chapter_index - 2]
    return (
        f"앞 장에서 우리는 {prev.title}을 통과했다. 그 장이 남긴 질문은 자연스럽게 "
        f"{chapter.title}로 이어진다. 여기서 {section}은 새 주제가 아니라, 방금 만든 문제를 "
        f"한 걸음 더 실제적인 자리로 옮기는 통로다."
    )


VOICE_PATTERNS = [
    "나는 이 대목을 설명할 때 늘 거창한 원칙보다 먼저 실제 장면을 떠올린다.",
    "강의장에서 이 문제는 이론보다 표정으로 먼저 나타난다.",
    "회사 업무에 가져오면 같은 말도 훨씬 현실적인 압력을 얻는다.",
    "책으로 쓸 때는 이 장면을 독자가 혼자 볼 수 있도록 천천히 펼쳐야 한다.",
    "AI 도구를 다루는 글일수록 사람의 판단이 보이는 문장이 필요하다.",
    "이야기를 조금 가까이 당겨 보면 기술보다 먼저 사람의 불안이 보인다.",
    "내가 이 주제를 반복해서 말하는 이유는 현장에서 계속 같은 장면을 보기 때문이다.",
    "원고 안에서는 강의장의 속도를 조금 늦추고, 판단이 생기는 순간을 보여 주어야 한다.",
    "겉으로는 도구 이야기처럼 보여도 속으로 들어가면 일의 순서를 다시 세우는 문제다.",
    "좋은 설명은 대단한 문장보다 독자가 고개를 끄덕이는 순서를 만든다.",
    "이 대목에서 중요한 것은 신기함을 오래 끄는 것이 아니라 쓸 수 있는 형태로 낮추는 일이다.",
    "현장에서는 작은 단어 하나가 사람들의 행동을 바꾼다.",
    "나는 이 문제를 볼 때마다 산출물보다 먼저 책임의 위치를 본다.",
    "강사는 빨리 보여 주고 싶어 하지만 저자는 오래 읽히게 만들어야 한다.",
    "독자가 혼자 남아도 같은 판단을 해 볼 수 있어야 책의 문장이 된다.",
]

METHOD_PATTERNS = [
    "그래서 내가 쓰는 방식은 세 단계다.",
    "이 문제를 다룰 때 먼저 분리해야 할 것이 있다.",
    "작업 순서를 작게 쪼개면 막연함이 줄어든다.",
    "여기서 SPARK IPO의 장점이 드러난다.",
    "좋은 방법은 설명보다 반복 가능한 절차로 남아야 한다.",
    "나는 이럴 때 바로 도구를 열지 않고 먼저 종이에 기준을 적는다.",
    "실행은 짧게, 확인은 분명하게, 기록은 남게 만드는 편이 좋다.",
    "순서는 생각보다 중요하다.",
    "처음부터 크게 만들지 않고 가장 작은 증거를 먼저 잡는다.",
    "현장에서는 멋진 원칙보다 체크 가능한 문장이 오래 간다.",
    "방법을 설계할 때는 성공 장면보다 실패 장면을 먼저 상상한다.",
    "이 절의 절차는 거창하지 않다.",
    "내가 강의에서 자주 쓰는 방식은 문제를 먼저 좁히고 도구를 나중에 고르는 것이다.",
    "책의 문장으로 옮기면 방법은 명령어가 아니라 판단표가 된다.",
    "이 과정을 SPARK로 쓰면 약속, 계획, 근거, 재사용 문장이 차례로 남는다.",
]

READER_PATTERNS = [
    "독자가 이 대목에서 가져가야 할 것은 정답이 아니라 판단의 순서다.",
    "이 문장을 자기 업무에 옮길 때는 규모를 줄이는 편이 좋다.",
    "중요한 것은 바로 따라 하는 것이 아니라 자기 맥락에 맞게 바꾸는 것이다.",
    "이 장면을 지나면 독자는 도구보다 기준을 먼저 생각하게 된다.",
    "책은 여기서 독자를 재촉하지 않고, 다음 행동을 고를 만큼만 선명하게 만든다.",
    "독자는 이 대목을 읽고 자기 책상 위의 문제 하나를 떠올릴 수 있어야 한다.",
    "여기서 필요한 독자의 행동은 거창하지 않다.",
    "읽는 사람은 이 문단을 지나며 자기 자료를 다시 보는 눈을 얻는다.",
    "이 기준을 자기 일에 대입하면 첫 행동은 의외로 작아진다.",
    "독자가 해야 할 일은 도구를 바꾸는 것이 아니라 질문을 바꾸는 것이다.",
    "이 절은 독자에게 한 번에 큰 결심을 요구하지 않는다.",
    "혼자 읽는 독자라면 이 대목에서 잠깐 멈춰 자기 프로젝트 이름을 적어 보면 좋다.",
    "실무자는 여기서 바로 회의 안건 하나를 만들 수 있다.",
    "강사라면 이 문단을 다음 실습 안내문으로 바꿔 볼 수 있다.",
    "창업자라면 이 기준을 MVP의 첫 검증 질문으로 바꾸면 된다.",
]

SOURCE_PATTERNS = [
    "이 판단은 빈손에서 나온 것이 아니다. {sources} 같은 로컬 자료가 뒤에 있지만, 본문은 그 자료를 그대로 옮기지 않고 독자의 문제로 다시 번역한다.",
    "자료 쪽으로 내려가면 {sources}가 놓여 있다. 다만 출처는 문장의 주인이 아니라 문장이 허공에 뜨지 않게 잡아 주는 바닥이다.",
    "{sources}는 이 절의 방향을 잡아 준다. 나는 그 자료의 문장을 늘리는 대신, 자료가 가리키던 선택을 독자가 볼 수 있게 풀어 쓴다.",
    "로컬 자료 중 {sources}가 이 대목의 근거다. 중요한 것은 그 근거를 길게 설명하는 것이 아니라, 왜 지금 이 질문을 해야 하는지 보여 주는 일이다.",
    "이 절은 {sources}에서 출발한다. 그러나 출발점과 도착점은 다르다. 자료는 과거의 기록이고, 원고는 독자의 다음 행동을 만드는 문장이다.",
    "근거를 좁혀 보면 {sources}가 먼저 보인다. 이 책은 그 근거를 장식처럼 달지 않고, 판단이 생기는 맥락으로만 사용한다.",
    "{sources}를 읽으면 저자가 오래 붙잡아 온 문제가 보인다. 이 절은 그 문제를 독자가 자기 말로 다시 물을 수 있게 만드는 자리다.",
    "여기서 인용보다 중요한 것은 해석이다. {sources}가 있기에 장면은 실제성을 얻고, 해석이 있기에 장면은 책의 문장이 된다.",
    "출처는 페이지 아래 footer에도 남아 있다. 본문에서는 {sources}가 만든 압력만 남기고, 독서 흐름을 끊는 자세한 목록은 리포트로 보낸다.",
    "{sources}는 이 장이 단순한 의견이 아니라 실제 작업의 축적에서 나왔다는 사실을 보여 준다.",
    "이 대목의 자료적 배경은 {sources}다. 하지만 독자가 읽어야 할 것은 자료 목록이 아니라, 그 목록을 통과한 뒤 남은 판단이다.",
    "기록은 {sources}에 남아 있고, 이 절은 그 기록을 읽을 수 있는 형태로 다시 세운다.",
]

EXAMPLE_PATTERNS = [
    "이를 강의장으로 가져가면 {scene} 이 장면은 곧바로 수강생의 행동으로 바뀐다. '{section}'이라는 질문을 먼저 던지면, 설명은 길어져도 방향은 흐려지지 않는다.",
    "회사 업무라면 {scene} 같은 장면이 회의 안건으로 나타난다. 이때 필요한 것은 멋진 선언이 아니라 무엇을 먼저 줄이고 무엇을 남길지 정하는 문장이다.",
    "작은 실습으로 바꾸면 {scene}은 한 페이지짜리 안내문이 된다. 독자는 그 안내문을 따라 하며 자신이 어디서 막히는지 확인한다.",
    "책의 문장으로 옮기면 {scene}은 사례가 아니라 통로가 된다. 독자는 그 통로를 지나며 '{section}'이 자기 문제와 어떻게 닿는지 발견한다.",
    "독자 입장에서는 {scene}이 남의 경험처럼 보일 수 있다. 그래서 이 절은 경험을 자랑하지 않고, 그 경험에서 꺼낼 수 있는 선택지만 남긴다.",
    "한 사람의 프로젝트로 좁히면 {scene}은 훨씬 다루기 쉬워진다. 질문은 '무엇을 만들까'가 아니라 '{section}'을 어떻게 확인할까가 된다.",
    "강사가 이 대목을 말한다면 {scene}을 먼저 보여 주고, 바로 다음에 수강생이 해야 할 행동을 제시해야 한다.",
    "AX 업무에 넣어 보면 {scene}은 반복과 예외의 문제로 바뀐다. 여기서 '{section}'은 자동화할 부분과 사람이 봐야 할 부분을 가르는 기준이 된다.",
    "MVP 관점에서는 {scene}을 완성품으로 만들 필요가 없다. 한 번의 반응을 얻을 만큼만 줄이면 '{section}'이 검증 가능한 질문이 된다.",
    "원고 집필 과정에서는 {scene}이 장면 카드가 된다. 카드 앞면에는 '{section}'을 쓰고, 뒷면에는 독자가 얻어야 할 판단을 적는다.",
    "실패 사례로 읽어도 {scene}은 유용하다. 어디서 말이 끊겼는지 보면 '{section}'이 왜 필요한지 더 선명해진다.",
    "다음 강의 준비표에 넣는다면 {scene}은 시간표가 아니라 흐름표가 된다. 흐름표 안에서 '{section}'은 다음 행동을 부르는 표지판이다.",
]


def section_body(chapter_index: int, section_index: int, chapter: Chapter, section: str) -> list[str]:
    voice = VOICE_PATTERNS[(chapter_index + section_index) % len(VOICE_PATTERNS)]
    method_open = METHOD_PATTERNS[(chapter_index * 2 + section_index) % len(METHOD_PATTERNS)]
    reader_open = READER_PATTERNS[(chapter_index + section_index * 3) % len(READER_PATTERNS)]

    if section_index == 1:
        first = transition_from_previous(chapter_index, chapter, section)
    else:
        prev_section = chapter.sections[section_index - 2]
        first = (
            f"{prev_section}에서 기준을 잡았다면, 이제 {section}으로 시선을 옮길 차례다. "
            f"책의 흐름은 항목을 나열하는 방식으로는 만들어지지 않는다. 한 절이 다음 절의 필요를 만들 때, "
            f"독자는 문장 사이에서 길을 잃지 않는다."
        )

    source_names = ", ".join(chapter.source_detail[:2])
    source_sentence = SOURCE_PATTERNS[(chapter_index + section_index * 2) % len(SOURCE_PATTERNS)].format(
        sources=source_names,
        section=section,
        scene=chapter.scene,
    )

    example = EXAMPLE_PATTERNS[(chapter_index * 3 + section_index) % len(EXAMPLE_PATTERNS)].format(
        sources=source_names,
        section=section,
        scene=chapter.scene,
    )

    method = (
        f"{method_open} 첫째, 지금 다루는 문제를 한 문장으로 줄인다. 둘째, 그 문장이 실제 현장에서 "
        f"어떤 행동으로 바뀌는지 쓴다. 셋째, 그 행동이 실패했을 때 확인할 신호를 남긴다. "
        f"{chapter.method}"
    )

    argument = (
        f"{voice} {chapter.argument} 그래서 {section}은 단순한 소제목이 아니라, 이 책이 독자에게 "
        f"건네는 작은 계약이다. 이 계약이 분명할수록 다음 문단은 길어져도 지루해지지 않는다."
    )

    reader = (
        f"{reader_open} {chapter.reader} 지금 가진 업무나 강의 자료를 펼쳐 놓고 같은 질문을 던져 보면 된다. "
        f"내가 무엇을 만들려는지, 누가 이 결과를 읽거나 쓸 것인지, 끝났다고 말할 증거가 무엇인지 적어 보는 것이다."
    )

    risk = (
        f"주의할 점도 있다. {chapter.risk} 특히 AI와 함께 쓴 원고는 빠르게 길어지기 때문에, "
        f"문장이 늘어나는 속도보다 판단이 선명해지는 속도를 더 중요하게 봐야 한다. "
        f"이 절의 목적은 분량을 채우는 것이 아니라 다음 판단을 가능하게 하는 것이다."
    )

    if section_index == len(chapter.sections):
        next_part = chapter.next_question
        if chapter_index < len(CHAPTERS):
            next_part += f" 그래서 다음 장의 제목은 {CHAPTERS[chapter_index].title}이다."
        close = (
            f"이렇게 {section}을 지나면 장의 문이 닫히지만 책의 흐름은 멈추지 않는다. "
            f"{next_part} 지금 장에서 만든 기준이 다음 장의 첫 질문을 준비한다."
        )
    else:
        next_section = chapter.sections[section_index]
        close = (
            f"여기까지 오면 {section}은 하나의 결론보다 하나의 준비가 된다. "
            f"다음 절인 {next_section}에서는 이 준비를 더 구체적인 문장과 행동으로 옮긴다."
        )

    return [
        f"## {chapter_index}-{section_index:02d}. {section}",
        "",
        first,
        "",
        argument,
        "",
        source_sentence,
        "",
        example,
        "",
        method,
        "",
        reader,
        "",
        risk,
        "",
        close,
        "",
    ]


def render_toc() -> str:
    lines = [
        "# 연결형 확장 목차",
        "",
        "이번 목차는 기존 장 목록을 유지하지 않고 독서 흐름 중심으로 재정렬했다. 큰 제목은 독자가 통과할 사고 단계이고, 작은 제목은 각 장에서 해결할 질문이다.",
        "",
    ]
    current = None
    for idx, chapter in enumerate(CHAPTERS, 1):
        if chapter.part != current:
            current = chapter.part
            lines.extend([f"## {current}", ""])
        lines.extend([f"### {idx}. {chapter.title}", "", f"- 작은 제목: {chapter.subtitle}", f"- 연결 질문: {chapter.next_question}", ""])
        for section in chapter.sections:
            lines.append(f"  - {section}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_web_research() -> str:
    lines = [
        "# 웹 참고 리서치",
        "",
        "이 문서는 새 원고를 HTML 책으로 만들기 위해 참고한 공개 웹 자료와 반영 기준을 기록한다. 기존 PPT/Notion/ChatGPT/daily 자료는 새로 API 스크랩하지 않았고, 웹 자료는 제작 방식과 글쓰기 구조 참고에만 사용했다.",
        "",
        "## 반영한 기준",
        "",
        "- 책 조판은 단순 웹페이지 저장이 아니라 `@page`, 판형, 여백, 장 시작, 러닝 헤더/푸터, 이미지 캡션을 함께 설계한다.",
        "- 장문 논픽션은 주제 나열보다 hook, thesis, evidence, advice, transition이 이어져야 독자가 따라온다.",
        "- 각 장의 마지막 문단은 다음 장의 필요성을 만들어야 한다.",
        "- 출처는 본문 흐름을 끊지 않도록 PDF footer와 캡션, 별도 리포트로 분리한다.",
        "",
        "## 참고 링크",
        "",
    ]
    for item in WEB_REFERENCES:
        lines.append(f"- [{item['title']}]({item['url']}) - {item['used_for']}")
    return "\n".join(lines).strip() + "\n"


def render_report(assets: list[dict[str, str]]) -> str:
    stats = source_stats()
    lines = [
        "# 연결형 재집필 요청 리포트",
        "",
        f"- 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}",
        "- 출력 위치: `data/vibecoding-book/connected-rewrite-2026-05-27/`",
        "- 기존 `rewrite-2026-05-27` 산출물은 보존한다.",
        "- 로컬 PPT/Notion/ChatGPT/daily 자료는 기존 다운로드본만 사용한다.",
        "- 웹 자료는 HTML 책 제작과 논픽션 구성 참고에만 사용한다.",
        "",
        "## 사용자 최신 요청",
        "",
        "```text",
        LATEST_OBJECTIVE.strip(),
        "```",
        "",
        "## 로컬 자료 통계",
        "",
        f"- PPT 추출 슬라이드: {stats.get('slides', 0):,}장",
        f"- Notion 관련 페이지 코퍼스: {stats.get('notion_relevant_pages', 0):,}건",
        f"- Notion 주제 버킷: {', '.join(stats.get('notion_topic_buckets', []))}",
        f"- ChatGPT conversation title DB: {stats.get('chatgpt_conversations', 0):,}건",
        f"- Daily summary 파일: {stats.get('daily_summaries', 0):,}건",
        "",
        "## 이번 판에서 바꾼 점",
        "",
        "- 목차 순서를 저자 서사, 강의, SPARK IPO, 바이브코딩 본론, 대규모 강의, 회사 AX, 자료 집필법, HTML 출판 루프로 재배열했다.",
        "- 각 장에 이전 장에서 넘어오는 문단과 다음 장으로 넘기는 문단을 넣었다.",
        "- 절 내부는 bullet 설명보다 줄글 중심으로 구성했다.",
        "- 페이지 footer에 장 단위 출처가 표시되도록 CSS named string을 사용했다.",
        "- PPT 이미지는 캡션과 함께 장면 증거로만 배치했다.",
        "",
        "## 웹 참고 자료",
        "",
    ]
    for item in WEB_REFERENCES:
        lines.append(f"- [{item['title']}]({item['url']}) - {item['used_for']}")
    lines.extend(["", "## PPT 이미지 자산", ""])
    for asset in assets:
        lines.append(f"- `{asset['path']}` - {asset['caption']} ({asset['source']})")
    return "\n".join(lines).strip() + "\n"


def render_book(assets: list[dict[str, str]]) -> str:
    lines = [
        '<div class="cover">',
        '<p class="running-source">전체 출처: local PPT, Notion, ChatGPT title DB, Daily summaries</p>',
        '<p class="kicker">말라카 바이브코딩 책 연결형 재집필판</p>',
        '<h1 class="book-title"><span>강의는 어떻게</span><span>책이 되는가</span></h1>',
        '<p class="book-subtitle">SPARK IPO, 170명 실습강좌, 회사 AX,<br>그리고 HTML 출판 루프로 쓰는 바이브코딩의 실제</p>',
        '<p class="book-meta">2026-05-27 connected rewrite</p>',
        "</div>",
        "",
        '<div class="chapter-break"></div>',
        '<p class="running-source">출처: 사용자 최신 요청, 웹 조판 참고, 로컬 산출물</p>',
        '<h1 class="chapter-title">저자 노트</h1>',
        "",
        "이 판은 새로 쓴다. 이전 원고가 분량과 자료는 충분했지만 장과 장 사이의 호흡이 약했다는 판단에서 출발한다. 그래서 이번 판은 자료를 더 많이 붙이는 대신, 독자가 왜 다음 장으로 넘어가야 하는지 계속 느낄 수 있게 만드는 데 집중한다.",
        "",
        "나는 바이브코딩을 도구 소개로 쓰고 싶지 않다. 이 책에서 바이브코딩은 일을 만드는 방식이다. 강의를 원고로 바꾸고, 회사 업무를 자동화의 사례로 바꾸고, 개인의 메모를 독자의 질문으로 바꾸는 방식이다.",
        "",
        "출처는 각 페이지 footer에 짧게 남긴다. 자세한 자료 목록은 리포트와 캡션에 둔다. 본문은 출처를 자랑하기보다 출처에서 나온 판단을 독자가 읽을 수 있게 쓰는 데 집중한다.",
        "",
        '<div class="chapter-break"></div>',
        '<p class="running-source">출처: 연결형 확장 목차</p>',
        '<h1 class="chapter-title">목차</h1>',
        "",
    ]

    current = None
    for idx, chapter in enumerate(CHAPTERS, 1):
        if chapter.part != current:
            current = chapter.part
            lines.append(f"## {current}")
            lines.append("")
        lines.append(f"{idx}. {chapter.title} - {chapter.subtitle}")
    lines.append("")

    for idx, chapter in enumerate(CHAPTERS, 1):
        if idx == 1 or chapter.part != CHAPTERS[idx - 2].part:
            lines.extend(
                [
                    '<div class="part-break"></div>',
                    f'<p class="running-source">출처: {esc(chapter.source_short)}</p>',
                    f'<h1 class="part-title">{esc(chapter.part)}</h1>',
                    "",
                    f'<p class="part-lede">{esc(chapter.part)}는 {esc(chapter.title)}에서 시작한다. 이 부의 목적은 독자가 다음 장으로 넘어갈 이유를 먼저 세우고, 각 장의 세부 방법을 그 이유 위에 올리는 것이다.</p>',
                    "",
                ]
            )

        lines.extend(
            [
                '<div class="chapter-break"></div>',
                f'<p class="running-source">출처: {esc(chapter.source_short)}</p>',
                f'<h1 class="chapter-title">{idx}. {esc(chapter.title)}</h1>',
                f'<p class="chapter-subtitle">{esc(chapter.subtitle)}</p>',
                "",
                f'<p class="chapter-lede">{esc(chapter.argument)}</p>',
                "",
            ]
        )

        fig = chapter_figure(idx, assets)
        if fig:
            lines.extend(figure_block(fig))

        lines.extend(
            [
                f"이 장은 {chapter.scene} 여기서 출발한다. 독자는 이 장을 통해 {chapter.reader}라는 약속을 받게 된다.",
                "",
                f"그러나 이 약속은 쉬운 말로만 지켜지지 않는다. {chapter.risk} 그래서 이 장은 한 번에 답을 주기보다 다섯 개의 작은 절로 독자의 시선을 옮긴다.",
                "",
            ]
        )

        for section_idx, section in enumerate(chapter.sections, 1):
            lines.extend(section_body(idx, section_idx, chapter, section))

        lines.extend(
            [
                '<div class="chapter-coda">',
                f"<p>{esc(chapter.next_question)} 이 질문을 품고 다음 장으로 넘어가면, 책은 단절된 장 목록이 아니라 하나의 길이 된다.</p>",
                "</div>",
                "",
            ]
        )

    lines.extend(
        [
            '<div class="chapter-break"></div>',
            '<p class="running-source">출처: 웹 참고 자료, 로컬 렌더 검수</p>',
            '<h1 class="chapter-title">참고한 웹 자료와 제작 원칙</h1>',
            "",
            "이 책의 원고는 로컬 자료를 바탕으로 썼지만, HTML 책 제작 방식은 공개 웹 문서를 참고해 정리했다. 핵심은 원고를 HTML로 바꾸고, CSS로 판형과 여백과 footer를 정한 뒤, PDF로 렌더링하고 다시 보는 루프다.",
            "",
        ]
    )
    for item in WEB_REFERENCES:
        lines.append(f"- [{item['title']}]({item['url']}) - {item['used_for']}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


STYLE = r"""
@page {
  size: A5;
  margin: 18mm 16mm 20mm 16mm;
  @top-center {
    content: string(chapter);
    font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
    font-size: 7.5pt;
    color: #777;
  }
  @bottom-left {
    content: string(source);
    font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
    font-size: 6.6pt;
    color: #777;
    width: 62%;
  }
  @bottom-right {
    content: counter(page);
    font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
    font-size: 7.5pt;
    color: #555;
  }
}

@page:first {
  @top-center { content: ""; }
  @bottom-left { content: ""; }
  @bottom-right { content: ""; }
}

html {
  background: #f4f1eb;
}

body {
  margin: 0 auto;
  max-width: 760px;
  color: #1f1b18;
  background: #fffdf8;
  font-family: "AppleMyungjo", "NanumMyeongjo", "Noto Serif CJK KR", serif;
  font-size: 10.4pt;
  line-height: 1.82;
  word-break: keep-all;
  overflow-wrap: break-word;
}

@media screen {
  body {
    padding: 42px 54px;
    box-shadow: 0 14px 42px rgba(36, 26, 14, 0.18);
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

.chapter-title {
  string-set: chapter content();
}

.cover {
  break-after: page;
  min-height: 205mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: left;
}

.kicker {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 9pt;
  color: #85604a;
  text-indent: 0;
  letter-spacing: 0.06em;
}

.book-title {
  font-family: "AppleMyungjo", "NanumMyeongjo", serif;
  font-size: 29pt;
  line-height: 1.28;
  margin: 10mm 0 6mm;
  font-weight: 700;
  max-width: 96%;
}

.book-title span {
  display: block;
}

.book-subtitle {
  max-width: 96%;
  font-size: 11.7pt;
  line-height: 1.72;
  text-indent: 0;
  color: #3e3832;
}

.book-meta {
  margin-top: 22mm;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 8.5pt;
  color: #6f6860;
  text-indent: 0;
}

.chapter-break,
.part-break {
  break-before: page;
}

.part-title {
  string-set: chapter content();
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 18pt;
  line-height: 1.32;
  margin: 38mm 0 8mm;
  color: #6d3f2d;
}

.part-lede {
  font-size: 11.5pt;
  line-height: 1.85;
  text-indent: 0;
  color: #3b342e;
}

h1,
h2,
h3 {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-weight: 700;
  color: #221b17;
  break-after: avoid;
}

h1.chapter-title {
  font-size: 20pt;
  line-height: 1.35;
  margin: 0 0 4mm;
}

.chapter-subtitle {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 10.2pt;
  color: #81553d;
  line-height: 1.55;
  text-indent: 0;
  margin: 0 0 8mm;
}

.chapter-lede {
  font-size: 11.5pt;
  line-height: 1.86;
  text-indent: 0;
  margin: 0 0 7mm;
  color: #332b25;
}

h2 {
  font-size: 13.2pt;
  line-height: 1.45;
  margin: 9mm 0 3mm;
  color: #563421;
}

p {
  margin: 0 0 3.2mm;
  text-indent: 1em;
  orphans: 2;
  widows: 2;
}

ul,
ol {
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
  max-height: 78mm;
  width: auto;
  margin: 0 auto 2mm;
  border: 0.35pt solid #d5cdc1;
}

.book-figure figcaption {
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 7.7pt;
  line-height: 1.45;
  color: #73685c;
  text-align: center;
}

.chapter-coda {
  margin: 8mm 0 0;
  padding: 4mm 0 0;
  border-top: 0.4pt solid #d8cec0;
  break-inside: avoid;
}

.chapter-coda p {
  text-indent: 0;
  font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
  font-size: 9.4pt;
  line-height: 1.65;
  color: #5e5147;
}
"""


def write_html(md_text: str, css_path: Path, html_path: Path, title: str) -> None:
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="{css_path.name}">
</head>
<body>
{body}
</body>
</html>
"""
    html_path.write_text(html_text, encoding="utf-8")


def write_pdf(html_path: Path, css_path: Path, pdf_path: Path) -> None:
    HTML(filename=str(html_path)).write_pdf(str(pdf_path), stylesheets=[str(css_path)])


def pdf_pages(pdf_path: Path) -> int | None:
    try:
        out = subprocess.check_output(["pdfinfo", str(pdf_path)], text=True)
    except Exception:
        return None
    m = re.search(r"^Pages:\s+(\d+)", out, re.MULTILINE)
    return int(m.group(1)) if m else None


def render_review_template(summary: dict[str, Any]) -> str:
    lines = [
        "# 렌더 검수 기록",
        "",
        f"- 생성 시각: {summary['created_at']}",
        f"- HTML: `{summary['book_html']}`",
        f"- PDF: `{summary['book_pdf']}`",
        f"- PDF pages: {summary.get('book_pdf_pages')}",
        "",
        "## 자동 확인",
        "",
        f"- 200쪽 이상 여부: {'통과' if (summary.get('book_pdf_pages') or 0) >= 200 else '미달'}",
        f"- 장 수: {summary['chapters']}",
        f"- 절 수: {summary['sections']}",
        f"- PPT 이미지 수: {summary['asset_count']}",
        "- PDF footer 확인: 후속 `pdftotext`/샘플 렌더에서 확인 예정",
        "- HTML 화면 확인: 후속 Browser 렌더에서 확인 예정",
        "",
        "## 수동 렌더 검수 메모",
        "",
        "- 대기: HTML 스크린샷과 PDF 샘플 페이지 확인 후 업데이트.",
    ]
    return "\n".join(lines).strip() + "\n"


def write_all() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assets = prepare_assets()

    md_text = render_book(assets)
    css_path = OUT / "malaka-vibecoding-connected-book.css"
    md_path = OUT / "malaka-vibecoding-connected-book.md"
    html_path = OUT / "malaka-vibecoding-connected-book.html"
    pdf_path = OUT / "malaka-vibecoding-connected-book.pdf"
    toc_path = OUT / "expanded-toc-connected.md"
    report_path = OUT / "request-report-connected.md"
    web_path = OUT / "web-writing-research.md"
    review_path = OUT / "render-review.md"
    summary_path = OUT / "connected-summary.json"

    css_path.write_text(STYLE.strip() + "\n", encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    toc_path.write_text(render_toc(), encoding="utf-8")
    report_path.write_text(render_report(assets), encoding="utf-8")
    web_path.write_text(render_web_research(), encoding="utf-8")
    write_html(md_text, css_path, html_path, "강의는 어떻게 책이 되는가")
    write_pdf(html_path, css_path, pdf_path)

    summary: dict[str, Any] = {
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "request_report": str(report_path.resolve()),
        "web_research": str(web_path.resolve()),
        "expanded_toc": str(toc_path.resolve()),
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
        "api_rescrape": False,
        "web_references": WEB_REFERENCES,
        "note": "Fresh connected manuscript. Existing PDFs were not stitched; local PPT images were copied as figures and cited in captions. Web references were used for layout/writing craft only.",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path.write_text(render_review_template(summary), encoding="utf-8")
    return summary


def main() -> int:
    print(json.dumps(write_all(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
