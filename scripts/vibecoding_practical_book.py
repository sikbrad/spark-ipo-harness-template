#!/usr/bin/env python3
"""Create a concise publication-style book draft from extracted vibecoding slides."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path("data/vibecoding-book")
SLIDES_PATH = ROOT / "extracts" / "all-slides.json"
BOOK_DIR = ROOT / "book"
LESSONS_PER_CHAPTER = 20

GENERIC_TITLES = {
    "발표자 소개",
    "강연자",
    "강연자 소개",
    "감사합니다",
    "이론강의",
    "stage 1",
    "stage 2",
    "stage 3",
    "stage 4",
    "stage 5",
}


CHAPTERS = [
    {
        "title": "AI 시대, 일하는 방식이 바뀐다",
        "keywords": ["vibe", "바이브", "ai", "gpt", "llm", "cursor", "lovable", "누구든", "코딩"],
        "claim": "바이브코딩의 핵심은 코딩 속도가 아니라, 문제 정의부터 검증까지의 실행 루프를 짧게 만드는 데 있다.",
        "sections": [
            (
                "바이브코딩은 도구명이 아니라 작업 방식이다",
                "강의 자료 전반에서 반복되는 메시지는 특정 서비스 하나를 배우라는 말이 아니다. "
                "Lovable, Cursor, Gemini, Firebase, Supabase 같은 도구명은 시대마다 바뀌지만, "
                "아이디어를 화면과 데이터와 검증 가능한 산출물로 바꾸는 흐름은 계속 남는다.",
            ),
            (
                "비개발자의 권한이 넓어진다",
                "기획자, 창업자, 운영 담당자가 개발자의 일을 대체한다는 의미가 아니다. "
                "요구사항을 글로 설명하는 사람과 실제 작동하는 프로토타입을 들고 대화하는 사람 사이에는 큰 차이가 있다. "
                "바이브코딩은 이 간극을 좁혀 협업의 출발점을 바꾼다.",
            ),
        ],
        "exercise": "지금 하고 있는 일을 하나 고르고, ‘문서로 설명 가능한 일’과 ‘작동하는 도구가 있으면 바로 검증 가능한 일’을 분리해 적어본다.",
    },
    {
        "title": "좋은 문제를 MVP로 바꾸는 법",
        "keywords": ["mvp", "문제", "고객", "사용자", "아이디어", "프로토타입", "가설", "제품"],
        "claim": "AI가 빠르게 만들어줄수록, 무엇을 만들지 정하는 사람의 판단이 더 중요해진다.",
        "sections": [
            (
                "Minimum은 작다는 뜻이 아니라 핵심이 남았다는 뜻이다",
                "MVP는 기능을 대충 줄인 제품이 아니다. 최소한으로 만들되 핵심 가설이 검증되어야 한다. "
                "슬라이드 자료에서 반복되는 ‘핵심 기능’과 ‘현실’이라는 표현은 이 지점을 강조한다.",
            ),
            (
                "아이디어를 요구사항으로 번역한다",
                "AI에게 ‘좋은 앱을 만들어줘’라고 말하면 결과는 흔들린다. 대신 사용자, 상황, 입력 데이터, 출력 화면, 성공 조건을 분리해야 한다. "
                "이 번역 과정이 바이브코딩의 첫 번째 실력이다.",
            ),
        ],
        "exercise": "만들고 싶은 서비스를 한 문장으로 쓰고, 그 문장을 사용자/문제/핵심 기능/검증 지표 네 줄로 다시 쪼갠다.",
    },
    {
        "title": "프롬프트보다 중요한 협업 프로토콜",
        "keywords": ["prompt", "프롬프트", "agent", "에이전트", "context", "spec", "plan", "skill", "기획서"],
        "claim": "좋은 결과는 멋진 한 줄 프롬프트가 아니라, 맥락을 보존하고 검증하는 절차에서 나온다.",
        "sections": [
            (
                "AI에게 제대로 일 시키는 법",
                "자료에는 ‘AI에게 제대로 일 시키는 법’, ‘Vibe-plan’, ‘바이브코딩 기획서 만들기’ 같은 소재가 반복된다. "
                "이 반복은 프롬프트 예시보다 작업 계약이 중요하다는 신호다.",
            ),
            (
                "명세, 계획, 산출물, 검증",
                "실무에서는 AI가 만든 결과를 사람이 바로 믿을 수 없다. 그래서 명세를 만들고, 계획을 쪼개고, 산출물을 저장하고, "
                "검증 결과를 다시 다음 지시에 넣는 루프가 필요하다.",
            ),
        ],
        "exercise": "다음 작업을 AI에게 맡기기 전에 목표, 입력, 출력, 금지사항, 검증 방법을 각각 한 줄로 쓴다.",
    },
    {
        "title": "웹앱을 구성하는 기본 부품",
        "keywords": ["웹앱", "web", "app", "ui", "데이터베이스", "database", "api", "supabase", "firebase", "서버"],
        "claim": "바이브코딩을 오래 쓰려면 웹앱의 부품 이름을 알아야 한다.",
        "sections": [
            (
                "화면, 데이터, 서버, 인증",
                "반복 제목에서 ‘정석적인 웹앱 제작 방법’, ‘Supabase 연동’, ‘데이터베이스’, ‘네트워크(HTTP/API)’가 크게 나타난다. "
                "이는 실습의 병목이 코딩 문법보다 웹앱 구조 이해에 있음을 보여준다.",
            ),
            (
                "도구는 구조 위에 올린다",
                "Lovable이나 Firebase 같은 도구는 구조를 숨겨주지만 없애지는 않는다. "
                "데이터가 어디에 저장되는지, 누가 읽을 수 있는지, API는 무엇을 반환하는지 모르면 AI가 만든 결과를 고치기 어렵다.",
            ),
        ],
        "exercise": "내가 만들 MVP를 화면 목록, 데이터 표, 외부 API, 로그인 필요 여부로 나눠 표를 만든다.",
    },
    {
        "title": "도구 스택은 목적에 맞게 고른다",
        "keywords": ["lovable", "cursor", "gemini", "firebase", "supabase", "replit", "bolt", "v0", "도구"],
        "claim": "좋은 도구 선택은 ‘가장 최신’이 아니라 ‘지금 검증할 가설에 가장 짧은 경로’를 고르는 일이다.",
        "sections": [
            (
                "풀스택 에이전트와 코드기반 에이전트",
                "자료는 풀스택형 도구와 코드기반 에이전트를 구분한다. 전자는 빠른 화면과 백엔드 초안을 만들기 좋고, "
                "후자는 기존 코드 수정, 구조화, 디버깅, 장기 유지보수에 유리하다.",
            ),
            (
                "도구 조합의 기준",
                "아이디어 검증은 빠른 풀스택 도구, 운영될 제품은 코드 저장소와 데이터베이스를 중심에 둔다. "
                "강의 자료의 여러 변형은 행사와 대상에 따라 도구 조합이 달라져야 함을 보여준다.",
            ),
        ],
        "exercise": "내 작업을 ‘오늘 데모’, ‘한 달 운영’, ‘팀 인수인계’ 세 기준으로 나눠 필요한 도구를 다시 고른다.",
    },
    {
        "title": "브라우저 자동화와 업무 자동화",
        "keywords": ["browser", "playwright", "automation", "자동화", "크롤", "스크래핑", "api", "데이터"],
        "claim": "바이브코딩은 앱 제작에서 끝나지 않고, 사람이 반복하던 화면 조작과 자료 수집을 자동화하는 방향으로 확장된다.",
        "sections": [
            (
                "업무 자동화는 작은 반복에서 시작한다",
                "브라우저 자동화 강의가 별도 덱으로 존재한다는 점은 중요하다. "
                "창업 MVP뿐 아니라 현업의 반복 업무, 자료 수집, 품질 확인도 바이브코딩의 자연스러운 응용 영역이다.",
            ),
            (
                "자동화의 위험",
                "자동화는 빨라지는 만큼 잘못된 행동도 빠르게 반복한다. 로그인, 개인정보, 서비스 약관, 데이터 품질을 반드시 확인해야 한다. "
                "자동화 코드는 ‘된다’보다 ‘어디까지 해도 되는가’를 먼저 물어야 한다.",
            ),
        ],
        "exercise": "내가 매주 반복하는 웹 작업 하나를 골라 입력, 클릭, 대기, 다운로드, 검증 단계로 분해한다.",
    },
    {
        "title": "창업과 조직 안에서 쓰는 바이브코딩",
        "keywords": ["startup", "스타트업", "창업", "사업", "시장", "고객", "venture", "entre", "아이코어"],
        "claim": "바이브코딩은 창업자의 빠른 검증 도구이자, 조직 내부 문제를 직접 해결하는 실무자의 도구다.",
        "sections": [
            (
                "창업 교육에서 반복되는 이유",
                "자료에는 대학, 벤처, 창업 포럼, 스타트업 에센셜 등 다양한 맥락이 섞여 있다. "
                "이 공통점은 창업자가 아이디어를 말로만 설명하지 않고 바로 만져볼 수 있는 형태로 보여줘야 한다는 요구다.",
            ),
            (
                "조직에서는 내부 도구부터 시작한다",
                "외부 고객용 제품보다 내부 운영 도구가 더 좋은 첫 실습일 수 있다. 문제 맥락이 뚜렷하고, 사용자를 바로 만나고, "
                "실패해도 리스크가 상대적으로 작기 때문이다.",
            ),
        ],
        "exercise": "창업 아이디어 또는 내부 업무 문제를 하나 고르고, 1일/1주/1개월 안에 검증할 수 있는 산출물을 각각 정의한다.",
    },
    {
        "title": "품질과 리스크를 관리하는 법",
        "keywords": ["test", "qa", "검증", "보안", "security", "품질", "운영", "리스크", "배포"],
        "claim": "AI가 만든 결과물을 실무에 쓰려면 사람이 검증 책임을 설계해야 한다.",
        "sections": [
            (
                "작동과 신뢰는 다르다",
                "화면이 열리고 버튼이 눌린다고 제품이 된 것은 아니다. 데이터가 맞는지, 권한이 맞는지, 예외 상황이 처리되는지, "
                "다른 사람이 이어받을 수 있는지가 별도 검증 대상이다.",
            ),
            (
                "출시 전 체크리스트",
                "로그인/권한, 개인정보, 데이터 백업, 비용, API 키, 오류 로그, 사용자의 오해 가능성을 확인한다. "
                "바이브코딩은 빠르게 만들기 때문에 이 체크리스트가 더 중요해진다.",
            ),
        ],
        "exercise": "내 MVP의 실패 시나리오를 10개 적고, 각 시나리오를 사람이 확인할지 자동 테스트로 확인할지 표시한다.",
    },
]


def clean_ws(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text.replace("\u00a0", " "))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def markdown_safe(text: str) -> str:
    return clean_ws(text).replace("\\", "\\\\")


def slide_text(slide: dict[str, Any]) -> str:
    return "\n".join(slide.get("paragraphs", []) + slide.get("notes", []))


def pick_examples(slides: list[dict[str, Any]], keywords: list[str], limit: int = 6) -> list[dict[str, Any]]:
    selected = []
    seen_titles = set()
    for slide in slides:
        if slide.get("hidden"):
            continue
        haystack = f"{slide.get('title', '')}\n{slide_text(slide)}".lower()
        score = sum(haystack.count(keyword.lower()) for keyword in keywords)
        title = clean_ws(slide.get("title", ""))
        if score <= 0 or not title or title in seen_titles or re.fullmatch(r"\d+", title):
            continue
        seen_titles.add(title)
        selected.append((score, slide))
    selected.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in selected[:limit]]


def first_meaningful_paragraph(slide: dict[str, Any]) -> str:
    for paragraph in slide.get("paragraphs", []):
        paragraph = clean_ws(paragraph)
        if len(paragraph) >= 12 and paragraph != slide.get("title"):
            return paragraph[:220]
    return ""


def meaningful_paragraphs(slide: dict[str, Any], limit: int = 4) -> list[str]:
    title = clean_ws(slide.get("title", ""))
    out = []
    for paragraph in slide.get("paragraphs", []) + slide.get("notes", []):
        paragraph = clean_ws(paragraph)
        if len(paragraph) < 10 or paragraph == title:
            continue
        if paragraph in out:
            continue
        out.append(paragraph[:280])
        if len(out) >= limit:
            break
    return out


def is_generic_title(title: str) -> bool:
    title = clean_ws(title)
    if not title or re.fullmatch(r"\d+", title):
        return True
    return title.lower() in GENERIC_TITLES


def slide_keyword_score(slide: dict[str, Any], keywords: list[str]) -> int:
    haystack = f"{slide.get('title', '')}\n{slide_text(slide)}".lower()
    return sum(haystack.count(keyword.lower()) for keyword in keywords)


def pick_lesson_slides(slides: list[dict[str, Any]], keywords: list[str], limit: int) -> list[dict[str, Any]]:
    candidates = []
    for slide in slides:
        title = clean_ws(slide.get("title", ""))
        if slide.get("hidden") or is_generic_title(title):
            continue
        paragraphs = meaningful_paragraphs(slide, limit=2)
        if not paragraphs:
            continue
        score = slide_keyword_score(slide, keywords)
        if score <= 0:
            continue
        candidates.append((score, slide))

    candidates.sort(key=lambda item: (item[0], len(slide_text(item[1]))), reverse=True)
    selected = []
    seen_titles = set()
    per_deck: dict[str, int] = {}
    for _, slide in candidates:
        title = clean_ws(slide.get("title", ""))
        deck = slide.get("deck_file_name", "")
        if title in seen_titles or per_deck.get(deck, 0) >= 4:
            continue
        seen_titles.add(title)
        per_deck[deck] = per_deck.get(deck, 0) + 1
        selected.append(slide)
        if len(selected) >= limit:
            return selected

    for _, slide in candidates:
        title = clean_ws(slide.get("title", ""))
        if title in seen_titles:
            continue
        seen_titles.add(title)
        selected.append(slide)
        if len(selected) >= limit:
            return selected
    return selected


def lesson_focus(chapter: dict[str, Any], slide: dict[str, Any]) -> str:
    title = clean_ws(slide.get("title", ""))
    return (
        f"이 레슨은 '{title}'라는 자료 단서를 중심으로, {chapter['claim']} "
        "독자는 이 페이지를 읽고 자기 문제를 더 작은 실행 단위로 나누는 기준을 얻어야 한다."
    )


def render_lesson_page(chapter_idx: int, lesson_idx: int, chapter: dict[str, Any], slide: dict[str, Any]) -> list[str]:
    title = markdown_safe(slide.get("title", f"Lesson {lesson_idx}"))
    source = f"{slide.get('deck_file_name')} #{slide.get('slide_number')}"
    evidence = meaningful_paragraphs(slide, limit=4)
    excerpt = evidence[0] if evidence else first_meaningful_paragraph(slide)
    return [
        "",
        '<div class="lesson-break"></div>',
        "",
        f"## {chapter_idx}-{lesson_idx:02d}. {title}",
        "",
        f"<div class=\"slide-meta\">원천 슬라이드: {markdown_safe(source)}</div>",
        "",
        "### 레슨의 초점",
        "",
        lesson_focus(chapter, slide),
        "",
        "### 왜 중요한가",
        "",
        "바이브코딩에서는 한 번의 지시로 완성품이 나오기를 기대하기보다, 어떤 문제를 어떤 순서로 AI와 나눠 풀지 결정하는 능력이 중요하다. "
        f"이 슬라이드의 핵심 단서는 '{title}'이며, 이는 장 전체의 주제인 '{chapter['title']}'를 실제 작업으로 옮기는 출발점이 된다. "
        "도구가 바뀌어도 남는 것은 문제를 구조화하고, 작은 산출물을 만들고, 검증 기준으로 다음 반복을 결정하는 방식이다.",
        "",
        "### 자료에서 뽑은 단서",
        "",
    ] + [
        f"> {markdown_safe(item)}" for item in (evidence or [excerpt or title])
    ] + [
        "",
        "### 적용 절차",
        "",
        "1. 슬라이드 제목을 내 프로젝트의 작업 문장으로 바꾼다.",
        "2. 필요한 입력 자료, 만들 산출물, 검증 기준을 각각 한 줄로 적는다.",
        "3. AI에게 한 번에 전체를 맡기지 말고 첫 번째 검증 가능한 조각만 요청한다.",
        "4. 나온 결과를 직접 실행하거나 읽어보고, 실패한 지점을 다음 지시의 제약 조건으로 넣는다.",
        "",
        "### 프롬프트 스타터",
        "",
        f"> 나는 '{title}'와 관련된 작업을 하고 있다. 목표는 [목표]이고, 사용자는 [사용자]이며, 현재 가진 자료는 [자료]다. "
        "먼저 MVP 수준에서 검증할 가장 작은 산출물을 정의하고, 구현 단계와 확인 방법을 표로 정리해줘.",
        "",
        "### 검증 질문",
        "",
        "- 이 작업은 오늘 안에 눈으로 확인할 수 있는 산출물로 끝나는가?",
        "- AI가 만든 결과를 확인할 수 있는 기준이 명확한가?",
        "- 실패했을 때 어느 단계로 되돌아갈지 정해져 있는가?",
    ]


def render_markdown(slides: list[dict[str, Any]]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(slides)
    nonhidden = sum(not slide.get("hidden") for slide in slides)
    hidden = total - nonhidden
    lines = [
        '<div class="cover">',
        "",
        "# 바이브코딩 실전 입문",
        "",
        "## AI와 함께 문제를 제품과 자동화로 바꾸는 방법",
        "",
        f"**작성일:** {generated_at}",
        "",
        f"**기반 자료:** latest PPT/PPTX 30개에서 추출한 슬라이드 {total}장(본문 {nonhidden}장, 숨김 {hidden}장)",
        "",
        "</div>",
        "",
        '<div class="page-break"></div>',
        "",
        "# 머리말",
        "",
        "이 원고는 바이브코딩 강의 슬라이드를 전수 추출한 뒤, 출판기획서의 목차에 맞춰 중복 소재를 통합한 편집 초안이다. "
        "원본 슬라이드의 모든 문장은 별도 소스북과 `extracts/` 폴더에 보존했고, 이 책은 독자가 한 번의 흐름으로 읽을 수 있도록 개념, 절차, 실습, 검증 기준을 재구성했다.",
        "",
        "바이브코딩은 ‘AI가 코드를 대신 써준다’는 낙관만으로는 설명되지 않는다. 실제 현장에서는 무엇을 만들지 고르는 판단, AI에게 일을 나누어 맡기는 방식, 결과물을 검증하는 책임이 더 중요해진다. "
        "따라서 이 책은 특정 도구의 사용법보다 반복 가능한 작업 방식에 초점을 둔다.",
        "",
        "# 이 책의 사용법",
        "",
        "- 각 장의 첫 문장은 그 장의 판단 기준이다.",
        "- 본문은 강의자료에서 반복된 소재를 출판용 문장으로 정리한 것이다.",
        "- `자료에서 확인한 단서`는 원본 슬라이드 제목과 일부 문장을 연결한 근거 목록이다.",
        "- `실습`은 독자가 자기 문제에 바로 적용할 수 있는 최소 과제다.",
    ]

    total_lessons = len(CHAPTERS) * LESSONS_PER_CHAPTER
    lines.extend(
        [
            "",
            "# 150쪽 확장판 구성",
            "",
            f"이 확장판은 8개 장, 장별 {LESSONS_PER_CHAPTER}개 레슨, 총 {total_lessons}개 레슨 페이지로 구성했다. "
            "각 레슨은 원천 슬라이드 하나를 기준으로 해설, 적용 절차, 프롬프트 스타터, 검증 질문을 붙인 독립 페이지다.",
        ]
    )

    for idx, chapter in enumerate(CHAPTERS, start=1):
        examples = pick_examples(slides, chapter["keywords"])
        lesson_slides = pick_lesson_slides(slides, chapter["keywords"], LESSONS_PER_CHAPTER)
        lines.extend(
            [
                "",
                '<div class="page-break"></div>',
                "",
                f"# {idx}. {chapter['title']}",
                "",
                f"**핵심 주장:** {chapter['claim']}",
                "",
            ]
        )
        for section_title, body in chapter["sections"]:
            lines.extend([f"## {section_title}", "", body, ""])
        lines.extend(["## 자료에서 확인한 단서", ""])
        if examples:
            for slide in examples:
                excerpt = first_meaningful_paragraph(slide)
                source = f"{slide.get('deck_file_name')} #{slide.get('slide_number')}"
                lines.append(f"- **{markdown_safe(slide.get('title', ''))}** ({source})")
                if excerpt:
                    lines.append(f"  - {markdown_safe(excerpt)}")
        else:
            lines.append("- 직접 매칭된 대표 슬라이드가 적어, 이 장은 전체 검토 메모의 반복 주제에 근거해 구성했다.")
        lines.extend(
            [
                "",
                "## 실습",
                "",
                chapter["exercise"],
                "",
                "## 체크리스트",
                "",
                "- 문제와 사용자가 한 문장으로 설명되는가?",
                "- AI에게 줄 입력과 기대 출력이 분리되어 있는가?",
                "- 결과물을 사람이 확인할 기준이 있는가?",
                "- 실패했을 때 되돌릴 방법이 있는가?",
            ]
        )
        lines.extend(
            [
                "",
                f"## {idx}장 레슨 페이지",
                "",
                f"다음 {len(lesson_slides)}개 레슨은 추출 슬라이드에서 직접 고른 대표 단서를 바탕으로 구성했다.",
            ]
        )
        for lesson_idx, slide in enumerate(lesson_slides, start=1):
            lines.extend(render_lesson_page(idx, lesson_idx, chapter, slide))

    lines.extend(
        [
            "",
            '<div class="page-break"></div>',
            "",
            "# 부록 A. 1일 바이브코딩 워크숍 진행안",
            "",
            "## 1교시: 문제와 독자 정의",
            "",
            "참가자는 만들고 싶은 도구를 한 문장으로 쓰고, 사용자와 상황을 분리한다. 목표는 멋진 아이디어가 아니라 검증 가능한 작업 단위를 만드는 것이다.",
            "",
            "## 2교시: MVP 명세 작성",
            "",
            "화면, 데이터, 액션, 성공 조건을 표로 만든다. 이 표가 AI에게 줄 첫 번째 컨텍스트가 된다.",
            "",
            "## 3교시: 첫 구현",
            "",
            "선택한 도구로 첫 화면과 데이터 흐름을 만든다. 이 단계에서는 완성도보다 작동 경로를 확보한다.",
            "",
            "## 4교시: 검증과 리팩터링",
            "",
            "작동 결과를 테스트하고, 오류를 기록하고, 다음 프롬프트에 반영한다. 발표는 기능 설명보다 배운 제약과 다음 실험을 중심으로 한다.",
            "",
            "# 부록 B. 출간 전 편집 과제",
            "",
            "- 중복 덱을 하나의 최종 원고 흐름으로 병합한다.",
            "- 이미지로만 들어간 슬라이드 문구와 데모 화면은 수동 OCR/캡처로 보강한다.",
            "- 도구명과 스크린샷은 출간 직전 버전으로 갱신한다.",
            "- 초상권, 로고, 제3자 서비스 화면, 사례 공개 범위를 검토한다.",
            "- 각 장에 실제 실습 파일과 다운로드 링크를 붙인다.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def css() -> str:
    base = (BOOK_DIR / "book.css").read_text(encoding="utf-8")
    return (
        base
        + """
blockquote {
  border-left: 3pt solid #111827;
  margin-left: 0;
  padding-left: 4mm;
  color: #374151;
}

.lesson-break {
  break-before: page;
}

.slide-meta {
  color: #6b7280;
  font-size: 8.2pt;
  margin: -1mm 0 3mm;
}

h3 {
  font-size: 11.5pt;
  margin: 5mm 0 2mm;
  color: #111827;
  break-after: avoid;
}
"""
    )


def write_pdf(md_text: str, css_path: Path, html_path: Path, pdf_path: Path) -> None:
    import markdown
    from weasyprint import HTML

    body = markdown.markdown(md_text, extensions=["extra", "tables", "sane_lists"], output_format="html5")
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>바이브코딩 실전 입문</title>
  <link rel="stylesheet" href="{html.escape(css_path.name)}">
</head>
<body>
{body}
</body>
</html>
"""
    html_path.write_text(html_text, encoding="utf-8")
    HTML(filename=str(html_path)).write_pdf(str(pdf_path), stylesheets=[str(css_path)])


def main() -> int:
    BOOK_DIR.mkdir(parents=True, exist_ok=True)
    slides = json.loads(SLIDES_PATH.read_text(encoding="utf-8"))
    md_text = render_markdown(slides)
    md_path = BOOK_DIR / "vibecoding-practical-book.md"
    html_path = BOOK_DIR / "vibecoding-practical-book.html"
    css_path = BOOK_DIR / "vibecoding-practical-book.css"
    pdf_path = BOOK_DIR / "vibecoding-practical-book.pdf"
    md_path.write_text(md_text, encoding="utf-8")
    css_path.write_text(css(), encoding="utf-8")
    write_pdf(md_text, css_path, html_path, pdf_path)
    print(pdf_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
