# 2026-06-15 Linux Qwen3-ASR CUDA

## 목표
Mac의 MLX 기반 `mlx-qwen3-asr` 파이프라인을 Linux/NVIDIA 환경에 맞게 Qwen3-ASR CUDA backend로 구성한다.

## 판단
- 현재 머신: Linux x86_64, NVIDIA RTX 3060 12GB, CUDA driver 정상.
- Mac 전사 파이프라인은 Apple Silicon 전용 MLX이므로 그대로 실행하지 않는다.
- 공식 Qwen3-ASR는 `qwen-asr` Python package를 통해 transformers/vLLM backend를 제공한다.
- RTX 3060 12GB에서는 우선 transformers backend + `max_inference_batch_size=1`로 안전하게 시작한다.

## 작업 항목
- [x] 격리 venv 생성
- [x] PyTorch CUDA 설치
- [x] `qwen-asr` 설치
- [x] CUDA smoke test
- [x] 기존 voice pipeline과 호환되는 Linux transcribe wrapper 작성
- [x] 샘플 오디오 1건 전사
- [x] OS별 자동 backend dispatcher 적용
- [x] 최근 녹음 5건 임시 전사로 긴 파일 동작 검증

## 결과
- venv: `/Users/gq/works/lecture/vibe-coding-book/vibe-coding-book-writing-01/.venv-linux-asr`
- PyTorch: `2.11.0+cu128`
- GPU: `NVIDIA GeForce RTX 3060`, CUDA available.
- Qwen package: `qwen-asr==0.0.6`
- 모델 캐시: `Qwen/Qwen3-ASR-1.7B`
- 공통 entrypoint: `/Users/gq/works/lecture/vibe-coding-book/vibe-coding-book-writing-01/src/02_transcribe.py`
- Linux wrapper: `/Users/gq/works/lecture/vibe-coding-book/vibe-coding-book-writing-01/src/02_transcribe_cuda.py`
- Mac MLX wrapper: `/Users/gq/works/lecture/vibe-coding-book/vibe-coding-book-writing-01/src/02_transcribe_mlx.py`
- 샘플: `250515_183840_R415.wav`
  - dispatcher: Linux -> CUDA backend
  - model: `Qwen/Qwen3-ASR-1.7B`
  - cached model load: 5.4s
  - transcription: 1.18s
  - output: `input/voice-recordings/20-transcribed/250515_183840_R415.txt`
- 최근 5건 임시 전사:
  - 출력: `/tmp/qwen3-asr-recent5-5m/out`
  - 청크: `/tmp/qwen3-asr-recent5-5m/splits`
  - 결과: `done=5 errors=0`
  - 30분/20분 단일 또는 30분 청크는 RTX 3060 12GB에서 OOM 발생.
  - 5분 청크 + `max_new_tokens=1536`에서는 52분/29분/20분 파일 모두 성공.

## 실행 예
```bash
cd /Users/gq/works/lecture/vibe-coding-book/vibe-coding-book-writing-01
python3 -u src/02_transcribe.py \
  --dtype float16 \
  --batch-size 1 \
  --chunk-sec 300
```

특정 파일만:
```bash
python3 -u src/02_transcribe.py \
  --glob '260505_182327_ax.m4a' \
  --dtype float16 \
  --batch-size 1 \
  --chunk-sec 300
```

## 메모
- `src/02_transcribe.py`는 OS별 dispatcher다.
- macOS/Darwin에서는 기존 MLX 파이프라인 `src/02_transcribe_mlx.py`를 실행한다.
- Linux에서는 CUDA/PyTorch 파이프라인 `src/02_transcribe_cuda.py`를 실행한다.
- `VOICE_TRANSCRIBE_BACKEND=mlx|cuda`로 backend를 강제할 수 있다.
- `VOICE_TRANSCRIBE_PYTHON=/path/to/python`으로 실행 Python을 강제할 수 있다.
- RTX 3060 12GB에서는 `float16`, `batch-size 1`, `chunk-sec 300`, `max-new-tokens 1536`이 안전한 기본값이다.
- 임시 테스트는 `--output-dir /tmp/.../out --splits-dir /tmp/.../splits`로 기존 전사본을 덮지 않고 실행할 수 있다.

## 주의
- MLX/Apple Silicon 패키지는 설치하지 않는다.
- 기존 Mac 스크립트 내용은 `src/02_transcribe_mlx.py`로 보존한다.
- 실패 시 OpenAI API 전사로 fallback하지 않고, 로컬 CUDA 문제로 따로 기록한다.
