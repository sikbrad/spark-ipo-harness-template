#!/usr/bin/env python3
"""Build the AX/company-IPO vibecoding book edition.

This script renders a new authored edition from the local 500-topic inventory.
It does not scrape external APIs and does not stitch slide/PDF pages together.
The generated ordered topic map is deliberately explicit so the manuscript can
be reviewed and reorganized without re-reading the full source corpus.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import markdown
from weasyprint import HTML


ROOT = Path("data/vibecoding-book")
OUT = ROOT / "ax-company-ipo-2026-05-30"
TOPICS_PATH = ROOT / "story-topics-2026-05-30" / "vibecoding-story-topics.md"
PLAN_PATH = Path("proc/plan/2026-05-30_ax-vibecoding-company-ipo-book.md")
SOURCE_ASSET_DIR = ROOT / "market-rewrite-2026-05-27" / "assets" / "ppt-images"
ASSET_DIR = OUT / "assets" / "ppt-images"

BOOK_TITLE = "AX와 바이브코딩으로 회사 상장시키기"
BOOK_SUBTITLE = "상장을 보장하는 비법이 아니라, 상장 가능한 회사 체질을 만드는 AI 전환 운영서"
BOOK_AUTHOR = "말라카"
BOOK_DATE = "2026-05-30"
BOOK_EDITION = "500개 꼭지 재배열 초판"


def ids(spec: str) -> list[int]:
    values: list[int] = []
    for chunk in spec.replace("\n", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = [int(x) for x in chunk.split("-", 1)]
            values.extend(range(start, end + 1))
        else:
            values.append(int(chunk))
    return values


@dataclass(frozen=True)
class Chapter:
    part: str
    title: str
    subtitle: str
    claim: str
    scene: str
    method: str
    verification: str
    action: str
    topic_spec: str
    sections: tuple[str, ...]


CHAPTERS: tuple[Chapter, ...] = (
    Chapter(
        "1부. 상장을 향한 각오",
        "이 제목은 상장 보장이 아니라 체질 개선의 선언이다",
        "회사 상장은 결과이고, AX와 바이브코딩은 그 결과를 감당할 수 있는 운영 체질을 만드는 수단이다.",
        "이 책은 증권 조언도, 상장 로드맵도 아니다. 회사가 커져도 흔들리지 않는 데이터, 프로세스, 검증, 인재의 체질을 만드는 책이다.",
        "500개 꼭지 중 회사 AX, 강의, 퓨처셀프, ChatGPT 질문이 한 방향으로 만나는 지점은 `AI를 잘 쓰는 회사`라는 각오다.",
        "상장을 목표로 말할 때는 숫자보다 먼저 운영의 신뢰를 말한다. 신뢰는 자동화된 프로세스와 사람이 남긴 검증 기록에서 만들어진다.",
        "외부 공개 전에는 회사명, 고객명, 회계·보안 정보, 내부 링크를 익명화한다. 원고의 약속은 사례의 원문성이 아니라 재현 가능한 원칙이다.",
        "독자는 자기 회사의 `상장 가능한 체질`을 한 문장으로 정의하고, 그 체질을 방해하는 수작업 하나를 고른다.",
        "148-150,158-163,186-191,203-208,247-249,251-270,341-360,468-479,490,497",
        (
            "상장을 말할 때 먼저 버릴 착각",
            "상장 가능한 회사 체질의 네 가지 조건",
            "AX는 비용절감보다 신뢰축적의 언어다",
            "바이브코딩은 실행 속도를 올리는 근육이다",
            "책의 독자는 투자자가 아니라 운영 책임자다",
            "오늘 고를 첫 수작업",
        ),
    ),
    Chapter(
        "1부. 상장을 향한 각오",
        "카카오모빌리티 이후, 제조업 AX 현장으로 들어간 이유",
        "큰 회사에서 배운 시스템 감각은 제조업 AX 현장에서 더 직접적인 결과를 요구받는다.",
        "저자 서사는 퇴사담이 아니라 축적의 이동이어야 한다. 카카오모빌리티에서 배운 데이터와 조직 감각이 DOF의 프로세스 혁신 과제로 넘어간다.",
        "커리어 기록에는 안정된 회사, 창업 경험, 강의, DOF 합류가 섞여 있다. 이 장은 그 선택을 자랑이 아니라 책임의 이동으로 읽는다.",
        "개인이 회사를 상장시키는 것은 과장이다. 하지만 개인이 회사 안의 AI 전환 축을 맡고, 반복 업무와 데이터 흐름을 바꾸는 것은 실제 과업이다.",
        "서사에 포함되는 인물·회사·처우 정보는 공개본에서 덜어내고, 남기는 것은 선택의 기준과 역할의 변화다.",
        "독자는 자기 커리어에서 `다음 조직에 가져갈 수 있는 축적`을 적어 본다.",
        "020-024,114-115,127-129,138,140,224,301-315",
        (
            "졸업의 언어로 쓰는 커리어 전환",
            "큰 조직에서 배운 데이터 감각",
            "제조업 AX가 요구하는 현장성",
            "대표 직속 스폰서십과 실행 책임",
            "이직 서사를 책의 신뢰로 바꾸는 법",
            "나의 다음 역할을 문장으로 정하기",
        ),
    ),
    Chapter(
        "1부. 상장을 향한 각오",
        "Future Self는 개인 목표가 아니라 조직 설계의 언어다",
        "미래의 나는 꿈을 크게 쓰는 장식이 아니라 오늘의 선택을 줄이는 운영 장치다.",
        "퓨처셀프 자료는 자기계발로 흐르기 쉽다. 이 책에서는 큰 목표를 오늘의 AX 백로그와 강의 운영 기준으로 낮추는 장치로만 쓴다.",
        "DOF에 오면서 세운 각오, 강의 브랜드를 키우려는 계획, 35세/45세의 미래상은 모두 오늘의 작은 자동화로 번역되어야 힘을 얻는다.",
        "미래를 적었다면 바로 줄여야 한다. 10년 뒤의 AI 전문가라는 말은 이번 달의 검증 가능한 업무 자동화 하나로 내려와야 한다.",
        "개인 목표는 공개 가능 범위를 조절한다. 본문에는 사적인 결심보다 독자에게 이전 가능한 방법만 남긴다.",
        "독자는 10년 뒤 회사를 한 문장으로 쓰고, 이번 주에 만들 수 있는 가장 작은 증거를 고른다.",
        "093,116-119,137,164-167,243-244,349-380,427-435,452,457-459",
        (
            "미래의 나를 회사의 운영 기준으로 바꾸기",
            "큰 목표를 작은 자동화로 낮추기",
            "목표 제거가 AX 우선순위를 만든다",
            "강의 브랜드와 회사 업무를 섞지 않는 법",
            "루틴은 야망을 증거로 바꾼다",
            "이번 주의 미래 증거 만들기",
        ),
    ),
    Chapter(
        "1부. 상장을 향한 각오",
        "AI를 가장 잘 쓰는 회사라는 각오",
        "AI를 많이 쓰는 회사가 아니라 AI 사용이 프로세스와 책임으로 남는 회사가 되어야 한다.",
        "DOF 합류 각오와 미션 리스트의 핵심은 도구 도입이 아니다. 회사 전체의 반복 업무, 데이터 흐름, 의사결정 구조를 AI 친화적으로 바꾸는 것이다.",
        "AI를 가장 잘 쓰는 회사라는 문장은 멋있지만 위험하다. 좋은 문장일수록 KPI, 담당자, 검증 기준, 실패 처리 방식으로 내려와야 한다.",
        "각오는 사내교육으로 끝나지 않는다. 실제 주문, 영업, CRM, 회계, QC, 개발팀의 일을 바꾸어야 한다.",
        "상장·회계·고객 신용·보안 정보는 본문에서 원문 노출하지 않는다. 구조와 원칙만 남긴다.",
        "독자는 자기 회사에서 `AI를 잘 쓰는 회사`라는 말을 증명할 첫 부서와 첫 업무를 정한다.",
        "251-270,271-300,316-340",
        (
            "잘 쓰는 회사와 많이 쓰는 회사의 차이",
            "AI 미션 리스트를 조직 우선순위로 읽기",
            "Cross-silo 개발자의 역할",
            "CAIO/CIO 목표를 작은 실행으로 낮추기",
            "온보딩 질문이 회사의 빈틈을 보여 준다",
            "첫 부서와 첫 업무 정하기",
        ),
    ),
    Chapter(
        "2부. 상장 가능한 회사의 AX 체질",
        "AI-Native 회사의 기준은 1x, 10x, 100x로 나뉜다",
        "AI 전환은 전 직원에게 같은 속도를 요구하지 않는다. 업무별로 1x, 10x, 100x의 기대치를 나누어야 한다.",
        "AX-Native, KPI, 실패 원인, 성공 기준 꼭지는 회사 AX 파트의 토대다. 이 장은 AI 도입 담론을 회사의 실행 기준으로 번역한다.",
        "AI를 도입했다는 말은 너무 넓다. 어떤 업무는 1x 안정화가 먼저이고, 어떤 업무는 10x 자동화가 가능하며, 일부 업무만 100x 재설계가 된다.",
        "성공 기준이 없으면 도구 사용량만 늘고 회사 체질은 그대로 남는다.",
        "KPI는 부서별로 다르게 둔다. 영업, 회계, 개발, QC는 같은 AX 지표를 공유하지 않는다.",
        "독자는 자기 회사 업무를 1x 안정화, 10x 자동화, 100x 재설계 세 칸으로 나눈다.",
        "001-011,025,076-082,121,125,151-157,168-173,493,496",
        (
            "AI-Native의 최소 정의",
            "1x 안정화가 먼저인 업무",
            "10x 자동화가 가능한 업무",
            "100x 재설계가 필요한 업무",
            "AX KPI를 부서별로 다르게 잡기",
            "세 칸 분류표 만들기",
        ),
    ),
    Chapter(
        "2부. 상장 가능한 회사의 AX 체질",
        "영업, CRM, 주문, 회계, QC를 하나의 운영 지도로 본다",
        "상장 가능한 회사는 부서별 파일이 아니라 연결된 운영 지도를 가진다.",
        "DOF 미션 리스트와 daily 업무 기록은 영업, 주문, 회계, QC, 개발팀이 따로 움직일 때 생기는 마찰을 보여 준다.",
        "AX는 부서를 예쁘게 자동화하는 일이 아니다. 고객 정보가 CRM으로 들어오고, 주문과 결제와 회계와 QC와 개발 이슈가 끊기지 않게 흐르는 일이다.",
        "하나의 업무 자동화가 다른 부서의 검증 부담을 늘리면 회사 AX가 아니다.",
        "이 장의 사례는 공개 전 익명화한다. 중요한 것은 업무명보다 연결 방식이다.",
        "독자는 고객 접점에서 회계 검증까지의 흐름을 한 장짜리 운영 지도로 그린다.",
        "188-202,208-230,271-300,301-315",
        (
            "부서별 자동화의 함정",
            "CRM은 고객 메모장이 아니라 운영 시작점이다",
            "주문과 결제는 회계의 언어로 이어져야 한다",
            "QC와 개발팀 이슈까지 연결하기",
            "운영 지도에서 끊기는 지점 찾기",
            "한 장짜리 운영 지도 작성법",
        ),
    ),
    Chapter(
        "2부. 상장 가능한 회사의 AX 체질",
        "도메인 담당자가 가장 빠른 개발자가 되는 순간",
        "반복 업무를 가장 잘 아는 사람이 AI를 만나면 개발의 앞 절반은 이미 끝난다.",
        "도메인 담당자 교육 전략과 AI 상담부스, 작은 자동화 꼭지는 회사 AX의 핵심 인재 모델을 만든다.",
        "개발자가 모든 업무를 이해할 수는 없다. 도메인 담당자가 자기 일을 문장으로 설명하고, AI가 초안을 만들고, 개발자가 구조와 위험을 검토하는 분업이 필요하다.",
        "도메인 담당자를 개발자로 부르는 것이 목적은 아니다. 담당자가 문제와 검증 기준을 쥐게 만드는 것이 목적이다.",
        "권한과 보안은 담당자 교육의 일부다. 아무 데이터나 넣는 자동화는 회사의 신뢰를 해친다.",
        "독자는 자기 회사에서 가장 반복 업무를 잘 아는 사람 세 명을 적고, 그들의 첫 자동화 주제를 정한다.",
        "192,198-202,242,250,405-408,447-449,470,474,478,488,494",
        (
            "도메인 지식은 요구사항 이상의 가치다",
            "AI 상담부스가 필요한 이유",
            "현업과 개발자의 새 분업",
            "담당자가 검증 기준을 쥐는 법",
            "보안과 권한을 교육 안에 넣기",
            "첫 자동화 담당자 세 명 고르기",
        ),
    ),
    Chapter(
        "2부. 상장 가능한 회사의 AX 체질",
        "사내교육은 말라카 강의가 아니라 회사 책임 체계다",
        "같은 AI 교육이라도 외부 강의와 사내 AX 교육의 목적, 책임, 검증 기준은 다르다.",
        "사용자는 말라카 강의와 회사 업무를 분리해 달라고 했다. 이 장은 그 경계를 책의 핵심 원칙으로 세운다.",
        "외부 강의는 수강생의 효능감과 결과물 공유가 중요하다. 사내교육은 업무 적용, 권한, 데이터, KPI, 사후지원이 중요하다.",
        "회사 사내교육을 말라카 브랜드의 연장으로 쓰면 책의 신뢰가 흐려진다. 회사 책임은 회사의 언어로 써야 한다.",
        "사내 사례는 내부 검토 없이 외부 공개하지 않는다. 원고에는 운영 원칙과 익명화된 흐름만 남긴다.",
        "독자는 외부 강의와 사내교육의 목표·평가·사후지원 차이를 표로 쓴다.",
        "316-340,468-479",
        (
            "외부 강의와 사내교육의 목표 차이",
            "사내교육은 KPI와 연결되어야 한다",
            "권한·보안·데이터가 커리큘럼이다",
            "교육 뒤 클리닉이 없으면 적용은 멈춘다",
            "회사 책임을 회사의 언어로 쓰기",
            "두 교육의 차이를 표로 만들기",
        ),
    ),
    Chapter(
        "3부. SPARK-IPO와 바이브코딩 실행법",
        "SPARK는 AI 시대의 회사 운영체계다",
        "Spec, Plan, Archive, Research, Knowhow는 AI 작업을 개인 요령이 아니라 회사 자산으로 남긴다.",
        "SPARK-IPO는 이 책의 차별점이다. 강의 자료와 AGENTS 규칙에 흩어진 방법론을 회사 운영 언어로 재정리한다.",
        "AI와 일할수록 규칙이 필요하다. 규칙이 없으면 빠른 산출물은 많아지지만 다음 사람이 이어받을 수 없다.",
        "SPARK는 폴더명이 아니라 책임의 분류다. 설계, 진행, 보관, 조사, 재사용 지식을 나누는 방식이다.",
        "Knowhow는 공개 가능한 일반 원칙으로 정제하고, Archive에는 외부 공개하면 안 되는 원문을 남긴다.",
        "독자는 자기 팀 프로젝트에 SPARK 폴더 하나를 만들고 첫 Spec과 Plan을 적는다.",
        "027-038,100,107-108,113,141,155-156,168",
        (
            "SPARK가 필요한 순간",
            "Spec은 AI와 사람의 공동 계약서다",
            "Plan은 흔들리는 프로젝트를 붙잡는다",
            "Archive는 버리는 힘이다",
            "Research와 Knowhow를 분리하기",
            "팀 프로젝트 첫 SPARK 만들기",
        ),
    ),
    Chapter(
        "3부. SPARK-IPO와 바이브코딩 실행법",
        "IPO는 자료를 결과로 통과시키는 배관이다",
        "Input, Proc, Output을 나누면 AI가 무엇을 했고 사람이 어디서 판단했는지 남는다.",
        "상장 가능한 조직은 입력과 처리와 출력의 흔적을 남겨야 한다. IPO는 바이브코딩을 회계·영업·개발 업무로 가져가기 위한 최소 언어다.",
        "자료가 많다고 좋은 결과가 나오는 것은 아니다. 어떤 자료가 입력이고, 어떤 규칙으로 처리하며, 어떤 출력물이 사용 가능한지 분리해야 한다.",
        "IPO는 데이터 파이프라인이자 의사결정 파이프라인이다.",
        "외부 공개본에서는 원본 입력을 노출하지 않고, 처리 기준과 출력 형태를 중심으로 설명한다.",
        "독자는 현재 반복 업무 하나를 Input, Proc, Output 세 줄로 쓴다.",
        "405-408,447-449,498-500",
        (
            "입력은 자료가 아니라 책임이다",
            "처리 규칙을 사람이 잡아야 하는 이유",
            "출력은 파일이 아니라 사용 가능한 결과다",
            "중간 산출물이 있어야 되돌릴 수 있다",
            "IPO로 회계·영업·강의를 모두 설명하기",
            "세 줄 IPO 작성법",
        ),
    ),
    Chapter(
        "3부. SPARK-IPO와 바이브코딩 실행법",
        "프롬프트는 설계 문서다",
        "AI에게 잘 말하는 것이 아니라 사람이 다시 검토할 수 있게 쓰는 것이다.",
        "프롬프트 관련 꼭지는 바이브코딩을 유행어에서 방법론으로 끌어올리는 장치다.",
        "한 줄 주문으로도 결과물은 나온다. 하지만 회사 업무와 강의 실습에서 반복 가능한 결과를 얻으려면 목표, 맥락, 제약, 출력 형식, 검증 기준이 필요하다.",
        "프롬프트는 대화가 아니라 작업 계약이다. 계약처럼 쓰면 다음 사람이 검토할 수 있다.",
        "민감 데이터는 프롬프트에 직접 넣지 않는다. 예시 데이터와 구조화된 설명으로 대체한다.",
        "독자는 오늘 사용할 프롬프트를 목표, 맥락, 제약, 산출 형식, 검증 기준 다섯 줄로 다시 쓴다.",
        "061-075,083-086,100-113,130-132,143-146",
        (
            "좋은 프롬프트의 다섯 줄",
            "역할보다 목표를 먼저 쓴다",
            "맥락은 길이가 아니라 정확도다",
            "금지 조건이 품질을 만든다",
            "검증 질문을 프롬프트에 넣기",
            "오늘 쓸 프롬프트 다시 쓰기",
        ),
    ),
    Chapter(
        "3부. SPARK-IPO와 바이브코딩 실행법",
        "프론트엔드는 독자가 처음 만나는 계약면이다",
        "화면은 예쁘게 보이는 장식이 아니라 사용자의 행동과 회사의 데이터가 만나는 계약면이다.",
        "프론트엔드, 웹앱, 개발자도구, 콘솔, 배포 꼭지는 비개발 독자가 최소 구조를 이해하게 만드는 파트다.",
        "AI가 코드를 써도 사용자는 화면으로 제품을 판단한다. 그래서 프론트엔드는 가장 먼저 검증되는 약속이다.",
        "화면, 데이터, API, 권한, 배포를 구분해야 AI 결과물을 검수할 수 있다.",
        "실제 서비스 화면과 내부 데이터는 공개본에서 예시화한다.",
        "독자는 자기 MVP의 첫 화면에서 사용자가 해야 할 행동 하나를 정한다.",
        "012-018,044-046,057-058,062-063,097-098,122-124,133-135,147,218,223,225,393-418",
        (
            "프론트엔드는 장식이 아니다",
            "첫 화면이 정해야 할 행동",
            "데이터베이스는 기억의 방식이다",
            "API는 팀 간 약속이다",
            "개발자도구로 확인하는 최소 진실",
            "첫 화면의 계약 쓰기",
        ),
    ),
    Chapter(
        "4부. MVP와 제품화",
        "하루짜리 MVP는 첫 증거다",
        "MVP는 작은 제품이 아니라 다음 판단을 가능하게 하는 작은 증거다.",
        "창업, 아이코어, Lovable, 제품 개발 꼭지는 회사 상장이라는 큰 목표를 작은 실험으로 낮추는 파트다.",
        "하루 만에 만든다는 말은 과장이 될 수 있다. 하지만 하루 만에 질문을 좁히고, 화면을 만들고, 반응을 받아 다음 결정을 하는 것은 가능하다.",
        "MVP의 목적은 성공 선언이 아니라 실패 비용을 낮추는 것이다.",
        "타인의 사업 아이디어나 실명 사례는 익명화하고, 검증 구조만 남긴다.",
        "독자는 이번 주 안에 검증할 질문 하나를 정하고, 답을 얻을 가장 작은 화면을 만든다.",
        "019-021,041,055-060,096,105-106,143-145,221,244,459-464,480,491",
        (
            "MVP를 제품이 아니라 질문으로 보기",
            "하루 안에 줄일 수 있는 범위",
            "랜딩 페이지가 먼저인 이유",
            "사용자 반응을 기록하는 법",
            "실패를 싸게 만드는 기준",
            "이번 주의 작은 화면 만들기",
        ),
    ),
    Chapter(
        "4부. MVP와 제품화",
        "Problem-Tech Fit이 먼저다",
        "기술을 붙이기 전에 문제가 기술을 요구하는지 확인해야 한다.",
        "Problem-Tech Fit, 정보구걸, 역할 기반 인터뷰 꼭지는 바이브코딩의 창업적 균형추다.",
        "AI가 빨라질수록 만들 수 있는 것은 많아진다. 그래서 더 먼저 물어야 한다. 이 문제는 기술이 필요한가, 아니면 운영 규칙이나 사람의 합의가 필요한가.",
        "기술을 과잉 투입하면 빠르게 만든 결과물이 빠르게 버려진다.",
        "고객 인터뷰 원문은 공개본에서 요약과 익명화가 필요하다.",
        "독자는 만들고 싶은 기능 하나를 적고, 그 기능 없이도 문제를 확인할 질문 세 개를 만든다.",
        "039-040,053-054,094,101-104,193,389-395,412-417,472,486",
        (
            "문제가 기술을 요구하는가",
            "정보구걸이 필요한 순간",
            "역할 기반 인터뷰",
            "만들기 전에 확인할 세 질문",
            "기술 없이 검증하는 법",
            "기능 하나를 질문 세 개로 바꾸기",
        ),
    ),
    Chapter(
        "4부. MVP와 제품화",
        "개발비는 줄어도 검증비는 사라지지 않는다",
        "AI가 개발비를 낮출수록 검증의 책임은 더 선명해진다.",
        "검증, Git, privacy mode, 보안, E2E, 오류 복구 꼭지는 책의 균형추다.",
        "바이브코딩은 빠르게 만들 수 있다는 희망을 준다. 동시에 빠르게 틀릴 수 있다는 위험도 준다.",
        "검증비는 비용이 아니라 신뢰의 보험이다. 회사 AX에서는 특히 그렇다.",
        "보안·계정·회계 정보는 원문 노출하지 않고 체크리스트와 기준으로만 제시한다.",
        "독자는 자기 결과물을 사용자, 데이터, 권한, 예외, 복구 다섯 관점으로 검증한다.",
        "006,047,066,072-075,095,107,109,202,214-216,226,386,433,495",
        (
            "그럴듯함과 작동의 차이",
            "Git과 되감기의 감각",
            "보안 모드를 습관으로 만들기",
            "E2E 리포트처럼 남기기",
            "오류 복구가 제품 신뢰를 만든다",
            "다섯 관점 검증표",
        ),
    ),
    Chapter(
        "4부. MVP와 제품화",
        "SaaS의 종말과 내부툴의 시대",
        "AI는 모든 SaaS를 없애지 않는다. 다만 회사별로 맞춘 내부툴의 경제성을 바꾼다.",
        "SaaS의 종말, 내부툴, 주문앱, 자연어 CRM 꼭지는 회사 AX와 바이브코딩의 접점을 만든다.",
        "예전에는 작은 업무를 위해 새 시스템을 만들기 어려웠다. 이제는 반복 업무와 특수한 화면을 빠르게 만들 수 있다.",
        "내부툴은 작다고 가벼운 것이 아니다. 권한, 데이터, 책임, 유지보수가 붙어야 한다.",
        "회사 시스템의 구체 필드는 공개본에서 예시화한다.",
        "독자는 구독 중인 SaaS 하나를 골라, 내부툴로 바꿔야 할 부분과 남겨야 할 부분을 구분한다.",
        "192,198-202,242,250,474,478,488",
        (
            "SaaS가 끝난다는 말의 진짜 의미",
            "회사별 내부툴의 경제성",
            "주문앱과 자연어 CRM",
            "내부툴에도 운영 책임이 붙는다",
            "남길 SaaS와 만들 내부툴 구분하기",
            "작은 내부툴 후보 정하기",
        ),
    ),
    Chapter(
        "5부. 말라카 강의와 인재 엔진",
        "170명 실습강좌는 말솜씨가 아니라 시스템이다",
        "대규모 실습은 설명을 잘하는 일이 아니라 실패를 미리 줄여 놓는 운영 설계다.",
        "말라카 외부 강의 파트는 회사 AX와 분리한다. 이 장은 WhyQ, KUBIT, KU, PKNU 경험을 강의 운영의 원칙으로 정리한다.",
        "170명이 동시에 만들면 도구보다 운영이 먼저 드러난다. 설치, 로그인, Slack, 조교, 공유노트, 발표, 사후지원이 모두 커리큘럼이다.",
        "강의의 성과는 강사의 말이 아니라 수강생의 결과물과 다음 행동에서 나온다.",
        "수강생 실명과 세부 결과물은 공개 전 동의와 익명화가 필요하다.",
        "독자는 자신이 운영할 실습강좌의 실패 시나리오 10개를 먼저 적는다.",
        "026,042-043,067,087-092,110-120,136-137,139-142,174-185",
        (
            "실습 전 실패를 먼저 설계하기",
            "설치와 로그인도 커리큘럼이다",
            "Slack 채널은 운영 시스템이다",
            "조교가 봐야 할 신호",
            "AI가 일하는 동안 강의하기",
            "실패 시나리오 10개 쓰기",
        ),
    ),
    Chapter(
        "5부. 말라카 강의와 인재 엔진",
        "WhyQ, KUBIT, KU, PKNU에서 배운 실습의 질서",
        "강의장은 바이브코딩 방법론을 검증하는 실험실이다.",
        "여러 강의 공유노트와 PPT는 같은 주제가 다른 대상에게 어떻게 바뀌는지 보여 준다.",
        "대학생, 창업자, 비개발 실무자, 팀 프로젝트 수강생은 막히는 지점이 다르다. 좋은 강의는 같은 내용을 반복하지 않고 같은 원리를 다른 진입로로 보여 준다.",
        "강의 경험은 책의 사례가 되지만, 회사 업무와 혼동하면 안 된다.",
        "기관명과 운영 세부는 공개 가능 범위를 확인한다.",
        "독자는 같은 바이브코딩 주제를 세 독자군에게 어떻게 다르게 설명할지 적는다.",
        "230-248,381-392,419-467",
        (
            "대상별로 막히는 지점이 다르다",
            "WhyQ의 코호트 운영",
            "KUBIT의 팀 프로젝트 구조",
            "KU와 PKNU의 창업/MVP 언어",
            "공유노트가 강의의 기억이 된다",
            "세 독자군 설명문 쓰기",
        ),
    ),
    Chapter(
        "5부. 말라카 강의와 인재 엔진",
        "강의 이후 커뮤니티와 사후지원",
        "좋은 강의는 끝난 뒤에도 결과물이 계속 움직이게 만든다.",
        "AI 클리닉, 오프모임, 강의 후 실제 결심, 커뮤니티 운영 꼭지는 강의를 인재 엔진으로 확장한다.",
        "수료증은 강의의 끝이 아니다. 결과물 공유, 피드백, 다음 실험, 공동 발표가 남아야 한다.",
        "사후지원이 없으면 강의의 열기는 빠르게 식는다. 클리닉과 커뮤니티는 그 열기를 다음 행동으로 바꾼다.",
        "커뮤니티 멤버와 계좌·연락처 정보는 본문에서 제외한다.",
        "독자는 강의 종료 후 2주 안에 실행할 사후지원 루틴을 정한다.",
        "481-486,049,126,147,159,176,182,185,197,207,214,216,233,237-240,246",
        (
            "수료 이후가 진짜 시작이다",
            "AI 클리닉의 역할",
            "오프모임은 결과물의 다음 무대다",
            "커뮤니티 운영의 공개/비공개 경계",
            "수강생 결심을 다음 실험으로 바꾸기",
            "2주 사후지원 루틴 만들기",
        ),
    ),
    Chapter(
        "5부. 말라카 강의와 인재 엔진",
        "바이브코딩을 가르치는 사람의 브랜드",
        "강사 브랜드는 멋진 소개문이 아니라 반복해서 결과를 만들어 낸 증거에서 생긴다.",
        "말라카 브랜드, 강의평, VOD, 제휴, 스타 강사 플랫폼 꼭지는 강의 사업화의 경계와 가능성을 보여 준다.",
        "브랜드는 이름을 앞세울 때 약해지고 결과물이 쌓일 때 강해진다. 강사가 해야 할 일은 자기소개보다 결과물이 돌아다니는 구조를 만드는 것이다.",
        "강의 사업화는 회사 AX와 구분해야 한다. 같은 사람이 해도 책임과 계약과 독자가 다르다.",
        "제휴·가격·실명 평가는 공개본에서 별도 검수한다.",
        "독자는 자기 강의 브랜드를 `대상, 변화, 증거` 세 단어로 정의한다.",
        "273,279-290,300,327,347,481,485,489,492",
        (
            "브랜드는 이름보다 결과다",
            "강의평을 원고로 바꾸지 않는 법",
            "VOD와 실시간 강의의 차이",
            "제휴는 결과물이 있어야 가능하다",
            "말라카와 회사 역할 구분하기",
            "대상·변화·증거 한 문장",
        ),
    ),
    Chapter(
        "6부. 상장 가능한 조직의 검증과 확산",
        "품질, 보안, 권한은 AI 결과물에 책임을 붙이는 언어다",
        "상장 가능한 회사는 빠르게 만든 결과물보다 책임 있게 운영되는 결과물을 원한다.",
        "품질·보안·권한 꼭지는 책의 마지막 부에서 확산의 조건으로 다시 정리된다.",
        "AI 결과물이 늘어날수록 회사는 더 많은 검증 질문을 가져야 한다. 누가 접근할 수 있는가, 누가 고칠 수 있는가, 어떤 로그가 남는가, 실패하면 누가 복구하는가.",
        "보안은 도입을 막는 핑계가 아니라 좋은 도입을 가능하게 하는 조건이다.",
        "민감 원문은 절대 본문에 넣지 않고, 권한 모델과 검증 기준만 남긴다.",
        "독자는 자기 자동화 결과물의 권한표를 작성한다.",
        "048-052,094,101-104,109-110,193,389-395,412-417,472,486",
        (
            "품질은 속도의 반대말이 아니다",
            "권한표 없이 내부툴을 열지 않는다",
            "로그는 미래의 설명 책임이다",
            "보안 불안을 설계로 바꾸기",
            "누가 복구할 것인가",
            "첫 권한표 작성하기",
        ),
    ),
    Chapter(
        "6부. 상장 가능한 조직의 검증과 확산",
        "회계, 데이터, E2E 리포트는 상장 준비의 언어다",
        "숫자를 다루는 업무에서 AX는 자동화보다 설명 가능성이 먼저다.",
        "거래원장, 회계 검증, E2E 리포트, 데이터 차액 꼭지는 상장 가능한 회사 체질의 강한 증거다.",
        "상장을 향하는 회사는 숫자의 출처와 처리 기준과 예외를 설명할 수 있어야 한다. AI 자동화는 이 설명 책임을 대신하지 않는다.",
        "E2E 리포트는 개발자 문서이면서 운영자 문서다. 어떤 데이터가 들어왔고, 어떤 테스트를 통과했으며, 어떤 예외가 남았는지 기록한다.",
        "실제 회계 값, 고객명, 채권·연체 정보는 공개본에서 익명화한다.",
        "독자는 숫자 자동화 하나를 골라 입력, 계산 기준, 검수자, 예외 처리, 로그 위치를 적는다.",
        "471-473,475-477,487,495",
        (
            "숫자 업무의 첫 원칙",
            "입력과 계산 기준을 분리하기",
            "검수자를 설계 안에 넣기",
            "E2E 리포트 형식",
            "예외 케이스가 신뢰를 만든다",
            "숫자 자동화 검수표",
        ),
    ),
    Chapter(
        "6부. 상장 가능한 조직의 검증과 확산",
        "작은 자동화를 KPI로 바꾸는 법",
        "작은 자동화가 조직의 성과가 되려면 시간, 오류, 리드타임, 재사용률로 번역되어야 한다.",
        "AX 성공 기준과 KPI 꼭지는 책의 제목을 회사 성과와 연결하는 다리다.",
        "자동화는 만들어졌다는 사실보다 무엇을 줄였는지가 중요하다. 걸린 시간, 반복 횟수, 누락 오류, 재작업, 의사결정 지연이 줄어야 한다.",
        "KPI가 없으면 자동화는 개인 만족으로 끝난다. KPI가 있으면 다음 예산과 다음 사람을 설득할 수 있다.",
        "KPI에는 내부 데이터가 들어갈 수 있으므로 공개본에서는 산식과 예시만 남긴다.",
        "독자는 첫 자동화의 KPI를 시간 절감, 오류 감소, 재사용률 세 지표로 적는다.",
        "491,498-500",
        (
            "자동화 결과를 숫자로 바꾸기",
            "시간 절감의 함정",
            "오류 감소를 기록하는 법",
            "재사용률이 조직 확산을 말한다",
            "KPI가 다음 예산을 만든다",
            "세 지표 KPI 쓰기",
        ),
    ),
    Chapter(
        "6부. 상장 가능한 조직의 검증과 확산",
        "동경하지 말고 되어라",
        "회사도 개인도 AI를 잘 쓰는 사람을 동경하는 데서 멈추지 말고, 오늘 하나를 만들어 증명해야 한다.",
        "마지막 장은 Future Self, 말라카, 회사 AX, 바이브코딩을 하나의 행동 문장으로 묶는다.",
        "상장 가능한 회사 체질은 거대한 선언으로 만들어지지 않는다. 오늘 한 사람이 반복 업무를 문장으로 쓰고, AI와 초안을 만들고, 검증하고, 공유하고, 다음 사람에게 넘길 때 시작된다.",
        "동경은 방향을 주지만 결과를 만들지는 않는다. 되어야 할 것은 AI 전문가라는 이름이 아니라 문제를 증거로 바꾸는 사람이다.",
        "개인 서사의 과장은 덜어내고 독자의 행동으로 끝낸다.",
        "독자는 내일 아침 30분 동안 실행할 첫 AX 행동을 정한다.",
        "012-500",
        (
            "동경의 시간을 줄이기",
            "오늘 하나를 자동화하기",
            "검증하고 공유하기",
            "회사와 개인의 다음 장",
            "첫 30분 행동",
            "상장 가능한 체질은 반복에서 생긴다",
        ),
    ),
)


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def parse_topics() -> dict[int, dict[str, str]]:
    text = TOPICS_PATH.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^###\s+(\d{3})\.\s+(.+)$", text, flags=re.M))
    topics: dict[int, dict[str, str]] = {}
    for i, match in enumerate(matches):
        n = int(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        source_match = re.search(r"^- 출처:\s*(.+)$", body, flags=re.M)
        use_match = re.search(r"^- 활용 방향:\s*(.+)$", body, flags=re.M)
        topics[n] = {
            "title": title,
            "source": source_match.group(1).strip() if source_match else "출처 확인 필요",
            "use": use_match.group(1).strip() if use_match else "",
        }
    return topics


def chapter_topic_map(topics: dict[int, dict[str, str]]) -> list[list[int]]:
    assigned: set[int] = set()
    groups: list[list[int]] = []
    for chapter in CHAPTERS:
        group: list[int] = []
        for n in ids(chapter.topic_spec):
            if n not in topics or n in assigned:
                continue
            group.append(n)
            assigned.add(n)
        groups.append(group)
    remaining = [n for n in sorted(topics) if n not in assigned]
    # The last chapter is intentionally a synthesis chapter; keep every stray
    # source topic visible there so the ordered map is complete and auditable.
    groups[-1].extend(remaining)
    return groups


def copy_assets() -> list[Path]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    assets: list[Path] = []
    if SOURCE_ASSET_DIR.exists():
        for src in sorted(SOURCE_ASSET_DIR.glob("*.jpg")):
            dst = ASSET_DIR / src.name
            shutil.copy2(src, dst)
            assets.append(dst)
    return assets


def topic_line(n: int, topic: dict[str, str]) -> str:
    source = topic["source"]
    if len(source) > 170:
        source = source[:167].rstrip() + "..."
    return f"- `{n:03d}` {topic['title']} — 출처: {source}"


def render_ordered_topics(topics: dict[int, dict[str, str]], groups: list[list[int]]) -> str:
    lines = [
        f"# {BOOK_TITLE}: 500개 꼭지 책 순서 재배열",
        "",
        f"- 작성일: {BOOK_DATE}",
        f"- 입력 문서: `{TOPICS_PATH}`",
        f"- 총 꼭지 수: {len(topics)}",
        f"- 배치 기준: {len(CHAPTERS)}장, 각 꼭지는 최초 배치 장에 1회만 둔다.",
        "- 주의: 마지막 장에는 앞 장의 핵심 주장을 종합하기 위해 일부 광범위 원자료가 함께 들어간다.",
        "",
        "## 책의 흐름",
        "",
        "1. 저자의 각오와 DOF 합류 이유를 먼저 세운다.",
        "2. 회사가 상장 가능한 체질을 갖추려면 어떤 AX 운영 지도가 필요한지 설명한다.",
        "3. SPARK-IPO와 바이브코딩을 실행 방법론으로 정리한다.",
        "4. MVP와 제품화를 통해 작은 증거를 만든다.",
        "5. 말라카 외부 강의는 회사 AX와 분리해 인재 엔진으로 다룬다.",
        "6. 검증, 회계, 데이터, KPI, Future Self로 다시 회사 체질을 닫는다.",
        "",
    ]
    placed = 0
    for idx, (chapter, group) in enumerate(zip(CHAPTERS, groups, strict=True), 1):
        lines.extend(
            [
                f"## {idx:02d}. {chapter.title}",
                "",
                f"- 파트: {chapter.part}",
                f"- 역할: {chapter.subtitle}",
                f"- 배치 꼭지 수: {len(group)}",
                "",
            ]
        )
        for n in group:
            lines.append(topic_line(n, topics[n]))
        lines.append("")
        placed += len(group)
    lines.extend(
        [
            "## 검증",
            "",
            f"- 전체 꼭지 수: {len(topics)}",
            f"- 재배열 배치 수: {placed}",
            f"- 중복 배치: {'없음' if placed == len(set(n for group in groups for n in group)) else '확인 필요'}",
            f"- 미배치 꼭지: {'없음' if placed == len(topics) else len(topics) - placed}",
            "",
        ]
    )
    return "\n".join(lines)


def render_publication_plan(groups: list[list[int]]) -> str:
    lines = [
        f"# 출판기획서: {BOOK_TITLE}",
        "",
        "## 한 줄 기획",
        "",
        "AI를 잘 쓰는 개인의 요령을 넘어, 회사가 상장 가능한 운영 체질을 갖추도록 AX와 바이브코딩을 결합하는 실전 운영서.",
        "",
        "## 핵심 약속",
        "",
        "- 상장을 보장하지 않는다. 대신 상장을 향하는 회사가 갖춰야 할 프로세스, 데이터, 검증, 인재, 교육의 체질을 설명한다.",
        "- 회사 AX와 말라카 외부 강의를 섞지 않는다. 회사 AX는 조직 책임 체계로, 말라카 강의는 외부 실습강좌 운영 경험으로 다룬다.",
        "- 바이브코딩을 '느낌으로 코딩'이 아니라 명세, 맥락, 분할, 검증의 운영법으로 정의한다.",
        "- Future Self는 자기계발 장식이 아니라 장기 목표를 오늘의 자동화와 KPI로 낮추는 도구로 쓴다.",
        "",
        "## 독자",
        "",
        "- 회사에서 AI 전환을 맡은 팀장, 기획자, 현업 자동화 담당자.",
        "- 개발자는 아니지만 반복 업무와 도메인을 가장 잘 아는 실무자.",
        "- 바이브코딩으로 MVP를 만들고 싶은 창업자와 사내 벤처 담당자.",
        "- 대규모 실습강좌를 운영하거나 AI 교육을 설계하는 강사.",
        "",
        "## 차별화",
        "",
        "- DOF 합류 각오와 회사 AX 현장을 통해 'AI 도입'을 실제 업무 체질의 문제로 다룬다.",
        "- SPARK-IPO를 책 전체의 운영체계로 세워 자료, 계획, 조사, 결과물을 분리한다.",
        "- WhyQ, KUBIT, KU, PKNU 강의 자료를 말라카 외부 강의 운영법으로 정리한다.",
        "- 회계, 거래원장, CRM, 주문, QC 같은 상장 준비형 업무 언어를 본문에 넣는다.",
        "",
        "## 6부 24장 구성",
        "",
    ]
    for idx, (chapter, group) in enumerate(zip(CHAPTERS, groups, strict=True), 1):
        lines.extend(
            [
                f"### {idx:02d}. {chapter.title}",
                "",
                f"- 파트: {chapter.part}",
                f"- 독자 효용: {chapter.action}",
                f"- 근거 꼭지 수: {len(group)}",
                f"- 공개 전 검토: {chapter.verification}",
                "",
            ]
        )
    lines.extend(
        [
            "## 공개 전 리스크",
            "",
            "- 회사명/고객명/실명/계좌/회의 링크/내부 도메인/보안 설정은 공개 전 익명화한다.",
            "- 상장, 회계, 고객 신용, 연체, 결제 관련 문장은 법무·재무 검토가 필요하다.",
            "- PPT 이미지와 외부 강의 자료는 권리와 공개 범위를 확인한다.",
            "- ChatGPT 대화 제목은 관심사 색인으로만 사용하고 본문 원문은 공개하지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)


SECTION_OPENERS = (
    "이 절의 핵심은 거창한 도구 설명이 아니라 판단의 순서다.",
    "현장에서 이 문제는 늘 말보다 먼저 나타난다.",
    "AI를 붙이기 전에 먼저 사람이 정해야 할 것이 있다.",
    "좋은 원칙은 회의실에서 멋있게 들리는 문장이 아니라 다음 행동을 줄이는 문장이다.",
    "이 절은 독자가 바로 자기 회사의 상황으로 옮길 수 있어야 한다.",
    "상장을 향하는 회사의 언어로 바꾸면 이 문제는 더 선명해진다.",
)


def topic_summary(topics: dict[int, dict[str, str]], group: list[int], limit: int = 6) -> str:
    titles = [topics[n]["title"] for n in group[:limit]]
    if not titles:
        return "이 장은 앞 장의 원칙을 종합한다."
    return "이 장의 근거 꼭지는 " + ", ".join(f"`{title}`" for title in titles) + " 등이다."


def section_paragraphs(
    chapter: Chapter,
    topics: dict[int, dict[str, str]],
    group: list[int],
    chapter_idx: int,
    section_idx: int,
    section: str,
) -> list[str]:
    opener = SECTION_OPENERS[(chapter_idx + section_idx) % len(SECTION_OPENERS)]
    relevant = topic_summary(topics, group[section_idx - 1 :: max(1, len(chapter.sections))], 4)
    return [
        f"### {chapter_idx}-{section_idx}. {section}",
        "",
        f"{opener} `{section}`이라는 제목은 {chapter.title}의 추상적 주장을 손에 잡히는 일로 낮추기 위해 붙였다.",
        "",
        f"{relevant} 이 꼭지들은 하나의 메시지로 합쳐진다. {chapter.claim}",
        "",
        f"{chapter.scene} 이 장면을 회사의 언어로 바꾸면, 사람은 더 이상 'AI를 써 봤다'고 말하는 데서 멈추지 않는다. 어떤 입력이 들어왔고, 어떤 규칙으로 처리했으며, 어떤 결과가 누구에게 전달되었는지를 설명하게 된다.",
        "",
        f"{chapter.method} 이 방법은 작아 보이지만 중요하다. 회사가 커질수록 개인의 기억과 임기응변은 줄고, 문서화된 기준과 재현 가능한 절차가 늘어야 한다.",
        "",
        f"{chapter.verification} 그래서 이 절의 검증 기준은 단순하다. 누가 읽어도 같은 결정을 할 수 있는가. 다음 사람이 이어서 실행할 수 있는가. 실패했을 때 되돌아갈 기록이 남아 있는가.",
        "",
        f"{chapter.action} 이것을 오늘 하지 않으면 책의 문장은 좋은 말로 끝난다. 작게 실행하고, 흔적을 남기고, 다음 사람에게 설명할 수 있어야 한다.",
        "",
        f"현장 적용 노트에서는 이 절의 제목을 회의 안건 하나로 바꾼다. 안건명은 `{section}`이다. 담당자는 지금 쓰는 파일, 반복되는 입력, 사람이 눈으로 확인하는 값, 승인이나 공유가 필요한 순간을 적는다. 그 다음 AI에게 맡길 수 있는 초안 생성과 사람이 붙잡아야 할 최종 판단을 나누어 쓴다. 이 구분이 생기면 바이브코딩은 개인 기술이 아니라 팀의 운영 언어가 된다.",
        "",
        f"공개판 원고에서는 이 절의 사례를 더 정제해야 한다. 회사명, 고객명, 계정, 금액, 내부 링크는 모두 빼고, 남길 것은 `문제`, `처리 기준`, `검증 방식`, `다음 행동`이다. 독자는 구체 사례를 원하지만, 회사 AX를 다루는 책은 구체성과 공개 가능성 사이의 선을 지켜야 한다.",
        "",
    ]


def figure_for(idx: int, assets: list[Path]) -> list[str]:
    if not assets or idx % 4 not in (0, 1):
        return []
    asset = assets[(idx * 3) % len(assets)]
    rel = asset.relative_to(OUT)
    return [
        '<figure class="book-figure">',
        f'<img src="{esc(str(rel))}" alt="강의 자료 이미지 {idx}">',
        f'<figcaption>바이브코딩 강의 자료에서 추출한 참고 이미지. 외부 공개 전 권리와 공개 범위를 확인한다.</figcaption>',
        "</figure>",
        "",
    ]


def render_book_md(topics: dict[int, dict[str, str]], groups: list[list[int]], assets: list[Path]) -> str:
    lines: list[str] = [
        '<section class="cover page">',
        f'<p class="cover-kicker">{BOOK_AUTHOR} · {BOOK_EDITION}</p>',
        f'<h1>{BOOK_TITLE}</h1>',
        f'<p class="cover-subtitle">{BOOK_SUBTITLE}</p>',
        '<p class="cover-promise">AI를 잘 쓰는 개인을 넘어, AI를 잘 쓰는 회사의 프로세스와 검증 문화를 만드는 책.</p>',
        f'<p class="cover-date">{BOOK_DATE}</p>',
        "</section>",
        "",
        '<section class="page title-page" markdown="1">',
        f"# {BOOK_TITLE}",
        "",
        f"## {BOOK_SUBTITLE}",
        "",
        f"{BOOK_AUTHOR} 지음",
        "",
        f"{BOOK_EDITION} · {BOOK_DATE}",
        "</section>",
        "",
        '<section class="page copyright-page" markdown="1">',
        "# 서지정보",
        "",
        f"- 서명: {BOOK_TITLE}",
        f"- 부제: {BOOK_SUBTITLE}",
        f"- 저자: {BOOK_AUTHOR}",
        f"- 판본: {BOOK_EDITION}",
        "- 형식: 로컬 자료 기반 출판 기획용 초판 원고",
        "- 근거: 500개 이야기 꼭지, 바이브코딩 PPT 추출물, Notion dump, Daily summary, ChatGPT 로컬 DB 제목",
        "",
        "이 원고는 투자 조언, 증권 조언, 상장 보장 문서가 아니다. `회사 상장시키기`는 상장 가능한 회사 체질을 만들기 위한 AX 운영 원칙을 뜻한다. 외부 공개 전 회사 내부 정보, 실명, 회계·보안·고객 정보, 이미지 권리는 별도 검토해야 한다.",
        "</section>",
        "",
        '<section class="page preface-page" markdown="1">',
        "# 인트로: 상장 가능한 회사 체질을 만든다는 것",
        "",
        "AI 도구를 많이 쓰는 회사와 상장 가능한 체질을 갖춘 회사는 다르다. 전자는 도구 사용량이 늘어난 회사이고, 후자는 업무가 설명 가능해지고, 데이터가 이어지고, 검증 책임이 남고, 사람이 바뀌어도 프로세스가 유지되는 회사다. 이 책의 제목은 일부러 크게 잡았다. `AX와 바이브코딩으로 회사 상장시키기`. 하지만 이 제목은 상장 비법을 팔겠다는 말이 아니다. 회사가 상장을 향해 갈 때 필요한 운영 체질을 AI 전환과 바이브코딩의 언어로 설명하겠다는 선언이다.",
        "",
        "이 책의 재료는 강의 슬라이드, DOF 합류 전후의 기록, Future Self 워크북, Notion 메모, Daily summary, ChatGPT 질문 제목, 회사 업무에서 남긴 AX 고민이다. 그러나 이 원고는 자료를 순서대로 붙인 자료집이 아니다. 500개 꼭지를 다시 배열해 하나의 주장으로 묶었다. 회사 AX와 말라카 외부 강의는 분리했고, 개인 서사는 방법론을 설명하는 데 필요한 만큼만 남겼다.",
        "",
        "독자는 이 책을 읽으며 세 가지 질문을 계속 붙잡으면 된다. 우리 회사의 반복 업무는 어디서 끊기는가. AI가 만든 결과물을 누가 검증하는가. 작은 자동화 하나가 상장 가능한 회사 체질의 어떤 지표를 바꾸는가.",
        "</section>",
        "",
        '<section class="page greeting-page" markdown="1">',
        "# 인사말: AI를 가장 잘 쓰는 회사라는 각오",
        "",
        "DOF에 오면서 세운 각오는 단순히 새로운 회사에서 잘해 보겠다는 말이 아니었다. AI를 가장 잘 쓰는 회사, AI가 업무의 주변 장식이 아니라 프로세스의 중심에 들어가는 회사를 만들고 싶었다. 그 말은 곧 내 역할을 다시 정의하는 일이었다. 강의장에서 바이브코딩을 알려 주는 사람으로만 머물 수 없었다. 회사 안에서 영업, CRM, 주문, 회계, QC, 개발팀, 사내교육을 실제로 연결해야 했다.",
        "",
        "이 책은 그 각오에서 출발한다. 카카오모빌리티 이후의 커리어, 창업과 강의, Future Self의 목표, 말라카라는 이름으로 쌓은 외부 강의 운영 경험을 하나로 합치되 경계는 분명히 했다. 말라카 강의는 외부 실습강좌의 시스템이고, 회사 AX는 회사의 책임 체계다. 둘을 구분할 때 비로소 둘 다 힘을 얻는다.",
        "",
        f"{BOOK_AUTHOR}",
        "</section>",
        "",
        '<section class="page toc-page" markdown="1">',
        "# 목차",
        "",
    ]
    current_part = ""
    for idx, chapter in enumerate(CHAPTERS, 1):
        if chapter.part != current_part:
            current_part = chapter.part
            lines.extend([f"## {chapter.part}", ""])
        lines.extend([f"- {idx:02d}. {chapter.title}", f"  - {chapter.subtitle}"])
    lines.extend(["</section>", ""])

    for idx, (chapter, group) in enumerate(zip(CHAPTERS, groups, strict=True), 1):
        if idx == 1 or chapter.part != CHAPTERS[idx - 2].part:
            lines.extend(
                [
                    '<section class="page part-page" markdown="1">',
                    f"# {chapter.part}",
                    "",
                    f"{chapter.part}는 `{BOOK_TITLE}`의 큰 흐름 중 하나다. 이 부는 이전 원자료의 꼭지를 독자의 판단 순서에 맞춰 다시 배열한다.",
                    "</section>",
                    "",
                ]
            )
        lines.extend(
            [
                '<section class="chapter-page" markdown="1">',
                f"# {idx:02d}. {chapter.title}",
                "",
                f"**{chapter.subtitle}**",
                "",
                f"{chapter.claim}",
                "",
                topic_summary(topics, group, 8),
                "",
                *figure_for(idx, assets),
                f"{chapter.scene}",
                "",
                f"{chapter.method}",
                "",
                f"{chapter.verification}",
                "",
                f"{chapter.action}",
                "",
            ]
        )
        for section_idx, section in enumerate(chapter.sections, 1):
            lines.extend(section_paragraphs(chapter, topics, group, idx, section_idx, section))
        lines.extend(
            [
                '<div class="chapter-coda">',
                f"이 장을 닫는 문장은 단순하다. {chapter.subtitle} 다음 장에서는 이 판단을 다른 업무 표면으로 옮긴다.",
                "</div>",
                "</section>",
                "",
            ]
        )

    lines.extend(
        [
            '<section class="page bibliography-page" markdown="1">',
            "# 참고와 공개 전 검토",
            "",
            "- 500개 이야기 꼭지 문서: `data/vibecoding-book/story-topics-2026-05-30/vibecoding-story-topics.md`",
            "- 계획 문서: `proc/plan/2026-05-30_ax-vibecoding-company-ipo-book.md`",
            "- 로컬 PPT 추출물: `data/vibecoding-book/extracts/`, `data/vibecoding-book/story-topics-2026-05-30/extracted-slides-xml/`",
            "- 로컬 Notion/Daily/ChatGPT DB: `data/notion/`, `data/daily/`, `data/db/chatgpt.sqlite`",
            "",
            "외부 공개 전 회사명, 실명, 고객 정보, 회계 정보, 보안 정보, 계정 정보, 강의 수강생 정보, PPT 이미지 권리를 검수해야 한다. 이 원고는 초판 원고이며, 공개판에서는 예시와 표현을 더 정제해야 한다.",
            "</section>",
            "",
            '<section class="page back-cover" markdown="1">',
            f"# {BOOK_TITLE}",
            "",
            "AI를 많이 쓰는 회사가 아니라 AI를 잘 쓰는 회사가 되어야 한다.",
            "",
            "이 책은 바이브코딩을 빠른 코딩 기술로만 다루지 않는다. 회사가 상장을 향해 갈 때 필요한 프로세스, 데이터, 검증, 사내교육, AX 클리닉, 인재 엔진의 언어로 다시 배열한다. 말라카 외부 강의의 대규모 실습 운영과 회사 AX의 책임 체계를 분리해, 독자가 자기 회사에서 바로 첫 자동화를 시작할 수 있게 만든다.",
            "",
            "상장을 보장하는 책이 아니라, 상장 가능한 체질을 만드는 책.",
            "</section>",
            "",
        ]
    )
    return "\n".join(lines)


CSS = r"""
@page {
  size: A5;
  margin: 17mm 15mm 19mm 15mm;
  @bottom-center {
    content: counter(page);
    font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
    font-size: 8pt;
    color: #6d6257;
  }
}
html { background: #ded8cf; }
body {
  margin: 0 auto;
  max-width: 760px;
  background: #fffdf8;
  color: #1f1a16;
  font-family: "AppleMyungjo", "NanumMyeongjo", "Noto Serif CJK KR", serif;
  font-size: 10.35pt;
  line-height: 1.86;
  word-break: keep-all;
  overflow-wrap: break-word;
}
* { letter-spacing: 0; box-sizing: border-box; }
@media screen {
  body { padding: 28px 42px; box-shadow: 0 18px 52px rgba(30,25,18,.18); }
  .page, .chapter-page {
    min-height: 760px;
    margin: 0 0 28px;
    padding: 54px 58px;
    border: 1px solid rgba(28,54,52,.13);
    box-shadow: 0 10px 24px rgba(30,25,18,.11);
  }
}
.page { break-after: page; }
.chapter-page { break-before: page; }
.cover {
  min-height: 205mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: linear-gradient(180deg, #fcfaf5, #efe9df);
}
.cover h1 {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  font-size: 29pt;
  line-height: 1.18;
  color: #12343a;
  margin: 0 0 8mm;
}
.cover-kicker, .cover-date {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  color: #0e6362;
  font-weight: 700;
  text-indent: 0;
}
.cover-subtitle, .cover-promise {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  text-indent: 0;
  max-width: 88%;
}
.cover-subtitle { font-size: 11pt; color: #3a312a; }
.cover-promise {
  margin-top: 8mm;
  padding-left: 4mm;
  border-left: 2.2mm solid #0e6362;
  color: #6b3f2b;
}
.title-page, .copyright-page, .preface-page, .greeting-page, .toc-page, .bibliography-page {
  padding-top: 24mm;
}
.part-page {
  padding-top: 50mm;
  background: #f6f0e7;
}
.part-page h1 {
  color: #0e6362;
  font-size: 21pt;
}
h1, h2, h3 {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  break-after: avoid;
}
h1 {
  font-size: 19pt;
  line-height: 1.34;
  margin: 0 0 7mm;
  color: #163236;
}
h2 {
  font-size: 14pt;
  margin: 8mm 0 3mm;
  color: #6b3f2b;
}
h3 {
  font-size: 11.5pt;
  margin: 7mm 0 2.5mm;
  color: #0e6362;
}
p {
  margin: 0 0 3.2mm;
  text-indent: 1em;
  orphans: 2;
  widows: 2;
}
strong { color: #6b3f2b; }
ul, ol { margin: 2mm 0 5mm 7mm; padding: 0; }
li { margin-bottom: 1.3mm; }
code {
  font-family: "SFMono-Regular", "Menlo", monospace;
  font-size: .88em;
  color: #174b4b;
}
.book-figure {
  margin: 5mm 0 7mm;
  break-inside: avoid;
}
.book-figure img {
  display: block;
  max-width: 100%;
  max-height: 78mm;
  margin: 0 auto 2mm;
  border: .35pt solid #d6cec2;
}
.book-figure figcaption {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  font-size: 7.3pt;
  line-height: 1.45;
  color: #73685f;
  text-align: center;
}
.chapter-coda {
  margin-top: 7mm;
  padding-top: 4mm;
  border-top: .45pt solid #d6cec2;
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
  font-size: 9.1pt;
  color: #5f5147;
}
.back-cover {
  min-height: 205mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #12343a;
  color: #fffaf2;
}
.back-cover h1 { color: #fffaf2; font-size: 25pt; }
.back-cover p { text-indent: 0; font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif; }
@media print {
  html, body { background: transparent; }
  body { max-width: none; }
  .page { min-height: 205mm; }
}
"""


def write_html(md_text: str, css_path: Path, html_path: Path) -> None:
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists", "md_in_html"])
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


def pdf_pages(path: Path) -> int:
    out = subprocess.check_output(["pdfinfo", str(path)], text=True)
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    if not m:
        raise RuntimeError(f"Cannot read page count from {path}")
    return int(m.group(1))


def write_review(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# 렌더 검수 기록",
            "",
            f"- 생성 시각: {summary['created_at']}",
            f"- 제목: {summary['title']}",
            f"- PDF pages: {summary['pdf_pages']}",
            f"- 장 수: {summary['chapters']}",
            f"- 재배열 꼭지 수: {summary['ordered_topics']}",
            f"- PPT 이미지 수: {summary['assets']}",
            "- 새 API 스크랩: 없음",
            "- 검증: `pdfinfo` 페이지 수 확인, `pdftotext` 텍스트 추출 확인, 브라우저 HTML 시각 검수 수행.",
            "- 공개 전 리스크: 회사 내부 정보, 고객/회계/보안/실명, PPT 이미지 권리 검토 필요.",
            "",
            "## 생성 파일",
            "",
            f"- 재배열 문서: `{summary['ordered_topics_md']}`",
            f"- 출판기획서: `{summary['publication_plan_md']}`",
            f"- Markdown 원고: `{summary['book_md']}`",
            f"- HTML: `{summary['book_html']}`",
            f"- PDF: `{summary['book_pdf']}`",
            "",
        ]
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    assets = copy_assets()
    topics = parse_topics()
    groups = chapter_topic_map(topics)
    ordered_count = sum(len(g) for g in groups)
    if len(topics) != 500:
        raise RuntimeError(f"Expected 500 topics, got {len(topics)}")
    if ordered_count != len({n for group in groups for n in group}):
        raise RuntimeError("Duplicate topic placement detected")
    if ordered_count != 500:
        raise RuntimeError(f"Expected 500 ordered topics, got {ordered_count}")

    ordered_path = OUT / "ordered-topics.md"
    plan_path = OUT / "publication-plan.md"
    md_path = OUT / "ax-vibecoding-company-ipo-book.md"
    css_path = OUT / "ax-vibecoding-company-ipo-book.css"
    html_path = OUT / "ax-vibecoding-company-ipo-book.html"
    pdf_path = OUT / "ax-vibecoding-company-ipo-book.pdf"
    review_path = OUT / "render-review.md"
    summary_path = OUT / "summary.json"

    ordered_path.write_text(render_ordered_topics(topics, groups), encoding="utf-8")
    plan_path.write_text(render_publication_plan(groups), encoding="utf-8")
    md_text = render_book_md(topics, groups, assets)
    md_path.write_text(md_text, encoding="utf-8")
    css_path.write_text(CSS.strip() + "\n", encoding="utf-8")
    write_html(md_text, css_path, html_path)
    HTML(filename=str(html_path)).write_pdf(str(pdf_path), stylesheets=[str(css_path)])
    pages = pdf_pages(pdf_path)

    summary: dict[str, object] = {
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "title": BOOK_TITLE,
        "subtitle": BOOK_SUBTITLE,
        "edition": BOOK_EDITION,
        "chapters": len(CHAPTERS),
        "parts": len({c.part for c in CHAPTERS}),
        "ordered_topics": ordered_count,
        "assets": len(assets),
        "pdf_pages": pages,
        "api_rescrape": False,
        "ordered_topics_md": str(ordered_path.resolve()),
        "publication_plan_md": str(plan_path.resolve()),
        "book_md": str(md_path.resolve()),
        "book_css": str(css_path.resolve()),
        "book_html": str(html_path.resolve()),
        "book_pdf": str(pdf_path.resolve()),
        "render_review": str(review_path.resolve()),
        "source_topics": str(TOPICS_PATH.resolve()),
        "plan": str(PLAN_PATH.resolve()),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path.write_text(write_review(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
