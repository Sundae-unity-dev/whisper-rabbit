"""CLI 진입점 공통 I/O 유틸."""
from __future__ import annotations

import sys


def force_utf8_stdio() -> None:
    """Windows cp949 콘솔에서 한글·emdash 출력이 깨지지 않도록 stdio 를 utf-8 로 재설정.

    Python 3.7+ 의 ``sys.stdout.reconfigure`` 사용. 인코딩이 이미 utf-8 이면
    동작에 변화 없음. 다른 플랫폼에서도 안전.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            # 일부 환경(파이프, 캡쳐 등)에서는 reconfigure 가 없거나 실패할 수 있음
            pass
