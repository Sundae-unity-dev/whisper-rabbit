"""faster-whisper로 오디오를 받아쓰는 핵심 로직."""
from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .device import DeviceChoice
from .formats import Format, Segment, WRITERS, write_json

log = logging.getLogger("whisper_rabbit.transcribe")

# 모델별 대략적 다운로드 크기 (사용자 안내용)
MODEL_DOWNLOAD_SIZE = {
    "tiny": "~75 MB",
    "base": "~150 MB",
    "small": "~500 MB",
    "medium": "~1.5 GB",
    "large-v1": "~3.0 GB",
    "large-v2": "~3.0 GB",
    "large-v3": "~3.0 GB",
    "distil-large-v3": "~1.5 GB",
}


def _ensure_hf_env() -> None:
    """HuggingFace 의 Windows 다운로드 hang 회피용 환경변수를 보장한다.

    xet 백엔드(LFS 후속) 가 Windows 에서 첫 핸드셰이크 직후 멈추는 사례가
    재현되므로 모델 로딩 직전에 무조건 우회 옵션을 켜둔다. 이미 사용자가
    명시적으로 다른 값을 지정한 경우는 그대로 둔다 (setdefault).
    """
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def _is_model_cached(model_size: str) -> bool:
    """faster-whisper-<model_size> 가 HF 캐시에 이미 받아져 있는지 확인."""
    try:
        from huggingface_hub import scan_cache_dir
        repo_id = f"Systran/faster-whisper-{model_size}"
        info = scan_cache_dir()
        for r in info.repos:
            if r.repo_id == repo_id and r.size_on_disk > 1_000_000:  # 1MB 이상
                return True
    except Exception:
        pass
    return False


@dataclass
class TranscribeOptions:
    model_size: str = "small"
    language: str | None = "ko"     # None → 자동 감지
    beam_size: int = 5
    vad_filter: bool = True
    vad_min_silence_ms: int = 500
    condition_on_previous_text: bool = False  # 긴 회의 hallucination 방지
    batch_size: int = 8  # BatchedInferencePipeline 사용 시
    use_batched: bool = True


@dataclass
class TranscribeResult:
    audio_path: Path
    audio_sha1: str
    duration_sec: float
    detected_language: str
    language_probability: float
    elapsed_sec: float
    segments: list[Segment] = field(default_factory=list)
    model_size: str = ""
    device: str = ""
    compute_type: str = ""
    batched: bool = False

    @property
    def realtime_factor(self) -> float:
        """오디오 길이 대비 처리 시간. 1.0 미만이면 실시간보다 빠름."""
        return self.elapsed_sec / self.duration_sec if self.duration_sec > 0 else 0.0

    def meta_dict(self) -> dict:
        return {
            "audio_path": str(self.audio_path),
            "audio_sha1": self.audio_sha1,
            "duration_sec": self.duration_sec,
            "detected_language": self.detected_language,
            "language_probability": self.language_probability,
            "elapsed_sec": self.elapsed_sec,
            "realtime_factor": self.realtime_factor,
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "batched": self.batched,
        }


def sha1_of_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _load_model(model_size: str, choice: DeviceChoice):
    _ensure_hf_env()

    if not _is_model_cached(model_size):
        size = MODEL_DOWNLOAD_SIZE.get(model_size, "용량 미상")
        log.warning(
            "Whisper '%s' 모델이 캐시에 없어 HuggingFace 에서 다운로드를 시작합니다 "
            "(%s, 네트워크 상태에 따라 1~5분 소요). 이후 호출부터는 캐시되어 즉시 시작됩니다.",
            model_size, size,
        )
        log.warning(
            "다운로드 진행률은 huggingface_hub 가 stderr 로 출력합니다. "
            "5분 이상 멈춰 있다면 Ctrl+C 후 캐시 디렉토리를 정리하고 재시도하세요: "
            "Remove-Item -Recurse -Force \"$env:USERPROFILE\\.cache\\huggingface\\hub\\models--Systran--faster-whisper-%s\"",
            model_size,
        )

    from faster_whisper import WhisperModel
    log.info("WhisperModel(%s, device=%s, compute_type=%s) 로딩",
             model_size, choice.device, choice.compute_type)
    t0 = time.time()
    model = WhisperModel(model_size, device=choice.device, compute_type=choice.compute_type)
    log.info("모델 로드 완료 (%.1fs)", time.time() - t0)
    return model


def prefetch_model(model_size: str, choice: DeviceChoice | None = None) -> None:
    """모델만 미리 받아두고 종료. install.ps1 등에서 호출.

    transcribe 까지는 안 하므로 캐시만 채워두는 용도.
    """
    from .device import resolve
    if choice is None:
        choice = resolve("auto", "auto")
    log.info("Whisper '%s' 모델 사전 다운로드", model_size)
    _load_model(model_size, choice)
    log.info("사전 다운로드 완료")


def _iter_segments(raw_iter: Iterable) -> Iterator[Segment]:
    for i, seg in enumerate(raw_iter, start=1):
        text = (seg.text or "").strip()
        if not text:
            continue
        yield Segment(index=i, start=float(seg.start), end=float(seg.end), text=text)


def run(
    audio: Path,
    options: TranscribeOptions,
    choice: DeviceChoice,
    progress_cb=None,
) -> TranscribeResult:
    """오디오를 transcribe 하고 결과를 반환. 출력 파일은 만들지 않는다."""
    if not audio.exists():
        raise FileNotFoundError(f"audio not found: {audio}")

    model = _load_model(options.model_size, choice)

    transcribe_fn = model.transcribe
    batched = False
    if options.use_batched:
        try:
            from faster_whisper import BatchedInferencePipeline
            batched_model = BatchedInferencePipeline(model=model)
            transcribe_fn = batched_model.transcribe
            batched = True
            log.info("BatchedInferencePipeline 사용 (batch_size=%d)", options.batch_size)
        except ImportError:
            log.info("BatchedInferencePipeline 미지원 — 일반 transcribe 사용")

    log.info("받아쓰기 시작: %s", audio)
    t0 = time.time()
    kwargs = dict(
        language=options.language,
        beam_size=options.beam_size,
        vad_filter=options.vad_filter,
        vad_parameters=dict(min_silence_duration_ms=options.vad_min_silence_ms),
        condition_on_previous_text=options.condition_on_previous_text,
    )
    if batched:
        kwargs["batch_size"] = options.batch_size

    raw_segments, info = transcribe_fn(str(audio), **kwargs)

    segments: list[Segment] = []
    for seg in _iter_segments(raw_segments):
        segments.append(seg)
        if progress_cb is not None:
            progress_cb(seg.end, info.duration)

    elapsed = time.time() - t0
    log.info(
        "받아쓰기 완료 — %d 세그먼트, 오디오 %.1fs, 처리 %.1fs (RTF %.2fx)",
        len(segments), info.duration, elapsed,
        elapsed / info.duration if info.duration > 0 else 0.0,
    )

    return TranscribeResult(
        audio_path=audio,
        audio_sha1=sha1_of_file(audio),
        duration_sec=float(info.duration),
        detected_language=info.language,
        language_probability=float(info.language_probability),
        elapsed_sec=elapsed,
        segments=segments,
        model_size=options.model_size,
        device=choice.device,
        compute_type=choice.compute_type,
        batched=batched,
    )


def write_outputs(result: TranscribeResult, base_path: Path, formats: Iterable[Format]) -> dict[Format, Path]:
    """포맷별로 파일을 쓰고 {포맷: 경로} 를 반환."""
    outputs: dict[Format, Path] = {}
    for fmt in formats:
        out = base_path.with_suffix(base_path.suffix + f".{fmt}")
        if fmt == "json":
            write_json(result.segments, out, result.meta_dict())
        else:
            WRITERS[fmt](result.segments, out)
        outputs[fmt] = out
    return outputs
