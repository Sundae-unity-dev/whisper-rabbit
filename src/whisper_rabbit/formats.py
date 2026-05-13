"""transcript 출력 포맷: txt / srt / vtt / json."""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

Format = Literal["txt", "srt", "vtt", "json"]
ALL_FORMATS: tuple[Format, ...] = ("txt", "srt", "vtt", "json")


@dataclass(frozen=True)
class Segment:
    index: int
    start: float
    end: float
    text: str


def fmt_clock(seconds: float) -> str:
    """[HH:MM:SS] 형태."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:  # rounding overflow
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_vtt_time(seconds: float) -> str:
    return fmt_srt_time(seconds).replace(",", ".")


def write_txt(segments: Iterable[Segment], out: Path) -> None:
    lines = [f"[{fmt_clock(s.start)}] {s.text}" for s in segments]
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_srt(segments: Iterable[Segment], out: Path) -> None:
    blocks: list[str] = []
    for i, s in enumerate(segments, start=1):
        blocks.append(
            f"{i}\n{fmt_srt_time(s.start)} --> {fmt_srt_time(s.end)}\n{s.text}\n"
        )
    out.write_text("\n".join(blocks), encoding="utf-8")


def write_vtt(segments: Iterable[Segment], out: Path) -> None:
    parts = ["WEBVTT", ""]
    for s in segments:
        parts.append(f"{fmt_vtt_time(s.start)} --> {fmt_vtt_time(s.end)}")
        parts.append(s.text)
        parts.append("")
    out.write_text("\n".join(parts), encoding="utf-8")


def write_json(segments: Iterable[Segment], out: Path, meta: dict) -> None:
    payload = {"meta": meta, "segments": [asdict(s) for s in segments]}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


WRITERS = {
    "txt": write_txt,
    "srt": write_srt,
    "vtt": write_vtt,
}
