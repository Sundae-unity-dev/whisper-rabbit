from __future__ import annotations

import pytest

from whisper_rabbit import device as dev_mod
from whisper_rabbit.device import resolve


def test_auto_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev_mod, "_cuda_device_count", lambda: 0)
    c = resolve("auto", "auto")
    assert c.device == "cpu"
    assert c.compute_type == "int8"
    assert c.cuda_device_count == 0


def test_auto_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev_mod, "_cuda_device_count", lambda: 1)
    c = resolve("auto", "auto")
    assert c.device == "cuda"
    assert c.compute_type == "float16"


def test_cuda_explicit_without_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev_mod, "_cuda_device_count", lambda: 0)
    with pytest.raises(RuntimeError, match="CUDA"):
        resolve("cuda", "auto")


def test_explicit_compute_type_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev_mod, "_cuda_device_count", lambda: 0)
    c = resolve("cpu", "int8_float16")
    assert c.device == "cpu"
    assert c.compute_type == "int8_float16"
