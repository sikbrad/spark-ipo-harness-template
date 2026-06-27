#!/usr/bin/env python3
"""Build and publish the domestic dental sales-candidate report for 260607."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dof_prospect_outline_publish as outline_publish  # noqa: E402


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_DIR = ROOT / "output/domestic-dental-candidates-260607"
SEARCH_JSONL = OUT_DIR / "naver_search_results.jsonl"
ENRICHED_JSON = OUT_DIR / "domestic_candidate_enriched.json"
REPORT_MD = OUT_DIR / "recommended_domestic_dental_report_260607.md"
RESULT_JSON = OUT_DIR / "recommended_domestic_dental_report_260607_result.json"
HEALTH_JSON = OUT_DIR / "outline_health_260607.json"

OUTLINE_BASE = "https://outline.doflab.com"
REPORT_PARENT_ID = "07b08eec-2ecb-42aa-b043-8e89f5ac6fb9"
REPORT_PARENT_URL = "https://outline.doflab.com/doc/66as7ys7yq4-cJZ5YdyvPw"
DOMESTIC_ROOT_URL = "https://outline.doflab.com/doc/ab-eGA5WmKiEM"
DOMESTIC_ROOT_ID = "5978b97b-028a-4bc5-a90a-6a72c854f3af"
REPORT_TITLE = "리포트260607-국내"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
TIMEOUT = 10
MAX_BODY = 800_000
MAX_FETCH_WORKERS = 12

SEARCH_QUERIES = [
    "치과기공소 디지털 기공소 CAD CAM",
    "치과기공소 구강스캐너 CAD CAM",
    "덴탈랩 치과기공소 CAD CAM",
    "디지털 치과기공소 지르코니아",
    "치과기공소 3D 프린터 밀링",
    "치과기공소 홈페이지 디지털",
    "치과기공소 모델리스 구강스캔",
    "치과기공소 지르코니아 밀링센터",
    "덴탈랩 지르코니아 모델리스",
    "치과기공소 CADCAM zirconia",
    "구강스캐너 치과 디지털 보철 원내기공",
    "원내 디지털 기공 치과",
    "원내기공소 치과 CAD CAM",
    "자체 디지털 기공소 치과",
    "세렉 치과 CEREC 원데이 보철",
    "자체 기공소 치과",
    "자체 기공센터 치과",
    "디지털 기공실 치과",
    "원내 기공실 치과",
    "원내 기공소 치과",
    "당일 보철 치과 CAD CAM",
    "원데이 크라운 치과",
    "프라임스캔 치과",
    "트리오스3 치과",
    "CEREC 치과",
    "치과 자체 기공센터",
    "치과 원내 기공센터",
    "치과 디지털 기공센터",
    "치과 원데이 보철 센터",
    "치과 디지털 보철센터",
    "프라임스캔 치과 구강스캐너",
    "TRIOS 구강스캐너 치과 디지털",
    "Medit i700 치과 구강스캐너",
    "3D 구강스캐너 치과 디지털 보철",
    "디지털 보철 치과 원내기공",
    "네비게이션 임플란트 구강스캐너 치과",
    "3D 프린터 보철 치과 구강스캐너",
    "서울 원내기공소 치과 디지털",
    "강남 원내기공소 치과 디지털",
    "부산 원내기공소 치과 디지털",
    "대구 디지털 치과 원내기공",
    "인천 디지털 치과 원내기공",
    "광주 디지털 치과 원내기공",
    "대전 디지털 치과 원내기공",
    "울산 디지털 치과 원내기공",
    "수원 디지털 치과 구강스캐너",
    "분당 디지털 치과 구강스캐너",
    "일산 디지털 치과 구강스캐너",
    "송도 디지털 치과 원내기공",
    "제주 디지털 치과 구강스캐너",
    "임플란트 치과 자체 기공센터 디지털",
    "당일 보철 치과 CAD CAM",
    "원데이 크라운 치과 구강스캐너",
    "치과 자체 기공센터 구강스캐너",
    "치과 디지털 워크플로우 원내 기공",
    'site:co.kr 치과 "원내 기공"',
    'site:co.kr 치과 "자체 기공소"',
    'site:co.kr 치과 "디지털 기공소"',
    'site:co.kr 치과 "구강스캐너" "원데이"',
    'site:co.kr 치과 "Primescan"',
    'site:co.kr 치과 "CEREC"',
    'site:co.kr 치과 "TRIOS"',
    'site:co.kr 치과 "메디트"',
    'site:co.kr 치과 "CAD/CAM"',
    'site:co.kr 치과 "캐드캠"',
    'site:co.kr 치과 "밀링"',
    'site:co.kr 치과 "3D 프린터"',
    'site:co.kr 치과 "네비게이션 임플란트" "구강스캐너"',
    'site:kr 치과 "원내 기공" "구강스캐너"',
    'site:kr 치과 "자체 기공소" "CAD/CAM"',
    'site:kr 치과 "디지털 기공실"',
    'site:kr 치과 "원데이 크라운" "구강스캐너"',
    "서울 치과 Primescan CEREC",
    "경기 치과 Primescan CEREC",
    "인천 치과 구강스캐너 원내기공",
    "부산 치과 CEREC 원데이 크라운",
    "대구 치과 TRIOS 구강스캐너",
    "대전 치과 CAD CAM 구강스캐너",
    "광주 치과 원데이 보철 구강스캐너",
    "강원 원주 치과 자체 기공소",
    "제주 치과 구강스캐너 원데이 보철",
]

SIGNAL_PATTERNS = [
    ("치과기공/덴탈랩", r"치과\s*기공|치과기공소|기공소|덴탈\s*랩|덴탈랩|Dental\s*Lab|밀링\s*센터|모델리스"),
    ("원내기공/기공센터", r"원내\s*기공|자체\s*(디지털\s*)?기공|기공\s*센터|in[- ]?house"),
    ("구강스캐너", r"구강\s*스캐너|3D\s*구강|intraoral\s*scanner"),
    ("Primescan/CEREC", r"프라임스캔|Primescan|세렉|CEREC"),
    ("TRIOS/3Shape", r"TRIOS|트리오스|3Shape|3\s*Shape"),
    ("Medit", r"Medit|메디트|i700|i900|i600"),
    ("Shining3D/Aoralscan", r"Shining\s*3D|샤이닝\s*3D|Aoralscan|오랄스캔"),
    ("CAD/CAM", r"CAD\s*/?\s*CAM|캐드\s*캠|캐드캠"),
    ("밀링/원데이 보철", r"밀링|milling|원데이\s*보철|당일\s*보철|원데이\s*크라운|당일\s*크라운"),
    ("3D 프린터", r"3D\s*프린터|3D\s*printer|프린팅"),
    ("네비게이션 임플란트", r"네비게이션\s*임플란트|내비게이션\s*임플란트|가이드\s*임플란트|implant\s*studio"),
    ("디지털 보철/워크플로우", r"디지털\s*보철|디지털\s*워크플로우|디지털\s*덴티스트리"),
]
RECENT_RE = re.compile(r"\b(2026|2025|2024)\b")
PHONE_RE = re.compile(r"(?<!\d)(0(?:2|[3-6][1-5]|70|10|50|80)[-.\s)]?\d{3,4}[-.\s]?\d{4})(?!\d)")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
ADDRESS_RE = re.compile(
    r"((?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)[^\\n|,;]{6,80})"
)
KOREAN_CLINIC_RE = re.compile(
    r"([가-힣A-Za-z0-9&·.\-\s]{2,45}"
    r"(?:치과병원|치과의원|치과기공소|치과|덴탈클리닉|덴탈랩|기공소|기공센터|밀링센터|Dental Clinic|Dental Lab|DENTAL LAB|Lab|LAB))"
)
SKIP_DOMAIN_MARKERS = (
    "doflab.com",
    "dailydental.co.kr",
    "dentalarirang.com",
    "dttoday.com",
    "news.",
    "youtube.com",
    "youtu.be",
)
ENTITY_NAME_RE = re.compile(r"(치과|치과기공소|기공소|덴탈랩|덴탈|밀링센터|Dental|DENTAL|Lab|LAB|DLAB)", re.I)
LAB_ENTITY_RE = re.compile(r"(치과기공소|기공소|덴탈랩|덴탈\s*랩|밀링센터|Dental\s*Lab|DLAB|Lab|LAB)", re.I)
BAD_CANDIDATE_DOMAIN_MARKERS = (
    "blog.naver.com",
    "post.naver.com",
    "cafe.naver.com",
    "namu.wiki",
    "goodoc.co.kr",
    "modoodoc.com",
    "icloudhospital.com",
    "dailydental.co.kr",
    "dentalarirang.com",
    "dttoday.com",
    "dentalzero.com",
    "dentalnews1.com",
    "dentalnews.or.kr",
    "dentistnews.kr",
    "denfoline.co.kr",
    "businesskorea.co.kr",
    "sportsseoul.com",
    "stardailynews.co.kr",
    "mt.co.kr",
    "dental2804.com",
    "huvitz.com",
    "dentsplysirona.com",
    "sidex.or.kr",
    "kdha.or.kr",
    "vcs.go.kr",
    "work24.go.kr",
    "moneypin.biz",
    "yucera.com",
    "ivoclar.com",
    "medit.com",
    "hyumc.com",
    "bizinfo.go.kr",
    "weseb.com",
    "ddocdoc.com",
    "kin.naver.com",
    "youtube.com",
    "youtu.be",
    "cashdoc.me",
    "ko.wikipedia.org",
    "wikipedia.org",
    "search.shopping.naver.com",
    "shopping.naver.com",
    "help.naver.com",
    "keep.naver.com",
    "doflab.com",
)
SECONDARY_DOMAIN_MARKERS = (
    "blog.naver.com",
    "post.naver.com",
    "youtube.com",
    "youtu.be",
    "dailydental.co.kr",
    "dentalarirang.com",
    "dttoday.com",
    "sportsseoul.com",
    "mt.co.kr",
)
GENERIC_NAME_PREFIX_RE = re.compile(
    r"^(?:"
    r"디지털|원내|자체|기공|기공실|기공소|기공센터|원내기공|원내기공실|"
    r"원데이|크라운|보철|보철치료|심미치료|임플란트|전체임플란트|"
    r"첨단장비|장비|소개|시스템|네비게이션|내비게이션|"
    r"주말진료|당일|즉시|치아|시술법입니다|보다꼼꼼한진단이가능한|매일진료하는|"
    r"[.·\s]+"
    r")+"
)
GENERIC_BAD_NAME_RE = re.compile(
    r"(뉴스|신문|기자|기사|세미나|DENTEX|SIDEX|DOF|디오에프|기획특집|인터뷰|"
    r"나무위키|CloudHospital|자유게시판|구강스캐너.*워크플로우|개원치과|치과의사신문|"
    r"보존치료|라미네이트|당일보철|풍부한경험|부한경험|임플란트중심진료)"
)
GENERIC_LOCATION_NAME_RE = re.compile(
    r"^(?:서울|강남|광화문|송도|수원|안산|대구|청주|전주|부산|울산|창원|분당|"
    r"권선구|관악구|대구북구|부산서면|종로|영종도|강동구|대치동|광명|일산|계양|달서구|서창동|"
    r"남양주|이천|평택|청라동|제주|강북|강서|강동|강남구|수영구|부평|고잔동|일산역|인천논현동|"
    r"대구임플란트|청주임플란트|수면마취|교정전문)"
    r"치과(?:의원|병원)?$"
)
REGION_KEYWORDS = {
    "수도권": ["서울", "경기", "인천", "강남", "강북", "송도", "분당", "수원", "일산", "광화문", "선정릉", "안성", "평택", "파주", "안산"],
    "영남": ["부산", "대구", "울산", "경북", "경남", "창원", "포항", "진주", "수영구", "서면"],
    "충청": ["대전", "세종", "충북", "충남", "청주", "천안"],
    "호남": ["광주", "전북", "전남", "전주", "순천", "목포"],
    "강원": ["강원", "원주", "춘천", "강릉"],
    "제주": ["제주"],
}

DOMAIN_NAME_OVERRIDES = {
    "zircamp.com": "Zircamp치과기공소",
    "kangnange.com": "강냉이닷컴치과기공소",
    "dlab.center": "DLAB덴탈랩",
    "abledental.aramcomms.com": "에이블덴탈랩",
    "dan-a.kr": "단아치과기공소",
    "zirart.co.kr": "지르아트치과기공소",
    "bngdentallab.com": "B&G덴탈랩",
    "himilling.com": "하이밀링치과기공소",
    "ideallab.co.kr": "아이디얼치과기공소",
    "zircarlab.com": "지르카디지털기공소",
    "anddentallab.com": "AND덴탈랩",
    "dontworrylab.com": "돈워리덴탈랩",
    "dendeal.ai.kr": "덴딜치과기공제조네트워크",
    "ttedental-mo2.imweb.me": "서울튼튼이치과",
    "soonplant.com": "서울순플란트치과",
    "77implant.co.kr": "77플란트치과",
    "haruplant.co.kr": "하루플란트치과",
    "minishlab.co.kr": "미니쉬치과병원",
    "granddc.co.kr": "부천그랜드치과",
    "w75.co.kr": "W치과",
    "gdfirstdent.co.kr": "고덕퍼스트치과",
    "gounfaced.co.kr": "고운얼굴치과",
    "ivandentallab.co.kr": "아이반치과기공소",
    "heriplant.co.kr": "강남헤리치과의원",
    "dbdh.co.kr": "닥터뷰티치과병원",
    "jinsimsmart.co.kr": "진심스마트치과",
    "yswith.com": "연세위드치과",
    "misofulldental.com": "진해미소가득치과의원",
    "seoultopplant.com": "서울탑플란트치과",
    "365dream.kr": "365드림치과병원",
    "thek365.co.kr": "더케이365치과병원",
    "suwon365.com": "수원365일치과",
    "1daydental.co.kr": "오늘하루치과",
    "smile75.com": "함박웃음치과",
    "inplantansan.co.kr": "안산인플란트치과",
    "xn--vb0b27ivsaf63fba.xn--hu5b25b77nvwc.org": "더이음치과",
    "e-medis.co.kr": "서면메디스치과",
    "hobak.kr": "대구호박치과",
    "jinjumir.co.kr": "진주미르치과",
}


@dataclass
class SearchHit:
    query: str
    title: str
    url: str
    snippet: str
    source: str


MANUAL_SOURCE_ROWS = [
    {
        "query": "web.run 치과기공소 디지털 CAD/CAM",
        "title": "Zircamp 치과기공소",
        "url": "https://www.zircamp.com/",
        "snippet": "치과기공소, 지르코니아, CAD/CAM, 밀링, 3D 프린터 기반 디지털 보철 제작 신호.",
        "source": "공식/일반웹",
    },
    {
        "query": "naver 치과기공소 디지털 기공소 CAD CAM",
        "title": "강냉이닷컴",
        "url": "https://www.kangnange.com/",
        "snippet": "치과기공소/덴탈랩 후보. 디지털 기공, 치과 보철 제작, 거래처용 웹 채널 확인 필요.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run dental lab korea zirconia milling",
        "title": "DLAB Dental Lab",
        "url": "https://www.dlab.center/",
        "snippet": "디지털 덴탈랩, 모델리스, 지르코니아, CAD/CAM, milling workflow 후보.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run 치과기공소 CAD/CAM",
        "title": "에이블덴탈랩",
        "url": "http://abledental.aramcomms.com/bbs/content.php?co_id=about",
        "snippet": "치과기공소/덴탈랩, 보철 제작, CAD/CAM 디지털 기공 후보.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run 치과기공소 모델리스",
        "title": "단아치과기공소",
        "url": "https://dan-a.kr/",
        "snippet": "치과기공소, 지르코니아, 밀링, 3D 프린터, 디지털 보철 제작 신호.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run 치과기공소 지르코니아",
        "title": "지르아트 치과기공소",
        "url": "https://zirart.co.kr/aboutus/",
        "snippet": "치과기공소, 지르코니아, 심미 보철, 디지털 기공 후보.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run 덴탈랩 치과기공소",
        "title": "B&G덴탈랩",
        "url": "https://bngdentallab.com/",
        "snippet": "덴탈랩/치과기공소, 3D 디지털 보철 제작 신호.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run 치과기공소 밀링센터",
        "title": "하이밀링",
        "url": "https://www.himilling.com/",
        "snippet": "치과기공소, 모델리스, 구강스캔, 밀링, 디지털 보철 제작 신호.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run 치과기공소 모델리스 구강스캔",
        "title": "아이디얼치과기공소",
        "url": "https://ideallab.co.kr/1",
        "snippet": "치과기공소, 구강스캔, 모델리스, 디지털 보철 제작 workflow 후보.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run 치과기공소 지르코니아 밀링",
        "title": "지르카 디지털 기공소",
        "url": "https://zircarlab.com/article",
        "snippet": "디지털 기공소, 구강스캔, 모델리스, 지르코니아, CAD/CAM 보철 제작 신호.",
        "source": "공식/일반웹",
    },
    {
        "query": "naver 덴탈랩 치과기공소 CAD CAM",
        "title": "AND 덴탈랩 치과기공소",
        "url": "https://anddentallab.com/product",
        "snippet": "덴탈랩/치과기공소, 3D 디지털 보철 제작 제품/서비스 신호.",
        "source": "공식/일반웹",
    },
    {
        "query": "naver 치과기공소 홈페이지 디지털",
        "title": "돈워리랩",
        "url": "https://www.dontworrylab.com/",
        "snippet": "치과기공소/덴탈랩, 모델리스, 지르코니아, 디지털 보철 제작 신호.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run 치과기공소 3D 프린터 밀링",
        "title": "덴딜/TLPlant 제조 네트워크",
        "url": "https://dendeal.ai.kr/manufacturing.html",
        "snippet": "치과기공소 제조 네트워크, 3D 프린터, 보철 제조/디지털 workflow 후보.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 원내 기공 구강스캐너",
        "title": "기공센터 — 하루플란트치과",
        "url": "https://haruplant.co.kr/lab-center",
        "snippet": "디지털 기공센터, 3D 스캐너, 밀링기, CAD/CAM, 디지털 설계 시스템, 당일 보철 가능.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 원내 기공 구강스캐너",
        "title": "미니쉬 기공연구소",
        "url": "https://www.minishlab.co.kr/",
        "snippet": "미니쉬치과병원 내 기공 연구소, 밀링머신 9대, 스캐너 6대, 디지털 연구소.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 Primescan CAD/CAM",
        "title": "부천 그랜드치과",
        "url": "https://granddc.co.kr/home",
        "snippet": "PrimeScan, CAD/CAM, 3D 네비게이션 임플란트 시스템 소개.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 Primescan CAD/CAM",
        "title": "W치과-강남치과, 신논현역치과",
        "url": "https://www.w75.co.kr/en/one-day-clinic/inlay",
        "snippet": "PrimeScan, CAD/CAM technology 기반 one-day clinic/inlay 진료.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 CAD/CAM 디지털",
        "title": "고덕퍼스트치과 인사이트",
        "url": "https://www.gdfirstdent.co.kr/insights/anjung-denture-digital-001",
        "snippet": "디지털 데이터, CAD 설계, CAM 밀링 장비를 활용한 디지털 틀니/보철 설명.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 Medit 구강스캐너",
        "title": "구강스캐너 - 답십리 고운얼굴치과",
        "url": "https://gounfaced.co.kr/%EA%B5%AC%EA%B0%95%EC%8A%A4%EC%BA%90%EB%84%88/",
        "snippet": "디지털 3D 구강스캐너 Medit 도입, 본뜨기 대신 3D 스캔 인상채득.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 TRIOS 구강스캐너",
        "title": "아이반치과기공소 | 구강스캐너 전문 디지털 기공소",
        "url": "https://www.ivandentallab.co.kr/",
        "snippet": "Medit, TRIOS, Primescan 등 구강스캐너 데이터 기반 디지털 기공소, CAD/CAM 밀링.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 TRIOS 3D 프린터",
        "title": "장비 소개 | 강남헤리치과의원",
        "url": "https://www.heriplant.co.kr/about-us/equipment/",
        "snippet": "NEXTDENT 5100 3D 프린터, 3Shape Trios3 구강스캐너 장비 소개.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 Medit 구강스캐너",
        "title": "닥터뷰티치과병원 의정부 임플란트",
        "url": "https://dbdh.co.kr/treatments/implant-overview",
        "snippet": "CT 영상과 구강스캐너 데이터, Medit 구강스캐너 기반 디지털 본 데이터 워크플로우.",
        "source": "공식/일반웹",
    },
    {
        "query": "web.run site:co.kr 치과 3D 프린터 구강스캐너",
        "title": "진심스마트치과",
        "url": "https://jinsimsmart.co.kr/",
        "snippet": "구강스캐너, 3D 프린터, 디지털 임플란트/심미 진료 신호.",
        "source": "공식/일반웹",
    },
]


@dataclass
class Candidate:
    name: str
    url: str
    source_url: str
    source_title: str
    search_queries: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)
    page_title: str = ""
    status: str = ""
    final_url: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    signals: list[str] = field(default_factory=list)
    recent: list[str] = field(default_factory=list)
    trust: str = "중간"
    priority: str = "B-검증후접촉"
    portal_status: str = "포털/주문 미확인"
    region: str = "기타/확인필요"
    subregion: str = "확인필요"
    description: str = ""
    recommendation: str = ""
    follow_up: str = ""


def compact(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def md_escape(value: Any, limit: int = 320) -> str:
    return compact(value, limit).replace("|", "\\|")


def normalize_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value or "").lower()


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    except Exception:
        return ""
    return host.removeprefix("www.")


def unwrap_naver_url(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ("url", "u"):
        if qs.get(key):
            return unquote(qs[key][0])
    return url


def result_source(url: str) -> str:
    domain = domain_of(url)
    if "blog.naver.com" in domain:
        return "네이버 블로그"
    if "youtube.com" in domain or "youtu.be" in domain:
        return "YouTube"
    if any(marker in domain for marker in ("dailydental", "dentalarirang", "dttoday", "sportsseoul", "mt.co.kr")):
        return "언론/전문지"
    if "naver.com" in domain:
        return "네이버"
    return "공식/일반웹"


def likely_official(url: str) -> bool:
    domain = domain_of(url)
    return bool(domain) and not any(marker in domain for marker in SECONDARY_DOMAIN_MARKERS)


def candidate_domain_allowed(url: str) -> bool:
    domain = domain_of(url)
    return bool(domain) and not any(marker in domain for marker in BAD_CANDIDATE_DOMAIN_MARKERS)


def clean_clinic_name(value: str) -> str:
    text = compact(value, 120)
    text = re.sub(r"https?://\S+|www\.\S+|[A-Za-z0-9.-]+\.(?:co\.kr|kr|com|net|org)\S*", "", text)
    text = re.sub(r"\b(?:Keep에 저장|Keep에 바로가기|AI 출처 정보)\b.*", "", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"^[A-Za-z]*DentalClinic", "", text)
    for token in ("의료서비스확충", "보유", "있는", "위한", "위해", "에서는", "에서", "는"):
        if token in text and text.rfind(token) < text.rfind("치과"):
            text = text.split(token)[-1]
    text = GENERIC_NAME_PREFIX_RE.sub("", text)
    text = re.sub(r"^(?:[-–—|/›>_:]+)+", "", text)
    text = re.sub(r"(치과(?:병원|의원)?)(?:.+)\1$", r"\1", text)
    if len(text) > 30:
        ends = [
            text.rfind(token) + len(token)
            for token in ("치과병원", "치과의원", "치과기공소", "덴탈랩", "기공소", "기공센터", "밀링센터", "치과")
            if token in text
        ]
        if ends:
            end = max(ends)
            start = max(0, end - 20)
            text = text[start:end]
    return compact(text, 60)


def has_entity_name(name: str) -> bool:
    return bool(ENTITY_NAME_RE.search(name or ""))


def is_lab_candidate(cand: Candidate) -> bool:
    return bool(LAB_ENTITY_RE.search(cand.name or ""))


def is_bad_candidate_name(name: str) -> bool:
    if not name or not has_entity_name(name):
        return True
    if any(ch in name for ch in "[]{}") or name.startswith(("-", "소-")):
        return True
    if GENERIC_BAD_NAME_RE.search(name) or GENERIC_LOCATION_NAME_RE.search(name):
        return True
    if len(name) < 4 or len(name) > 24:
        return True
    return False


def extract_clinic_name(*texts: str) -> str:
    combined = " ".join(compact(t, 260) for t in texts if t)
    combined = re.sub(r"\s*(?:홈페이지|공식|www\.[^\s]+|https?://\S+|›.*)$", "", combined)
    parts = re.split(r"\||｜|-|–|—|›|>|/|\n", combined)
    matches: list[str] = []
    for part in parts + [combined]:
        matches.extend(KOREAN_CLINIC_RE.findall(part))
    cleaned: list[str] = []
    for match in matches:
        item = clean_clinic_name(match)
        if len(item) >= 3 and has_entity_name(item):
            cleaned.append(item)
    if cleaned:
        non_bad = [item for item in cleaned if not is_bad_candidate_name(item)]
        if non_bad:
            return min(non_bad, key=lambda item: (len(item), item))
        cleaned = [item for item in cleaned if not GENERIC_BAD_NAME_RE.search(item)]
        if cleaned:
            return min(cleaned, key=lambda item: (GENERIC_LOCATION_NAME_RE.search(item) is not None, len(item), item))
    title = re.split(r"\||-|–|—|:", combined)[0].strip()
    return clean_clinic_name(title)


def detect_signals(text: str) -> list[str]:
    found: list[str] = []
    for label, pattern in SIGNAL_PATTERNS:
        if re.search(pattern, text, re.I) and label not in found:
            found.append(label)
    return found


def extract_recent(text: str) -> list[str]:
    out: list[str] = []
    for match in RECENT_RE.finditer(text):
        start = max(0, match.start() - 70)
        end = min(len(text), match.end() + 100)
        snip = compact(text[start:end], 180)
        if snip and snip not in out:
            out.append(snip)
        if len(out) >= 2:
            break
    return out


def extract_first(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return compact(match.group(1) if match and match.groups() else match.group(0) if match else "", 120)


def infer_region(address: str, query: str, name: str, snippet: str, phone: str = "") -> tuple[str, str]:
    for text in (address, snippet, name):
        earliest: tuple[int, str, str] | None = None
        for region, keys in REGION_KEYWORDS.items():
            for key in keys:
                idx = (text or "").find(key)
                if idx >= 0 and (earliest is None or idx < earliest[0]):
                    earliest = (idx, region, key)
        if earliest:
            return earliest[1], earliest[2]
    phone_digits = re.sub(r"\D", "", phone or "")
    if phone_digits.startswith("02"):
        return "수도권", "서울"
    if phone_digits.startswith(("031", "032")):
        return "수도권", "경기/인천"
    if phone_digits.startswith(("041", "042", "043", "044")):
        return "충청", "충청"
    if phone_digits.startswith(("051", "052", "053", "054", "055")):
        return "영남", "영남"
    if phone_digits.startswith(("061", "062", "063", "064")):
        return "호남/제주", "호남/제주"
    combined = " ".join([query, snippet, name])
    earliest: tuple[int, str, str] | None = None
    for region, keys in REGION_KEYWORDS.items():
        for key in keys:
            idx = combined.find(key)
            if idx >= 0 and (earliest is None or idx < earliest[0]):
                earliest = (idx, region, key)
    if earliest:
        return earliest[1], earliest[2]
    return "기타/확인필요", "확인필요"


def naver_search(query: str, start: int = 1) -> list[SearchHit]:
    response = requests.get(
        "https://search.naver.com/search.naver",
        params={"query": query, "start": start},
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = unwrap_naver_url(a["href"])
        if not href.startswith("http"):
            continue
        domain = domain_of(href)
        if not domain or domain in {"search.naver.com", "www.naver.com"}:
            continue
        text = compact(a.get_text(" ", strip=True), 180)
        if not text:
            continue
        parent = a.find_parent(["div", "li", "section", "article"])
        snippet = compact(parent.get_text(" ", strip=True) if parent else text, 520)
        combined = f"{text} {snippet} {href}"
        if not has_entity_name(combined) and not any(re.search(p, combined, re.I) for _, p in SIGNAL_PATTERNS):
            continue
        if any(marker in domain for marker in ("adcr.naver.com", "adcreative", "ader.naver.com")):
            continue
        key = href.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        hits.append(SearchHit(query=query, title=text, url=href, snippet=snippet, source=result_source(href)))
        if len(hits) >= 20:
            break
    return hits


def collect_search_hits(limit_queries: int) -> list[SearchHit]:
    rows: list[SearchHit] = [SearchHit(**row) for row in MANUAL_SOURCE_ROWS]
    for query in SEARCH_QUERIES[:limit_queries]:
        for start in (1, 11):
            try:
                rows.extend(naver_search(query, start=start))
                time.sleep(0.08)
            except Exception as error:
                rows.append(SearchHit(query=query, title=f"SEARCH_ERROR {type(error).__name__}", url="", snippet=str(error), source="error"))
    return rows


def fetch_page(url: str) -> dict[str, Any]:
    if not url:
        return {"status": "no link", "final_url": "", "title": "", "text": ""}
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        status = f"{response.status_code} {'OK' if response.status_code < 400 else 'WARN'}"
        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "html" not in content_type and response.content[:4] == b"%PDF":
            return {"status": status, "final_url": response.url, "title": "PDF", "text": ""}
        raw = response.text[:MAX_BODY]
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        title = compact(soup.title.get_text(" ", strip=True) if soup.title else "", 160)
        text = compact(soup.get_text(" ", strip=True), 5500)
        return {"status": status, "final_url": response.url, "title": title, "text": text}
    except Exception as error:
        return {"status": f"ERROR {type(error).__name__}", "final_url": url, "title": "", "text": str(error)}


def load_existing_customer_keys() -> set[str]:
    keys: set[str] = set()
    for path in [
        ROOT / "output/portal-contact-update-20260525/contact-update-analysis.json",
        ROOT / "output/portal-contact-update-20260525/contact-update-ready.json",
        ROOT / "output/portal-contact-update-20260525/contact-update-holds.json",
        ROOT / "output/portal-contact-update-20260525/hold-candidate-db-details.json",
    ]:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                for k, v in item.items():
                    if isinstance(v, str) and any(token in k.lower() for token in ("name", "company", "customer", "account")):
                        norm = normalize_key(v)
                        if len(norm) >= 4:
                            keys.add(norm)
                    elif isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(item, list):
                stack.extend(item)
    invoice_dirs = [
        Path("/Users/gq/onedrive-drops/DOF Inc - Process innovation - Documents"),
        Path("/Users/gq/onedrive-drops/DOF Inc - Process innovation - Documents 2"),
    ]
    for base in invoice_dirs:
        if not base.exists():
            continue
        for path in base.glob("**/*INVOICE*"):
            name = re.sub(r"^\[|\].*$", "", path.name)
            norm = normalize_key(name)
            if len(norm) >= 4:
                keys.add(norm)
    return keys


def group_hits(hits: list[SearchHit]) -> dict[str, Candidate]:
    grouped: dict[str, Candidate] = {}
    for hit in hits:
        if not hit.url:
            continue
        if not candidate_domain_allowed(hit.url):
            continue
        name = DOMAIN_NAME_OVERRIDES.get(domain_of(hit.url), extract_clinic_name(hit.title, hit.snippet))
        if not name or "디오에프" in name or GENERIC_BAD_NAME_RE.search(name):
            continue
        combined = f"{hit.title} {hit.snippet}"
        if not has_entity_name(name) and not has_entity_name(combined):
            continue
        key = domain_of(hit.url) or normalize_key(name)
        if len(key) < 4:
            continue
        official_url = hit.url
        if key not in grouped:
            grouped[key] = Candidate(
                name=name,
                url=official_url if likely_official(official_url) else "",
                source_url=hit.url,
                source_title=hit.title,
                search_queries=[hit.query],
                snippets=[hit.snippet],
            )
        else:
            cand = grouped[key]
            if hit.query not in cand.search_queries:
                cand.search_queries.append(hit.query)
            if hit.snippet not in cand.snippets and len(cand.snippets) < 5:
                cand.snippets.append(hit.snippet)
            if likely_official(hit.url) and (not cand.url or not likely_official(cand.url)):
                cand.url = hit.url
            if hit.source == "언론/전문지" and cand.source_url == cand.url:
                cand.source_url = hit.url
                cand.source_title = hit.title
    return grouped


def enrich_candidate(cand: Candidate, existing_keys: set[str]) -> Candidate:
    target_url = cand.url or cand.source_url
    fetched = fetch_page(target_url)
    combined = " ".join([cand.name, cand.source_title, " ".join(cand.snippets), fetched.get("title", ""), fetched.get("text", "")])
    refined_name = DOMAIN_NAME_OVERRIDES.get(domain_of(target_url), extract_clinic_name(cand.source_title, fetched.get("title", ""), cand.name))
    if refined_name and not GENERIC_BAD_NAME_RE.search(refined_name) and not is_bad_candidate_name(refined_name):
        cand.name = refined_name
    if fetched.get("title"):
        cand.page_title = fetched["title"]
    cand.status = fetched.get("status", "")
    cand.final_url = fetched.get("final_url", target_url)
    if not cand.url and likely_official(cand.final_url):
        cand.url = cand.final_url
    cand.signals = detect_signals(combined)
    cand.recent = extract_recent(combined)
    cand.phone = extract_first(PHONE_RE, combined)
    cand.email = extract_first(EMAIL_RE, combined)
    cand.address = extract_first(ADDRESS_RE, combined)
    cand.region, cand.subregion = infer_region(
        cand.address,
        " ".join(cand.search_queries),
        cand.name,
        " ".join(cand.snippets),
        cand.phone,
    )
    norm = normalize_key(cand.name)
    if norm in existing_keys or any(norm and norm in key for key in existing_keys):
        cand.portal_status = "기존 포털/주문 유사명 - 후보 제외 권장"
    else:
        cand.portal_status = "포털/주문 직접 매칭 없음"

    lab_candidate = is_lab_candidate(cand)
    high_signal = {"치과기공/덴탈랩", "원내기공/기공센터", "Primescan/CEREC", "CAD/CAM", "밀링/원데이 보철"}
    scanner_signal = {"구강스캐너", "TRIOS/3Shape", "Medit", "Shining3D/Aoralscan"}
    official = bool(cand.url and likely_official(cand.url))
    status_ok = cand.status.startswith("200") or cand.status.startswith("3")
    if cand.portal_status.startswith("기존"):
        cand.priority = "제외/주의"
        cand.trust = "중간"
    elif official and status_ok and (set(cand.signals) & high_signal) and (set(cand.signals) & scanner_signal):
        cand.priority = "A-우선접촉"
        cand.trust = "높음"
    elif official and status_ok and len(cand.signals) >= 2:
        cand.priority = "A-우선접촉"
        cand.trust = "높음" if cand.phone or cand.address else "중간"
    elif len(cand.signals) >= 2:
        cand.priority = "B-검증후접촉"
        cand.trust = "중간"
    else:
        cand.priority = "C-추가확인"
        cand.trust = "낮음"

    if lab_candidate:
        cand.description = "디지털 보철 제작/밀링/CAD-CAM 신호가 있는 치과기공소·덴탈랩"
    elif "원내기공/기공센터" in cand.signals:
        cand.description = "원내/자체 기공 또는 기공센터 운영 신호가 있는 치과"
    elif "Primescan/CEREC" in cand.signals:
        cand.description = "CEREC/Primescan 기반 체어사이드 보철 신호가 있는 치과"
    elif "구강스캐너" in cand.signals:
        cand.description = "구강스캐너 기반 디지털 진료 신호가 있는 치과"
    else:
        cand.description = "디지털 임플란트/보철 신호가 검색되는 치과"

    signal_text = ", ".join(cand.signals[:5]) or "디지털 진료 키워드 추가확인"
    cand.recommendation = (
        f"{signal_text} 신호가 있어 DOF 구강스캐너, 밀링기, 치기공 디지털 보철 워크플로우 제안 대상성이 있다."
    )
    if lab_candidate and cand.priority == "A-우선접촉":
        cand.follow_up = "기공소장/디지털 담당자 확인 후 스캔 데이터-디자인-밀링 workflow 제안"
    elif cand.priority == "A-우선접촉":
        cand.follow_up = "원장/디지털 담당자 확인 후 원내기공·스캔-밀링 데모 제안"
    elif cand.priority.startswith("B"):
        cand.follow_up = "홈페이지/블로그 기반 장비 보유 여부 재확인 후 콜드아웃"
    else:
        cand.follow_up = "HIRA/네이버플레이스/전화로 실운영 여부 확인"
    return cand


def choose_candidates(candidates: list[Candidate], target_count: int) -> list[Candidate]:
    rank = {"A-우선접촉": 0, "B-검증후접촉": 1, "C-추가확인": 2, "제외/주의": 9}
    sorted_rows = sorted(
        candidates,
        key=lambda c: (
            rank.get(c.priority, 5),
            -len(c.signals),
            0 if c.trust == "높음" else 1 if c.trust == "중간" else 2,
            c.region,
            c.name,
        ),
    )
    rows: list[Candidate] = []
    seen: set[str] = set()
    seen_domains: set[str] = set()
    for cand in sorted_rows:
        if cand.priority in {"제외/주의", "C-추가확인"}:
            continue
        if not candidate_domain_allowed(cand.url or cand.final_url or cand.source_url):
            continue
        if is_bad_candidate_name(cand.name):
            continue
        key = normalize_key(cand.name)
        domain = domain_of(cand.url or cand.final_url or cand.source_url)
        if key in seen or domain in seen_domains:
            continue
        seen.add(key)
        if domain:
            seen_domains.add(domain)
        rows.append(cand)
        if len(rows) >= target_count:
            break
    return rows


def make_report(rows: list[Candidate], all_count: int, outline_status: dict[str, Any]) -> str:
    counts = Counter(row.priority for row in rows)
    regions = Counter(row.region for row in rows)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 260607 국내 치과 영업후보 추천 요약",
        "",
        "## 작성 기준",
        f"- 대상: {DOMESTIC_ROOT_URL} 하위 국내 치과의원 영업후보와 별도 공개 조사로 보강한 국내 치과기공소/덴탈랩 후보.",
        "- 참고 형식: `리포트260604-해외`의 추천 요약/추천 테이블 구조를 국내 치과/치기공 후보용으로 변환했다.",
        "- 우선순위 기준: 공개 웹에서 원내/자체 기공, 치과기공소/덴탈랩, 구강스캐너, CEREC/Primescan/TRIOS/Medit, CAD/CAM, 원데이 보철, 지르코니아/밀링, 네비게이션 임플란트 신호가 확인되는 곳을 상위로 두었다.",
        "- 포탈/주문 기준: 로컬 portal/contact/order 산출물의 회사명·거래명세서 파일명과 강한 이름 매칭이 있는 경우 추천 후보에서 제외하거나 주의 표시했다.",
        "- 신뢰도 기준: 공식 홈페이지/치과·기공소 자체 페이지 + HTTP 200 + 장비/워크플로우 키워드가 같이 잡히면 높음, 블로그/영상/언론 단독이면 중간 이하로 표시했다.",
        f"- 작성 시각: {now} KST. Outline API 상태: {compact(outline_status.get('status') or 'unknown', 180)}",
        "",
        "## 추천 요약",
        f"- 검색·수집 후보: {all_count}개",
        f"- 추천 반영: {len(rows)}개",
        f"- A-우선접촉: {counts.get('A-우선접촉', 0)}개",
        f"- B-검증후접촉: {counts.get('B-검증후접촉', 0)}개",
        f"- C-추가확인: {counts.get('C-추가확인', 0)}개",
        "- 핵심 소싱 방법: 네이버 웹 검색, 공개 웹검색(site:co.kr), 공식 치과/기공소 홈페이지 직접 fetch, 로컬 portal/order 이름 매칭.",
        "- 권역 분포: " + ", ".join(f"{k} {v}" for k, v in regions.most_common()) if rows else "- 권역 분포: 없음",
        "",
        "## 추천 업체 테이블",
        "| 우선순위 | 대분류 | 중분류 | 소분류 | 업체/치과 | 어떤 곳인지 | 포털 존재 여부 | 확인된 디지털/보철 신호 | 왜 추천하는지 | 연락/웹 | 확인 출처 | 웹 링크 상태 | 최근 온라인 흔적 | 신뢰도 | 후속 액션 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        contact_bits = []
        if row.phone:
            contact_bits.append(row.phone)
        if row.email:
            contact_bits.append(row.email)
        if row.address:
            contact_bits.append(row.address)
        if row.url or row.final_url:
            web_url = row.url or row.final_url
            contact_bits.append(f"[web]({web_url})")
        source = f"[{md_escape(row.source_title or result_source(row.source_url), 90)}]({row.source_url})" if row.source_url else ""
        recent = "<br>".join(md_escape(item, 140) for item in row.recent[:2]) or "최근연도 직접 신호 미확인"
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(row.priority, 80),
                    "국내 치과/치기공 영업후보",
                    md_escape(row.region, 60),
                    md_escape(row.subregion, 60),
                    f"[{md_escape(row.name, 80)}]({row.url or row.source_url})" if (row.url or row.source_url) else md_escape(row.name, 80),
                    md_escape(row.description, 140),
                    md_escape(row.portal_status, 120),
                    md_escape(", ".join(row.signals) or "추가확인", 160),
                    md_escape(row.recommendation, 240),
                    "<br>".join(md_escape(x, 110) for x in contact_bits) or "연락처 웹 확인 필요",
                    source,
                    md_escape(row.status, 80),
                    recent,
                    md_escape(row.trust, 60),
                    md_escape(row.follow_up, 140),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 신뢰도 메모",
            "- 높음: 치과/치과기공소 자체 홈페이지 또는 공식 페이지에서 장비·원내기공·디지털 보철 관련 문구가 확인되고 링크가 정상 응답.",
            "- 중간: 블로그/영상/언론/검색 스니펫 중심으로 확인되며 공식 페이지 또는 연락처 확인이 추가로 필요.",
            "- 낮음: 키워드는 있으나 실제 장비 보유·진료 활용 여부가 약해 전화 또는 네이버플레이스 재확인이 필요.",
            "",
            "## 후속 작업",
            "- A 후보는 원장/기공소장/디지털 담당자 컨택 전 HIRA/네이버플레이스/사업자 정보에서 영업상태와 전화번호를 한 번 더 검증한다.",
            "- CEREC/Primescan/TRIOS/Medit/원내기공/치과기공소 신호가 있는 곳은 구강스캐너 단품보다 스캔-디자인-밀링 workflow 관점으로 제안한다.",
            "- 기존 portal/order 유사명이 발견되는 경우 별도 고객관리 대상인지 확인하고 신규 후보 리포트에서는 제외한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def candidate_to_dict(cand: Candidate) -> dict[str, Any]:
    return {
        "name": cand.name,
        "url": cand.url,
        "source_url": cand.source_url,
        "source_title": cand.source_title,
        "search_queries": cand.search_queries,
        "snippets": cand.snippets,
        "page_title": cand.page_title,
        "status": cand.status,
        "final_url": cand.final_url,
        "phone": cand.phone,
        "email": cand.email,
        "address": cand.address,
        "signals": cand.signals,
        "recent": cand.recent,
        "trust": cand.trust,
        "priority": cand.priority,
        "portal_status": cand.portal_status,
        "region": cand.region,
        "subregion": cand.subregion,
        "description": cand.description,
        "recommendation": cand.recommendation,
        "follow_up": cand.follow_up,
    }


def outline_api(session: requests.Session, endpoint: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = session.post(f"{OUTLINE_BASE}/api/{endpoint}", json=body, timeout=timeout)
    response.raise_for_status()
    return response.json()


def publish_to_outline(markdown: str, timeout: int) -> dict[str, Any]:
    key = outline_publish.read_env_key("DOF_OUTLINE_KEY")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}"})
    health: dict[str, Any] = {"checked_at": datetime.now().isoformat(timespec="seconds"), "status": "starting"}
    try:
        root = outline_api(session, "documents.info", {"id": DOMESTIC_ROOT_ID}, timeout)
        parent = outline_api(session, "documents.info", {"id": REPORT_PARENT_ID}, timeout)
        health.update(
            {
                "status": "healthy",
                "domestic_root_title": (root.get("data") or {}).get("title"),
                "parent_title": (parent.get("data") or {}).get("title"),
            }
        )
    except Exception as error:
        health.update({"status": f"outline health failed: {type(error).__name__}: {error}"})
        save_json(HEALTH_JSON, health)
        return {"published": False, "health": health, "error": health["status"]}

    try:
        existing_id = ""
        existing_url = ""
        listed = outline_api(session, "documents.list", {"parentDocumentId": REPORT_PARENT_ID, "limit": 100, "offset": 0}, timeout)
        for doc in listed.get("data") or []:
            if doc.get("title") == REPORT_TITLE:
                existing_id = doc.get("id") or ""
                existing_url = f"{OUTLINE_BASE}/doc/{doc.get('urlId')}"
                break
        if existing_id:
            data = outline_api(
                session,
                "documents.update",
                {"id": existing_id, "title": REPORT_TITLE, "text": markdown, "publish": True, "fullWidth": True},
                timeout,
            )["data"]
            action = "updated"
        else:
            data = outline_api(
                session,
                "documents.create",
                {
                    "title": REPORT_TITLE,
                    "parentDocumentId": REPORT_PARENT_ID,
                    "text": markdown,
                    "publish": True,
                    "fullWidth": True,
                },
                timeout,
            )["data"]
            action = "created"
        doc_id = data.get("id") or existing_id
        readback = outline_api(session, "documents.info", {"id": doc_id}, timeout)["data"]
        result = {
            "published": True,
            "action": action,
            "doc_id": doc_id,
            "url": f"{OUTLINE_BASE}/doc/{readback.get('urlId')}" if readback.get("urlId") else existing_url,
            "title": readback.get("title"),
            "text_length": len(readback.get("text") or ""),
            "health": health,
        }
        save_json(HEALTH_JSON, health)
        return result
    except Exception as error:
        health.update({"status": f"outline publish failed: {type(error).__name__}: {error}"})
        save_json(HEALTH_JSON, health)
        return {"published": False, "health": health, "error": health["status"]}


def build_report(target_count: int, limit_queries: int, publish: bool, outline_timeout: int) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    hits = collect_search_hits(limit_queries)
    write_jsonl(SEARCH_JSONL, [hit.__dict__ for hit in hits])
    grouped = group_hits(hits)
    existing_keys = load_existing_customer_keys()
    enriched: list[Candidate] = []
    with ThreadPoolExecutor(max_workers=MAX_FETCH_WORKERS) as executor:
        futures = [executor.submit(enrich_candidate, cand, existing_keys) for cand in grouped.values()]
        for future in as_completed(futures):
            try:
                enriched.append(future.result())
            except Exception:
                continue
    chosen = choose_candidates(enriched, target_count)
    outline_status = {"status": "publish skipped"}
    markdown = make_report(chosen, len(enriched), outline_status)
    REPORT_MD.write_text(markdown, encoding="utf-8")
    save_json(ENRICHED_JSON, {"all": [candidate_to_dict(c) for c in enriched], "chosen": [candidate_to_dict(c) for c in chosen]})
    publish_result: dict[str, Any] = {"published": False, "skipped": not publish}
    if publish:
        publish_result = publish_to_outline(markdown, outline_timeout)
        markdown = make_report(chosen, len(enriched), publish_result.get("health") or publish_result)
        REPORT_MD.write_text(markdown, encoding="utf-8")
        if publish_result.get("published"):
            publish_result = publish_to_outline(markdown, outline_timeout)
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "search_hits": len([h for h in hits if h.url]),
        "candidate_count": len(enriched),
        "chosen_count": len(chosen),
        "priority_counts": dict(Counter(c.priority for c in chosen)),
        "region_counts": dict(Counter(c.region for c in chosen)),
        "report_md": str(REPORT_MD),
        "enriched_json": str(ENRICHED_JSON),
        "search_jsonl": str(SEARCH_JSONL),
        "outline": publish_result,
    }
    save_json(RESULT_JSON, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-count", type=int, default=120)
    parser.add_argument("--limit-queries", type=int, default=len(SEARCH_QUERIES))
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--outline-timeout", type=int, default=15)
    args = parser.parse_args()
    result = build_report(args.target_count, args.limit_queries, args.publish, args.outline_timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
