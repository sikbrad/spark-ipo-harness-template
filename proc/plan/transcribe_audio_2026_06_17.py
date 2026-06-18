#!/usr/bin/env python3
"""Transcribe 2026-06-17 downloaded Drive audio into daily raw voice txt files."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/daily/2026-06-17/raw"
OUT_LOG = RAW / "voice-transcribe-result.json"
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
    converted = path.with_suffix(".transcribe.mp3")
    if converted.exists() and converted.stat().st_size <= MAX_DIRECT_BYTES:
        return converted
    if path.stat().st_size <= MAX_DIRECT_BYTES:
        return path
    out = converted
    if out.exists() and out.stat().st_size <= MAX_DIRECT_BYTES:
        return out
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
            str(out),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return out


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
    items = [
        (RAW / "audio-260617_124035.m4a", RAW / "voice-260617_124035.txt"),
        (RAW / "audio-260617_134029.m4a", RAW / "voice-260617_134029.txt"),
    ]
    results = []
    for audio, voice in items:
        row = {"audio": str(audio.relative_to(ROOT)), "voice": str(voice.relative_to(ROOT))}
        try:
            if not audio.exists():
                raise FileNotFoundError(audio)
            if voice.exists() and voice.stat().st_size > 0:
                row["status"] = "exists"
            else:
                text = transcribe(audio)
                voice.write_text(text, encoding="utf-8")
                row["status"] = "transcribed"
                row["chars"] = len(text)
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = repr(exc)
        results.append(row)
    OUT_LOG.write_text(json.dumps({"items": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"items": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
