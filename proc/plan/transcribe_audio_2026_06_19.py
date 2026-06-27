#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from google_auth import GoogleClient  # noqa: E402
from gdrive_api import download, get_file  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
DAY = "2026-06-19"
RAW = ROOT / f"data/daily/{DAY}/raw"
UPLOAD_RAW = ROOT / "data/daily/2026-06-22/raw"
FILE_ID = "1p4nmk-0O5JYyEYA4M5hsCNgUvb6HLDQi"
ACCOUNT = "bispro89"
LOCAL_AUDIO = RAW / "audio-260619_124619-ax-kimchaewon-resignation-week.m4a"
LOCAL_VOICE = RAW / "voice-260619_124619-ax-kimchaewon-resignation-week.txt"
OUT_LOG = RAW / "voice-260619_124619-transcribe-result.json"
UPLOAD_META = UPLOAD_RAW / "gdrive-audio-upload-260619_124619.json"
MAX_DIRECT_BYTES = 24 * 1024 * 1024


def load_env() -> None:
    for env_path in [ROOT / ".env", Path.home() / ".env"]:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key, value.strip().strip("\"'"))


def ensure_small_audio(path: Path) -> Path:
    if path.stat().st_size <= MAX_DIRECT_BYTES:
        return path
    converted = path.with_suffix(".transcribe.mp3")
    if converted.exists() and converted.stat().st_size <= MAX_DIRECT_BYTES:
        return converted
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "32k",
            str(converted),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return converted


def transcribe(path: Path) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing")
    upload = ensure_small_audio(path)
    with upload.open("rb") as f:
        response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            data={"model": "whisper-1", "language": "ko"},
            files={"file": (upload.name, f)},
            timeout=300,
        )
    if not response.ok:
        raise RuntimeError(f"transcription failed [{response.status_code}]: {response.text[:500]}")
    return response.json().get("text", "")


def main() -> int:
    load_env()
    RAW.mkdir(parents=True, exist_ok=True)
    UPLOAD_RAW.mkdir(parents=True, exist_ok=True)
    g = GoogleClient(ACCOUNT)
    meta = get_file(g, FILE_ID)
    if not LOCAL_AUDIO.exists():
        download(g, FILE_ID, LOCAL_AUDIO)
    row = {
        "source_account": ACCOUNT,
        "drive_file": meta,
        "content_day": DAY,
        "upload_observed_day": "2026-06-22",
        "audio": str(LOCAL_AUDIO.relative_to(ROOT)),
        "voice": str(LOCAL_VOICE.relative_to(ROOT)),
    }
    try:
        if LOCAL_VOICE.exists() and LOCAL_VOICE.stat().st_size > 0:
            row["status"] = "exists"
        else:
            text = transcribe(LOCAL_AUDIO)
            LOCAL_VOICE.write_text(text, encoding="utf-8")
            row["status"] = "transcribed"
            row["chars"] = len(text)
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = repr(exc)
    OUT_LOG.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    UPLOAD_META.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0 if row.get("status") in {"exists", "transcribed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
