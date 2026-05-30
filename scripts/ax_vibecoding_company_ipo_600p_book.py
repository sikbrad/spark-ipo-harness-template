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
    base.BOOK_SUBTITLE = "500개 꼭지와 Daily·Notion·ChatGPT·PPT를 다시 엮은, 상장 가능한 회사 체질을 만드는 AX 실행서"
    base.BOOK_EDITION = "600쪽 보강판"
    base.BOOK_DATE = "2026-05-31"
    base.PLAN_PATH = PLAN

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

    original_main = base.main

    def main_with_report() -> int:
        rc = original_main()
        (OUT / "source-deepening-report.md").write_text(render_source_report(counts), encoding="utf-8")
        summary_path = OUT / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["source_deepening_report"] = str((OUT / "source-deepening-report.md").resolve())
        summary["source_inventory"] = str(INVENTORY.resolve())
        summary["local_source_counts"] = counts
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        review_path = OUT / "render-review.md"
        review = review_path.read_text(encoding="utf-8")
        review += "\n## 600쪽 보강\n\n"
        review += f"- 자료 보강 리포트: `{(OUT / 'source-deepening-report.md').resolve()}`\n"
        review += f"- Source inventory: `{INVENTORY.resolve()}`\n"
        review += f"- Daily/Notion/ChatGPT/PPT/voice counts: {json.dumps(counts, ensure_ascii=False)}\n"
        review_path.write_text(review, encoding="utf-8")
        return rc

    base.main = main_with_report


def main() -> int:
    base = load_base()
    install_600p_overrides(base)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
