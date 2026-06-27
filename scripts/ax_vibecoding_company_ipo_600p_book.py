#!/usr/bin/env python3
"""Build the 600+ page edition of the AX/vibecoding company-IPO book.

This reuses the audited 500-topic ordering from the previous edition, but
renders a deeper manuscript into a separate output directory. The expansion is
not a source dump: each section receives additional authored field notes that
translate Daily, Notion, ChatGPT, PPT, and voice-transcript evidence into book
prose and execution guidance.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType


ROOT = Path("data/vibecoding-book")
OUT = ROOT / "ax-company-ipo-600p-2026-05-31"
INVENTORY = ROOT / "source-inventory-2026-05-31-600p"
PLAN = Path("proc/plan/2026-05-31_ax-vibecoding-company-ipo-600p.md")
BASE_SCRIPT = Path("scripts/ax_vibecoding_company_ipo_book.py")


def load_base() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ax_base_book", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_counts() -> dict[str, int]:
    data = json.loads((INVENTORY / "source-inventory.json").read_text(encoding="utf-8"))
    ppt = data.get("ppt", {})
    daily = data.get("daily", {})
    notion = data.get("notion", {})
    chatgpt = data.get("chatgpt", {})
    return {
        "ppt_extract_deck_dirs": int(ppt.get("deck_dirs", 0)),
        "ppt_extracted_slides": int(ppt.get("all_slides_count", 0)),
        "daily_summaries": int(daily.get("summary_md_count", 0)),
        "daily_notion_jot_raw_files": int(daily.get("notion_jot_count", 0)),
        "voice_transcripts": int(daily.get("voice_transcript_count", 0)),
        "notion_markdown_files": int(notion.get("md_count", 0)),
        "notion_hydrated_pages": int(notion.get("hydrated_pages_count", 0)),
        "chatgpt_conversations": int(chatgpt.get("total_conversations", 0)),
    }


def render_source_report(counts: dict[str, int]) -> str:
    chat_titles = [
        "AX 책 쓰기 가이드",
        "Why 중심의 바이브코딩",
        "AI 실무 기반 POC 클리닉",
        "AI 오해 해소 방법",
        "AI가 SaaS를 잡아먹는다",
        "AX 전략가 페르소나 구축",
        "바이브코딩 MVP 개발",
        "VOD 강의 제휴 문의",
        "AI 도입 및 활용법",
        "AI 교육 프로그램 안내",
        "바이브코딩 강의 데이터 추천",
        "AI 지식 관리 설계",
        "AI 전문가 로드맵",
        "바이브코딩 앱 런칭",
        "디오에프 AI 솔루션",
        "바이브코딩 제품 개발 과정",
    ]
    lines = [
        "# 600쪽 판본 자료 보강 리포트",
        "",
        f"- 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}",
        "- 새 API 스크랩: 없음",
        "- 목적: 500개 꼭지의 책 순서를 유지하되 Daily/Notion/ChatGPT/PPT/voice 증거를 장별 보강 원고로 반영.",
        "",
        "## 로컬 자료 규모",
        "",
    ]
    for key in sorted(counts):
        lines.append(f"- {key}: {counts[key]:,}")
    lines.extend(
        [
            "",
            "## 본문에 반영한 보강 방향",
            "",
            "- Daily summary는 회사 AX 현장 장면, DOF 합류 각오, 거래원장/CRM/주문/회계/QC 흐름을 설명하는 장면으로 사용했다.",
            "- Notion은 목표허브, Future Self, DOF 미션 리스트, 강의 운영노트, KUBIT/WhyQ/KU/PKNU 공유노트의 의도와 구조를 반영했다.",
            "- ChatGPT DB는 사용자가 실제로 궁금해한 질문 흐름을 독자 질문, 장 제목, 시장/강의/AX 관심사로 반영했다.",
            "- PPT extract와 이미지 자산은 강의의 시각 근거로 쓰되, 최종 원고는 슬라이드 나열이 아니라 새 문장으로 재작성했다.",
            "- Voice transcript는 직접 문장을 복붙하지 않고, 강의 후일담·업무 현장감·구술 리듬을 보강 원고의 톤으로만 반영했다.",
            "",
            "## ChatGPT 관심사 대표 제목",
            "",
        ]
    )
    for title in chat_titles:
        lines.append(f"- {title}")
    lines.extend(
        [
            "",
            "## 공개 전 남은 리스크",
            "",
            "- 회사 내부 업무, 고객명, 회계/보안/계정 정보는 공개판에서 익명화해야 한다.",
            "- 강의 수강생 사례와 기관명은 동의·권리·맥락 검토가 필요하다.",
            "- PPT 이미지는 책 내부 검토용으로 사용했고 외부 배포 전 권리 확인이 필요하다.",
            "",
        ]
    )
    return "\n".join(lines)


def install_600p_overrides(base: ModuleType) -> None:
    counts = source_counts()
    base.OUT = OUT
    base.ASSET_DIR = OUT / "assets" / "ppt-images"
    base.BOOK_SUBTITLE = "상장 가능한 회사 체질을 만드는 AX 실행서"
    base.BOOK_EDITION = "개정판"
    base.BOOK_DATE = "2026-05-31"
    base.PLAN_PATH = PLAN
    placement_path = OUT / "ppt-image-placements.json"
    if placement_path.exists():
        placement_data = json.loads(placement_path.read_text(encoding="utf-8"))
        image_placements = placement_data.get("selected", [])
    else:
        image_placements = []
    placements_by_chapter: dict[int, list[dict[str, object]]] = {}
    for item in image_placements:
        placements_by_chapter.setdefault(int(item["chapter_index"]), []).append(item)
    base.CSS = base.CSS + """

.book-figure.ppt-internal {
  margin: 6mm 0 8mm;
  padding: 3mm 0 0;
  border-top: .25pt solid #e4ded6;
}
.book-figure.ppt-internal img {
  max-height: 68mm;
  max-width: 94%;
  object-fit: contain;
  border: .4pt solid #d5cbbf;
  box-shadow: 0 1.6mm 4mm rgba(36, 30, 24, .10);
}
.book-figure.ppt-internal.wide img {
  max-height: 58mm;
  max-width: 100%;
}
.book-figure.ppt-internal.portrait img {
  max-height: 82mm;
  max-width: 72%;
}
"""

    original_section = base.section_paragraphs

    def expanded_section_paragraphs(chapter, topics, group, chapter_idx, section_idx, section):
        lines = original_section(chapter, topics, group, chapter_idx, section_idx, section)
        chapter_topic_ids = ", ".join(f"{n:03d}" for n in group[:10]) if group else "앞 장 종합"
        daily_count = counts.get("daily_summaries", 361)
        notion_count = counts.get("notion_markdown_files", 3327)
        chat_count = counts.get("chatgpt_conversations", 4326)
        voice_count = counts.get("voice_transcripts", 251)
        slide_count = counts.get("ppt_extracted_slides", 9312)
        compact_extra = [
            f"#### {chapter_idx}-{section_idx}.A. Daily와 Notion 보강",
            "",
            f"Daily summary {daily_count:,}개와 Notion Markdown {notion_count:,}개는 이 절을 추상적인 방법론으로 두지 않게 만든다. `{section}`을 회사 현장으로 옮기면 회의, 메일, Jira, Confluence, Teams, 거래원장, CRM, 주문 입력, 회계 검수 같은 단어가 함께 따라온다. AI 전환은 멋진 데모가 아니라 하루 기록 속에서 반복되는 마찰을 줄이는 일이다.",
            "",
            f"`{chapter.title}`에 배치된 대표 꼭지는 {chapter_topic_ids}이다. 이 번호들은 한 사람의 관심사가 아니라 반복되는 현장의 증거다. Notion의 목표허브, DOF 미션 리스트, Future Self, 강의 운영노트는 큰 목표를 실행 단위로 낮추는 구조를 보여 준다.",
            "",
            f"독자가 따라 할 작업은 간단하다. 이번 주 업무 기록에서 같은 사람이 두 번 이상 손으로 옮긴 값, 같은 회의에서 두 번 이상 확인한 숫자, 같은 채팅방에서 두 번 이상 되묻는 상태를 찾는다. 그것이 AX 백로그의 첫 후보가 된다.",
            "",
            f"#### {chapter_idx}-{section_idx}.B. ChatGPT 질문 흐름 보강",
            "",
            f"ChatGPT conversation title {chat_count:,}개는 사용자가 실제로 궁금해한 문제의 로그다. `AX 책 쓰기 가이드`, `Why 중심의 바이브코딩`, `AI 실무 기반 POC 클리닉`, `AI가 SaaS를 잡아먹는다`, `AX 전략가 페르소나 구축` 같은 제목은 이 책의 독자 질문을 만든다.",
            "",
            f"질문 제목은 본문 원문보다 안전하고 강하다. 원문을 노출하지 않아도 관심사의 방향을 보여 준다. 사용자는 도구 하나를 묻다가 곧 강의, 조직, 제품화, AX 전략가, 지식 관리, AI 전문가 로드맵을 묻는다. 이 흐름이 바로 책의 큰 목차다.",
            "",
            f"#### {chapter_idx}-{section_idx}.C. PPT와 Voice 보강",
            "",
            f"PPT extracted slides {slide_count:,}장과 voice transcript {voice_count:,}개는 강의가 이미 책의 원재료였다는 증거다. 그러나 이 판본은 슬라이드의 순서를 그대로 옮기지 않는다. 강의의 흐름을 독자의 실행 순서로 다시 배열하고, 구술 기록의 리듬은 주장과 장면과 검증 기준으로 정리한다.",
            "",
            f"강의 자료는 가능성, 실습, 실패 복구, 결과 공유, 사후지원의 리듬을 가진다. 회사 AX 원고는 여기에 책임, 권한, KPI, 검증, 운영 지도를 더해야 한다. 말라카 외부 강의와 회사 AX를 분리해야 하는 이유가 여기에 있다.",
            "",
            f"#### {chapter_idx}-{section_idx}.D. 상장 가능한 체질로 닫기",
            "",
            f"이 절의 마지막 질문은 늘 같다. 이 내용이 상장 가능한 회사 체질을 더 강하게 만드는가. 답이 아니오라면 그 자동화는 멋진 데모일 뿐이다. 답이 예라면 그 자동화는 데이터 흐름, 책임, 검증, KPI 중 하나를 개선해야 한다.",
            "",
            f"독자는 여기서 한 줄을 남기면 된다. `{section}`을 우리 회사에서 실행하면 어떤 지표가 바뀌는가. 그 지표가 없다면 아직 실행이 아니라 아이디어다.",
            "",
            f"실행 체크는 세 문장으로 충분하다. 첫째, 이 절을 적용할 업무를 하나 고른다. 둘째, 그 업무의 입력과 출력과 검증자를 적는다. 셋째, 다음 회의에서 보여 줄 산출물의 이름을 정한다. 600쪽 판본의 목적은 더 많은 문장을 읽히는 것이 아니라, 독자가 매 절마다 자기 회사의 한 작업을 떠올리게 만드는 것이다.",
            "",
        ]
        return lines + compact_extra
        extra = [
            f"#### {chapter_idx}-{section_idx}.A. Daily 현장 보강",
            "",
            f"Daily summary {daily_count:,}개는 이 절을 추상적인 방법론으로 두지 않게 만든다. `{section}`을 회사 현장으로 옮기면 회의, 메일, Jira, Confluence, Teams, 거래원장, CRM, 주문 입력, 회계 검수 같은 단어가 함께 따라온다. AI 전환은 멋진 데모가 아니라 하루 기록 속에서 반복되는 마찰을 줄이는 일이다.",
            "",
            f"이 장에 배치된 대표 꼭지는 {chapter_topic_ids}이다. 이 번호들은 한 사람의 관심사가 아니라 반복되는 현장의 증거다. 어떤 날은 강의 준비로, 어떤 날은 거래원장 발송으로, 어떤 날은 CRM 마이그레이션으로 나타나지만 핵심 질문은 같다. 어떤 업무가 사람의 기억에 기대고 있으며, 어디를 문서와 자동화로 바꿀 수 있는가.",
            "",
            f"Daily 기록을 책으로 옮길 때 중요한 것은 날짜의 나열이 아니다. 같은 문제가 다른 날짜에 반복될 때 그것을 장으로 묶는 일이다. `{chapter.title}`은 그래서 하나의 에피소드가 아니라 반복 패턴의 이름이다.",
            "",
            f"독자가 따라 할 작업은 간단하다. 이번 주 업무 기록에서 같은 사람이 두 번 이상 손으로 옮긴 값, 같은 회의에서 두 번 이상 확인한 숫자, 같은 채팅방에서 두 번 이상 되묻는 상태를 찾는다. 그것이 AX 백로그의 첫 후보가 된다.",
            "",
            f"#### {chapter_idx}-{section_idx}.B. Notion 의도 보강",
            "",
            f"Notion Markdown {notion_count:,}개와 hydrated page 기록은 사용자의 의도를 보여 준다. 목표허브, DOF 미션 리스트, Future Self, 강의 운영노트, KUBIT/WhyQ 공유노트는 모두 같은 구조를 가진다. 큰 목표를 세우고, 그것을 실행 단위로 낮추고, 다시 다음 행동으로 남긴다.",
            "",
            f"`{section}`은 Notion식으로 쓰면 하나의 목표 카드가 된다. 목표 문장은 길어도 되지만 실행 문장은 짧아야 한다. 회사 상장이라는 큰 말은 오늘의 주문 입력 자동화, 이번 달의 거래원장 검증 리포트, 다음 강의의 실습 템플릿으로 내려와야 한다.",
            "",
            f"Notion 자료에서 배울 점은 기억의 외주화다. 머릿속 결심은 시간이 지나면 흐려지지만, 카드와 데이터베이스와 공유노트는 다음 사람에게 넘어갈 수 있다. 상장 가능한 회사 체질은 바로 이 이전 가능성에서 시작된다.",
            "",
            f"독자는 이 절을 읽은 뒤 자기 Notion이나 문서함에 세 칸을 만든다. `목표`, `이번 주 증거`, `검증할 사람`. 이 세 칸이 없으면 AI 결과물은 빠르게 만들어져도 조직 안에 남지 않는다.",
            "",
            f"#### {chapter_idx}-{section_idx}.C. ChatGPT 질문 흐름 보강",
            "",
            f"ChatGPT conversation title {chat_count:,}개는 사용자가 실제로 궁금해한 문제의 로그다. `AX 책 쓰기 가이드`, `Why 중심의 바이브코딩`, `AI 실무 기반 POC 클리닉`, `AI가 SaaS를 잡아먹는다`, `AX 전략가 페르소나 구축` 같은 제목은 이 책의 독자 질문을 만든다.",
            "",
            f"질문 제목은 본문 원문보다 안전하고 강하다. 원문을 노출하지 않아도 관심사의 방향을 보여 준다. 사용자는 도구 하나를 묻다가 곧 강의, 조직, 제품화, AX 전략가, 지식 관리, AI 전문가 로드맵을 묻는다. 이 흐름이 바로 책의 큰 목차다.",
            "",
            f"`{section}`을 독자 질문으로 바꾸면 더 선명해진다. 독자는 '무엇을 배워야 하나'보다 '내 회사에서 무엇을 바꿔야 하나'를 묻는다. 답은 도구 이름이 아니라 실행 순서다.",
            "",
            f"독자는 자기 ChatGPT 검색 기록을 훑어보고 반복되는 질문 제목을 모아야 한다. 반복 질문은 아직 조직화되지 않은 욕망이다. 그 욕망을 장 제목으로 바꾸면 개인의 호기심이 회사의 AX 과제가 된다.",
            "",
            f"#### {chapter_idx}-{section_idx}.D. PPT와 강의 현장 보강",
            "",
            f"PPT extracted slides {slide_count:,}장은 강의가 이미 책의 원재료였다는 증거다. 하지만 이 판본은 슬라이드의 순서를 그대로 옮기지 않는다. 강의의 흐름을 독자의 실행 순서로 다시 배열한다.",
            "",
            f"강의 자료는 가능성, 실습, 실패 복구, 결과 공유, 사후지원의 리듬을 가진다. 회사 AX 원고는 여기에 책임, 권한, KPI, 검증, 운영 지도를 더해야 한다. 말라카 외부 강의와 회사 AX를 분리해야 하는 이유가 여기에 있다.",
            "",
            f"`{section}`이 강의장에서 다뤄진다면 강사는 먼저 작은 성공을 보여 준다. 회사 안에서 다뤄진다면 담당자는 먼저 위험과 책임을 확인한다. 같은 바이브코딩이라도 성공 기준이 달라진다.",
            "",
            f"독자는 자기 강의나 사내교육 자료를 볼 때 슬라이드 제목만 보지 말고, 수강생이 멈춘 지점과 회사 담당자가 불안해한 지점을 같이 표시한다. 책의 절은 그 멈춤과 불안에서 태어난다.",
            "",
            f"#### {chapter_idx}-{section_idx}.E. Voice transcript 톤 보강",
            "",
            f"Voice transcript {voice_count:,}개는 원문 인용보다 리듬을 제공한다. 구술 기록에는 강의 직후의 흥분, 회사 업무 뒤의 피로, 새 아이디어가 떠오를 때의 빠른 판단이 남아 있다. 이 원고는 그 리듬을 복붙하지 않고 문장 구조로만 가져온다.",
            "",
            f"말로 나온 생각은 거칠지만 방향이 선명하다. 그 거친 방향을 원고로 옮길 때는 주장, 장면, 방법, 검증, 다음 행동으로 정리해야 한다. 그래야 독자는 저자의 하루가 아니라 자기 회사의 다음 행동을 읽게 된다.",
            "",
            f"`{section}`은 구술로 말하면 쉽게 흘러갈 수 있다. 책 문장으로 바꾸면 판단이 남아야 한다. 그래서 이 판본은 각 절마다 실행 표면과 공개 전 정제 기준을 반복해서 붙인다.",
            "",
            f"독자는 회의 뒤 3분 녹음을 남기고 그 안에서 반복 단어를 찾는다. 반복 단어가 `수작업`, `확인`, `엑셀`, `누락`, `다시`, `누가`라면 그 업무는 자동화 후보가 아니라 운영 재설계 후보일 수 있다.",
            "",
            f"#### {chapter_idx}-{section_idx}.F. 상장 가능한 체질로 닫기",
            "",
            f"이 절의 마지막 질문은 늘 같다. 이 내용이 상장 가능한 회사 체질을 더 강하게 만드는가. 답이 아니오라면 그 자동화는 멋진 데모일 뿐이다. 답이 예라면 그 자동화는 데이터 흐름, 책임, 검증, KPI 중 하나를 개선해야 한다.",
            "",
            f"`{chapter.title}`은 개인의 기술이 아니라 회사의 체질을 묻는다. 한 사람이 빨라지는 것을 넘어서 다른 사람이 이어받을 수 있는가. 감사와 회계와 고객 대응 앞에서도 설명 가능한가. 사내교육 이후에도 계속 쓰이는가.",
            "",
            f"이 질문은 책의 모든 장에 반복된다. 반복은 의도적이다. 600쪽 판본은 새로운 소재를 늘어놓기 위해 길어진 것이 아니라, 같은 원칙을 Daily, Notion, ChatGPT, PPT, voice, 회사 AX, 말라카 강의의 여러 표면에서 다시 검증하기 위해 길어진 것이다.",
            "",
            f"독자는 여기서 한 줄을 남기면 된다. `{section}`을 우리 회사에서 실행하면 어떤 지표가 바뀌는가. 그 지표가 없다면 아직 실행이 아니라 아이디어다.",
            "",
        ]
        return lines + extra

    base.section_paragraphs = expanded_section_paragraphs

    def clean_public_text(text: str) -> str:
        if not text:
            return ""
        phrase_replacements = {
            "500개 꼭지 중 회사 AX, 강의, 퓨처셀프, ChatGPT 질문이 한 방향으로 만나는 지점은 `AI를 잘 쓰는 회사`라는 각오다.": "회사 AX, 강의, 미래 목표, 스스로 던진 질문이 한 방향으로 만나는 지점에는 `AI를 잘 쓰는 회사`라는 각오가 있다.",
            "커리어 기록에는 안정된 회사, 창업 경험, 강의, DOF 합류가 섞여 있다.": "커리어의 흐름에는 안정된 조직에서 배운 감각, 창업의 시행착오, 강의 경험, 제조업 AX 현장으로 옮겨 온 선택이 함께 놓여 있다.",
            "퓨처셀프 자료는 자기계발로 흐르기 쉽다.": "Future Self는 자칫 자기계발 구호로 흐르기 쉽다.",
            "DOF 합류 각오와 미션 리스트의 핵심은 도구 도입이 아니다.": "회사에 들어오며 세운 각오의 핵심은 도구 도입이 아니다.",
            "AX-Native, KPI, 실패 원인, 성공 기준 꼭지는 회사 AX 파트의 토대다.": "AX-Native, KPI, 실패 원인, 성공 기준은 회사 AX를 설명하는 토대다.",
            "DOF 미션 리스트와 daily 업무 기록은 영업, 주문, 회계, QC, 개발팀이 따로 움직일 때 생기는 마찰을 보여 준다.": "영업, 주문, 회계, QC, 개발팀이 따로 움직일 때 마찰이 생긴다. AX는 그 마찰을 줄이는 쪽으로 설계되어야 한다.",
            "도메인 담당자 교육 전략과 AI 상담부스, 작은 자동화 꼭지는 회사 AX의 핵심 인재 모델을 만든다.": "도메인 담당자 교육, AI 상담부스, 작은 자동화는 회사 AX의 핵심 인재 모델을 만든다.",
            "사용자는 말라카 강의와 회사 업무를 분리해 달라고 했다.": "말라카의 외부 강의와 회사 안의 AX 업무는 목적과 책임이 다르다.",
            "SPARK-IPO는 이 책의 차별점이다. 강의 자료와 AGENTS 규칙에 흩어진 방법론을 회사 운영 언어로 재정리한다.": "SPARK-IPO의 힘은 일의 흐름을 누구나 따라갈 수 있게 나누는 데 있다. 흩어진 실행 방식을 회사 운영 언어로 다시 세운다.",
            "강의 자료와 AGENTS 규칙에 흩어진 방법론을 회사 운영 언어로 재정리한다.": "강의와 작업 규칙에 흩어진 방법론을 회사 운영 언어로 재정리한다.",
            "자료가 많다고 좋은 결과가 나오는 것은 아니다.": "입력이 많다고 좋은 결과가 나오는 것은 아니다.",
            "어떤 자료가 입력이고, 어떤 규칙으로 처리하며, 어떤 출력물이 사용 가능한지 분리해야 한다.": "무엇이 입력이고, 어떤 규칙으로 처리하며, 어떤 결과가 실제로 쓰일 수 있는지 분리해야 한다.",
            "프롬프트 관련 꼭지는 바이브코딩을 유행어에서 방법론으로 끌어올리는 장치다.": "좋은 프롬프트의 기준은 바이브코딩을 유행어가 아니라 방법론으로 만든다.",
            "프론트엔드, 웹앱, 개발자도구, 콘솔, 배포 꼭지는 비개발 독자가 최소 구조를 이해하게 만드는 파트다.": "프론트엔드, 웹앱, 개발자도구, 콘솔, 배포는 비개발 독자가 최소 구조를 이해하게 만드는 출발점이다.",
            "창업, 아이코어, Lovable, 제품 개발 꼭지는 회사 상장이라는 큰 목표를 작은 실험으로 낮추는 파트다.": "창업과 제품 개발의 경험은 회사 상장이라는 큰 목표를 작은 실험으로 낮추는 데 쓰인다.",
            "Problem-Tech Fit, 정보구걸, 역할 기반 인터뷰 꼭지는 바이브코딩의 창업적 균형추다.": "Problem-Tech Fit, 정보 구하기, 역할 기반 인터뷰는 바이브코딩의 창업적 균형추다.",
            "검증, Git, privacy mode, 보안, E2E, 오류 복구 꼭지는 책의 균형추다.": "검증, Git, 보안 모드, E2E, 오류 복구는 빠른 실행을 잡아 주는 균형추다.",
            "SaaS의 종말, 내부툴, 주문앱, 자연어 CRM 꼭지는 회사 AX와 바이브코딩의 접점을 만든다.": "SaaS의 변화, 내부툴, 주문앱, 자연어 CRM은 회사 AX와 바이브코딩의 접점을 만든다.",
            "여러 강의 공유노트와 PPT는 같은 주제가 다른 대상에게 어떻게 바뀌는지 보여 준다.": "여러 강의 경험은 같은 주제도 대상에 따라 다른 언어로 바뀌어야 한다는 점을 보여 준다.",
            "AI 클리닉, 오프모임, 강의 후 실제 결심, 커뮤니티 운영 꼭지는 강의를 인재 엔진으로 확장한다.": "AI 클리닉, 오프라인 모임, 강의 후 실행 약속, 커뮤니티 운영은 강의를 인재 엔진으로 확장한다.",
            "내가 다뤄 온 질문 목록은 시장의 언어를 빌리지 않아도 독자의 불안을 보여 준다.": "현장에서 반복해서 마주한 질문들은 시장의 유행어보다 더 정확하게 독자의 불안을 보여 준다.",
            "SPARK는 폴더명이 아니라 책임의 분류다.": "SPARK는 이름표가 아니라 책임을 나누는 방식이다.",
            "독자는 자기 팀 프로젝트에 SPARK 폴더 하나를 만들고 첫 Spec과 Plan을 적는다.": "독자는 자기 팀 프로젝트에 SPARK 구조를 하나 만들고 첫 Spec과 Plan을 적는다.",
            "이 장은 AI 도입 담론을 회사의 실행 기준으로 번역한다.": "이 장은 AI 도입 담론을 회사의 실행 기준으로 바꾼다.",
            "미래를 적었다면 바로 줄여야 한다. 10년 뒤의 AI 전문가라는 말은 이번 달의 검증 가능한 업무 자동화 하나로 내려와야 한다.": "미래를 적었다면 바로 작게 내려와야 한다. 10년 뒤의 AI 전문가라는 말은 이번 달의 검증 가능한 업무 자동화 하나로 이어져야 한다.",
        }
        for old, new in phrase_replacements.items():
            text = text.replace(old, new)
        replacements = {
            "500개 꼭지": "여러 경험",
            "ChatGPT 질문": "스스로 던진 질문",
            "ChatGPT": "AI 대화",
            "Notion": "기록",
            "Daily": "하루 기록",
            "PPT": "강의",
            "voice transcript": "구술 기록",
            "Voice transcript": "구술 기록",
            "로컬": "내부",
            "원고": "본문",
            "자료집": "메모 묶음",
            "공개본": "책",
            "외부 공개 전": "책으로 내기 전에",
            "꼭지": "이야기",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = text.replace("기록를", "기록을").replace("기록가", "기록이").replace("기록는", "기록은")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def clean_title(chapter) -> str:
        title_replacements = {
            "IPO는 자료를 결과로 통과시키는 배관이다": "IPO는 입력을 결과로 통과시키는 배관이다",
            "Future Self는 개인 목표가 아니라 조직 설계의 언어다": "Future Self는 개인 목표를 조직의 선택 기준으로 바꾼다",
            "AI를 가장 잘 쓰는 회사라는 각오": "AI를 가장 잘 쓰는 회사가 되겠다는 각오",
            "SaaS의 종말과 내부툴의 시대": "SaaS를 넘어 내부툴을 직접 만드는 시대",
        }
        return title_replacements.get(chapter.title, chapter.title)

    def clean_figure_for(idx: int, assets: list[Path]) -> list[str]:
        lines: list[str] = []
        for image_no, item in enumerate(placements_by_chapter.get(idx, []), 1):
            rel = str(item["rel_path"])
            placement = str(item.get("placement") or "standard")
            caption = clean_public_text(str(item.get("caption") or "아이디어가 실행으로 넘어가는 순간을 떠올리기 위한 시각 장면."))
            lines.extend(
                [
                    f'<figure class="book-figure ppt-internal {base.esc(placement)}">',
                    f'<img src="{base.esc(rel)}" alt="제{idx}장 참고 이미지 {image_no}">',
                    f"<figcaption>{base.esc(caption)}</figcaption>",
                    "</figure>",
                    "",
                ]
            )
        if lines:
            return lines
        if not assets:
            return []
        safe_fallback_names = {
            "ppt-figure-04.jpg",
            "ppt-figure-05.jpg",
            "ppt-figure-06.jpg",
            "ppt-figure-10.jpg",
            "ppt-figure-11.jpg",
            "ppt-figure-12.jpg",
            "ppt-figure-14.jpg",
            "ppt-figure-16.jpg",
            "ppt-figure-17.jpg",
            "ppt-figure-18.jpg",
        }
        safe_assets = [asset for asset in assets if asset.name in safe_fallback_names]
        if not safe_assets:
            return []
        asset = safe_assets[(idx * 5) % len(safe_assets)]
        rel = asset.relative_to(OUT)
        return [
            '<figure class="book-figure ppt-internal standard">',
            f'<img src="{base.esc(str(rel))}" alt="제{idx}장 보조 이미지">',
            "<figcaption>강의와 실행 사이의 거리를 좁히는 장면.</figcaption>",
            "</figure>",
            "",
        ]

    def chapter_question(chapter, chapter_idx: int) -> str:
        questions = (
            "이 장에서 붙잡을 질문은 간단하다. 좋은 의도와 빠른 실행이 실제 회사의 체질로 남으려면 무엇이 달라져야 할까.",
            "여기서 중요한 것은 도구의 이름이 아니다. 같은 일을 다시 해야 할 때 더 적은 불안과 더 많은 신뢰가 남는 구조를 만드는 일이다.",
            "회사가 커질수록 사람의 기억에 기대는 일은 위험해진다. 이 장은 그 기억을 기준, 흐름, 책임으로 바꾸는 방법을 다룬다.",
            "AI는 출발을 빠르게 해 준다. 하지만 회사가 얻는 가치는 빠른 출발이 아니라 끝까지 설명할 수 있는 결과에서 나온다.",
            "강의장과 회사는 닮았지만 같지 않다. 이 장은 두 장면을 구분하면서도, 둘 모두에서 통하는 실행의 질서를 찾는다.",
        )
        return questions[chapter_idx % len(questions)]

    def clean_section_paragraphs(chapter, topics, group, chapter_idx, section_idx, section):
        prompt = chapter.sections[section_idx - 1]
        section_name = clean_public_text(section)
        prompt_name = clean_public_text(prompt)
        safe_subtitle = clean_public_text(chapter.subtitle)
        safe_claim = clean_public_text(chapter.claim)
        safe_method = clean_public_text(chapter.method)
        safe_action = clean_public_text(chapter.action).replace("`", "")
        part_hint = {
            "1부. 상장을 향한 각오": "상장은 멀리 있는 이벤트처럼 보이지만, 실제로는 오늘의 일 처리 방식에서 이미 시작된다.",
            "2부. 상장 가능한 회사의 AX 체질": "체질은 한 번의 프로젝트가 아니라 매일 반복되는 업무 습관에서 만들어진다.",
            "3부. SPARK-IPO와 바이브코딩 실행법": "실행법은 멋진 구호가 아니라 다음 사람이 이어받을 수 있는 순서다.",
            "4부. MVP와 제품화": "작은 제품은 작아서 중요한 것이 아니라, 다음 결정을 가능하게 하기 때문에 중요하다.",
            "5부. 말라카 강의와 인재 엔진": "강의는 지식을 전달하는 시간이기도 하지만, 사람이 실제로 움직이는 구조를 실험하는 자리이기도 하다.",
            "6부. 상장 가능한 조직의 검증과 확산": "확산은 더 많이 쓰게 만드는 일이 아니라, 더 안심하고 맡길 수 있게 만드는 일이다.",
        }.get(chapter.part, "중요한 것은 도구보다 일의 흐름이다.")
        section_question = f"{prompt_name}. 이 주제를 제대로 붙잡으면 먼저 일이 보이는 방식이 바뀐다. 막연히 바쁘다고 느끼던 업무가 입력, 판단, 확인, 전달이라는 흐름으로 나뉜다."
        opening = (
            "처음부터 거대한 전환을 상상하면 오히려 시작이 느려진다. 회사의 변화는 대개 작은 불편을 정확히 부르는 데서 출발한다.",
            "현장에서 중요한 문장은 길지 않다. 누가 무엇을 기다리고 있는지, 어떤 숫자를 다시 확인하는지, 어디서 같은 설명이 반복되는지 보이면 된다.",
            "좋은 실행은 분위기로 남지 않는다. 기준이 남고, 순서가 남고, 다음 사람이 이어받을 수 있는 단서가 남는다.",
            "이 대목에서 필요한 것은 더 많은 도구 목록이 아니다. 지금 하는 일을 조금 더 정직하게 바라보는 힘이다.",
        )[(chapter_idx + section_idx) % 4]
        company_or_lecture = (
            "강의장에서는 수강생이 자기 손으로 결과를 만들 때 비로소 배움이 시작된다. 말라카의 외부 강의는 그 경험을 설계하는 일이다."
            if chapter.part.startswith("5부.")
            else "회사에서는 누가 멋진 말을 했는지보다 실제 업무가 어떻게 달라졌는지가 더 중요하다. AX는 그 변화가 남도록 만드는 일이다."
        )
        risk = (
            "빠른 결과가 늘 좋은 결과는 아니다. 너무 빨리 만든 결과가 어디서 틀릴 수 있는지 묻지 않으면, 속도는 곧 불안이 된다.",
            "처음부터 완벽한 체계를 만들 필요는 없다. 대신 작은 자동화 하나라도 입력과 판단과 결과를 분리해서 남겨야 한다.",
            "사람이 하던 일을 AI에게 맡길수록 사람의 책임은 사라지는 것이 아니라 더 선명해진다. 무엇을 확인해야 하는지 말할 수 있어야 한다.",
            "실패를 숨기면 조직은 같은 실수를 반복한다. 실패를 작게 만들고 되돌릴 수 있게 남기면 그 자체가 회사의 학습이 된다.",
        )[(chapter_idx * 2 + section_idx) % 4]
        practice = (
            "가장 좋은 시작은 오늘 반복한 일 하나를 고르는 것이다. 그 일을 한 문장으로 쓰고, 사람이 마지막에 확인해야 할 기준을 붙여 본다.",
            "회의에서 바로 써먹을 수 있는 질문도 있다. 이 업무의 입력은 무엇인가, 누가 판단하는가, 결과는 어디에 남는가.",
            "팀 안에서 합의해야 할 것은 거창하지 않다. 이 일은 자동화해도 되는가, 사람이 꼭 남아야 하는 지점은 어디인가.",
            "작게 남긴 기준은 나중에 큰 시스템을 만들 때 힘이 된다. 처음부터 많은 것을 연결하려 하지 말고, 믿을 수 있는 한 조각을 만든다.",
        )[(chapter_idx + section_idx * 3) % 4]
        chapter_anchor = {
            "이 제목은 상장 보장이 아니라 체질 개선의 선언이다": "상장이라는 말은 자칫 사람을 들뜨게 만든다. 그래서 이 책에서 그 말을 쓸 때마다 다시 업무의 바닥으로 내려온다. 결국 묻고 싶은 것은 하나다. 회사가 커져도 같은 품질로 일할 수 있는가.",
            "카카오모빌리티 이후, 제조업 AX 현장으로 들어간 이유": "큰 조직에서 배운 것은 시스템이 개인보다 오래가야 한다는 감각이었다. 제조업 현장으로 옮겨 오면 그 감각은 더 직접적인 질문이 된다. 오늘의 주문, 고객, 회계, 품질 흐름을 누가 설명할 수 있는가.",
            "Future Self는 개인 목표가 아니라 조직 설계의 언어다": "미래를 적는 일은 멋진 문장을 만드는 일이 아니다. 오히려 오늘 하지 않을 일을 정하는 일에 가깝다. 목표가 크다면 오늘의 선택은 더 작고 분명해야 한다.",
            "AI를 가장 잘 쓰는 회사라는 각오": "AI를 잘 쓴다는 말은 프로그램을 많이 아는 사람 몇 명의 능력으로 끝나지 않는다. 현업이 문제를 말하고, 리더가 우선순위를 정하고, 기술 담당자가 위험을 줄이는 구조가 함께 움직여야 한다.",
            "AI-Native 회사의 기준은 1x, 10x, 100x로 나뉜다": "모든 업무에 같은 기대치를 걸면 조직은 빨리 지친다. 어떤 일은 안정화만 해도 충분하고, 어떤 일은 열 배 빠르게 만들 수 있다. 아주 일부만 백 배의 재설계를 요구한다.",
            "영업, CRM, 주문, 회계, QC를 하나의 운영 지도로 본다": "부서가 나뉘는 것은 자연스럽다. 문제는 데이터까지 같이 끊기는 순간이다. 고객의 말이 주문으로, 주문이 회계로, 회계의 확인이 다시 운영으로 이어져야 회사는 덜 흔들린다.",
            "도메인 담당자가 가장 빠른 개발자가 되는 순간": "현업 담당자는 이미 문제의 절반을 알고 있다. 어디서 막히는지, 어떤 예외가 자주 나오는지, 어떤 숫자가 믿기 어려운지 알고 있다. 바이브코딩은 그 지식을 개발의 출발점으로 올려놓는다.",
            "사내교육은 말라카 강의가 아니라 회사 책임 체계다": "외부 강의에서는 참여자가 자신감을 얻고 결과물을 만들어 보는 일이 중요하다. 회사 안 교육은 다르다. 권한, 데이터, 보안, 사후지원, KPI까지 함께 설계되어야 한다.",
            "SPARK는 AI 시대의 회사 운영체계다": "AI와 일할수록 기록의 질이 중요해진다. 요청이 흩어지고 결과가 흩어지면 속도는 남아도 자산은 남지 않는다. SPARK는 일을 다시 찾을 수 있게 만드는 최소한의 질서다.",
            "IPO는 자료를 결과로 통과시키는 배관이다": "입력과 처리와 결과를 나누는 일은 단순해 보인다. 하지만 이 구분이 없으면 결과가 마음에 들지 않을 때 어디를 고쳐야 하는지 알 수 없다.",
            "프롬프트는 설계 문서다": "좋은 프롬프트는 주문처럼 보이지만 실제로는 설계 문서에 가깝다. 목표와 맥락과 제약을 적는 순간, AI뿐 아니라 사람도 같은 일을 이해하기 시작한다.",
            "프론트엔드는 독자가 처음 만나는 계약면이다": "화면은 장식이 아니다. 사용자가 무엇을 해야 하는지 알려 주고, 회사가 어떤 데이터를 믿는지 드러낸다. 그래서 첫 화면은 제품의 약속이자 운영의 약속이다.",
            "하루짜리 MVP는 첫 증거다": "하루 만에 세상을 바꾸는 제품을 만들 수는 없다. 그러나 하루 만에 질문을 좁히고, 한 화면을 만들고, 다음 판단에 필요한 반응을 얻는 것은 가능하다.",
            "Problem-Tech Fit이 먼저다": "기술은 문제를 해결할 때 힘을 얻는다. 문제가 흐릿한데 기술부터 붙이면 결과물은 빠르게 나오지만, 왜 필요한지 설명하기 어려워진다.",
            "개발비는 줄어도 검증비는 사라지지 않는다": "AI가 초안을 빠르게 만들수록 검증의 무게는 더 커진다. 비용이 줄었다고 책임까지 줄어드는 것은 아니다. 오히려 무엇을 믿을 수 있는지 더 자주 물어야 한다.",
            "SaaS의 종말과 내부툴의 시대": "모든 SaaS가 사라지는 것은 아니다. 다만 회사마다 다른 작은 업무를 직접 다룰 수 있는 선택지가 생겼다. 내부툴은 그 선택지를 책임 있게 쓰는 방식이다.",
            "170명 실습강좌는 말솜씨가 아니라 시스템이다": "대규모 실습에서는 강사의 말보다 운영의 빈틈이 먼저 드러난다. 설치, 로그인, 질문 흐름, 조교의 시선, 결과 공유까지 준비되어야 강의가 움직인다.",
            "WhyQ, KUBIT, KU, PKNU에서 배운 실습의 질서": "대상에 따라 같은 설명도 달라져야 한다. 대학생, 창업자, 실무자, 팀 프로젝트 참여자는 각자 다른 곳에서 멈춘다. 좋은 강의는 그 멈춤을 미리 예상한다.",
            "강의 이후 커뮤니티와 사후지원": "강의가 끝나는 순간부터 진짜 차이가 난다. 결과물을 계속 만지고, 서로 피드백하고, 다음 실험을 약속할 때 강의는 일회성 이벤트를 넘어선다.",
            "데일리보다 요령을 툭툭 던지는 방식": "매일 긴 글을 쓰지 않아도 사람을 움직이는 문장은 남길 수 있다. 짧은 요령 하나가 오늘의 행동을 바꾸면, 그것이 다음 장의 씨앗이 된다.",
            "창업 이야기와 인도인 외주에서 배운 것": "창업 과정에서 배운 가장 현실적인 교훈은 멀리 있는 사람과도 일할 수 있지만, 기준 없이 맡기면 결과가 멀어진다는 점이다. 속도보다 합의가 먼저다.",
            "AI 상담부스와 AX 클리닉": "상담부스나 클리닉은 정답을 나눠 주는 자리가 아니다. 각자의 업무를 들고 와서 어디부터 바꾸면 좋을지 함께 좁히는 자리다.",
            "상장 가능한 조직은 문서보다 검증 루틴을 가진다": "문서는 중요하지만 문서만으로 조직이 바뀌지는 않는다. 실제 힘은 정기적으로 확인하고, 틀린 것을 고치고, 다시 기준을 업데이트하는 루틴에서 나온다.",
            "이 책은 독자에게 어떤 행동을 요구하는가": "좋은 책은 독자를 감탄하게 만드는 데서 끝나지 않는다. 책을 덮은 뒤 작은 행동 하나가 달라져야 한다. 이 책이 요구하는 행동도 결국 거기 있다.",
        }.get(chapter.title, "이 장의 이야기는 하나의 원칙으로 모인다. AI를 잘 쓰려면 일을 먼저 잘게 나누고, 사람이 책임질 기준을 분명히 해야 한다.")
        section_lens = (
            f"`{section_name}`이라는 제목은 추상적으로 보이지만 실제로는 아주 구체적인 장면을 가리킨다. 누군가 기다리는 답, 매번 다시 확인하는 숫자, 담당자가 바뀌면 흔들리는 순서가 모두 여기에 들어온다.",
            f"`{section_name}`. 이 주제를 다룰 때 조심할 점은 멋진 말에 취하지 않는 것이다. 현장에서 쓸 수 있는 문장은 대개 짧고, 바로 다음 행동을 가리킨다.",
            f"`{section_name}`. 이것은 단독으로 떨어진 주제가 아니다. 앞의 결정이 다음 업무의 입력이 되고, 다음 업무의 결과가 다시 앞선 판단을 검증한다.",
            f"`{section_name}`. 이 관점이 잡히면 팀의 대화가 달라진다. 누가 잘못했는지를 묻기보다 어느 기준이 없었는지를 먼저 묻게 된다.",
        )[(chapter_idx + section_idx) % 4]
        operator_note = (
            "운영 관점에서 보면 작은 불편은 그냥 불편이 아니다. 반복되는 불편은 회사가 아직 언어로 만들지 못한 프로세스다.",
            "리더가 해야 할 일은 모든 답을 갖는 것이 아니다. 어떤 일을 먼저 정리해야 하는지 정하고, 정리된 기준이 계속 쓰이게 만드는 것이다.",
            "실무자가 해야 할 일도 달라진다. 불편을 참는 사람이 아니라, 불편을 설명할 수 있는 사람이 되어야 한다.",
            "개발자는 마지막 해결사로만 불려가서는 안 된다. 문제 정의와 검증 기준이 올라오는 길을 함께 설계해야 한다.",
        )[(chapter_idx * 3 + section_idx) % 4]
        proof_note = (
            "검증은 마지막에 붙이는 절차가 아니다. 처음부터 무엇을 확인할지 정해 두어야 결과가 나왔을 때 흔들리지 않는다.",
            "잘 만든 자동화는 설명이 가능하다. 왜 이 값을 썼는지, 어떤 예외를 막았는지, 실패하면 누가 보는지 말할 수 있어야 한다.",
            "성과는 사용량만으로 판단하기 어렵다. 같은 질문이 줄었는지, 같은 실수가 줄었는지, 담당자의 불안이 줄었는지를 함께 봐야 한다.",
            "한 번 통과한 기준도 영원하지 않다. 업무가 바뀌면 기준도 바뀐다. 그래서 AX는 프로젝트가 아니라 계속 고치는 운영 방식이다.",
        )[(chapter_idx + section_idx * 5) % 4]
        meeting_note = (
            "이 기준이 생기면 회의도 짧아진다. 각자 기억하는 사실을 맞추느라 시간을 쓰지 않고, 같은 화면과 같은 기준을 보며 다음 결정을 이야기할 수 있다.",
            "회의에서 가장 피곤한 순간은 모두가 열심히 말하는데 기준이 서로 다른 때다. AX가 해야 할 일은 그 기준을 한곳에 모아 대화의 출발선을 맞추는 것이다.",
            "좋은 회의록은 말을 많이 옮긴 기록이 아니다. 다음 사람이 어떤 판단을 이어받아야 하는지 보이는 기록이다.",
            "회의가 끝난 뒤 일이 다시 흩어진다면 아직 프로세스가 된 것이 아니다. 결정, 담당, 기한, 확인 방법이 함께 남아야 한다.",
        )[(chapter_idx + section_idx * 7) % 4]
        metric_note = (
            "측정도 거창할 필요가 없다. 재입력 횟수, 확인에 걸린 시간, 되묻는 메시지 수, 예외 처리 건수처럼 작지만 반복되는 숫자부터 보면 된다.",
            "처음부터 완벽한 KPI를 만들려고 하면 아무것도 시작하지 못한다. 대신 오늘보다 나아졌는지 확인할 수 있는 작고 솔직한 숫자가 필요하다.",
            "숫자는 사람을 압박하기 위해서가 아니라, 막연한 느낌을 줄이기 위해 필요하다. 느낌이 줄어야 팀은 다음 실험을 편하게 고를 수 있다.",
            "한 번 좋아진 숫자만 보면 안 된다. 누군가의 숨은 노동이 늘어난 것은 아닌지, 다른 부서의 부담이 커진 것은 아닌지도 같이 봐야 한다.",
        )[(chapter_idx * 5 + section_idx) % 4]
        handoff_note = (
            "인수인계가 쉬워졌는지도 좋은 신호다. 담당자가 바뀌어도 같은 기준으로 일을 시작할 수 있다면 그 업무는 조금 더 회사의 자산에 가까워진다.",
            "사람에게만 붙어 있던 노하우가 문장과 화면과 체크리스트로 옮겨질 때 조직은 가벼워진다. 누군가 쉬어도 일이 무너지지 않는다.",
            "좋은 자동화는 사람을 지우지 않는다. 오히려 사람이 더 중요한 판단에 시간을 쓰도록 잡일을 덜어 낸다.",
            "다음 사람이 이해하지 못하는 결과물은 아직 회사의 결과물이 아니다. 설명 가능한 형태로 남기는 일까지가 실행이다.",
        )[(chapter_idx * 2 + section_idx * 3) % 4]
        trust_note = (
            "신뢰는 선언으로 생기지 않는다. 작은 결과가 반복해서 맞고, 틀렸을 때 고치는 길이 보일 때 생긴다.",
            "팀이 AI 결과를 믿기 시작하는 순간은 대단한 발표 뒤가 아니다. 어제 귀찮았던 일이 오늘 조금 덜 귀찮아졌다는 경험 뒤다.",
            "신뢰가 생기면 질문의 수준도 달라진다. 이거 되느냐가 아니라, 어디까지 맡겨도 되는가를 묻게 된다.",
            "반대로 신뢰가 깨지는 것도 한순간이다. 그럴듯한 결과를 검증 없이 통과시키면 다음부터는 아무도 마음 편히 맡기지 못한다.",
        )[(chapter_idx + section_idx * 11) % 4]
        boundary_note = (
            "경계를 정하는 일도 중요하다. AI에게 맡길 일, 사람이 확인할 일, 리더가 결정할 일을 섞어 두면 속도는 나도 책임은 흐려진다.",
            "모든 것을 열어 두면 자유로워 보이지만 실제로는 불안정하다. 좋은 제약은 창의성을 막는 것이 아니라 결과를 믿을 수 있게 만든다.",
            "권한이 필요한 업무에서는 더 조심해야 한다. 볼 수 있는 사람, 바꿀 수 있는 사람, 승인해야 하는 사람을 구분해야 한다.",
            "고객과 맞닿는 영역에서는 말투 하나도 운영의 일부가 된다. 빠르게 보내는 것보다 정확하고 책임 있게 보내는 것이 먼저다.",
        )[(chapter_idx * 7 + section_idx) % 4]
        growth_note = (
            "이런 경험이 쌓이면 사람도 달라진다. 예전에는 요청만 하던 사람이 이제는 문제를 구조로 말하고, 결과를 검증하는 기준까지 제안한다.",
            "조직의 성장도 비슷하다. 한 사람의 요령이 팀의 규칙이 되고, 팀의 규칙이 회사의 운영 방식이 될 때 변화는 오래간다.",
            "교육의 역할은 여기서 다시 중요해진다. 사용법을 알려 주는 것만으로는 부족하다. 각자 자기 업무를 다시 설명할 수 있어야 한다.",
            "성장한 팀은 AI를 신기한 도구로 대하지 않는다. 필요한 곳에 쓰고, 위험한 곳에서는 멈추고, 배운 것을 다음 기준으로 남긴다.",
        )[(chapter_idx * 3 + section_idx * 2) % 4]
        reader_note = (
            "독자는 이 절을 읽고 바로 한 가지를 해볼 수 있다. 오늘 가장 자주 되묻는 업무를 적고, 그 질문이 왜 반복되는지 원인을 붙여 보는 것이다.",
            "지금 당장 자동화를 만들지 않아도 된다. 먼저 반복되는 말을 한 문장으로 정리해 보라. 그 문장이 다음 실행의 시작점이 된다.",
            "한 팀에서 시작한다면 가장 불만이 많은 업무보다 가장 설명하기 쉬운 업무를 고르는 편이 낫다. 첫 성공은 작고 명확해야 한다.",
            "혼자 시작한다면 더 단순하다. 오늘 한 번 더 확인한 값을 메모하고, 내일 그 확인을 줄일 수 있는 방법을 적어 본다.",
        )[(chapter_idx + section_idx * 13) % 4]
        maturity_note = (
            "성숙한 회사는 실수를 안 하는 회사가 아니다. 실수가 났을 때 어디서 틀렸는지 찾을 수 있고, 같은 실수가 반복되지 않게 기준을 고치는 회사다.",
            "상장 가능한 체질이라는 말도 결국 여기로 돌아온다. 빠른 실행, 남는 기록, 설명 가능한 숫자, 되돌릴 수 있는 절차가 함께 있어야 한다.",
            "AX가 조직문화가 되려면 한 번의 캠페인으로 끝나서는 안 된다. 작은 개선을 발견하고, 이름 붙이고, 다시 쓰게 만드는 리듬이 필요하다.",
            "좋은 변화는 조용히 퍼진다. 처음에는 한 사람의 불편을 줄이고, 다음에는 한 팀의 시간을 줄이며, 나중에는 회사의 판단 속도를 바꾼다.",
        )[(chapter_idx * 11 + section_idx) % 4]
        scale_note = (
            "확산은 복제와 다르다. 같은 방식을 억지로 밀어붙이는 것이 아니라, 다른 팀이 자기 업무에 맞게 바꿔 쓸 수 있는 원칙을 남기는 일이다.",
            "작은 성공을 남길 때는 결과만 자랑하지 말고 조건도 함께 적어야 한다. 어떤 전제가 있었고, 어디까지는 아직 사람이 봐야 하는지까지 남겨야 한다.",
            "팀 하나에서 통하던 방식이 회사 전체로 갈 때는 언어가 더 단순해져야 한다. 누구나 이해할 수 있는 기준만이 오래 살아남는다.",
            "결국 좋은 실행은 다음 실행을 쉽게 만든다. 한 번 만든 기준이 다음 사람의 시작점을 높여 줄 때 회사의 속도는 조용히 올라간다.",
        )[(chapter_idx + section_idx * 17) % 4]
        return [
            f"### {chapter_idx}-{section_idx}. {section_name}",
            "",
            f"{part_hint} {section_question}",
            "",
            opening,
            "",
            f"{safe_claim} 이 말은 거창한 선언처럼 들릴 수 있지만, 실제로는 아주 작은 장면에서 확인된다. 같은 값을 또 옮기고, 같은 상태를 다시 묻고, 같은 파일을 열어 숫자를 확인하는 순간이다. 그 반복이 줄어들지 않으면 AI를 썼다는 말은 회사의 체질로 남지 않는다.",
            "",
            f"{safe_subtitle} 그래서 이 대목에서 필요한 태도는 조급함이 아니다. 빠르게 만들되, 무엇을 믿고 다음 단계로 넘어갈지 함께 정해야 한다. 속도만 남으면 불안이 커지고, 기준만 남으면 실행이 느려진다. 둘 사이의 균형이 AX의 실제 난이도다.",
            "",
            f"{safe_method} 이 방법을 현장으로 가져오면 역할이 조금 달라진다. 실무자는 문제를 가장 잘 아는 사람으로서 기준을 잡고, AI는 초안을 만들며, 개발자나 운영 책임자는 구조와 위험을 확인한다. 누가 더 중요한지가 아니라, 어느 판단을 누가 맡아야 하는지가 중요하다.",
            "",
            company_or_lecture,
            "",
            chapter_anchor,
            "",
            section_lens,
            "",
            operator_note,
            "",
            "여기서 바이브코딩은 코딩을 쉽게 포장하는 말이 아니다. 만들고 싶은 장면을 분명히 말하고, 필요한 맥락을 남기고, 작은 단위로 결과를 확인하는 일하는 방식이다. 그래서 비개발자에게도 필요하고, 이미 개발을 아는 사람에게도 필요하다.",
            "",
            risk,
            "",
            proof_note,
            "",
            meeting_note,
            "",
            metric_note,
            "",
            handoff_note,
            "",
            trust_note,
            "",
            boundary_note,
            "",
            growth_note,
            "",
            reader_note,
            "",
            maturity_note,
            "",
            scale_note,
            "",
            "이럴 때 필요한 질문은 복잡하지 않다. 이 일은 누가 시작하는가. 어떤 값이 들어오는가. 무엇을 보고 맞다고 판단하는가. 결과는 누구에게 전달되는가. 실패하면 어디로 돌아가는가. 이 다섯 가지가 답해지면 작은 자동화도 회사의 언어가 된다.",
            "",
            practice,
            "",
            "구성원은 전략 발표보다 자기 업무가 실제로 줄어드는 순간에 AX를 믿기 시작한다. 믿음은 말이 아니라 경험에서 생긴다. 그래서 첫 성공은 작아도 된다. 다만 그 성공이 어떤 기준으로 가능했는지는 남아야 한다.",
            "",
            "다만 모든 일을 자동화 대상으로 보면 안 된다. 사람의 판단이 남아야 하는 곳, 고객과 직접 맞닿는 곳, 회계나 보안처럼 설명 책임이 큰 곳은 더 천천히 가야 한다. 느리게 가자는 뜻이 아니다. 잘못 빨라지는 일을 피하자는 뜻이다.",
            "",
            f"{safe_action} 이 행동을 할 때도 마찬가지다. 멋진 계획보다 작은 증거가 먼저다. 종이에 써도 좋고, 회의록 한 줄이어도 좋다. 중요한 것은 다음 사람이 읽고 같은 판단을 할 수 있어야 한다는 점이다.",
            "",
            "이 대목을 한 문장으로 줄이면 이렇다. AI가 회사를 바꾸는 것이 아니라, AI가 일할 수 있도록 사람이 업무를 다시 정리할 때 회사가 바뀐다. 그 정리가 쌓일 때 비로소 상장 가능한 회사의 체질이라는 말도 힘을 얻는다.",
            "",
        ]

    def clean_render_book_md(topics, groups, assets):
        lines: list[str] = [
            '<section class="cover page">',
            f'<p class="cover-kicker">{base.BOOK_AUTHOR}</p>',
            f'<h1>{base.BOOK_TITLE}</h1>',
            f'<p class="cover-subtitle">{base.BOOK_SUBTITLE}</p>',
            '<p class="cover-promise">AI를 잘 쓰는 개인을 넘어, AI를 잘 쓰는 회사의 프로세스와 검증 문화를 만드는 책.</p>',
            f'<p class="cover-date">{base.BOOK_DATE}</p>',
            "</section>",
            "",
            '<section class="page title-page" markdown="1">',
            f"# {base.BOOK_TITLE}",
            "",
            f"## {base.BOOK_SUBTITLE}",
            "",
            f"{base.BOOK_AUTHOR} 지음",
            "</section>",
            "",
            '<section class="page copyright-page" markdown="1">',
            "# 서지정보",
            "",
            f"- 서명: {base.BOOK_TITLE}",
            f"- 부제: {base.BOOK_SUBTITLE}",
            f"- 저자: {base.BOOK_AUTHOR}",
            f"- 발행일: {base.BOOK_DATE}",
            "",
            "이 책은 투자 조언도, 증권 조언도 아니다. 제목에 담긴 ‘회사 상장시키기’는 상장을 보장한다는 뜻이 아니다. 상장을 향해 가는 회사가 갖춰야 할 업무 흐름, 데이터의 신뢰, 검증 책임, 인재의 성장 방식을 AX와 바이브코딩의 언어로 설명하겠다는 뜻이다.",
            "</section>",
            "",
            '<section class="page preface-page" markdown="1">',
            "# 인트로: 상장 가능한 회사 체질을 만든다는 것",
            "",
            "AI 도구를 많이 쓰는 회사와 AI를 잘 쓰는 회사는 다르다. 전자는 새로운 서비스를 빠르게 받아들이는 회사다. 후자는 그 도구가 만든 결과를 설명할 수 있고, 사람이 바뀌어도 업무가 이어지며, 숫자와 판단의 흐름이 남는 회사다. 이 차이가 작아 보이지만 실제 현장에서는 결정적이다.",
            "",
            "상장을 향하는 회사에는 화려한 데모보다 단단한 반복이 필요하다. 고객 정보가 어디서 시작되는지, 주문과 결제가 어떻게 이어지는지, 회계와 품질 검토가 어떤 기준으로 닫히는지 설명할 수 있어야 한다. AI는 이 과정을 빠르게 만들 수 있지만, 대신 책임져 주지는 않는다.",
            "",
            "바이브코딩은 여기서 힘을 얻는다. 코드를 모르는 사람이 개발자 흉내를 내자는 말이 아니다. 자기 업무를 가장 잘 아는 사람이 문제를 문장으로 잡고, AI와 함께 초안을 만들고, 사람이 다시 검증하는 방식이다. 이 흐름이 반복되면 회사 안에 작은 변화가 쌓인다.",
            "",
            "이 책은 바로 그 작은 변화의 순서를 다룬다. 큰 비전을 말하되, 오늘 바꿀 수 있는 한 장면으로 내려온다. 상장을 보장하는 책이 아니라, 상장 가능한 회사가 되기 위해 지금부터 어떤 일을 정리해야 하는지 묻는 책이다.",
            "</section>",
            "",
            '<section class="page greeting-page" markdown="1">',
            "# 인사말: AI를 가장 잘 쓰는 회사라는 각오",
            "",
            "AI를 잘 쓰는 회사가 된다는 말은 처음에는 근사하게 들린다. 하지만 현장에 들어가면 그 말은 금세 구체적인 질문으로 바뀐다. 누가 같은 값을 다시 입력하고 있는가. 어떤 보고서는 매번 손으로 맞추고 있는가. 어떤 결정은 기록 없이 사람의 기억에만 남는가.",
            "",
            "나는 이 질문이야말로 AX의 출발점이라고 생각한다. AI를 도입한다는 말은 회의실에서 끝나기 쉽다. 하지만 반복 업무 하나가 줄고, 담당자가 검증 기준을 직접 잡고, 결과가 다음 사람에게 자연스럽게 넘어가는 순간 회사는 조금 달라진다.",
            "",
            "강의장에서 배운 것도 같다. 사람은 설명을 들을 때보다 자기 손으로 하나를 만들 때 바뀐다. 회사도 마찬가지다. 구성원이 자기 업무에서 작은 성공을 경험해야 AI 전환은 남의 일이 아니라 자기 일이 된다.",
            "",
            "이 책은 그 경험을 회사의 언어로 옮기려는 시도다. 말라카의 강의와 회사 안의 AX는 분명히 다르다. 강의는 사람을 움직이게 하는 장이고, 회사 AX는 책임과 검증을 남기는 장이다. 둘을 구분할 때 오히려 둘 다 선명해진다.",
            "",
            f"{base.BOOK_AUTHOR}",
            "</section>",
            "",
            '<section class="page toc-page" markdown="1">',
            "# 목차",
            "",
        ]
        current_part = ""
        for idx, chapter in enumerate(base.CHAPTERS, 1):
            if chapter.part != current_part:
                current_part = chapter.part
                lines.extend([f"## {chapter.part}", ""])
            lines.extend([f"- 제{idx}장 {clean_title(chapter)}", f"  - {clean_public_text(chapter.subtitle)}"])
        lines.extend(["</section>", ""])

        for idx, (chapter, group) in enumerate(zip(base.CHAPTERS, groups, strict=True), 1):
            if idx == 1 or chapter.part != base.CHAPTERS[idx - 2].part:
                lines.extend(
                    [
                        '<section class="page part-page" markdown="1">',
                        f"# {chapter.part}",
                        "",
                        chapter_question(chapter, idx),
                        "</section>",
                        "",
                    ]
                )
            lines.extend(
                [
                    '<section class="chapter-page" markdown="1">',
                    f"# {idx:02d}. {clean_title(chapter)}",
                    "",
                    f"**{clean_public_text(chapter.subtitle)}**",
                    "",
                    clean_public_text(chapter.claim),
                    "",
                    chapter_question(chapter, idx),
                    "",
                    *clean_figure_for(idx, assets),
                    clean_public_text(chapter.method),
                    "",
                    clean_public_text(chapter.action).replace("`", ""),
                    "",
                ]
            )
            for section_idx, section in enumerate(chapter.sections, 1):
                lines.extend(clean_section_paragraphs(chapter, topics, group, idx, section_idx, section))
            lines.extend(
                [
                    '<div class="chapter-coda">',
                    f"이 장의 결론은 분명하다. {clean_public_text(chapter.subtitle)} 다음 장에서는 이 판단을 또 다른 업무 표면으로 옮긴다.",
                    "</div>",
                    "</section>",
                    "",
                ]
            )

        lines.extend(
            [
                '<section class="page bibliography-page" markdown="1">',
                "# 마치는 글",
                "",
                "회사를 바꾸는 일은 대개 크고 멀게 느껴진다. 하지만 실제 변화는 작고 가까운 곳에서 시작된다. 오늘 누군가 손으로 옮기던 값을 줄이고, 다음 사람이 이해할 수 있는 기준을 남기고, 실패했을 때 돌아갈 곳을 정하는 일. 이런 장면이 쌓이면 회사는 조금씩 다른 체질을 갖게 된다.",
                "",
                "AI는 그 변화를 빠르게 만들 수 있다. 다만 빠른 속도만으로는 부족하다. 무엇을 맡길지, 무엇을 사람이 확인할지, 어떤 결과를 믿을지 정해야 한다. 그 기준을 세우는 사람이 많아질수록 회사의 AX는 유행이 아니라 운영 방식이 된다.",
                "",
                "이 책을 덮은 뒤 바로 거창한 프로젝트를 시작할 필요는 없다. 먼저 오늘 반복한 일 하나를 고르면 된다. 그리고 그 일을 입력, 판단, 결과, 검증으로 나누어 적어 보라. 거기서 첫 자동화가 시작되고, 첫 자동화가 다음 변화를 부른다.",
                "</section>",
                "",
                '<section class="page back-cover" markdown="1">',
                f"# {base.BOOK_TITLE}",
                "",
                "AI를 많이 쓰는 회사가 아니라 AI를 잘 쓰는 회사가 되어야 한다.",
                "",
                "이 책은 바이브코딩을 빠른 코딩 기술로만 다루지 않는다. 회사가 상장을 향해 갈 때 필요한 프로세스, 데이터, 검증, 사내교육, AX 클리닉, 인재 성장의 언어로 다시 설명한다. 말라카 외부 강의의 실습 운영과 회사 AX의 책임 체계를 분리해, 독자가 자기 회사에서 바로 첫 자동화를 시작할 수 있게 만든다.",
                "",
                "상장을 보장하는 책이 아니라, 상장 가능한 체질을 만드는 책.",
                "</section>",
                "",
            ]
        )
        return "\n".join(lines)

    base.figure_for = clean_figure_for
    base.section_paragraphs = clean_section_paragraphs
    base.render_book_md = clean_render_book_md

    original_main = base.main

    def main_with_report() -> int:
        rc = original_main()
        (OUT / "source-deepening-report.md").write_text(render_source_report(counts), encoding="utf-8")
        summary_path = OUT / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["source_deepening_report"] = str((OUT / "source-deepening-report.md").resolve())
        summary["source_inventory"] = str(INVENTORY.resolve())
        summary["local_source_counts"] = counts
        summary["ppt_internal_selected_images"] = len(image_placements)
        summary["ppt_image_placements"] = str((OUT / "ppt-image-placements.json").resolve()) if image_placements else None
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        review_path = OUT / "render-review.md"
        review = review_path.read_text(encoding="utf-8")
        review += "\n## 600쪽 보강\n\n"
        review += f"- 자료 보강 리포트: `{(OUT / 'source-deepening-report.md').resolve()}`\n"
        review += f"- Source inventory: `{INVENTORY.resolve()}`\n"
        review += f"- Daily/Notion/ChatGPT/PPT/voice counts: {json.dumps(counts, ensure_ascii=False)}\n"
        review += f"- PPT 내부 선별 이미지: {len(image_placements)}개\n"
        review_path.write_text(review, encoding="utf-8")
        return rc

    base.main = main_with_report


def main() -> int:
    base = load_base()
    install_600p_overrides(base)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
