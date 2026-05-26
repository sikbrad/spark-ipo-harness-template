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


PAGE_COUNT_PER_CHAPTER = 17


def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def md(text: str) -> str:
    return clean_ws(text).replace("\\", "\\\\")


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
            return paragraph[:260]
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
                        excerpt=clean_ws(item.get("excerpt", ""))[:300],
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
                    excerpt=clean_ws(item.get("excerpt", ""))[:300],
                ),
            )
        )
    candidates.sort(key=lambda item: (item[0], len(item[1].excerpt)), reverse=True)
    return [seed for _, seed in candidates[:limit]]


def chapter_sources(chapter: dict[str, Any], slides: list[dict[str, Any]], topic: dict[str, list[dict[str, Any]]], corpus: list[dict[str, Any]]) -> list[SourceSeed]:
    slide_seeds = select_slide_seeds(slides, chapter["keywords"], 12)
    notion_seeds = select_notion_seeds(topic, corpus, chapter["keywords"], 10)
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


def write_page(chapter_no: int, page_no: int, chapter: dict[str, Any], seed: SourceSeed) -> list[str]:
    title = page_title(chapter, seed, page_no)
    seed_excerpt = seed.excerpt or chapter["thesis"]
    # These paragraphs are intentionally synthetic prose. The source seed is used as
    # context and citation, not pasted as a page body.
    return [
        "",
        '<div class="book-page"></div>',
        "",
        f"## {chapter_no}-{page_no:02d}. {md(title)}",
        "",
        f"<div class=\"source-note\">근거 맥락: {md(seed.kind)} · {md(seed.source)}</div>",
        "",
        f"{chapter['title']}을 다룰 때 먼저 붙잡아야 할 문장은 이것이다. {chapter['thesis']} "
        f"말라카의 노션과 강의 자료에서 반복되는 신호는 '{md(seed.title)}'라는 단서로 모인다. "
        "이 단서는 단순한 참고자료가 아니라, 실제 일을 바꾸려는 사람의 사고방식이 어디에서 출발하는지를 보여준다.",
        "",
        "말라카의 문장은 늘 추상에서 끝나지 않는다. 목표를 잡고, 기록을 남기고, 산출물을 만들고, 다시 검증하는 순서로 내려온다. "
        f"그래서 이 페이지의 핵심은 {chapter['axis']}을 독자의 손에 잡히는 절차로 바꾸는 일이다. "
        "AI 도구는 그 절차를 빠르게 해주지만, 방향을 정하지 못한 사람에게 방향까지 대신 만들어주지는 않는다.",
        "",
        "자료를 읽으며 중요한 차이를 보았다. 말라카는 '잘 만들 수 있다'보다 '왜 이걸 만들어야 하는가'를 먼저 묻는다. "
        "그 다음에는 '오늘 확인 가능한 결과는 무엇인가'로 내려온다. 이 두 질문 사이에서 기획이 생기고, 구현이 생기고, 교육이 생긴다. "
        f"'{md(seed.title)}'라는 단서는 바로 그 중간 지점을 보여주는 작은 표식이다.",
        "",
        "독자가 여기서 가져가야 할 것은 새로운 도구 이름이 아니다. 다음 번에 AI에게 일을 맡길 때, 먼저 문제를 한 문장으로 고정하고, "
        "그 문제가 누구의 어떤 행동을 바꾸는지 적고, 가장 작은 검증물을 정해야 한다는 습관이다. "
        "이 습관이 없으면 바이브코딩은 빠른 장난감이 되고, 이 습관이 있으면 바이브코딩은 실행력을 키우는 언어가 된다.",
        "",
        "### 말라카식 적용",
        "",
        "- 지금 만들고 싶은 것을 기능명이 아니라 바꾸고 싶은 장면으로 쓴다.",
        "- AI에게 맡길 일을 전체 프로젝트가 아니라 한 번에 검증 가능한 산출물로 자른다.",
        "- 결과를 받으면 감탄하거나 실망하기 전에, 어떤 가정이 맞았고 어떤 가정이 틀렸는지 기록한다.",
        "- 기록은 다음 프롬프트의 재료가 되어야 한다. 저장만 되는 기록은 LifeOS가 아니라 창고다.",
        "",
        "### 원천에서 재구성한 메모",
        "",
        f"> {md(seed_excerpt[:420])}",
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
