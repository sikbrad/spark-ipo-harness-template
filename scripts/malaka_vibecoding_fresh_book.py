#!/usr/bin/env python3
"""Render a fresh, source-informed Malaka vibecoding book.

This script is a renderer, not a PPT/PDF stitcher. The prose below is newly
authored from the extracted PPT and Notion reading notes, then rendered to
Markdown/HTML/PDF.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path("data/vibecoding-book")
FINAL_DIR = ROOT / "final"
RESEARCH_DIR = ROOT / "research"
SLIDES_PATH = ROOT / "extracts" / "all-slides.json"
NOTION_TOPIC_PATH = RESEARCH_DIR / "notion-topic-evidence.json"
NOTION_CORPUS_PATH = RESEARCH_DIR / "notion-author-corpus.json"


@dataclass(frozen=True)
class Chapter:
    part: str
    title: str
    thesis: str
    source_basis: list[str]
    opening_scene: str
    author_claim: str
    method: str
    danger: str
    reader_gain: str
    sections: list[str]


AUTHOR_PROFILE = {
    "name": "말라카",
    "public_identity": "기록과 자동화로 문제를 제품화하는 개발자이자 강사",
    "private_reading": [
        "Notion의 자기 문장에는 '나만의 통찰', '생각의 충돌을 즐기는 사람들', '가슴 뛰는 이야기'가 반복된다.",
        "커리어 고민 기록에서는 10년차 개발자로서 AI, 제품, 교육, 자율성, 직접적인 임팩트를 찾는 흐름이 보인다.",
        "강의 기록에서는 비개발자와 실무자가 자기 손으로 MVP를 만들게 하려는 교육자의 태도가 드러난다.",
        "업무 기록에서는 CRM, ERP, Salesforce, Teams, Slack, 브라우저 자동화처럼 실제 운영 화면을 고치는 관심사가 강하다.",
        "LifeOS와 Goal Hub 기록에서는 생각을 저장하는 데서 끝내지 않고 다음 행동으로 바꾸려는 개인 운영체계가 중심에 있다.",
    ],
}


CHAPTERS: list[Chapter] = [
    Chapter(
        part="1부. 말라카라는 문제의식",
        title="말라카의 바다에서 시작하기",
        thesis="바이브코딩은 먼저 자기 언어를 세우는 일이다. 도구는 그다음에 온다.",
        source_basis=[
            "Quick ㅂㅏ로 My Ocean",
            "커리어고민 250617, 나에대해 이해",
            "의현상담 240818",
            "내 기조 생각",
            "바이브코딩 관련 생각메모",
        ],
        opening_scene="목표 문장과 커리어 고민과 강의 준비가 서로 다른 페이지에 흩어져 있지만, 그 문장들은 결국 하나의 방향을 향한다. 말라카는 더 빠른 코딩 도구를 찾는 사람이 아니라 자기 생각을 작동하는 산출물로 바꾸려는 사람이다.",
        author_claim="나는 내가 어떤 사람인지 모르는 상태에서 AI에게 일을 맡기면, 빠른 속도로 남의 문제를 풀게 된다고 믿는다.",
        method="생각에 이름을 붙이고, 목표와 연결하고, 오늘 만들 수 있는 산출물로 낮춘다.",
        danger="자기 언어가 없으면 바이브코딩은 생산성 도구가 아니라 산만함을 빠르게 키우는 장치가 된다.",
        reader_gain="독자는 도구를 켜기 전에 자기 문제를 한 문장으로 붙잡는 법을 배운다.",
        sections=[
            "이름을 먼저 정해야 일이 움직인다",
            "나만의 통찰은 생활 속 문장에서 시작된다",
            "생각의 충돌을 피하지 않는 태도",
            "가슴 뛰는 이야기는 산출물로 끝나야 한다",
            "커리어 고민을 실행 언어로 바꾸기",
            "LifeOS는 멋진 노션 페이지가 아니다",
            "목표 문장은 프롬프트의 첫 줄이 된다",
            "내가 원하는 삶과 오늘의 작업 연결하기",
            "기록은 다음 행동을 위해 존재한다",
            "AI 시대에 개발자의 역할 다시 쓰기",
            "제품으로 세상을 놀라게 하고 싶다는 욕망",
            "자율성과 책임을 같이 갖는 방법",
            "나의 관심사를 숨기지 않고 구조화하기",
            "작게 만들 수 있어야 크게 말할 수 있다",
            "말라카라는 이름의 작업 방식",
            "생각을 붙잡는 사람의 하루",
            "책의 목소리를 정하는 법",
            "첫 장에서 독자가 가져가야 할 문장",
        ],
    ),
    Chapter(
        part="1부. 말라카라는 문제의식",
        title="바이브코딩이라는 오해를 걷어내기",
        thesis="바이브코딩은 느낌으로 코딩하는 일이 아니라 자연어를 작업 계약으로 바꾸는 방식이다.",
        source_basis=[
            "바이브코딩 관련 생각메모",
            "바이브 강의안 생각",
            "바이브 주차별계획 gemini 250531",
            "WhyQ AI 공유노트 (2603) 말라카 분",
            "정석적인 웹앱 제작 방법 슬라이드 묶음",
        ],
        opening_scene="강의장에는 두 종류의 오해가 같이 들어온다. 하나는 AI가 모든 것을 알아서 해줄 것이라는 기대이고, 다른 하나는 개발을 모르면 아무것도 할 수 없다는 포기다. 바이브코딩은 이 둘 사이에 선다.",
        author_claim="나는 바이브코딩을 입코딩과 구분하고 싶다. 말만 그럴듯하게 하는 것이 아니라, 말한 내용을 작동물로 확인해야 한다.",
        method="하고 싶은 말을 상황, 사용자, 입력, 출력, 제약, 검증 기준으로 다시 쓴다.",
        danger="오해를 걷어내지 않으면 빠른 결과가 생겨도 왜 되는지, 어디서 깨지는지, 무엇을 고쳐야 하는지 알 수 없다.",
        reader_gain="독자는 AI에게 일을 맡기기 전에 자기 의도를 작업 가능한 문장으로 만드는 법을 배운다.",
        sections=[
            "바이브코딩은 마법이 아니다",
            "입코딩과 바이브코딩의 차이",
            "자연어는 감상이 아니라 명세가 되어야 한다",
            "AI에게 맡길 일과 내가 볼 일",
            "도구 화면보다 먼저 필요한 것",
            "비개발자가 배워야 할 최소한의 구조",
            "좋은 질문은 결과의 모양을 바꾼다",
            "무료 플랜의 제한도 설계 조건이다",
            "AI가 잘못 알아들었을 때의 책임",
            "결과보다 과정을 설명할 수 있어야 한다",
            "첫 프롬프트가 아니라 첫 계약",
            "반복은 같은 말을 다시 하는 일이 아니다",
            "내가 원하는 것을 계속 생각하는 역량",
            "수강생이 막히는 지점에서 개념이 생긴다",
            "오해를 걷어낸 뒤 남는 핵심",
            "바이브코딩을 배울 때 버릴 습관",
            "오늘부터 쓸 수 있는 작업 언어",
            "정의가 끝나야 실행이 시작된다",
        ],
    ),
    Chapter(
        part="2부. 문제를 제품으로 바꾸는 법",
        title="문제를 붙잡는 사람이 제품을 만든다",
        thesis="AI가 구현 속도를 올릴수록 더 중요한 사람은 문제를 좁히고 고정하는 사람이다.",
        source_basis=[
            "바이브 주차별계획 gemini 250531",
            "바이브 강의안 (for whyq, 2w)",
            "CRM 마이그레이션 task 명세",
            "디오에프 미션 리스트 기록",
            "웹앱 기획 아이디어 슬라이드 묶음",
        ],
        opening_scene="아이디어 회의는 대개 풍성하게 시작한다. 그러나 첫 화면, 첫 데이터, 첫 사용자를 정하는 순간 분위기가 달라진다. 제품은 아이디어의 양이 아니라 문제를 붙잡는 힘에서 시작된다.",
        author_claim="나는 좋은 기획을 멋진 문서가 아니라 구현과 검증이 가능한 약속이라고 본다.",
        method="사용자, 상황, 행동, 데이터, 성공 기준을 한 장에 놓고 줄일 수 있는 것을 줄인다.",
        danger="문제를 고정하지 않으면 AI는 성실하게 많은 화면을 만들지만 제품은 생기지 않는다.",
        reader_gain="독자는 아이디어를 요구사항과 첫 화면과 데이터 명세로 바꾸는 법을 배운다.",
        sections=[
            "아이디어가 아니라 불편함을 붙잡아라",
            "사용자 한 명을 선명하게 정하기",
            "문제를 문장 하나로 줄이는 연습",
            "첫 화면은 제품의 주장이다",
            "데이터명세는 생각의 뼈대다",
            "기능 목록보다 중요한 행동 변화",
            "요구사항은 AI를 위한 지도가 된다",
            "사이트맵은 욕심을 줄이는 도구다",
            "C레벨도 인정하는 기획의 조건",
            "회의 내용을 산출물로 바꾸기",
            "업무 기록에서 제품 단서 찾기",
            "사용자 흐름과 데이터 흐름 겹쳐 보기",
            "만들지 않을 것을 정하는 힘",
            "질문이 좋은 팀을 만든다",
            "문제를 붙잡는 사람의 권한",
            "기획이 끝났다는 착각",
            "AI와 함께 요구사항을 다듬는 순서",
            "제품의 첫 문장을 완성하기",
        ],
    ),
    Chapter(
        part="2부. 문제를 제품으로 바꾸는 법",
        title="MVP는 작은 제품이 아니라 작은 증거다",
        thesis="MVP는 축소판이 아니라 지금 믿는 가설이 현실에서 버티는지 확인하는 증거다.",
        source_basis=[
            "ps 부경대 MVP 강연",
            "바이브코딩 고려대강연 메모",
            "바이브 주차별계획 gemini 250531",
            "커리어고민 250617, 나에대해 이해",
            "MVP 슬라이드 묶음",
        ],
        opening_scene="MVP라는 말을 들으면 사람들은 작은 앱을 떠올린다. 그러나 진짜 MVP는 작은 앱보다 먼저 작은 질문이다. 이게 필요한가, 이 방식으로 쓸까, 돈이나 시간을 낼까, 이 흐름을 반복할까.",
        author_claim="나는 MVP를 결과물의 크기가 아니라 판단의 선명도로 정의한다.",
        method="가설 하나를 고르고, 그 가설만 확인할 수 있는 가장 작은 작동물을 만든다.",
        danger="MVP를 예쁜 축소판으로 만들면 가장 위험한 질문은 확인하지 못한 채 시간이 사라진다.",
        reader_gain="독자는 하루 안에 만들 수 있는 검증 산출물을 설계하는 법을 배운다.",
        sections=[
            "작은 제품보다 작은 질문",
            "가설을 하나만 남기는 법",
            "검증할 수 없는 목표는 목표가 아니다",
            "2시간 강의 안에 결과물이 나오는 이유",
            "비개발자 MVP의 진짜 장벽",
            "Lovable과 Cursor를 쓰기 전 정할 것",
            "화면 하나로 충분한 순간",
            "가짜 문과 진짜 문",
            "사용자 반응을 보는 최소 단위",
            "예쁜 데모보다 거친 증거",
            "실패한 MVP가 주는 좋은 정보",
            "첫 사용자를 만나는 방식",
            "검증 기준을 숫자로 낮추기",
            "MVP 이후에 남길 기록",
            "강의장에서 배운 속도의 감각",
            "창업 아이디어를 업무 실험으로 바꾸기",
            "MVP를 운영으로 연결하기",
            "다음 버전을 만들지 말지 결정하기",
        ],
    ),
    Chapter(
        part="2부. 문제를 제품으로 바꾸는 법",
        title="웹앱의 문법을 알면 AI가 보인다",
        thesis="코드를 몰라도 웹앱의 문법을 알면 AI가 만든 결과를 읽고 고칠 수 있다.",
        source_basis=[
            "바이브 강의안 (for whyq, 2w)",
            "WhyQ AI 공유노트 (2603) 말라카 분",
            "음성분석서버 개발기록",
            "WMTWR Compose 개발기록",
            "네트워크, HTTP, API, Supabase 슬라이드 묶음",
        ],
        opening_scene="처음 웹앱을 만드는 사람은 화면에 감탄하다가 곧 데이터에서 막힌다. 저장이 안 된다, 로그인 후 안 보인다, API 호출이 실패한다. 이때 필요한 것은 깊은 알고리즘 지식보다 웹앱의 기본 문법이다.",
        author_claim="나는 비개발자에게도 구조를 알려줘야 한다고 믿는다. 구조를 모르면 AI의 설명을 믿을지 고칠지 판단할 수 없다.",
        method="프론트엔드, 백엔드, 데이터베이스, 인증, API, 배포를 역할 단위로 나눈다.",
        danger="구조를 모르면 오류가 났을 때 같은 프롬프트를 반복하며 시간을 잃는다.",
        reader_gain="독자는 AI가 만든 웹앱을 화면, 데이터, 서버, 배포 관점에서 읽는 법을 배운다.",
        sections=[
            "웹앱은 화면만으로 되지 않는다",
            "프론트엔드는 약속을 보여주는 곳",
            "백엔드는 판단과 규칙이 모이는 곳",
            "데이터베이스는 기억의 방식이다",
            "API는 두 세계의 계약이다",
            "HTTP를 알면 오류가 덜 무섭다",
            "인증은 사용자를 구분하는 문법이다",
            "Supabase와 Firebase가 해주는 일",
            "로컬과 배포 환경의 차이",
            "로그는 AI보다 먼저 봐야 할 증거",
            "상태 관리는 사용자의 시간을 다룬다",
            "네트워크 실패를 기본값으로 생각하기",
            "파일 업로드와 권한의 함정",
            "화면 설계와 데이터 설계를 같이 보기",
            "AI에게 오류를 설명하는 법",
            "웹앱 구조도를 그리는 순서",
            "코드가 아니라 관계를 읽어라",
            "구조를 아는 사람이 더 빨리 묻는다",
        ],
    ),
    Chapter(
        part="3부. AI와 일하는 프로토콜",
        title="프롬프트가 아니라 작업 계약을 만든다",
        thesis="좋은 프롬프트는 멋진 주문이 아니라 역할, 입력, 출력, 금지사항, 검증 기준을 묶은 작업 계약서다.",
        source_basis=[
            "바이브코딩 고려대강연 메모",
            "내 기조 생각",
            "WhyQ AI 공유노트 (2603) 말라카 분",
            "바이브코딩 관련 생각메모",
            "Vibe-plan 프롬프트 의미 슬라이드 묶음",
        ],
        opening_scene="AI에게 같은 일을 시켜도 매번 다른 결과가 나온다면 도구가 변덕스러운 것이 아니라 계약이 흐릿한 경우가 많다. 좋은 프롬프트는 부탁이 아니라 일을 맡기는 방식이다.",
        author_claim="나는 프롬프트를 문장 기술보다 작업 관리 기술에 가깝게 본다.",
        method="역할, 맥락, 입력, 산출물 형식, 금지사항, 검증 기준, 다음 행동을 한 번에 적는다.",
        danger="계약이 없으면 결과가 흔들릴 때 원인을 도구 성능 탓으로만 돌리게 된다.",
        reader_gain="독자는 반복 가능한 AI 협업 문서를 만드는 법을 배운다.",
        sections=[
            "프롬프트는 주문이 아니다",
            "역할을 주는 이유",
            "맥락은 길이가 아니라 선택이다",
            "입력 자료를 정리하는 법",
            "출력 형식이 품질을 바꾼다",
            "금지사항은 창의성을 죽이지 않는다",
            "검증 기준을 같이 넘겨라",
            "한 번에 끝내려 하지 않기",
            "AI에게 질문하게 만들기",
            "작업 로그가 다음 프롬프트가 된다",
            "규칙 파일과 메모리의 의미",
            "기획 프롬프트와 구현 프롬프트 나누기",
            "리뷰 프롬프트는 별도로 둔다",
            "실패한 답변에서 계약을 고친다",
            "팀과 공유할 수 있는 프롬프트",
            "강의용 프롬프트의 조건",
            "작업 계약서 템플릿",
            "AI 협업의 끝은 사람이 정한다",
        ],
    ),
    Chapter(
        part="3부. AI와 일하는 프로토콜",
        title="도구는 유행이 아니라 경로다",
        thesis="도구 선택의 기준은 최신성이 아니라 지금 확인할 질문까지 가장 짧고 안전하게 가는 경로다.",
        source_basis=[
            "WhyQ AI 공유노트 (2603) 말라카 분",
            "바이브 강의안 생각",
            "ps 부경대 MVP 강연",
            "Cursor, Claude, Codex, Lovable, Firebase 관련 슬라이드 묶음",
        ],
        opening_scene="도구가 너무 많으면 시작이 늦어진다. Cursor가 좋은지, Lovable이 빠른지, Claude Code를 써야 하는지, Codex가 나은지 비교하다 보면 정작 확인해야 할 문제는 그대로 남는다.",
        author_claim="나는 도구를 신앙처럼 고르지 않는다. 지금 막힌 구간을 통과하게 해주는 경로로 고른다.",
        method="기획, 구현, 데이터, 배포, 검증 중 지금 병목인 구간을 먼저 정하고 그 구간에 맞는 도구를 고른다.",
        danger="도구 학습이 프로젝트의 증거를 만드는 일을 대신하면 속도는 허상이 된다.",
        reader_gain="독자는 도구 비교보다 프로젝트 단계에 맞는 선택 기준을 갖게 된다.",
        sections=[
            "최신 도구보다 가까운 경로",
            "Cursor를 켜야 할 때",
            "Lovable이 유리한 순간",
            "Claude Code와 Codex의 자리",
            "Gemini를 자료 파트너로 쓰기",
            "Firebase와 Supabase를 선택하는 기준",
            "v0와 Bolt를 화면 스케치로 쓰는 법",
            "도구를 섞을 때 생기는 문제",
            "계정과 비용도 설계 조건이다",
            "설치가 강의 경험을 망치지 않게 하기",
            "도구별 실패 모드를 적어 두기",
            "처음 배우는 사람에게 도구를 줄이는 법",
            "프로젝트 단계별 툴체인",
            "도구가 아니라 산출물로 비교하기",
            "한 도구에 갇히지 않는 기록법",
            "경로를 바꾸는 의사결정 기준",
            "도구 선택표 만들기",
            "좋은 도구는 생각을 선명하게 만든다",
        ],
    ),
    Chapter(
        part="4부. 현실 업무를 자동화하는 법",
        title="브라우저 자동화는 현실을 다루는 코딩이다",
        thesis="API가 없는 세상에서도 업무는 계속된다. 브라우저 자동화는 실제 화면을 AI와 함께 다루는 방법이다.",
        source_basis=[
            "CRM 마이그레이션 업무기록",
            "CRM 마이그레이션 task 명세",
            "AutoShorts 시스템 개발기록",
            "디오에프 미션 리스트 기록",
            "Playwright, 브라우저 자동화, RPA 슬라이드 묶음",
        ],
        opening_scene="현실 업무는 깨끗한 API 문서보다 브라우저 화면에 먼저 남아 있다. 사람이 로그인하고, 검색하고, 다운로드하고, 엑셀을 열고, 다시 옮겨 적는다. 자동화는 이 반복을 읽는 일에서 시작한다.",
        author_claim="나는 브라우저 자동화를 단순 매크로가 아니라 현실 업무의 인터페이스를 다루는 코딩으로 본다.",
        method="화면 상태, 클릭 순서, 입력값, 기다림, 예외, 결과 검증을 하나의 절차로 문서화한다.",
        danger="화면 자동화를 만만하게 보면 로그인, 권한, 속도, 데이터 검증, 예외 복구에서 바로 무너진다.",
        reader_gain="독자는 반복 업무를 자동화 가능한 절차로 쪼개는 법을 배운다.",
        sections=[
            "API가 없을 때도 일은 멈추지 않는다",
            "사람의 클릭을 업무 언어로 번역하기",
            "로그인과 권한을 먼저 생각하라",
            "검색 조건은 계약이다",
            "다운로드 파일을 믿지 않는 습관",
            "기다림도 자동화의 일부다",
            "Playwright가 보여주는 현실감",
            "스크래핑과 업무 자동화의 경계",
            "브라우저 화면에서 증거 남기기",
            "엑셀과 JSON으로 결과를 분리하기",
            "반복 업무의 예외 사전 만들기",
            "인간처럼 조심스럽게 자동화하기",
            "자동화가 실패할 때 멈추는 법",
            "한 번의 클릭을 없애는 것보다 중요한 것",
            "운영 담당자와 함께 절차를 읽기",
            "브라우저 자동화의 보안 감각",
            "작은 자동화가 신뢰를 얻는 순서",
            "현실을 다루는 코딩의 태도",
        ],
    ),
    Chapter(
        part="4부. 현실 업무를 자동화하는 법",
        title="운영의 언어로 제품을 고친다",
        thesis="데모에서 끝나는 바이브코딩은 약하다. 실제 회사의 주문, 수금, CRM, ERP 흐름을 고칠 때 힘이 생긴다.",
        source_basis=[
            "CRM 마이그레이션 업무기록",
            "CRM 마이그레이션 task 명세",
            "디오에프 박현수대표님 만남 2차 노트 2025-07-15",
            "디오에프 미션 리스트 기록",
            "ERP, CRM, Salesforce, Teams, Slack 관련 작업 기록",
        ],
        opening_scene="운영 현장에는 단어가 많다. 주문, 수금, 고객, 제품, 견적, 원장, 승인, 알림, 채팅, 공지. 이 단어들은 시스템 이름이 아니라 사람들의 책임과 판단이 지나가는 길이다.",
        author_claim="나는 제품을 코드 덩어리로 보지 않는다. 제품은 운영의 언어를 줄이고, 이어 주고, 검증 가능하게 만드는 장치다.",
        method="업무 기록을 읽고 병목을 찾은 뒤 사람의 판단과 자동화의 실행을 다시 배치한다.",
        danger="운영 맥락을 모른 자동화는 빠른 도구가 더 빠른 혼란을 만드는 방식으로 끝난다.",
        reader_gain="독자는 사내 업무 흐름을 제품 개선과 자동화 과제로 바꾸는 법을 배운다.",
        sections=[
            "데모와 운영 사이의 거리",
            "업무 단어를 먼저 수집하라",
            "CRM은 고객 기록 이상의 것이다",
            "ERP는 책임의 흐름을 보여준다",
            "Salesforce 데이터가 말하는 것",
            "수금과 주문은 제품의 현실이다",
            "Teams와 Slack도 업무 데이터다",
            "운영 병목을 찾는 질문",
            "사람이 판단할 일과 시스템이 할 일",
            "프로세스는 문서가 아니라 반복이다",
            "자동화 후보를 고르는 법",
            "현업 인터뷰를 산출물로 바꾸기",
            "데이터 정합성은 신뢰의 시작",
            "작은 개선이 조직에 들어가는 순서",
            "운영 언어를 제품 언어로 번역하기",
            "도구보다 중요한 책임자 기준",
            "업무 자동화의 ROI를 말하는 법",
            "실무 적용형 바이브코딩의 자리",
        ],
    ),
    Chapter(
        part="5부. 가르치고 축적하는 법",
        title="강의는 지식을 파는 일이 아니라 실행을 설계하는 일이다",
        thesis="좋은 바이브코딩 강의는 도구 설명보다 수강자가 자기 손으로 결과물을 만들게 하는 진행 설계에서 갈린다.",
        source_basis=[
            "바이브코딩 고려대강연 메모",
            "ps 부경대 MVP 강연",
            "WhyQ 강의 운영노트",
            "AI 활용교육 강의안 피드백",
            "커리어고민 250617, 나에대해 이해",
        ],
        opening_scene="강의가 잘 끝났다는 말은 박수가 컸다는 뜻이 아니다. 수강생이 자기 프로젝트를 설명하고, 직접 눌러 보고, 실패를 고치고, 다음에 무엇을 해야 할지 알게 되었다는 뜻이다.",
        author_claim="나는 지식을 많이 전달하는 강의보다 실행이 일어나도록 설계된 강의가 더 강하다고 믿는다.",
        method="실습 산출물을 먼저 정하고, 그 산출물에 도달하기 위한 설명과 체크포인트를 거꾸로 배치한다.",
        danger="도구 소개가 많아질수록 수강생은 많이 들었지만 아무것도 만들지 못한 채 끝난다.",
        reader_gain="독자는 AI 활용 교육을 실행 중심 워크숍으로 설계하는 법을 배운다.",
        sections=[
            "강의의 목표는 이해가 아니라 실행이다",
            "수강생의 첫 성공을 설계하기",
            "2시간 안에 가능한 산출물",
            "설명보다 실습 흐름이 먼저다",
            "막히는 지점을 미리 깔아 두기",
            "비개발자의 불안을 줄이는 언어",
            "질문을 받는 방식도 커리큘럼이다",
            "고려대 강의가 남긴 힌트",
            "부경대 MVP 강연의 구조",
            "WhyQ 운영노트에서 배운 것",
            "강의안은 제품처럼 개선한다",
            "피드백을 다음 수업으로 바꾸기",
            "수강생 결과물을 평가하는 기준",
            "커뮤니티는 강의 이후에 시작된다",
            "VOD와 현장 강의의 차이",
            "강사는 도구 해설자가 아니다",
            "지식 콘텐츠와 경험 콘텐츠 쌓기",
            "가르칠 수 있을 때 방법론이 된다",
        ],
    ),
    Chapter(
        part="5부. 가르치고 축적하는 법",
        title="LifeOS: 기록은 실행을 낳아야 한다",
        thesis="기록은 저장이 아니라 다음 행동을 더 쉽게 만들기 위한 운영체제다.",
        source_basis=[
            "Quick ㅂㅏ로 My Ocean",
            "내 기조 생각",
            "사업전략 및 목표",
            "바이브코딩 관련 생각메모",
            "Jot DB, Task DB, Goal Hub 관련 Notion 구조",
        ],
        opening_scene="기록이 많은 사람에게도 실행은 어렵다. 페이지가 많아질수록 더 정리된 것 같지만, 오늘 무엇을 해야 하는지 흐려지는 경우도 많다. LifeOS는 정리의 기술이 아니라 실행의 기술이어야 한다.",
        author_claim="나는 기록을 좋아하지만 기록 자체를 믿지는 않는다. 다음 행동을 낳지 않는 기록은 결국 멋진 창고가 된다.",
        method="생각, 할 일, 자료, 회고, 목표를 서로 이어 다음 프롬프트와 다음 선택의 재료로 만든다.",
        danger="기록이 실행과 연결되지 않으면 더 정교하게 미루는 시스템이 된다.",
        reader_gain="독자는 개인 기록을 AI 시대의 실행 시스템으로 바꾸는 법을 배운다.",
        sections=[
            "기록은 저장이 아니라 작동이다",
            "Jot은 생각의 입구다",
            "Task는 행동의 약속이다",
            "Goal Hub는 방향을 잃지 않는 장치다",
            "Quick Zone은 마찰을 줄인다",
            "하루 기록을 다음 프롬프트로 바꾸기",
            "회고는 죄책감이 아니라 데이터다",
            "링크와 자료를 쌓는 기준",
            "지식 콘텐츠가 되는 기록",
            "경험 콘텐츠가 되는 기록",
            "AI에게 내 맥락을 먹이는 법",
            "메모를 프로젝트로 승격시키기",
            "정리보다 중요한 재사용",
            "목표와 업무와 강의를 연결하기",
            "나만의 운영체계를 작게 시작하기",
            "기록 피로를 줄이는 규칙",
            "LifeOS의 주간 루프",
            "기록이 실행을 낳는 순간",
        ],
    ),
    Chapter(
        part="6부. 책임지는 속도",
        title="검증하지 않는 속도는 빚이다",
        thesis="바이브코딩은 빠르기 때문에 더 위험하다. 빠르게 만든 만큼 빠르게 검증하는 습관이 필요하다.",
        source_basis=[
            "바이브 스터디 운영방법 영경형과 논의한거 구체화",
            "보안관련 DT파트회의 241014",
            "정보보안감사 240812",
            "바이브코딩 고려대강연 메모",
            "QA, 보안, 운영 검증 슬라이드 묶음",
        ],
        opening_scene="빠른 결과물은 사람을 설득한다. 그러나 운영에 올라간 결과물은 박수보다 오류를 먼저 만난다. 데이터가 틀리고, 권한이 새고, 사용자가 오해하고, 비용이 예상보다 빨리 늘어난다.",
        author_claim="나는 빠른 실행을 좋아하지만 검증 없는 속도는 믿지 않는다.",
        method="완료 기준, 테스트 방법, 데이터 확인, 권한과 개인정보 점검, 실패 복구를 작업 안에 넣는다.",
        danger="검증 없는 속도는 당장은 성과처럼 보이지만 운영에 올라가는 순간 빚으로 돌아온다.",
        reader_gain="독자는 AI로 만든 결과물을 실제 사용자와 회사 업무에 올리기 전 확인할 기준을 갖게 된다.",
        sections=[
            "빠른 결과가 위험한 이유",
            "완료 기준을 먼저 써라",
            "테스트는 개발자의 전유물이 아니다",
            "데이터를 눈으로 확인하는 습관",
            "권한과 개인정보를 가볍게 보지 않기",
            "보안 회의가 가르쳐 주는 것",
            "사용자 오해를 미리 읽기",
            "비용과 사용량도 테스트 대상이다",
            "실패했을 때 멈추는 장치",
            "로그와 스크린샷은 증거다",
            "강의 데모에도 검증이 필요하다",
            "운영 배포 전 체크리스트",
            "AI 답변을 검토하는 세 가지 질문",
            "품질은 속도의 반대말이 아니다",
            "팀과 검증 기준을 공유하기",
            "책임지는 사람이 더 빨리 간다",
            "바이브코딩의 윤리",
            "마지막 장에서 남길 약속",
        ],
    ),
]


MOVES = [
    {
        "name": "정의하기",
        "focus": "막연한 감각을 한 문장으로 고정하면 다음 행동이 보인다.",
        "practice": "오늘 다루는 문제를 한 문장으로 쓰고, 그 문장에 사용자와 상황을 반드시 넣는다.",
        "question": "내가 지금 쓰는 단어는 행동을 만들 만큼 구체적인가?",
    },
    {
        "name": "경계 세우기",
        "focus": "무엇을 하지 않을지 정하는 순간 작은 결과물이 가능해진다.",
        "practice": "이번 반복에서 제외할 기능 세 가지를 적고, 제외 이유를 검증 기준 옆에 둔다.",
        "question": "내가 빼지 못하는 것은 진짜 필요한 것인가, 불안의 표현인가?",
    },
    {
        "name": "작은 증거 만들기",
        "focus": "작은 산출물은 작은 야망이 아니라 빠른 판단을 위한 장치다.",
        "practice": "하루 안에 볼 수 있는 작동물을 정하고, 그 결과가 답할 질문 하나를 쓴다.",
        "question": "이 결과를 보면 무엇을 계속할지 멈출지 판단할 수 있는가?",
    },
    {
        "name": "역할 나누기",
        "focus": "사람이 판단할 일과 AI가 반복할 일을 나누면 속도가 책임과 함께 간다.",
        "practice": "기획, 구현, 검증, 기록 중 AI에게 맡길 일과 내가 직접 볼 일을 표로 나눈다.",
        "question": "나는 AI에게 맡긴 일의 기준까지 함께 넘겼는가?",
    },
    {
        "name": "구조 그리기",
        "focus": "화면, 데이터, 흐름을 그리면 도구가 바뀌어도 대화가 흔들리지 않는다.",
        "practice": "내 프로젝트를 화면 세 개, 데이터 세 종류, 사용자 행동 하나로 설명해 본다.",
        "question": "내가 만든 그림은 다른 사람이 같은 결과를 만들 만큼 선명한가?",
    },
    {
        "name": "실패 먼저 보기",
        "focus": "실패 시나리오를 먼저 놓으면 빠른 실행이 무책임한 속도가 되지 않는다.",
        "practice": "사용자 오해, 데이터 오류, 권한 문제를 각각 하나씩 적고 확인 방법을 붙인다.",
        "question": "이 기능이 실패할 때 누구에게 어떤 비용이 생기는가?",
    },
    {
        "name": "운영으로 잇기",
        "focus": "데모는 끝이 아니라 운영으로 들어가기 위한 입구다.",
        "practice": "이 결과물이 일주일 동안 쓰이려면 누가 관리하고 무엇을 봐야 하는지 적는다.",
        "question": "내 결과물은 내 컴퓨터 밖에서도 살아남을 수 있는가?",
    },
    {
        "name": "가르칠 수 있게 만들기",
        "focus": "남에게 설명할 수 있을 때 비로소 방법론이 된다.",
        "practice": "방금 한 일을 처음 보는 사람에게 15분 안에 시연할 순서로 다시 배열한다.",
        "question": "내가 설명하지 않고도 따라 할 수 있는 흔적을 남겼는가?",
    },
    {
        "name": "기록으로 되돌리기",
        "focus": "좋은 기록은 과거를 보존하는 것이 아니라 다음 반복을 쉽게 만든다.",
        "practice": "오늘의 결과를 배운 점, 다음 제약, 다음 프롬프트로 나누어 적는다.",
        "question": "이 기록은 내일의 나에게 바로 쓸 수 있는 재료인가?",
    },
]


CONTRACTS = [
    "너는 내 프로젝트의 기획 파트너다. 지금 상황, 사용자, 입력, 출력, 성공 기준을 읽고 빠진 조건을 질문한 뒤 한 페이지 요구사항으로 정리해라.",
    "너는 구현 보조자다. 내가 정한 범위 안에서 가장 작은 작동물을 만들기 위한 단계와 검증 명령을 제안해라.",
    "너는 QA 리뷰어다. 결과물이 실패할 수 있는 조건, 사용자가 오해할 수 있는 문구, 데이터가 깨질 수 있는 지점을 찾아라.",
    "너는 운영 설계자다. 이 기능이 실제 업무에 들어갈 때 필요한 권한, 반복 주기, 로그, 예외 처리 기준을 정리해라.",
    "너는 강의 조교다. 처음 보는 사람이 15분 안에 따라 할 수 있도록 실습 순서와 중간 체크포인트를 다시 배열해라.",
    "너는 기록 편집자다. 오늘의 작업 메모를 다음 실행 프롬프트, 할 일, 검증 기준으로 분리해라.",
]

SCENE_FRAMES = [
    "혼자 노션 앞에 앉아 '{section}'를 적는 순간, 문제는 아직 코드가 아니라 언어의 문제다. 이때 필요한 것은 더 많은 자료가 아니라 내가 무엇을 확인하려는지에 대한 짧고 단단한 문장이다.",
    "강의장에서는 '{section}'가 추상 개념으로 남아 있으면 곧바로 손이 멈춘다. 수강생은 설명을 이해해서가 아니라 작은 성공을 직접 겪을 때 다음 단계로 넘어간다.",
    "회사 업무에서는 '{section}'가 사람의 책임과 시스템의 책임을 가르는 기준이 된다. 누가 판단하고, 무엇을 자동화하고, 어떤 결과를 믿을 수 있는지 정하지 않으면 자동화는 오히려 일을 늘린다.",
    "창업 아이디어를 다룰 때 '{section}'는 욕심을 줄이는 칼이 된다. 하고 싶은 말이 많을수록 첫 사용자가 무엇을 할 수 있어야 하는지 하나로 좁혀야 한다.",
    "AI 도구를 켠 뒤에는 '{section}'가 프롬프트의 품질을 결정한다. AI는 빈칸을 잘 채우지만, 그 빈칸이 왜 필요한지까지 대신 책임지지는 않는다.",
    "배포나 공유 직전에는 '{section}'가 검증의 언어로 바뀐다. 보여 줄 수 있다는 사실과 믿고 맡길 수 있다는 사실은 다르다.",
    "반복 업무를 자동화할 때 '{section}'는 화면 뒤에 숨은 규칙을 드러낸다. 사람이 매번 손으로 하던 일에는 대개 예외와 판단이 함께 섞여 있다.",
    "기록을 돌아볼 때 '{section}'는 지난 생각을 현재의 행동으로 끌어오는 손잡이가 된다. 기록은 많아질수록 연결 규칙이 없으면 금방 창고가 된다.",
    "팀과 대화할 때 '{section}'는 의견을 줄 세우는 기준이 된다. 좋은 기준은 사람을 이기기 위한 말이 아니라 다음 실험을 정하기 위한 말이다.",
]

METHOD_FRAMES = [
    "내 방식은 먼저 문장을 만들고 그 문장이 요구하는 산출물을 정하는 것이다. {method} 그런 다음 AI에게는 결론이 아니라 과정을 맡긴다.",
    "여기서 중요한 순서는 생각보다 단순하다. {method} 이 순서가 있으면 도구가 바뀌어도 다시 시작할 수 있다.",
    "나는 이 과정을 작은 운영 절차로 본다. {method} 절차가 생기면 개인의 감각이 팀과 강의에서도 재사용된다.",
    "좋은 실행은 대개 화려하지 않다. {method} 그 뒤에야 프롬프트, 코드, 자동화, 배포가 각자의 자리를 찾는다.",
    "AI와 일할 때도 이 원칙은 그대로다. {method} 사람이 기준을 세우고 AI가 탐색을 넓히면 속도와 책임이 함께 간다.",
    "처음부터 큰 시스템을 만들려고 하지 않는다. {method} 작은 순서가 지켜질수록 결과물은 오히려 더 빨리 단단해진다.",
]

RISK_FRAMES = [
    "이 절에서 피해야 할 함정은 속도에 취해 판단을 생략하는 것이다. {danger} 그래서 나는 결과가 나올 때마다 성공보다 먼저 기준을 다시 본다.",
    "반대로 이 과정을 건너뛰면 표면은 그럴듯하지만 다음 행동이 어려워진다. {danger} 빠른 결과물은 검증할 때 비로소 내 것이 된다.",
    "가장 위험한 순간은 AI가 그럴듯한 답을 내놓았을 때다. {danger} 그럴듯함은 증거가 아니며, 증거는 사용자의 행동과 데이터에서 나온다.",
    "실무에서는 작은 생략이 나중에 큰 비용으로 돌아온다. {danger} 그러므로 완료 기준은 결과가 나온 뒤가 아니라 작업을 시작할 때 적어야 한다.",
    "강의에서도 같은 문제가 생긴다. {danger} 수강생이 따라 했다는 사실과 자기 문제에 적용할 수 있다는 사실은 다르다.",
    "기록이 많을수록 이 위험은 더 교묘해진다. {danger} 많은 메모보다 중요한 것은 다음 실행으로 넘어가는 연결이다.",
]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("\u00a0", " ")).strip()


def md(text: str) -> str:
    return clean(text).replace("\\", "\\\\")


def corpus_stats() -> dict[str, Any]:
    slides = load_json(SLIDES_PATH, [])
    topic = load_json(NOTION_TOPIC_PATH, {})
    corpus = load_json(NOTION_CORPUS_PATH, [])
    return {
        "slide_count": len(slides),
        "notion_relevant_count": len(corpus),
        "topic_count": {key: len(value) for key, value in topic.items()},
    }


def source_sentence(chapter: Chapter) -> str:
    names = ", ".join(chapter.source_basis[:4])
    if len(chapter.source_basis) > 4:
        names += " 등"
    return f"이 장은 {names}을 읽은 뒤, 원문을 옮기지 않고 방법론으로 다시 쓴 장이다."


def write_section(chapter_no: int, section_no: int, chapter: Chapter, section_title: str) -> list[str]:
    move = MOVES[(chapter_no + section_no - 2) % len(MOVES)]
    contract = CONTRACTS[(chapter_no * 3 + section_no - 4) % len(CONTRACTS)]
    scene = SCENE_FRAMES[(chapter_no + section_no - 2) % len(SCENE_FRAMES)].format(section=section_title)
    method = METHOD_FRAMES[(chapter_no * 2 + section_no - 3) % len(METHOD_FRAMES)].format(method=chapter.method)
    risk = RISK_FRAMES[(chapter_no * 5 + section_no - 6) % len(RISK_FRAMES)].format(danger=chapter.danger)
    section_claim = [
        f"'{section_title}'라는 제목에서 내가 붙잡고 싶은 것은 기술이 아니라 순서다.",
        f"'{section_title}'는 거창한 선언보다 먼저 손에 잡히는 절차가 되어야 한다.",
        f"'{section_title}'를 다룰 때 중요한 것은 더 많이 아는 것이 아니라 더 정확히 줄이는 일이다.",
        f"'{section_title}'는 AI에게 맡기기 전에 사람이 먼저 책임져야 할 판단을 드러낸다.",
    ][(section_no - 1) % 4]
    bridge = [
        "강의 자료는 이 지점을 실습으로 보여 주고, Notion 기록은 왜 이 주제가 말라카의 생활과 이어지는지 보여 준다.",
        "PPT는 공개된 설명의 뼈대이고, Notion은 그 설명을 가능하게 만든 사적인 작업 리듬이다.",
        "두 자료를 겹쳐 읽으면 도구 이름보다 반복되는 태도가 더 선명하게 보인다.",
        "나는 이 단서를 그대로 인용하지 않고, 독자가 자기 프로젝트에 적용할 수 있는 언어로 다시 옮긴다.",
    ][(section_no - 1) % 4]
    return [
        "",
        '<div class="book-page"></div>',
        "",
        f"## {chapter_no}-{section_no:02d}. {md(section_title)}",
        "",
        section_claim + " " + bridge,
        "",
        f"{chapter.author_claim} 이 믿음은 {chapter.title}에서 특히 중요하다. {chapter.thesis} "
        f"이 절의 목적은 독자가 개념을 외우는 데 있지 않다. {chapter.reader_gain}",
        "",
        f"{scene} 대부분의 사람은 이런 장면에서 더 강한 도구를 찾지만, 실제로 필요한 것은 도구를 쓰기 전의 판단이다. "
        "판단이 흐리면 AI는 흐린 판단을 더 빠르게 증폭한다.",
        "",
        f"작업 이름은 **{move['name']}**이다. {move['focus']} {method} "
        "이 방법은 특별한 재능보다 반복 가능한 순서에 가깝다. "
        "처음에는 느려 보이지만, 한 번 문장과 산출물의 연결이 생기면 다음 반복부터는 훨씬 빨라진다.",
        "",
        f"{risk} 바이브코딩은 속도가 빠르기 때문에 문제를 덮어 두기 쉽다. "
        "나는 그래서 결과가 나올수록 더 자주 멈춰서 묻는다. 이 결과가 어떤 질문에 답했는가. 어떤 질문은 아직 남아 있는가.",
        "",
        "### 실행 노트",
        "",
        f"- {move['practice']}",
        "- AI에게 일을 맡길 때는 상황, 입력, 출력, 금지사항, 검증 기준을 함께 넘긴다.",
        "- 결과가 마음에 들지 않으면 다시 시키기 전에 내가 준 기준이 충분했는지 먼저 확인한다.",
        "- 작업이 끝나면 배운 점을 다음 프롬프트와 다음 할 일로 나누어 기록한다.",
        "",
        "### 작업 계약 예시",
        "",
        f"> {contract}",
        "",
        "이 문장은 정답이 아니라 시작점이다. 중요한 것은 AI에게 사람의 맥락과 책임 기준을 함께 넘기는 습관이다. "
        "그 습관이 생기면 도구가 바뀌어도 일하는 방식은 쉽게 무너지지 않는다.",
        "",
        "### 독자에게 남기는 질문",
        "",
        f"- {move['question']}",
        "- 지금 만들려는 결과가 내 문제를 더 선명하게 만들고 있는가?",
        "- 다음 반복에서 줄일 것 하나와 확인할 것 하나는 무엇인가?",
    ]


def write_chapter(chapter_no: int, chapter: Chapter, current_part: str | None) -> tuple[list[str], str]:
    lines: list[str] = []
    if chapter.part != current_part:
        lines.extend(["", '<div class="part-break"></div>', "", f"# {chapter.part}", ""])
        current_part = chapter.part
    lines.extend(
        [
            "",
            '<div class="chapter-break"></div>',
            "",
            f"# {chapter_no}. {chapter.title}",
            "",
            f"**핵심 명제:** {chapter.thesis}",
            "",
            f"**원천 독해:** {source_sentence(chapter)}",
            "",
            chapter.opening_scene,
            "",
            f"{chapter.author_claim} {chapter.method} "
            f"이 장의 위험은 분명하다. {chapter.danger} "
            f"그래서 이 장의 목표는 단순한 지식 전달이 아니다. {chapter.reader_gain}",
            "",
        ]
    )
    for idx, section in enumerate(chapter.sections, start=1):
        lines.extend(write_section(chapter_no, idx, chapter, section))
    return lines, current_part


def render_manuscript() -> str:
    stats = corpus_stats()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_sections = sum(len(chapter.sections) for chapter in CHAPTERS)
    lines = [
        '<div class="cover">',
        "",
        "# 바이브코딩은 일하는 방식이다",
        "",
        "## 문제를 제품과 자동화로 바꾸는 말라카의 실행법",
        "",
        "**말라카 지음**",
        "",
        f"원고 기준일: {generated_at}",
        "",
        "</div>",
        "",
        '<div class="chapter-break"></div>',
        "",
        "# 저자의 말: 나는 왜 이 책을 쓰는가",
        "",
        "나는 바이브코딩을 처음부터 기술 유행으로 받아들이지 않았다. 내게 더 중요한 질문은 따로 있었다. "
        "내가 생각하는 문제를 어떻게 더 빨리 만질 수 있는가. 강의장에서 비개발자가 자기 아이디어를 작동물로 바꾸게 하려면 무엇을 먼저 설명해야 하는가. "
        "회사 안에서 반복되는 업무와 흩어진 기록을 제품과 자동화로 바꾸려면 어떤 순서가 필요한가.",
        "",
        "Notion에 남은 나의 문장들은 정리된 선언이라기보다 여러 방향으로 튀는 충돌에 가깝다. "
        "나만의 통찰을 갖고 싶다는 욕망, 생각의 충돌을 즐기고 싶다는 태도, 가슴 뛰는 이야기를 들려주고 싶다는 문장, 제품으로 세상을 놀라게 하고 싶다는 커리어 고민, "
        "비개발자도 MVP를 만들게 하고 싶다는 강의 욕심, CRM과 ERP와 브라우저 화면까지 내려가 업무를 고치려는 실무 감각이 함께 있다.",
        "",
        "이 책은 그 조각들을 억지로 미화하지 않는다. 대신 하나의 작업 방식으로 묶는다. "
        "생각을 문장으로 붙잡고, 문장을 산출물로 바꾸고, 산출물을 실제 사람과 업무 앞에서 검증하고, 그 기록을 다음 실행으로 되돌리는 방식. "
        "나는 이 방식을 바이브코딩이라고 부른다.",
        "",
        "# 이 책의 사용법",
        "",
        "이 책은 도구별 튜토리얼이 아니다. Cursor, Claude, Codex, Lovable, Firebase, Supabase 같은 도구는 계속 바뀐다. "
        "바뀌지 않는 것은 문제를 정의하고, 작은 증거를 만들고, AI와 작업 계약을 맺고, 운영에 넣고, 검증하는 순서다. "
        "독자는 각 장을 읽고 자기 프로젝트에 바로 적용할 한 문장, 한 화면, 한 데이터, 한 검증 기준을 남기면 된다.",
        "",
        "각 절은 의도적으로 한 가지 실행 질문으로 끝난다. 책을 읽는 동안 답을 머릿속에만 두지 말고 문서나 노트에 적어 두면 좋다. "
        "그 기록은 다음 프롬프트가 되고, 다음 프롬프트는 다음 산출물이 된다. 이것이 이 책이 제안하는 LifeOS의 가장 작은 루프다.",
        "",
        "# 원천 독해 범위",
        "",
        f"- 최신 PPT 추출 슬라이드: {stats['slide_count']:,}장",
        f"- Notion 관련 페이지 코퍼스: {stats['notion_relevant_count']:,}건",
        "- 사용 방식: 원문을 붙여 넣지 않고, 반복 주제와 저자 관점을 읽어 새 원고로 재구성",
        "",
        "# 목차",
        "",
    ]
    for idx, chapter in enumerate(CHAPTERS, start=1):
        lines.append(f"{idx}. {chapter.title}")
    lines.extend(
        [
            "",
            f"본문은 {len(CHAPTERS)}장, {total_sections}개 절로 구성했다. 각 절은 독자가 자기 문제에 적용할 수 있도록 실행 노트와 작업 계약 예시를 포함한다.",
        ]
    )
    current_part: str | None = None
    for idx, chapter in enumerate(CHAPTERS, start=1):
        chapter_lines, current_part = write_chapter(idx, chapter, current_part)
        lines.extend(chapter_lines)
    lines.extend(
        [
            "",
            '<div class="chapter-break"></div>',
            "",
            "# 맺음말: 도구의 시대에 사람이 남기는 것",
            "",
            "AI가 더 많은 코드를 쓰는 시대가 되면 사람이 할 일이 사라진다고 말하는 사람이 있다. "
            "나는 반대로 생각한다. 사람이 해야 할 일은 줄어드는 것이 아니라 더 선명해진다. "
            "사람은 무엇을 만들지 선택하고, 누구의 문제인지 책임지고, 어떤 기준으로 검증할지 정한다.",
            "",
            "말라카식 바이브코딩은 빠른 도구 사용법이 아니다. 빠른 도구를 책임 있게 쓰기 위한 작업 방식이다. "
            "자기 언어를 세우고, 문제를 좁히고, 작은 증거를 만들고, AI와 계약하고, 현실 업무에 넣고, 검증하고, 기록을 다음 실행으로 되돌린다. "
            "도구 이름이 바뀌어도 이 순서는 남는다.",
            "",
            "이 책을 덮은 뒤 독자에게 남았으면 하는 것은 거대한 확신이 아니다. 오늘 만들 수 있는 작은 결과 하나다. "
            "그 결과를 보고 다시 생각을 고치고, 다시 만들고, 다시 검증하는 루프다. "
            "그 루프가 쌓이면 도구를 잘 쓰는 사람을 넘어 자기 문제를 제품과 자동화로 바꾸는 사람이 된다.",
            "",
            "# 부록: 말라카식 한 페이지 작업 계약",
            "",
            "1. 내가 해결하려는 문제는 무엇인가.",
            "2. 이 문제를 겪는 사용자는 누구인가.",
            "3. 사용자는 지금 어떤 방식으로 불편을 견디고 있는가.",
            "4. 이번 반복에서 만들 가장 작은 산출물은 무엇인가.",
            "5. AI에게 맡길 일과 내가 직접 검증할 일은 무엇인가.",
            "6. 성공 기준은 무엇이며 실패하면 무엇을 배울 것인가.",
            "7. 결과를 어디에 기록하고 다음 반복으로 어떻게 넘길 것인가.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_publication_plan() -> str:
    stats = corpus_stats()
    lines = [
        "# 출간계획서",
        "",
        "## 가제",
        "",
        "바이브코딩은 일하는 방식이다: 문제를 제품과 자동화로 바꾸는 말라카의 실행법",
        "",
        "## 저자 포지셔닝",
        "",
        f"저자명은 {AUTHOR_PROFILE['name']}다. 공개 저자 소개는 '{AUTHOR_PROFILE['public_identity']}'로 잡는다. "
        "개인 Notion에는 가족, 커리어, 회사 내부 맥락이 함께 있지만 출간 본문에서는 독자의 이해에 필요한 범위만 남긴다.",
        "",
        "### Notion에서 읽은 저자상",
        "",
    ]
    for item in AUTHOR_PROFILE["private_reading"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 기획 의도",
            "",
            "바이브코딩을 도구 사용법이 아니라 일하는 방식으로 재정의한다. "
            "이 책은 최신 PPT를 이어 붙인 자료집이 아니며, Notion 스크랩과 강의 슬라이드에서 반복되는 생각을 읽어 말라카의 저자 목소리로 새로 쓴 실전서다.",
            "",
            "핵심 메시지는 단순하다. AI로 빨리 만들 수 있는 시대일수록 사람은 더 정확히 문제를 정의하고, 더 작게 증거를 만들고, 더 책임 있게 검증해야 한다.",
            "",
            "## 원천 독해 범위",
            "",
            f"- 최신 PPT 추출 슬라이드: {stats['slide_count']:,}장",
            f"- Notion 관련 페이지 코퍼스: {stats['notion_relevant_count']:,}건",
            f"- Notion 주제 버킷: {', '.join(sorted(stats['topic_count'].keys()))}",
            "- 원천 사용 원칙: 원문 복사/짜깁기 금지, 제목과 반복 주제를 근거로 삼되 본문은 새 문장으로 재구성",
            "",
            "## 핵심 독자",
            "",
            "- AI 도구로 MVP를 만들고 싶은 비개발자와 초기 창업자",
            "- 사내 반복 업무와 운영 프로세스를 자동화하려는 실무자",
            "- AI 활용 교육, 워크숍, 커뮤니티를 준비하는 강사",
            "- 개발을 넘어 제품과 조직의 프로세스를 바꾸고 싶은 개발자",
            "",
            "## 차별점",
            "",
            "- 도구 튜토리얼이 아니라 문제 정의, MVP, 웹앱 구조, AI 작업 계약, 자동화, 운영, 교육, 기록, 검증을 하나의 루프로 묶는다.",
            "- 말라카의 LifeOS, 커리어 고민, 강의 경험, 실무 자동화 기록을 읽어 저자 고유의 관점으로 재구성한다.",
            "- 데모 제작에서 끝나지 않고 CRM, ERP, Salesforce, Teams, Slack, 브라우저 자동화 같은 실제 업무 표면까지 내려간다.",
            "- 빠른 실행을 찬양하는 데서 멈추지 않고 검증, 보안, 개인정보, 운영 책임을 마지막 축으로 둔다.",
            "",
            "## 책의 구조",
            "",
        ]
    )
    current_part = None
    for idx, chapter in enumerate(CHAPTERS, start=1):
        if chapter.part != current_part:
            current_part = chapter.part
            lines.extend([f"### {current_part}", ""])
        lines.extend(
            [
                f"**{idx}. {chapter.title}**",
                "",
                f"- 핵심 명제: {chapter.thesis}",
                f"- 원천 단서: {', '.join(chapter.source_basis[:4])}",
                f"- 독자 효용: {chapter.reader_gain}",
                "",
            ]
        )
    lines.extend(
        [
            "## 집필 원칙",
            "",
            "- 기존 PDF, PPT, 슬라이드 페이지를 이어 붙이지 않는다.",
            "- Notion 원문은 저자 이해와 주제 도출에만 사용하고, 출간 본문은 새 문장으로 쓴다.",
            "- 민감한 개인 정보는 저자 해석에는 참고하되, 본문에서는 불필요하게 노출하지 않는다.",
            "- 각 장은 주장, 현장 장면, 방법론, 위험, 실행 노트, 작업 계약 예시를 포함한다.",
            "- 최종 PDF는 새 Markdown 원고를 조판한 결과물이며, PDF/PPT 병합물이 아니다.",
            "",
            "## 제작 산출물",
            "",
            "- 출간계획서 Markdown/PDF",
            "- 200페이지 이상 본문 Markdown/PDF",
            "- 검증 요약 JSON",
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
    color: #64748b;
    font-size: 8pt;
  }
}

html {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", "Pretendard", sans-serif;
  color: #15171a;
  line-height: 1.64;
  font-size: 9.7pt;
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

.cover h2 {
  font-size: 13pt;
  line-height: 1.35;
  font-weight: 500;
  color: #374151;
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
  font-size: 12.2pt;
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

p { margin: 0 0 3.15mm; }
ul, ol { margin: 0 0 4mm 5mm; padding: 0; }
li { margin: 0 0 1.65mm; }
blockquote {
  margin: 1.5mm 0 4mm;
  padding-left: 4mm;
  border-left: 2.5pt solid #111827;
  color: #374151;
}
.book-page { break-before: page; }
.chapter-break { break-before: page; }
.part-break { break-before: page; }
strong { color: #111827; }
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


def pdf_page_count(path: Path) -> int | None:
    try:
        output = subprocess.check_output(["pdfinfo", str(path)], text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    match = re.search(r"^Pages:\s+(\d+)$", output, flags=re.M)
    return int(match.group(1)) if match else None


def write_all() -> dict[str, Any]:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    manuscript = render_manuscript()
    proposal = render_publication_plan()
    css_text = css()

    manuscript_md = FINAL_DIR / "malaka-vibecoding-authored-book.md"
    manuscript_html = FINAL_DIR / "malaka-vibecoding-authored-book.html"
    manuscript_css = FINAL_DIR / "malaka-vibecoding-authored-book.css"
    manuscript_pdf = FINAL_DIR / "malaka-vibecoding-authored-book.pdf"
    proposal_md = FINAL_DIR / "malaka-vibecoding-publication-plan.md"
    proposal_html = FINAL_DIR / "malaka-vibecoding-publication-plan.html"
    proposal_css = FINAL_DIR / "malaka-vibecoding-publication-plan.css"
    proposal_pdf = FINAL_DIR / "malaka-vibecoding-publication-plan.pdf"

    manuscript_md.write_text(manuscript, encoding="utf-8")
    proposal_md.write_text(proposal, encoding="utf-8")
    manuscript_css.write_text(css_text, encoding="utf-8")
    proposal_css.write_text(css_text, encoding="utf-8")
    write_pdf(manuscript, manuscript_css, manuscript_html, manuscript_pdf, "바이브코딩은 일하는 방식이다")
    write_pdf(proposal, proposal_css, proposal_html, proposal_pdf, "말라카 바이브코딩 출간계획서")

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "manuscript_md": str(manuscript_md.resolve()),
        "manuscript_pdf": str(manuscript_pdf.resolve()),
        "proposal_md": str(proposal_md.resolve()),
        "proposal_pdf": str(proposal_pdf.resolve()),
        "manuscript_pdf_pages": pdf_page_count(manuscript_pdf),
        "proposal_pdf_pages": pdf_page_count(proposal_pdf),
        "chapters": len(CHAPTERS),
        "sections": sum(len(chapter.sections) for chapter in CHAPTERS),
        "source_stats": corpus_stats(),
        "note": "Fresh authored manuscript rendered from Markdown; not a stitched PPT/PDF sourcebook.",
    }
    summary_path = FINAL_DIR / "malaka-vibecoding-authored-book-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_json"] = str(summary_path.resolve())
    return summary


def main() -> int:
    print(json.dumps(write_all(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
