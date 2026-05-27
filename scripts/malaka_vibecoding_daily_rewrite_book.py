#!/usr/bin/env python3
"""Create the daily-note driven Malaka vibecoding book rewrite.

The script renders authored Markdown/HTML/PDF from local evidence only. It does
not call external APIs and does not stitch existing PDFs or slide pages.
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
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from PIL import Image, ImageOps


ROOT = Path("data/vibecoding-book")
OUT = ROOT / "rewrite-2026-05-27"
ASSET_DIR = OUT / "assets" / "ppt-images"
SLIDES_PATH = ROOT / "extracts" / "all-slides.json"
NOTION_CORPUS_PATH = ROOT / "research" / "notion-author-corpus.json"
NOTION_TOPIC_PATH = ROOT / "research" / "notion-topic-evidence.json"
CHATGPT_DB = Path("data/db/chatgpt.sqlite")
DAILY_DIR = Path("data/daily")
PPT_DIR = ROOT / "source-ppts"


USER_REQUEST = """\
이런 타이틀로 소주제를 잡아보자.

“강의 자체를 책으로 바꾸는걸 먼저해야 하지 않나 — 내가 가장 잘 아는 내용” - spark ipo 관련.
“170명 실습강좌 설계하는 요령도 책에 담자” - 말라카강사 관련
“데일리보다 요령을 하나씩 툭툭 던지는 게 내 스탈 — 그걸 엮어서 책으로”. - 슬라이드에 있는정보들 챕터 한개씩 만들기.
그리고 나에대한 이야기와, 카카오모빌리티를 나오게 된 이야기.
회사에서 내가 추구하고있는 책 스타일.
강의에서 내가 다루고있는 내용들.

기존에 다운받은 ChatGPT 질문, Notion, daily note, PPT 자료를 조합하되 API로 새로 스크랩하지 않는다.
목차를 먼저 팽창시키고, 그다음 200페이지 이상 직접 쓴다.
코딩으로 기존 PDF를 엮지 말고 HTML 기반 출판 스타일로 새 책을 만든다.
PPT에 있는 그림도 가져온다.
요청사항은 리포트에 기록한다.
"""


@dataclass(frozen=True)
class Chapter:
    part: str
    title: str
    one_line: str
    evidence: list[str]
    scene: str
    method: str
    tension: str
    sections: list[str]


CHAPTERS = [
    Chapter(
        "1부. 강의가 책이 되는 순간",
        "강의 자체를 책으로 바꾸는 일",
        "내가 가장 잘 아는 내용을 책으로 바꾸려면 먼저 강의의 흐름을 목차로 번역해야 한다.",
        ["Daily note 요청", "바이브코딩 강의 자료", "ChatGPT: 마크다운 강의 기획", "ChatGPT: AX 책 쓰기 가이드"],
        "강의장은 이미 책의 원고를 품고 있다. 오프닝, 실습, 막히는 지점, 웃음이 터지는 문장, 끝난 뒤 남는 질문이 모두 장과 절의 씨앗이다.",
        "강의 한 회차를 메시지, 실습, 실패, 회고, 다음 행동으로 나누어 각 단위를 책의 절로 바꾼다.",
        "슬라이드를 순서대로 옮기면 자료집이 되고, 강의의 판단을 문장으로 다시 쓰면 책이 된다.",
        [
            "강의의 첫 문장을 책의 프롤로그로 바꾸기",
            "커리큘럼을 목차로 번역하는 법",
            "실습 안내문을 챕터 구조로 바꾸기",
            "수강생 질문이 절 제목이 되는 순간",
            "강사의 애드리브를 저자의 문장으로 정리하기",
            "강의 끝난 뒤 남는 아쉬움을 다음 장으로 옮기기",
            "슬라이드 순서와 책 순서가 달라야 하는 이유",
            "강의 자료집과 저술 원고의 차이",
            "내가 가장 잘 아는 내용부터 쓰기",
        ],
    ),
    Chapter(
        "1부. 강의가 책이 되는 순간",
        "SPARK IPO는 책의 뼈대다",
        "SPARK는 생각을 다루는 법이고 IPO는 산출물을 흐르게 하는 법이다.",
        ["SPARK/IPO 슬라이드", "AGENTS.md SPARK+IPO 규칙", "Daily 2026-05-23 SPARK/IPO 실습"],
        "말라카의 작업 세계는 폴더 구조와 닮았다. 입력을 모으고, 처리 규칙을 세우고, 출력물을 검증한다.",
        "Spec, Plan, Archive, Research, Knowhow를 책의 장치로 쓰고, Input, Proc, Output을 집필 파이프라인으로 쓴다.",
        "구조가 없으면 AI는 빠르게 쓰지만 책은 남지 않는다. 구조가 있으면 작은 요령도 축적된다.",
        [
            "SPARK를 독자의 사고 도구로 설명하기",
            "Spec은 책의 약속이다",
            "Plan은 장별 진행 메모다",
            "Research는 내 주장의 근거 창고다",
            "Knowhow는 반복 가능한 문장이다",
            "IPO로 원고의 흐름을 설계하기",
            "Input을 모으되 원문에 끌려가지 않기",
            "Proc에서 저자 판단을 만든다",
            "Output은 책, 강의, 실습, 커뮤니티로 갈라진다",
        ],
    ),
    Chapter(
        "1부. 강의가 책이 되는 순간",
        "요령을 하나씩 툭툭 던지는 책",
        "데일리 연재보다 내 스타일에 맞는 것은 요령 하나를 던지고, 그 요령이 쓰이는 장면을 보여 주는 방식이다.",
        ["Daily note 요청", "PPT의 바이브 기법 슬라이드", "Notion Jot DB"],
        "매일 긴 글을 쓰는 일은 성실하지만 항상 나다운 방식은 아니다. 말라카의 문장은 요령을 툭 던질 때 살아난다.",
        "각 절을 하나의 요령, 하나의 현장, 하나의 프롬프트, 하나의 질문으로 구성한다.",
        "요령만 있으면 트윗이 되고, 장면만 있으면 일기가 된다. 둘을 엮어야 책이 된다.",
        [
            "요령 하나가 절 하나가 되는 구조",
            "짧은 말 뒤에 긴 맥락 붙이기",
            "데일리 노트의 속도를 책의 리듬으로 바꾸기",
            "팁을 던지고 사례로 증명하기",
            "읽는 사람이 바로 따라 할 수 있게 쓰기",
            "슬라이드 제목을 요령 문장으로 바꾸기",
            "프롬프트보다 먼저 판단 기준을 준다",
            "짧은 절들이 모여 긴 책이 되는 방식",
            "말라카식 문장 리듬 만들기",
        ],
    ),
    Chapter(
        "2부. 말라카라는 저자",
        "나에 대한 이야기",
        "이 책의 저자는 도구 해설자가 아니라 자기 커리어와 생활을 걸고 AI 시대의 일하는 방식을 실험한 사람이다.",
        ["Quick My Ocean", "커리어고민 250617", "의현상담 240818", "Daily summaries"],
        "Notion의 말라카는 한 문장으로 고정되지 않는다. 개발자, 강사, 남편, 예비 아빠, 팀장, 자동화하는 사람, 책을 쓰려는 사람이 겹쳐 있다.",
        "사적인 정보는 덜어내고, 저자 목소리를 만드는 관심사와 선택의 패턴만 남긴다.",
        "자기 이야기가 과하면 자서전이 되고, 빠지면 매뉴얼이 된다. 이 책은 방법론이 있는 자기 이야기여야 한다.",
        [
            "말라카라는 이름이 가진 태도",
            "나만의 통찰이라는 문장",
            "생각의 충돌을 즐기는 사람들",
            "가슴 뛰는 이야기는 왜 산출물이어야 하나",
            "개발자에서 강사로 확장되는 정체성",
            "가족과 커리어가 동시에 오는 시기",
            "불안과 야망을 같은 문장에 놓기",
            "내가 잘 아는 것에서 시작하는 용기",
            "저자 소개를 과장하지 않는 법",
        ],
    ),
    Chapter(
        "2부. 말라카라는 저자",
        "카카오모빌리티를 나오게 된 이야기",
        "카카오모빌리티는 끝난 회사가 아니라 다음 장을 가능하게 한 축적의 장소다.",
        ["PPT: 카모 졸업", "Daily 2025-07-03", "Daily 2026-05-20", "Notion 커리어 고민"],
        "카카오모빌리티에서 보낸 시간은 안정과 성취와 한계를 동시에 남겼다. 큰 조직은 배울 수 있는 학교였고, 어느 순간 더 직접 만들고 움직여야 한다는 압력이 되었다.",
        "퇴사를 영웅담으로 쓰지 않고, 축적된 경험이 어떻게 AX와 바이브코딩으로 이어졌는지 설명한다.",
        "나오는 이야기를 원망으로 쓰면 힘이 약하다. 졸업의 언어로 써야 다음 장이 열린다.",
        [
            "카카오모빌리티는 무엇을 가르쳐 주었나",
            "HD맵과 데이터 파이프라인의 감각",
            "인수 이후 큰 조직에서 배운 것",
            "팀장 경험과 매니지먼트의 미완성",
            "돌아갈 곳이 있었다는 안정감",
            "카모 졸업이라는 표현",
            "나와야 보이는 내 강점",
            "AX로 이어진 회사 경험",
            "다음 회사에서 쓰고 싶은 역량",
        ],
    ),
    Chapter(
        "2부. 말라카라는 저자",
        "회사에서 내가 추구하는 책 스타일",
        "회사에서 쓰이는 책은 멋진 통찰보다 실제 업무의 우선순위를 바꾸는 문장이어야 한다.",
        ["Daily 2026-05-19", "Daily 2026-05-20", "CRM 마이그레이션 업무기록", "AX 관련 ChatGPT titles"],
        "회사에서 책은 취미가 아니라 정렬 도구가 된다. 어떤 영역을 먼저 AX 해야 하는지, 누가 도메인을 알고 있는지, 어떤 자동화가 위험한지를 설명해야 한다.",
        "현장 사례를 일반화해 AX 전략가의 판단표로 만든다.",
        "특수한 회사 잡무에 갇히면 책이 좁아지고, 너무 일반화하면 현장의 힘이 사라진다.",
        [
            "AX 책은 현장 우선순위표다",
            "영업관리 노가다를 줄이는 문장",
            "콜센터와 행정 자동화가 먼저인 이유",
            "마케팅 AI보다 먼저 필요한 DX",
            "도메인 담당자를 저자로 세우기",
            "개발자보다 빠른 현업의 시선",
            "사내 세미나가 책의 실험실이 된다",
            "대표에게 설명 가능한 프레임",
            "회사에서 읽히는 문장 만들기",
        ],
    ),
    Chapter(
        "3부. 말라카 강사의 설계법",
        "170명 실습강좌를 설계하는 요령",
        "대규모 실습강좌는 지식을 잘 설명하는 일이 아니라 실패를 미리 줄여 놓는 운영 설계다.",
        ["PPT: AX 하지 않으면 망한다", "KUBIT/POC Clinic 자료", "Daily 2026-05-09", "Daily 2026-05-23"],
        "170명이 동시에 실습하면 AI보다 사람이 먼저 흔들린다. 로그인, 설치, 속도, 자리, 질문, 결과 공유가 모두 강의 내용이 된다.",
        "대규모 실습을 단계, 템플릿, 공유노트, 조교, 실패 복구, 결과 발표로 설계한다.",
        "실습은 자유로워야 하지만 방치되면 무너진다. 통제 가능한 자유가 필요하다.",
        [
            "대규모 실습의 첫 번째 원칙",
            "설치와 로그인은 커리큘럼이다",
            "템플릿 없이는 자유도 없다",
            "조교가 봐야 할 실패 신호",
            "실습 공유노트 운영법",
            "AI가 일하는 동안 강의하기",
            "결과물을 Slack에 올리게 하는 이유",
            "못 따라온 사람을 포기하지 않는 구조",
            "170명을 한 흐름으로 묶는 마감",
        ],
    ),
    Chapter(
        "3부. 말라카 강사의 설계법",
        "강의에서 내가 다루는 내용들",
        "말라카의 강의는 바이브코딩 소개가 아니라 MVP, 웹앱, 프롬프트, 자동화, 검증을 한 흐름으로 묶는 설계다.",
        ["PPT 목차", "바이브 강의안", "WhyQ 공유노트", "부경대 MVP 강연"],
        "강의 제목은 자주 바뀌지만 뼈대는 반복된다. 가능성을 보여 주고, 기획을 시키고, 웹앱 구조를 알려 주고, 직접 만들게 하고, 더 잘하는 법을 남긴다.",
        "강의 내용을 책의 파트 구조로 재배열한다.",
        "강의 순서와 책 순서를 혼동하면 독자는 따라오지만 이해하지 못한다.",
        [
            "바이브코딩 가능성 보여 주기",
            "MVP와 스타트업의 언어",
            "웹앱의 구성요소",
            "기획강화 프롬프트",
            "Lovable과 Cursor의 자리",
            "직접 만들어 보는 실습",
            "바이브 기법들",
            "실무 노하우와 프론트엔드 부록",
            "강의 후 남겨야 할 숙제",
        ],
    ),
    Chapter(
        "3부. 말라카 강사의 설계법",
        "말라카 강사의 장악력",
        "강사는 도구를 설명하는 사람이 아니라 강의실의 에너지와 실패를 동시에 다루는 사람이다.",
        ["Daily 2025-06-28", "Daily 2026-05-09", "Daily 2026-05-14", "강의 피드백 메모"],
        "좋은 강의는 자료가 좋아서만 성립하지 않는다. 수강생이 지금 무엇을 두려워하는지, 어디서 웃을지, 언제 손을 움직일지 알아야 한다.",
        "스토리텔링, 농담, 지시, 침묵, 실습 시간을 강의의 리듬으로 배치한다.",
        "장악력이 과하면 수강생이 수동적이 되고, 부족하면 실습이 흩어진다.",
        [
            "스토리텔링은 강사의 기술이다",
            "쉬운 단어로 어려운 구조 말하기",
            "강의장 농담의 역할",
            "실습 전 긴장 낮추기",
            "수강생이 멈추는 순간 알아차리기",
            "결과물 발표로 에너지 회수하기",
            "질문을 무대 위로 올리기",
            "강사의 자기소개를 기능적으로 쓰기",
            "끝나고 남는 한 문장 설계",
        ],
    ),
    Chapter(
        "4부. 슬라이드를 챕터로 팽창시키는 법",
        "슬라이드 한 장을 챕터 하나로 만들기",
        "슬라이드의 제목은 챕터의 씨앗이고, 본문은 그 제목이 숨긴 판단을 풀어내는 일이다.",
        ["PPT 추출 9,312장", "content-review.md", "반복 제목 분석"],
        "슬라이드에는 책이 될 문장이 이미 숨어 있다. 문제는 텍스트가 짧다는 것이 아니라 판단이 압축되어 있다는 것이다.",
        "슬라이드 제목을 주장, 배경, 사례, 실행, 검증, 질문으로 팽창시킨다.",
        "슬라이드 문장을 늘리면 장황해지고, 판단을 풀면 챕터가 된다.",
        [
            "슬라이드 제목에서 주장 뽑기",
            "한 장의 숨은 독자 찾기",
            "배경을 붙이면 절이 된다",
            "사례를 붙이면 장이 된다",
            "프롬프트를 붙이면 실습이 된다",
            "검증 질문을 붙이면 책이 된다",
            "반복 슬라이드는 방법론 신호다",
            "숨김 슬라이드의 쓸모",
            "챕터 팽창 템플릿",
        ],
    ),
    Chapter(
        "4부. 슬라이드를 챕터로 팽창시키는 법",
        "PPT 그림을 책에 넣는 법",
        "PPT 그림은 장식이 아니라 강의 현장의 흔적이어야 한다.",
        ["PPTX 내부 media 추출", "대표 강의덱", "HTML/PDF 렌더링"],
        "그림을 많이 넣는다고 책이 좋아지지는 않는다. 어떤 그림은 장면을 열고, 어떤 그림은 설명을 보강하고, 어떤 그림은 강의의 분위기만 전달한다.",
        "PPT 내부 이미지를 대표 시각자료로 추출하고, 각 부의 도입부와 사례 절에 배치한다.",
        "그림을 원문 페이지처럼 붙이면 자료집이 된다. 그림에 새 해석을 붙이면 책의 장면이 된다.",
        [
            "이미지는 장식이 아니라 장면이다",
            "슬라이드 스크린샷 대신 media를 쓰는 이유",
            "캡션이 없으면 이미지는 말하지 않는다",
            "그림 하나에 주장 하나만 붙이기",
            "강의 현장감을 살리는 배치",
            "A5 판형에서 이미지 크기 잡기",
            "HTML 책에서 figure를 다루는 법",
            "이미지가 없어도 책이 서야 한다",
            "그림을 사례로 바꾸는 문장",
        ],
    ),
    Chapter(
        "4부. 슬라이드를 챕터로 팽창시키는 법",
        "HTML로 책을 만드는 바이브코딩",
        "HTML 책 만들기는 원고, 조판, 이미지, PDF 검증을 하나의 자동화 루프로 묶는 일이다.",
        ["이 작업의 HTML/PDF 파이프라인", "PPT HTML 관련 슬라이드", "Markdown/WeasyPrint 렌더링"],
        "바이브코딩으로 책을 만들면 원고와 조판이 분리된다. 글은 Markdown으로 쓰고, 책의 표정은 HTML/CSS가 맡고, PDF는 검증 가능한 출력물이 된다.",
        "원고를 HTML로 변환하고, print CSS로 판형과 페이지를 제어하고, pdfinfo로 페이지 수를 검증한다.",
        "자동화는 책을 대신 쓰지 않는다. 자동화는 책을 반복해서 고칠 수 있게 해 준다.",
        [
            "Markdown은 원고의 뼈대다",
            "HTML은 책의 몸이다",
            "CSS는 책의 표정이다",
            "A5 판형을 고른 이유",
            "page break를 설계하는 법",
            "figure와 caption 다루기",
            "PDF 렌더링 후 검증하기",
            "코드가 해도 되는 일과 안 되는 일",
            "출판 스타일을 반복 가능한 루프로 만들기",
        ],
    ),
    Chapter(
        "5부. 바이브코딩의 핵심 내용",
        "바이브코딩은 마법이 아니다",
        "바이브코딩은 AI에게 대충 맡기는 일이 아니라 자연어를 작업 계약으로 바꾸는 일이다.",
        ["바이브코딩 개념 슬라이드", "ChatGPT: Why 중심의 바이브코딩", "ChatGPT: 바이브코딩 제품 개발 과정"],
        "처음 듣는 사람은 바이브코딩을 신기한 자동 코딩으로 이해한다. 그러나 실제로는 사람의 판단을 더 정확히 드러내는 일에 가깝다.",
        "상황, 사용자, 입력, 출력, 금지사항, 검증 기준을 갖춘 작업 계약을 만든다.",
        "마법처럼 보일수록 책임이 흐려진다. 책임이 흐려지면 실무에 못 올린다.",
        [
            "바이브코딩의 오해",
            "챗GPT에게 물어보는 것과 무엇이 다른가",
            "자연어는 명세가 되어야 한다",
            "AI에게 맡기는 것과 방치하는 것",
            "작업 계약의 여섯 요소",
            "좋은 프롬프트보다 좋은 기준",
            "결과물을 보고 다시 묻기",
            "비개발자에게 필요한 최소 지식",
            "바이브코딩의 책임 감각",
        ],
    ),
    Chapter(
        "5부. 바이브코딩의 핵심 내용",
        "MVP는 작은 증거다",
        "MVP는 작은 제품이 아니라 판단을 가능하게 하는 작은 증거다.",
        ["MVP 강의 슬라이드", "부경대 MVP 강연", "고려대 강의 기록"],
        "수강생은 앱을 만들고 싶어 하지만 강사는 먼저 질문을 줄여야 한다. 이 앱이 필요한가, 누가 쓸까, 어떤 행동이 바뀔까.",
        "가설 하나를 정하고, 그 가설만 확인할 수 있는 작동물을 만든다.",
        "MVP를 축소판으로 만들면 가장 중요한 질문을 확인하지 못한다.",
        [
            "MVP는 왜 작아야 하나",
            "가설을 하나만 남기는 법",
            "사용자 반응을 보는 최소 단위",
            "실습용 MVP와 사업용 MVP",
            "Lovable로 가능한 것과 아닌 것",
            "첫 사용자의 반응 기록하기",
            "예쁜 화면보다 판단 가능한 화면",
            "MVP 이후의 다음 질문",
            "강의장에서 MVP를 다루는 법",
        ],
    ),
    Chapter(
        "5부. 바이브코딩의 핵심 내용",
        "웹앱의 정석",
        "AI가 코드를 만들어도 웹앱의 구조를 모르면 결과를 고칠 수 없다.",
        ["웹앱 구성요소 슬라이드", "Supabase/Firebase 슬라이드", "WhyQ 강의안"],
        "화면은 금방 나오지만 데이터에서 막힌다. 로그인에서 막히고, 저장에서 막히고, 배포에서 막힌다.",
        "프론트엔드, 백엔드, 데이터베이스, 인증, API, 배포를 역할 단위로 가르친다.",
        "구조를 모르면 같은 프롬프트를 반복하게 된다.",
        [
            "웹앱은 화면만으로 되지 않는다",
            "프론트엔드의 역할",
            "백엔드의 역할",
            "데이터베이스는 기억의 방식",
            "API는 약속이다",
            "인증과 권한의 기본",
            "Supabase와 Firebase의 자리",
            "배포 후에 보이는 문제",
            "웹앱 구조도를 그리는 법",
        ],
    ),
    Chapter(
        "5부. 바이브코딩의 핵심 내용",
        "바이브 기법들",
        "메모리뱅킹, 스테이징, 맥락주입, 멀티캐스트는 AI와 일하는 방식을 안정화하는 요령이다.",
        ["바이브 기법 슬라이드", "Vibe-plan 프롬프트", "SPARK/IPO 템플릿"],
        "기법은 거창한 이론이 아니라 실패를 줄이는 작은 장치다. AI가 잊어버리고, 흔들리고, 방향을 바꾸기 때문에 장치가 필요하다.",
        "각 기법을 언제 쓰는지, 어떤 실패를 막는지, 어떤 산출물로 남기는지 정리한다.",
        "기법 이름만 외우면 효과가 없다. 작업 흐름 안에 들어가야 한다.",
        [
            "메모리뱅킹",
            "스테이징",
            "맥락주입",
            "멀티캐스트",
            "단계적 사고법",
            "두뇌 두 개 쓰기",
            "하네스와 브라우저",
            "규칙 파일과 AGENTS",
            "기법을 강의 실습으로 바꾸기",
        ],
    ),
    Chapter(
        "6부. 회사에서 통하는 AX",
        "도메인 아는 사람이 바이브코딩을 배워야 한다",
        "개발자에게 주문 도메인을 가르치는 것보다 도메인을 아는 사람에게 바이브코딩을 가르치는 편이 빠를 때가 있다.",
        ["Daily 2026-05-20", "김채원 대리 사례", "회사 AX 메모"],
        "현업 담당자는 시스템의 이름보다 예외를 안다. 어디서 틀리고, 누가 다시 확인하고, 어떤 말이 고객에게 문제를 만드는지 안다.",
        "도메인 담당자에게 작은 자동화와 프롬프트 계약을 가르쳐 단건 업무를 해방한다.",
        "도메인 없이 만든 자동화는 현장의 언어를 놓친다.",
        [
            "도메인 지식은 데이터보다 빠르다",
            "현업이 아는 예외",
            "김채원 사례가 보여주는 것",
            "개발자 순환 배치의 한계",
            "작은 자동화부터 맡기기",
            "현업용 SPARK IPO 프로젝트",
            "영업관리와 회계의 접점",
            "AX 인력은 어떻게 자라는가",
            "도메인 담당자를 저자로 세우기",
        ],
    ),
    Chapter(
        "6부. 회사에서 통하는 AX",
        "실무 자동화는 주문과 수금에서 시작된다",
        "AX는 멋진 챗봇보다 주문, 수금, CRM, ERP 같은 지루한 흐름을 고칠 때 먼저 성과가 난다.",
        ["CRM 마이그레이션", "거래원장 업무", "Salesforce/ERP 기록", "Daily 2026-05-22"],
        "회사에는 매일 반복되는 손작업이 있다. 이름이 틀리고, 금액이 어긋나고, 누가 확인했는지 사라진다.",
        "업무 흐름을 데이터 흐름으로 바꾸고, 사람이 확인할 지점과 AI가 반복할 지점을 나눈다.",
        "사람에게 일 시키는 자동화는 위험하다. 데이터와 판단의 경계부터 잡아야 한다.",
        [
            "주문 업무에서 보이는 AX 기회",
            "수금 데이터는 신뢰의 언어다",
            "CRM은 영업의 기억이다",
            "ERP는 책임의 흐름이다",
            "사람에게 지시하는 자동화의 위험",
            "현장 인터뷰로 요구사항 뽑기",
            "세 부서 갈등을 시스템으로 풀기",
            "단건 자동화와 큰 시스템의 차이",
            "운영 후에도 쓰이는 결과물",
        ],
    ),
    Chapter(
        "6부. 회사에서 통하는 AX",
        "AX 전략가의 우선순위표",
        "AX 전략가는 무엇을 자동화할지보다 무엇을 먼저 자동화하지 않을지를 정하는 사람이다.",
        ["Daily 2026-05-19", "AX 책 쓰기 가이드", "회사 세미나 기록"],
        "아내와의 대화에서 나온 질문은 날카롭다. 특정 회사 잡무 해결이 아니라, 어떤 영역이 매출과 비용에 먼저 영향을 주는가.",
        "행정, 콜센터, 영업관리, 마케팅, DX, AX를 우선순위표로 정리한다.",
        "우선순위 없는 AX는 신기한 시연으로 끝난다.",
        [
            "AX 전략가의 첫 질문",
            "행정 자동화가 먼저인 이유",
            "콜센터와 응대 업무",
            "영업관리 노가다",
            "마케팅 AI는 언제 힘을 갖나",
            "DX 없는 AX는 없다",
            "매출 영향과 비용 영향 나누기",
            "대표에게 보고하는 방식",
            "우선순위표를 책으로 만들기",
        ],
    ),
    Chapter(
        "7부. ChatGPT 질문들이 보여주는 관심사",
        "내 질문들이 목차가 된다",
        "ChatGPT 질문 제목들은 내가 무엇을 반복해서 고민했는지 보여 주는 색인이다.",
        ["data/db/chatgpt.sqlite", "AX 책 쓰기 가이드", "바이브코딩 강의 계획", "책/목차 관련 질문"],
        "대화 본문을 새로 가져오지 않아도 제목만으로 흐름이 보인다. AX 책, 바이브코딩 강의, 앱 아이디어, 제품 개발, 강의안 요약이 반복된다.",
        "질문 제목을 관심사 버킷으로 묶고, 각 버킷을 책의 파트 후보로 쓴다.",
        "질문을 그대로 옮기면 로그이고, 질문의 반복을 읽으면 목차가 된다.",
        [
            "AX 책 쓰기 가이드",
            "바이브코딩 강의 계획",
            "바이브코딩 MVP 강의",
            "바이브코딩 앱 아이디어",
            "제품 개발 과정 질문",
            "마크다운 강의 기획",
            "책 표지와 책 요약 질문",
            "도구 가격과 정책 질문",
            "질문 로그를 저자 관심사로 바꾸기",
        ],
    ),
    Chapter(
        "7부. ChatGPT 질문들이 보여주는 관심사",
        "질문하는 습관이 저자성을 만든다",
        "AI에게 자주 묻는 사람은 자신이 반복해서 부딪히는 문제의 지도를 갖게 된다.",
        ["ChatGPT title DB", "Daily 2026-05-11 ChatGPT 업그레이드", "Notion WebLink DB"],
        "질문은 순간의 필요처럼 보이지만 오래 모이면 정체성이 된다. 무엇을 샀는지보다 무엇을 물었는지가 더 정확할 때가 있다.",
        "질문을 수집해 주제, 독자, 산출물, 미해결 과제로 분류한다.",
        "AI 질문이 많아도 정리하지 않으면 책이 되지 않는다.",
        [
            "질문은 관심사의 로그다",
            "반복 질문을 찾는 법",
            "가격 정책 질문의 의미",
            "강의 질문의 의미",
            "책 질문의 의미",
            "제품 질문의 의미",
            "질문을 목차로 승격하기",
            "질문을 요령으로 압축하기",
            "다음 질문을 설계하는 법",
        ],
    ),
    Chapter(
        "8부. 책 쓰기를 운영체제로 만들기",
        "책 쓰기는 LifeOS의 출력물이다",
        "책은 어느 날 몰아서 쓰는 결과가 아니라 기록, 강의, 질문, 업무가 오래 축적된 출력물이다.",
        ["Quick My Ocean", "Goal Hub", "Daily summaries", "Notion Jot DB"],
        "LifeOS가 진짜 작동한다면 언젠가 책이 나와야 한다. 기록이 다음 행동으로 이어지고, 행동이 강의가 되고, 강의가 책이 되는 흐름이 생겨야 한다.",
        "Jot, Task, Note, Slide, ChatGPT 질문을 하나의 책 제작 루프로 묶는다.",
        "기록이 많다고 책이 되지는 않는다. 출력물을 정해야 기록이 책을 향해 모인다.",
        [
            "Jot은 책의 씨앗이다",
            "Task는 집필을 움직인다",
            "Note는 근거를 보존한다",
            "슬라이드는 책의 실험이다",
            "ChatGPT 질문은 목차의 색인이다",
            "Daily summary는 저자 리듬이다",
            "출력물이 기록을 정렬한다",
            "책 쓰기 루틴 만들기",
            "LifeOS가 책이 되는 순간",
        ],
    ),
    Chapter(
        "8부. 책 쓰기를 운영체제로 만들기",
        "검증하지 않는 속도는 책에서도 빚이다",
        "AI와 HTML로 빨리 책을 만들수록 더 자주 원고 품질과 출처 사용 방식을 검증해야 한다.",
        ["이전 final 검증", "raw metadata leak check", "pdfinfo", "사용자 피드백"],
        "빠르게 만든 477쪽 PDF도 사용자가 보기에는 자료수집에 가까울 수 있다. 그 피드백은 중요하다. 페이지 수가 책을 보장하지 않기 때문이다.",
        "페이지 수, 목차, 원문 메타데이터 유입, 이미지 출처, 저자 목소리, 반복도를 함께 검증한다.",
        "검증 없이 길게 쓰면 긴 초안일 뿐이다.",
        [
            "페이지 수는 최소 조건이다",
            "raw metadata leak을 막는 법",
            "출처를 근거로만 쓰기",
            "반복 문장을 줄이는 법",
            "이미지 사용을 검증하기",
            "목차가 책의 약속인지 확인하기",
            "사용자 피드백을 다음 판에 반영하기",
            "초안과 최종본을 구분하기",
            "다음 개정판의 기준",
        ],
    ),
    Chapter(
        "8부. 책 쓰기를 운영체제로 만들기",
        "말라카식 출판 파이프라인",
        "말라카식 책 쓰기는 강의, daily note, ChatGPT 질문, Notion, PPT, HTML 조판을 한 루프로 묶는 일이다.",
        ["이번 rewrite 파이프라인", "SPARK IPO", "HTML/PDF 산출물"],
        "책은 글만으로 끝나지 않는다. 리포트, 목차, 원고, 이미지, HTML, PDF, 검증 요약이 함께 있어야 다음 판을 만들 수 있다.",
        "요청 리포트로 요구사항을 고정하고, 확장 목차로 책의 약속을 만든 뒤, Markdown 원고와 HTML 출판 스타일로 출력한다.",
        "파이프라인이 저자를 대신하면 안 된다. 파이프라인은 저자가 계속 고칠 수 있게 해야 한다.",
        [
            "요청사항을 먼저 기록한다",
            "목차를 팽창시킨다",
            "원천은 읽고 덜어낸다",
            "Markdown으로 저술한다",
            "HTML로 판형을 잡는다",
            "PPT 이미지를 장면으로 쓴다",
            "PDF로 검증한다",
            "리포트로 다음 판을 남긴다",
            "책은 한 번이 아니라 루프다",
        ],
    ),
]


PART_FIGURE_DECKS = [
    ("22-vivecodinglecentre2603-latest.pptx", [281, 282, 283, 284, 211, 180], "SPARK IPO 강의 자료"),
    ("28-vivecodinglecpocclinickubit2605-latest.pptx", [1, 2, 10, 20, 30, 40], "KUBIT POC 클리닉"),
    ("14-vivecodinglecku251111-latest.pptx", [4, 17, 18, 137], "카카오모빌리티와 말라카 소개"),
    ("06-vivecodinglecwhyq-latest-2.pptx", [1, 100, 170, 226, 238, 239], "WhyQ 바이브코딩 강의"),
    ("30-vivecodinglecpocclinickubit2605-lec2-latest.pptx", [1, 20, 40, 60, 80], "브라우저 자동화와 실습"),
]


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("\u00a0", " ")).strip()


def md(text: str) -> str:
    return clean(text).replace("\\", "\\\\")


def stats() -> dict[str, Any]:
    slides = read_json(SLIDES_PATH, [])
    notion = read_json(NOTION_CORPUS_PATH, [])
    topic = read_json(NOTION_TOPIC_PATH, {})
    chat_count = 0
    if CHATGPT_DB.exists():
        with sqlite3.connect(CHATGPT_DB) as con:
            chat_count = con.execute("select count(*) from conversations").fetchone()[0]
    daily_count = len(list(DAILY_DIR.glob("*/summary.md"))) if DAILY_DIR.exists() else 0
    return {
        "slides": len(slides),
        "notion_relevant_pages": len(notion),
        "notion_topic_buckets": sorted(topic.keys()),
        "chatgpt_conversations": chat_count,
        "daily_summaries": daily_count,
        "chapters": len(CHAPTERS),
        "sections": sum(len(c.sections) for c in CHAPTERS),
    }


def chatgpt_titles() -> list[str]:
    if not CHATGPT_DB.exists():
        return []
    terms = ["AX", "책", "바이브", "강의", "목차", "마크다운", "MVP", "제품"]
    where = " or ".join(["title like ?" for _ in terms])
    params = [f"%{term}%" for term in terms]
    with sqlite3.connect(CHATGPT_DB) as con:
        rows = con.execute(f"select title from conversations where {where} order by title", params).fetchall()
    titles = []
    seen = set()
    for (title,) in rows:
        if title and title not in seen:
            titles.append(title)
            seen.add(title)
    return titles[:80]


def daily_evidence() -> list[dict[str, str]]:
    patterns = re.compile(r"책|목차|출판|바이브|강의|SPARK|IPO|카카오|모빌리티|AX|KUBIT|POC", re.I)
    out = []
    for path in sorted(DAILY_DIR.glob("*/summary.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = [clean(line) for line in text.splitlines() if patterns.search(line)]
        if lines:
            out.append({"path": str(path), "lines": "\n".join(lines[:6])})
    return out[-30:]


def notion_evidence() -> list[dict[str, str]]:
    corpus = read_json(NOTION_CORPUS_PATH, [])
    terms = ["SPARK", "IPO", "강의", "책", "카카오모빌리티", "카모", "회사에서", "바이브"]
    selected = []
    seen = set()
    for term in terms:
        for item in corpus:
            text = f"{item.get('title','')} {item.get('excerpt','')}"
            if term.lower() in text.lower() and item.get("title") not in seen:
                selected.append(
                    {
                        "title": clean(item.get("title", "")),
                        "data_source": clean(item.get("data_source", "")),
                        "excerpt": clean(item.get("excerpt", ""))[:220],
                    }
                )
                seen.add(item.get("title"))
                break
    return selected


def slide_title(deck_name: str, slide_no: int) -> str:
    path = ROOT / "extracts" / deck_name.replace(".pptx", "") / "slides.json"
    slides = read_json(path, [])
    if isinstance(slides, dict):
        slides = slides.get("slides", [])
    for slide in slides:
        if int(slide.get("slide_number", -1)) == slide_no:
            return clean(slide.get("title", f"slide {slide_no}"))
    return f"slide {slide_no}"


def image_targets_for_slide(z: ZipFile, slide_no: int) -> list[str]:
    rel_path = f"ppt/slides/_rels/slide{slide_no}.xml.rels"
    slide_path = f"ppt/slides/slide{slide_no}.xml"
    if rel_path not in z.namelist() or slide_path not in z.namelist():
        return []
    rel_root = ET.fromstring(z.read(rel_path))
    rels = {}
    for rel in rel_root:
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if rid and target.startswith("../media/"):
            rels[rid] = "ppt/media/" + target.split("../media/", 1)[1]
    slide_root = ET.fromstring(z.read(slide_path))
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    targets = []
    for blip in slide_root.findall(".//a:blip", ns):
        rid = blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
        if rid in rels:
            targets.append(rels[rid])
    if targets:
        return targets
    return list(rels.values())


def save_image_from_zip(z: ZipFile, member: str, out_path: Path) -> bool:
    try:
        with z.open(member) as src:
            image = Image.open(src)
            image.seek(0)
            image = ImageOps.exif_transpose(image).convert("RGB")
            if image.width < 220 or image.height < 140:
                return False
            image.thumbnail((1300, 900))
            image.save(out_path, "JPEG", quality=84, optimize=True)
            return True
    except Exception:
        return False


def extract_ppt_images() -> list[dict[str, str]]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for old in ASSET_DIR.glob("*.jpg"):
        old.unlink()
    assets = []
    count = 1
    for deck, slide_numbers, group in PART_FIGURE_DECKS:
        ppt_path = PPT_DIR / deck
        if not ppt_path.exists():
            continue
        try:
            with ZipFile(ppt_path) as z:
                used = set()
                for slide_no in slide_numbers:
                    title = slide_title(deck, slide_no)
                    for member in image_targets_for_slide(z, slide_no):
                        if member in used:
                            continue
                        used.add(member)
                        out = ASSET_DIR / f"ppt-figure-{count:02d}.jpg"
                        if save_image_from_zip(z, member, out):
                            assets.append(
                                {
                                    "path": f"assets/ppt-images/{out.name}",
                                    "caption": f"{group} — {title}",
                                    "source": f"{deck} #{slide_no} {title}",
                                }
                            )
                            count += 1
                            break
                    if len(assets) >= 18:
                        return assets
                if len(used) == 0:
                    media = [info.filename for info in z.infolist() if info.filename.startswith("ppt/media/")]
                    for member in media[:20]:
                        out = ASSET_DIR / f"ppt-figure-{count:02d}.jpg"
                        if save_image_from_zip(z, member, out):
                            assets.append({"path": f"assets/ppt-images/{out.name}", "caption": group, "source": f"{deck} {member}"})
                            count += 1
                            break
        except Exception:
            continue
    return assets


def section_text(chapter_idx: int, section_idx: int, chapter: Chapter, section: str, figure: dict[str, str] | None) -> list[str]:
    tip_stems = [
        "요령은 간단하다.",
        "강의로 말하면 이렇게 된다.",
        "책으로 바꾸면 이 지점이 중요하다.",
        "회사에서 쓰려면 기준을 더 좁혀야 한다.",
        "AI에게 맡기기 전 사람이 먼저 해야 할 일이 있다.",
        "실습으로 만들려면 실패 지점을 먼저 깔아야 한다.",
        "데일리 노트식으로 쓰면 한 문장부터 시작하면 된다.",
        "HTML 책으로 만들 때도 같은 원리가 적용된다.",
        "다음 판을 위해 남길 기록은 따로 있다.",
    ]
    frame = tip_stems[(chapter_idx + section_idx - 2) % len(tip_stems)]
    lines = [
        "",
        '<div class="book-page"></div>',
        "",
        f"## {chapter_idx}-{section_idx:02d}. {md(section)}",
        "",
        f"<p class=\"lede\">{md(frame)} {md(chapter.one_line)}</p>",
        "",
        f"{section}라는 제목은 작은 팁처럼 보이지만, 실제로는 말라카가 강의와 회사와 기록 속에서 반복해서 부딪힌 문제를 압축한 말이다. "
        f"{chapter.scene} 이 장면을 책으로 옮길 때 중요한 것은 원문을 길게 붙이는 일이 아니라, 그 장면에서 어떤 판단이 작동했는지 독자가 따라올 수 있게 쓰는 일이다.",
        "",
        f"{chapter.method} 이 방법은 한 번에 완성되는 거대한 공식이 아니다. 강의에서는 수강생이 바로 손을 움직일 수 있는 단계가 되고, 회사에서는 담당자가 책임질 수 있는 업무 절차가 되며, 책에서는 독자가 자기 프로젝트에 옮길 수 있는 문장으로 바뀐다.",
        "",
        f"반대로 조심할 점도 분명하다. {chapter.tension} 그래서 이 절은 정답을 제공하려 하지 않는다. 대신 독자가 지금 가진 자료와 문제를 어떤 순서로 다시 볼지 제안한다. 빠르게 만들 수 있다는 사실보다, 무엇을 빠르게 확인할지가 더 중요하다.",
    ]
    if figure:
        lines.extend(
            [
                "",
                f"![{md(figure['caption'])}]({figure['path']})",
                f"<p class=\"caption\">{md(figure['caption'])}. 원천: {md(figure['source'])}</p>",
            ]
        )
    lines.extend(
        [
            "",
            "### 책으로 바꾸는 방식",
            "",
            "- 먼저 한 문장 요령으로 시작한다.",
            "- 그 요령이 나온 강의장, 회사, daily note의 장면을 붙인다.",
            "- AI에게 맡길 일과 사람이 판단할 일을 분리한다.",
            "- 결과물을 본 뒤 다음 판에 반영할 검증 질문을 남긴다.",
            "",
            "### 실행 프롬프트",
            "",
            "> 너는 말라카의 편집자다. 아래 요령을 독자가 바로 적용할 수 있는 책의 한 절로 바꿔라. 먼저 현장 장면을 만들고, 그다음 판단 기준, 실행 절차, 검증 질문을 순서대로 써라. 원문을 베끼지 말고 저자의 관점으로 다시 써라.",
            "",
            "### 독자에게 남기는 질문",
            "",
            f"- 이 절의 요령을 내 강의나 회사 업무에 적용하면 무엇이 먼저 바뀌는가?",
            "- 지금 내가 가진 자료는 책의 원문인가, 책을 쓰기 위한 근거인가?",
            "- 다음 반복에서 내가 줄일 것 하나와 더 선명하게 만들 것 하나는 무엇인가?",
        ]
    )
    return lines


def render_toc() -> str:
    lines = [
        "# 확장 목차",
        "",
        "이 목차는 사용자의 daily note 요청을 기준으로 다시 팽창시킨 책의 설계다. 기존 477쪽 PDF는 보존하되, 이번 판은 강의 자체를 책으로 바꾸는 방향과 SPARK IPO, 대규모 실습강좌, 카카오모빌리티 이후의 말라카 서사를 전면에 둔다.",
        "",
    ]
    current = None
    for idx, chapter in enumerate(CHAPTERS, 1):
        if chapter.part != current:
            current = chapter.part
            lines.extend([f"## {current}", ""])
        lines.extend([f"### {idx}. {chapter.title}", "", chapter.one_line, ""])
        for sec_idx, sec in enumerate(chapter.sections, 1):
            lines.append(f"{idx}-{sec_idx:02d}. {sec}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_report(assets: list[dict[str, str]]) -> str:
    s = stats()
    lines = [
        "# 요청사항 리포트",
        "",
        f"- 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- 원칙: 새 API 스크랩 없음. 기존 로컬 다운로드 자료만 사용.",
        "- 이전 final PDF는 보존하되, 이번 요청은 daily note 기반 rewrite 판으로 별도 제작.",
        "",
        "## 사용자가 남긴 요청",
        "",
        "```text",
        USER_REQUEST.strip(),
        "```",
        "",
        "## 로컬 자료 범위",
        "",
        f"- PPT 추출 슬라이드: {s['slides']:,}장",
        f"- Notion 관련 페이지 코퍼스: {s['notion_relevant_pages']:,}건",
        f"- Notion 주제 버킷: {', '.join(s['notion_topic_buckets'])}",
        f"- ChatGPT conversation title DB: {s['chatgpt_conversations']:,}건",
        f"- Daily summary 파일: {s['daily_summaries']:,}건",
        "",
        "## ChatGPT 질문 제목 신호",
        "",
    ]
    for title in chatgpt_titles()[:35]:
        lines.append(f"- {title}")
    lines.extend(["", "## Notion 근거 신호", ""])
    for item in notion_evidence():
        lines.append(f"- {item['title']} ({item['data_source']}): {item['excerpt']}")
    lines.extend(["", "## Daily note/summary 신호", ""])
    for item in daily_evidence()[-12:]:
        lines.append(f"### {item['path']}")
        lines.append(item["lines"])
        lines.append("")
    lines.extend(["## PPT 이미지 추출", ""])
    if assets:
        for asset in assets:
            lines.append(f"- `{asset['path']}` — {asset['caption']} ({asset['source']})")
    else:
        lines.append("- PPTX media 추출 시 usable image를 찾지 못함.")
    lines.extend(
        [
            "",
            "## 이번 판의 목차 축",
            "",
            "1. 강의 자체를 책으로 바꾸는 법",
            "2. SPARK IPO를 책의 구조와 집필 파이프라인으로 쓰는 법",
            "3. 170명 실습강좌를 운영 가능한 강의 설계로 바꾸는 법",
            "4. daily note식 요령을 챕터로 엮는 법",
            "5. 말라카 개인 서사와 카카오모빌리티 이후의 졸업 이야기",
            "6. 회사에서 통하는 AX 책 스타일",
            "7. 강의에서 실제로 다루는 바이브코딩/MVP/웹앱/프롬프트/검증 내용",
            "8. HTML 기반 출판 스타일과 PPT 그림을 포함한 책 제작 루프",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_book(assets: list[dict[str, str]]) -> str:
    s = stats()
    lines = [
        '<div class="cover">',
        "",
        "# 강의는 어떻게 책이 되는가",
        "",
        "## 말라카의 바이브코딩, SPARK IPO, 그리고 AX 실습 강의의 기술",
        "",
        "**말라카 지음**",
        "",
        f"rewrite: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "</div>",
        "",
        '<div class="chapter-break"></div>',
        "",
        "# 저자의 말: 내가 가장 잘 아는 내용부터 쓴다",
        "",
        "나는 이번 책을 도구 설명서로 쓰지 않기로 했다. 바이브코딩 도구는 계속 바뀐다. Cursor가 바뀌고, Claude가 바뀌고, Codex가 바뀌고, Lovable이 바뀐다. 그러나 강의장에서 사람이 막히는 지점은 크게 바뀌지 않는다. 무엇을 만들지 정하지 못하고, 첫 화면을 좁히지 못하고, 데이터가 어디에 있어야 하는지 헷갈리고, AI가 만든 결과를 믿어도 되는지 판단하지 못한다.",
        "",
        "그래서 나는 내가 가장 잘 아는 것부터 쓰기로 했다. 강의 자체를 책으로 바꾸는 일이다. 나는 이미 여러 번 강의장을 통과했다. 고려대, 부경대, WhyQ, KUBIT, 회사 개발부 세미나, POC 클리닉에서 같은 질문을 다른 얼굴로 만났다. 그 질문들은 슬라이드에 남았고, Notion에 남았고, daily note에 남았고, ChatGPT 질문 제목에도 남았다.",
        "",
        "이 책은 그 자료를 이어 붙인 결과가 아니다. 자료는 근거이고, 책은 판단이다. 나는 SPARK IPO라는 폴더 구조와 사고 구조를 책의 뼈대로 삼는다. Input에는 강의 자료와 기록을 넣고, Proc에서는 저자의 관점으로 다시 읽고, Output에서는 독자가 실제로 따라 할 수 있는 요령을 남긴다.",
        "",
        "# 이 책을 읽는 법",
        "",
        "각 절은 하나의 요령으로 시작한다. 요령은 짧지만, 짧은 말 뒤에는 강의장과 회사와 개인 기록의 맥락이 붙어 있다. 독자는 이 책을 처음부터 끝까지 읽어도 되고, 지금 필요한 장을 펼쳐 하나의 요령만 가져가도 된다. 중요한 것은 읽은 뒤 자기 강의, 자기 회사, 자기 프로젝트에 적용할 문장 하나를 남기는 것이다.",
        "",
        "# 원천 독해 범위",
        "",
        f"- PPT 추출 슬라이드: {s['slides']:,}장",
        f"- Notion 관련 페이지: {s['notion_relevant_pages']:,}건",
        f"- ChatGPT conversation titles: {s['chatgpt_conversations']:,}건",
        f"- Daily summaries: {s['daily_summaries']:,}건",
        "- 새 API 스크랩 없음. 로컬 다운로드 자료만 사용.",
        "",
        "# 목차",
        "",
    ]
    for i, chapter in enumerate(CHAPTERS, 1):
        lines.append(f"{i}. {chapter.title}")
    current_part = None
    figure_i = 0
    for chapter_idx, chapter in enumerate(CHAPTERS, 1):
        if chapter.part != current_part:
            current_part = chapter.part
            lines.extend(["", '<div class="part-break"></div>', "", f"# {chapter.part}", ""])
            if assets:
                fig = assets[figure_i % len(assets)]
                figure_i += 1
                lines.extend([f"![{md(fig['caption'])}]({fig['path']})", f"<p class=\"caption\">{md(fig['caption'])}. 원천: {md(fig['source'])}</p>", ""])
        lines.extend(
            [
                "",
                '<div class="chapter-break"></div>',
                "",
                f"# {chapter_idx}. {chapter.title}",
                "",
                f"**핵심 문장:** {chapter.one_line}",
                "",
                f"**근거:** {', '.join(chapter.evidence)}",
                "",
                chapter.scene,
                "",
                f"{chapter.method} {chapter.tension} 이 장은 이 긴장을 숨기지 않고, 오히려 독자가 자기 현장에서 같은 판단을 해 볼 수 있도록 절마다 하나의 요령으로 나눈다.",
                "",
            ]
        )
        for section_idx, section in enumerate(chapter.sections, 1):
            fig = None
            if assets and section_idx in {3, 7}:
                fig = assets[figure_i % len(assets)]
                figure_i += 1
            lines.extend(section_text(chapter_idx, section_idx, chapter, section, fig))
    lines.extend(
        [
            "",
            '<div class="chapter-break"></div>',
            "",
            "# 맺음말: 책도 하나의 실습이다",
            "",
            "이 책은 완성된 결론이 아니라 작동하는 실습이다. 강의를 책으로 바꾸고, daily note를 요령으로 바꾸고, ChatGPT 질문을 목차로 바꾸고, PPT 그림을 장면으로 바꾸는 실습이다. 말라카식 바이브코딩은 코드를 빨리 쓰는 기술로 끝나지 않는다. 생각을 산출물로 바꾸고, 산출물을 다시 다음 생각으로 돌려보내는 운영체계다.",
            "",
            "책을 쓰는 일도 마찬가지다. 한 번에 완성하려고 하면 무겁다. 그러나 한 절을 하나의 요령으로 쓰고, 그 요령을 강의장과 회사와 기록의 장면에 연결하면 책은 조금씩 자란다. 이 방식이라면 강의는 책이 되고, 책은 다시 강의가 되고, 강의는 다시 회사의 변화를 만든다.",
            "",
            "다음 판에서 해야 할 일도 분명하다. 실제 독자에게 읽히고, 강의에서 써 보고, 회사의 AX 사례와 연결해 다시 고쳐야 한다. 그때도 원칙은 같다. 원문을 붙이지 말고 판단을 써라. 페이지를 엮지 말고 책을 써라. 도구를 자랑하지 말고 사람이 무엇을 더 잘 판단하게 되었는지 보여 줘라.",
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
  color: #111827;
  line-height: 1.66;
  font-size: 9.6pt;
}
body { margin: 0; }
.cover {
  min-height: 178mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 6mm solid #0f172a;
  padding-left: 12mm;
}
.cover h1 { font-size: 25pt; line-height: 1.16; margin: 0 0 8mm; }
.cover h2 { font-size: 13pt; font-weight: 500; color: #334155; line-height: 1.35; }
h1 {
  break-before: page;
  font-size: 18pt;
  line-height: 1.22;
  margin: 0 0 7mm;
  padding-bottom: 3mm;
  border-bottom: 1pt solid #111827;
}
h2 {
  font-size: 12.2pt;
  line-height: 1.32;
  margin: 0 0 4mm;
  color: #111827;
}
h3 {
  font-size: 10.3pt;
  margin: 5mm 0 1.8mm;
  break-after: avoid;
}
p { margin: 0 0 3.15mm; }
ul, ol { margin: 0 0 4mm 5mm; padding: 0; }
li { margin: 0 0 1.65mm; }
blockquote {
  margin: 1.5mm 0 4mm;
  padding-left: 4mm;
  border-left: 2.5pt solid #0f172a;
  color: #334155;
}
img {
  display: block;
  max-width: 100%;
  max-height: 82mm;
  margin: 2mm auto 1mm;
  border: 0.6pt solid #d1d5db;
}
.caption {
  text-align: center;
  color: #64748b;
  font-size: 7.8pt;
  margin: 0 0 4mm;
}
.lede {
  font-size: 10.4pt;
  font-weight: 600;
  color: #0f172a;
}
.book-page { break-before: page; }
.chapter-break { break-before: page; }
.part-break { break-before: page; }
strong { color: #0f172a; }
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


def pdf_pages(path: Path) -> int | None:
    try:
        out = subprocess.check_output(["pdfinfo", str(path)], text=True)
    except Exception:
        return None
    match = re.search(r"^Pages:\s+(\d+)$", out, re.M)
    return int(match.group(1)) if match else None


def write_all() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assets = extract_ppt_images()
    request_report = render_report(assets)
    toc = render_toc()
    book = render_book(assets)
    style = css()

    report_path = OUT / "request-report.md"
    toc_path = OUT / "expanded-toc.md"
    md_path = OUT / "malaka-vibecoding-lecture-to-book.md"
    html_path = OUT / "malaka-vibecoding-lecture-to-book.html"
    css_path = OUT / "malaka-vibecoding-lecture-to-book.css"
    pdf_path = OUT / "malaka-vibecoding-lecture-to-book.pdf"
    report_path.write_text(request_report, encoding="utf-8")
    toc_path.write_text(toc, encoding="utf-8")
    md_path.write_text(book, encoding="utf-8")
    css_path.write_text(style, encoding="utf-8")
    write_pdf(book, css_path, html_path, pdf_path, "강의는 어떻게 책이 되는가")

    leak_pattern = re.compile(r"rich_text|created_time|last_edited_time|formula string|plain_text|multi_select|checkbox|000Z", re.I)
    leak_count = len(leak_pattern.findall(book + toc + request_report))
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "request_report": str(report_path.resolve()),
        "expanded_toc": str(toc_path.resolve()),
        "book_md": str(md_path.resolve()),
        "book_html": str(html_path.resolve()),
        "book_pdf": str(pdf_path.resolve()),
        "book_pdf_pages": pdf_pages(pdf_path),
        "chapters": len(CHAPTERS),
        "sections": sum(len(c.sections) for c in CHAPTERS),
        "assets": assets,
        "source_stats": stats(),
        "raw_metadata_leak_count": leak_count,
        "api_scrape": False,
        "note": "Fresh authored Markdown/HTML/PDF book. Existing PDFs/PPTs were not stitched; PPTX media images were locally extracted as figures.",
    }
    summary_path = OUT / "rewrite-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_json"] = str(summary_path.resolve())
    return summary


def main() -> int:
    print(json.dumps(write_all(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
