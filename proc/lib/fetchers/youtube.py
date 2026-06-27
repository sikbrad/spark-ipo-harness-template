"""YouTube fetcher — youtube-transcript-api (no auth) + yt-dlp metadata.

Caption extraction goes through `youtube-transcript-api` (pip), which hits
YouTube's public timedtext endpoint directly with a much lighter request
shape than yt-dlp — no browser cookies needed, much less aggressive
rate-limiting.

Video metadata (title, description, duration, channel, view count) comes
from `yt-dlp --print` — that endpoint is the regular player API and does
not 429 like timedtext does.

If captions are disabled / unavailable, we return status='partial' with
metadata-only text, which is still useful for the LLM (raindrop title +
excerpt + tags carry a lot of signal).
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.parse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

YT_DLP = "yt-dlp"
LANGS = ("ko", "en")
TIMEOUT_META = 30
MAX_TEXT = 12000

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _video_id(link: str) -> str | None:
    """Extract video id from common YT URL forms."""
    p = urllib.parse.urlparse(link)
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        vid = p.path.strip("/").split("/")[0]
        return vid if _VIDEO_ID_RE.match(vid) else None
    if "youtube.com" not in host:
        return None
    if p.path == "/watch":
        vid = urllib.parse.parse_qs(p.query).get("v", [None])[0]
        return vid if vid and _VIDEO_ID_RE.match(vid) else None
    # shorts/<id>, embed/<id>, live/<id>
    parts = [s for s in p.path.split("/") if s]
    if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
        vid = parts[1]
        return vid if _VIDEO_ID_RE.match(vid) else None
    return None


def _yt_metadata(link: str) -> dict:
    """Run yt-dlp --print to get the video metadata JSON. No subs, no 429."""
    try:
        r = subprocess.run(
            [
                YT_DLP,
                "--no-warnings",
                "--skip-download",
                "--ignore-no-formats-error",
                "--print",
                "%(.{id,title,duration,uploader,upload_date,view_count,channel,channel_id,description})j",
                link,
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_META,
        )
    except subprocess.TimeoutExpired:
        return {}
    if r.returncode != 0:
        return {}
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                return {}
    return {}


def _fetch_transcript(video_id: str) -> tuple[str, str | None]:
    """Return (joined_text, lang) or ('', None) if unavailable."""
    api = YouTubeTranscriptApi()
    try:
        tr = api.fetch(video_id, languages=list(LANGS))
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        return "", None
    except Exception:
        return "", None
    parts = [s.text.strip() for s in tr.snippets if s.text and s.text.strip()]
    # dedupe consecutive duplicates (common in auto-captions)
    deduped: list[str] = []
    last = None
    for t in parts:
        if t == last:
            continue
        deduped.append(t)
        last = t
    return "\n".join(deduped), tr.language_code


def fetch(link: str, raindrop: dict | None = None) -> dict:
    vid = _video_id(link)
    if not vid:
        return {
            "status": "failed",
            "fetcher": "youtube",
            "text": "",
            "meta": {"final_url": link},
            "error": "could not parse video id",
        }

    meta = _yt_metadata(link)
    transcript_text, lang = _fetch_transcript(vid)

    description = (meta.get("description") or "")[:1500]
    head = []
    if meta.get("title"):
        head.append(f"[Title] {meta['title']}")
    if meta.get("channel"):
        head.append(f"[Channel] {meta['channel']}")
    if meta.get("duration"):
        head.append(f"[Duration] {meta['duration']}s")
    if meta.get("view_count"):
        head.append(f"[Views] {meta['view_count']}")
    if description:
        head.append(f"[Description] {description}")
    if transcript_text:
        head.append(f"[Transcript ({lang})]")
        head.append(transcript_text)
    text = "\n".join(head)[:MAX_TEXT]

    if not transcript_text:
        # caller's LLM still has title/description/raindrop fields to work with
        return {
            "status": "partial",
            "fetcher": "youtube",
            "text": text,
            "meta": {
                "final_url": link,
                "video_id": vid,
                "yt": {k: meta.get(k) for k in
                       ("id", "title", "channel", "duration",
                        "upload_date", "view_count")
                       if meta.get(k) is not None},
                "no_captions": True,
            },
            "error": None,
        }

    return {
        "status": "ok",
        "fetcher": "youtube",
        "text": text,
        "meta": {
            "final_url": link,
            "video_id": vid,
            "yt": {k: meta.get(k) for k in
                   ("id", "title", "channel", "duration",
                    "upload_date", "view_count")
                   if meta.get(k) is not None},
            "transcript_lang": lang,
        },
    }
