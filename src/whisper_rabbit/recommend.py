"""오디오 길이 + 실행 장치 기반으로 Whisper 모델 / 예상 시간 추천.

사용:
    python -m whisper_rabbit.recommend <audio> [--device auto|cpu|cuda]

추천 결과(JSON) 를 stdout 에 출력. 슬래시 커맨드는 받아쓰기 시작 전 한 번
이 모듈을 호출해 ``recommended_model`` 과 ``estimated_minutes`` 를 사용자에게
미리 안내한 뒤 ``python -m whisper_rabbit ...`` 로 transcribe 를 띄울 수 있다.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from ._io_utils import force_utf8_stdio
from .device import resolve

# 모델별 RTF (Real-Time Factor) 추정. 1.0 = 실시간. 작을수록 빠름.
# 실측치(small/cpu/int8 + BatchedInferencePipeline = 0.28x)와
# faster-whisper 공식 벤치마크를 토대로 보수적으로 잡음.
CPU_RTF = {
    "tiny": 0.08,
    "base": 0.14,
    "small": 0.30,
    "medium": 0.65,
    "large-v3": 1.40,
    "distil-large-v3": 0.50,
}
GPU_RTF = {
    "tiny": 0.04,
    "base": 0.06,
    "small": 0.12,
    "medium": 0.22,
    "large-v3": 0.35,
    "distil-large-v3": 0.15,
}


@dataclass(frozen=True)
class Recommendation:
    duration_seconds: float
    device: str
    compute_type: str
    recommended_model: str
    estimated_seconds: float
    reason: str
    notes: list[str]


def probe_duration(audio: Path) -> float:
    """ffprobe 로 오디오/영상 길이(초) 추출."""
    if not shutil.which("ffprobe"):
        raise RuntimeError(
            "ffprobe 가 PATH 에 없습니다. ffmpeg 설치 후 PATH 등록 필요."
        )
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio),
    ]
    out = subprocess.check_output(cmd, encoding="utf-8").strip()
    return float(out)


def recommend(duration_sec: float, device: str) -> Recommendation:
    """오디오 길이·device 기반 모델 추천 + 예상 시간 계산.

    원칙:
      - GPU: 정확도 최우선 → large-v3
      - CPU + <60분: 균형(small) — 한국어 적당, 처리 빠름
      - CPU + 60~180분: small 유지하되 30분+ 처리 시간 안내
      - CPU + ≥180분: base 권장 (처리 시간 단축)
    """
    rtf_map = GPU_RTF if device == "cuda" else CPU_RTF
    minutes = duration_sec / 60
    notes: list[str] = []

    if device == "cuda":
        model = "large-v3"
        reason = "GPU 사용 가능 — 정확도 최우선으로 large-v3 권장"
    elif minutes < 60:
        model = "small"
        reason = "CPU 1시간 미만 — 균형(한국어 정확도 + 속도) 모델 small"
    elif minutes < 180:
        model = "small"
        reason = "CPU 1~3시간 — small 유지하되 처리 시간 30분+ 예상"
        notes.append("긴 회의이므로 백그라운드로 띄우고 진행률을 모니터링하는 것을 권장")
    else:
        model = "base"
        reason = "CPU 3시간 이상 — 정확도 약간 양보, 처리 시간 단축을 위해 base 권장"
        notes.append("정확도가 더 중요하면 small 로 올리고 1시간+ 처리 시간을 감안할 것")

    estimated = duration_sec * rtf_map[model]
    if device == "cpu" and minutes >= 30:
        notes.append("BatchedInferencePipeline 기본 사용(--batch-size 8). RAM 4GB+ 필요.")
    if device == "cpu" and minutes >= 90:
        notes.append("medium 모델은 CPU 에서 RTF ~0.65, 처리 시간 약 1시간+ 예상")

    return Recommendation(
        duration_seconds=duration_sec,
        device=device,
        compute_type="float16" if device == "cuda" else "int8",
        recommended_model=model,
        estimated_seconds=estimated,
        reason=reason,
        notes=notes,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="whisper_rabbit.recommend",
        description="오디오 길이·실행 장치 기반 Whisper 모델 추천.",
    )
    p.add_argument("audio", type=Path)
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    return p


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()
    args = build_parser().parse_args(argv)
    if not args.audio.exists():
        print(f"ERROR: 오디오 없음: {args.audio}", file=sys.stderr)
        return 2

    try:
        duration = probe_duration(args.audio)
    except (RuntimeError, subprocess.CalledProcessError) as e:
        print(f"ERROR: 오디오 길이 확인 실패: {e}", file=sys.stderr)
        return 3

    choice = resolve(device=args.device, compute_type="auto")
    rec = recommend(duration, choice.device)

    payload = {
        "audio": str(args.audio),
        "duration_seconds": round(rec.duration_seconds, 1),
        "duration_minutes": round(rec.duration_seconds / 60, 1),
        "device": rec.device,
        "compute_type": rec.compute_type,
        "recommended_model": rec.recommended_model,
        "estimated_seconds": round(rec.estimated_seconds, 1),
        "estimated_minutes": round(rec.estimated_seconds / 60, 1),
        "reason": rec.reason,
        "notes": rec.notes,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
