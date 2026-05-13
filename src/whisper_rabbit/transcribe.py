"""faster-whisper로 오디오를 받아쓰는 핵심 로직."""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .device import DeviceChoice
from .formats import Format, Segment, WRITERS, write_json

log = logging.getLogger("whisper_rabbit.transcribe")


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
    from faster_whisper import WhisperModel
    log.info("WhisperModel(%s, device=%s, compute_type=%s) 로딩",
             model_size, choice.device, choice.compute_type)
    t0 = time.time()
    model = WhisperModel(model_size, device=choice.device, compute_type=choice.compute_type)
    log.info("모델 로드 완료 (%.1fs)", time.time() - t0)
    return model


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
