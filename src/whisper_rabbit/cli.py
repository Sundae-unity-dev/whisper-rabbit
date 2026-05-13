"""커맨드라인 진입점."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .device import resolve
from .formats import ALL_FORMATS, Format
from .transcribe import TranscribeOptions, run, write_outputs

MODEL_CHOICES = ("tiny", "base", "small", "medium",
                 "large-v1", "large-v2", "large-v3", "distil-large-v3")


def _parse_formats(value: str) -> list[Format]:
    items = [v.strip().lower() for v in value.split(",") if v.strip()]
    invalid = [v for v in items if v not in ALL_FORMATS]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"unknown format(s): {invalid}. choices: {ALL_FORMATS}"
        )
    return items  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="whisper-rabbit",
        description="faster-whisper로 회의 녹음을 받아쓰기.",
    )
    p.add_argument("audio", type=Path, help="입력 오디오 파일")
    p.add_argument("--model", default="small", choices=MODEL_CHOICES,
                   help="Whisper 모델 (기본 small). 한국어 정확도 우선이면 medium 권장.")
    p.add_argument("--lang", default="ko",
                   help="언어 코드 (기본 ko). 자동 감지하려면 'auto'.")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                   help="실행 장치. auto는 CUDA가 있으면 cuda, 없으면 cpu.")
    p.add_argument("--compute-type", default="auto",
                   help="ctranslate2 compute_type. auto는 cuda→float16, cpu→int8.")
    p.add_argument("--batch-size", type=int, default=8,
                   help="BatchedInferencePipeline batch_size (기본 8).")
    p.add_argument("--no-batched", action="store_true",
                   help="BatchedInferencePipeline 비활성화.")
    p.add_argument("--beam-size", type=int, default=5)
    p.add_argument("--no-vad", action="store_true", help="VAD 필터 비활성화.")
    p.add_argument("--vad-silence-ms", type=int, default=500,
                   help="VAD 최소 무음 길이(ms) (기본 500).")
    p.add_argument("--condition-on-prev", action="store_true",
                   help="이전 텍스트 조건화 (긴 회의에서는 비활성 권장).")
    p.add_argument("--formats", type=_parse_formats, default=["txt", "json"],
                   help="콤마 구분 출력 포맷: txt,srt,vtt,json (기본 'txt,json')")
    p.add_argument("--out-base", type=Path, default=None,
                   help="출력 파일 기준 경로. 미지정 시 <audio> 자체.")
    p.add_argument("-v", "--verbose", action="count", default=0,
                   help="-v: INFO, -vv: DEBUG")
    p.add_argument("-q", "--quiet", action="store_true")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def configure_logging(verbosity: int, quiet: bool) -> None:
    if quiet:
        level = logging.WARNING
    elif verbosity >= 2:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname).1s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose, args.quiet)
    log = logging.getLogger("whisper_rabbit.cli")

    audio: Path = args.audio
    if not audio.exists():
        print(f"ERROR: audio not found: {audio}", file=sys.stderr)
        return 2

    try:
        choice = resolve(device=args.device, compute_type=args.compute_type)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    options = TranscribeOptions(
        model_size=args.model,
        language=None if args.lang == "auto" else args.lang,
        beam_size=args.beam_size,
        vad_filter=not args.no_vad,
        vad_min_silence_ms=args.vad_silence_ms,
        condition_on_previous_text=args.condition_on_prev,
        batch_size=args.batch_size,
        use_batched=not args.no_batched,
    )

    log.info("device=%s compute_type=%s cuda_devices=%d",
             choice.device, choice.compute_type, choice.cuda_device_count)

    progress = _tqdm_progress() if not args.quiet else None
    try:
        result = run(audio, options, choice, progress_cb=progress.update if progress else None)
    finally:
        if progress is not None:
            progress.close()

    out_base: Path = args.out_base or audio
    outputs = write_outputs(result, out_base, args.formats)

    summary = {
        **result.meta_dict(),
        "segments_count": len(result.segments),
        "outputs": {k: str(v) for k, v in outputs.items()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _tqdm_progress():
    try:
        from tqdm import tqdm
    except ImportError:
        return None

    class _Bar:
        def __init__(self) -> None:
            self.bar: "tqdm | None" = None

        def update(self, current: float, total: float) -> None:
            if self.bar is None:
                self.bar = tqdm(total=round(total), unit="s",
                                desc="transcribing", smoothing=0.3)
            delta = round(current) - self.bar.n
            if delta > 0:
                self.bar.update(delta)

        def close(self) -> None:
            if self.bar is not None:
                if self.bar.total and self.bar.n < self.bar.total:
                    self.bar.update(self.bar.total - self.bar.n)
                self.bar.close()

    return _Bar()


if __name__ == "__main__":
    sys.exit(main())
