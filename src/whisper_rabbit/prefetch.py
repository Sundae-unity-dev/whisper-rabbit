"""Whisper 모델 사전 다운로드 진입점.

사용: python -m whisper_rabbit.prefetch [tiny|base|small|medium|large-v3|...]

install.ps1 이 호출해 첫 사용 시 다운로드 지연·hang 을 미리 흡수한다.
"""
from __future__ import annotations

import argparse
import sys

from ._io_utils import force_utf8_stdio
from .cli import MODEL_CHOICES, configure_logging
from .device import resolve
from .transcribe import prefetch_model


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()
    p = argparse.ArgumentParser(
        prog="whisper_rabbit.prefetch",
        description="Whisper 모델 사전 다운로드 (캐시만 채우고 종료).",
    )
    p.add_argument("model", nargs="?", default="small", choices=MODEL_CHOICES,
                   help="다운로드할 모델 (기본 small)")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--compute-type", default="auto")
    p.add_argument("-v", "--verbose", action="count", default=0)
    args = p.parse_args(argv)

    configure_logging(args.verbose, quiet=False)
    choice = resolve(device=args.device, compute_type=args.compute_type)
    prefetch_model(args.model, choice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
