"""실행 장치(CPU/CUDA)와 compute_type을 자동 선택."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Device = Literal["auto", "cpu", "cuda"]
ComputeType = Literal[
    "auto", "int8", "int8_float16", "int8_float32",
    "int16", "float16", "float32", "bfloat16",
]


@dataclass(frozen=True)
class DeviceChoice:
    device: Literal["cpu", "cuda"]
    compute_type: str
    cuda_device_count: int


def _cuda_device_count() -> int:
    try:
        import ctranslate2
        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def resolve(device: Device = "auto", compute_type: ComputeType = "auto") -> DeviceChoice:
    """사용자 입력을 실제 device/compute_type 으로 해석.

    auto/auto 정책:
      - CUDA 있으면 device=cuda, compute_type=float16
      - 없으면 device=cpu, compute_type=int8
    """
    cuda_n = _cuda_device_count()

    if device == "auto":
        actual_device: Literal["cpu", "cuda"] = "cuda" if cuda_n > 0 else "cpu"
    else:
        actual_device = device
        if actual_device == "cuda" and cuda_n == 0:
            raise RuntimeError(
                "CUDA device 가 요청되었지만 사용 가능한 CUDA 디바이스가 없습니다. "
                "ctranslate2 의 CUDA 빌드가 설치되어 있는지, NVIDIA 드라이버가 잡혔는지 확인하세요."
            )

    if compute_type == "auto":
        actual_ct = "float16" if actual_device == "cuda" else "int8"
    else:
        actual_ct = compute_type

    return DeviceChoice(
        device=actual_device,
        compute_type=actual_ct,
        cuda_device_count=cuda_n,
    )
