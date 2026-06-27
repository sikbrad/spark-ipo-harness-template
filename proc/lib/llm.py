"""OpenAI Chat Completions wrapper for raindrop-infer.

Uses `OPENAI_API_KEY` from `.env`. JSON-mode response. Throttle/backoff.
Plain `requests` — no SDK dependency.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

DEFAULT_MODEL = "gpt-4o-mini"
API_URL = "https://api.openai.com/v1/chat/completions"
MIN_INTERVAL_SEC = 0.6
MAX_RETRIES = 5


def _load_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    out: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def api_key() -> str:
    if k := os.environ.get("OPENAI_API_KEY"):
        return k
    env = _load_env()
    if k := env.get("OPENAI_API_KEY"):
        return k
    raise RuntimeError("OPENAI_API_KEY not found in env or .env")


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key()}",
                "Content-Type": "application/json",
            }
        )
        self.model = model
        self._last_ts = 0.0

    def _throttle(self) -> None:
        delta = time.monotonic() - self._last_ts
        if delta < MIN_INTERVAL_SEC:
            time.sleep(MIN_INTERVAL_SEC - delta)
        self._last_ts = time.monotonic()

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 1200,
        temperature: float = 0.3,
    ) -> dict:
        """Send a chat completion in JSON-mode and return the parsed object."""
        body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        for attempt in range(MAX_RETRIES):
            self._throttle()
            r = self.session.post(API_URL, json=body, timeout=120)
            if r.status_code == 429 or 500 <= r.status_code < 600:
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                raise LLMError(f"[{r.status_code}] {r.text[:500]}")
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                raise LLMError(f"JSON decode failed: {e} :: {content[:300]}")
        raise LLMError("max retries exceeded")


INFER_SYSTEM_PROMPT = """\
당신은 사용자의 북마크(raindrop) 컨텐츠를 분석해 압축 요약, 핵심 인사이트, 그리고
'언제 다시 보면 좋을지'를 평가하는 어시스턴트입니다.

출력은 반드시 다음 JSON 스키마를 따릅니다(다른 키 금지):

{
  "summary": "3-5문장의 한국어 TL;DR",
  "insights": ["핵심 인사이트 1", "..."],          // 2-5개
  "detail": "컨텐츠에서 추출한 1000자 이내 한국어 상세 메모. 사실/숫자/도구명/링크 우선.",
  "revisit_after_days": 0,                        // 정수, 0=다시볼 필요 없음 / 7 / 30 / 90 / 180 / 365
  "revisit_trigger": "다시 봐야 할 트리거 조건 (한국어 한 문장)",
  "category": "news|reference|tutorial|tool|opinion|entertainment|tech-trend|product|other",
  "freshness": "evergreen|short|medium|long"      // 컨텐츠 유통기한 추정
}

판단 기준:
- evergreen: 개념·튜토리얼·도구 사용법 등 시간 지나도 가치 유지 → revisit_after_days=180~365 또는 0
- long: 깊은 기술 분석, 6~12개월 가치 → 90~180
- medium: 트렌드·제품 리뷰, 1~3개월 → 30~90
- short: 단신·뉴스·쇼츠·밈 → 0~7 (대부분 0 = 다시 볼 필요 없음)

'insights'는 일반론 금지. 컨텐츠에서 추출한 구체 사실/숫자/이름이어야 함.
"""


def render_md(meta: dict, llm_out: dict) -> str:
    """Render the per-raindrop markdown from raindrop meta + LLM output."""
    fm_lines = ["---"]
    for k in ("id", "link", "title", "type", "domain", "fetcher", "status",
              "raindrop_tags", "raindrop_created", "raindrop_last_update",
              "inferred_at"):
        v = meta.get(k)
        if v is None:
            continue
        fm_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    for k in ("revisit_after_days", "revisit_trigger", "category", "freshness"):
        if k in llm_out:
            fm_lines.append(f"{k}: {json.dumps(llm_out[k], ensure_ascii=False)}")
    fm_lines.append("---")
    title = meta.get("title") or "(untitled)"
    md = "\n".join(fm_lines) + "\n\n"
    md += f"# {title}\n\n"
    md += f"<{meta.get('link','')}>\n\n"
    md += "## 요약\n\n" + (llm_out.get("summary") or "") + "\n\n"
    md += "## 핵심 인사이트\n\n"
    for it in llm_out.get("insights") or []:
        md += f"- {it}\n"
    md += "\n## 상세 메모\n\n" + (llm_out.get("detail") or "") + "\n\n"
    md += "## 재방문 가이드\n\n"
    after = llm_out.get("revisit_after_days")
    trig = llm_out.get("revisit_trigger") or ""
    if after == 0:
        md += f"- **다시 안 봐도 됨** — {trig}\n"
    else:
        md += f"- **다시 볼 시점**: {after}일 후\n"
        md += f"- **트리거**: {trig}\n"
    md += f"- **카테고리**: {llm_out.get('category')}\n"
    md += f"- **유통기한**: {llm_out.get('freshness')}\n"
    return md
