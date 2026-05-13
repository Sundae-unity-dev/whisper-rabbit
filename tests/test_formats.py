from __future__ import annotations

import json
from pathlib import Path

import pytest

from whisper_rabbit.formats import (
    Segment,
    fmt_clock,
    fmt_srt_time,
    fmt_vtt_time,
    write_json,
    write_srt,
    write_txt,
    write_vtt,
)


@pytest.fixture
def segments() -> list[Segment]:
    return [
        Segment(index=1, start=0.0, end=2.5, text="안녕하세요"),
        Segment(index=2, start=2.5, end=5.123, text="오늘 회의를 시작하겠습니다"),
        Segment(index=3, start=3601.999, end=3603.5, text="끝났습니다"),
    ]


class TestClock:
    @pytest.mark.parametrize(
        "seconds, expected",
        [
            (0.0, "00:00:00"),
            (59.4, "00:00:59"),
            (60.0, "00:01:00"),
            (3661.0, "01:01:01"),
            (-5.0, "00:00:00"),  # 음수 방어
        ],
    )
    def test_fmt_clock(self, seconds: float, expected: str) -> None:
        assert fmt_clock(seconds) == expected


class TestSrtTime:
    def test_basic(self) -> None:
        assert fmt_srt_time(0.0) == "00:00:00,000"
        assert fmt_srt_time(1.5) == "00:00:01,500"
        assert fmt_srt_time(3661.123) == "01:01:01,123"

    def test_rounding_overflow(self) -> None:
        # 0.9995 → 1000ms 반올림되면 정상적으로 다음 초로 올라가야 한다
        assert fmt_srt_time(0.9995) == "00:00:01,000"

    def test_vtt_uses_dot(self) -> None:
        assert fmt_vtt_time(1.5) == "00:00:01.500"


class TestWriters:
    def test_write_txt(self, tmp_path: Path, segments: list[Segment]) -> None:
        out = tmp_path / "t.txt"
        write_txt(segments, out)
        text = out.read_text(encoding="utf-8")
        assert text.startswith("[00:00:00] 안녕하세요\n")
        assert "[01:00:01] 끝났습니다" in text
        assert text.endswith("\n")

    def test_write_txt_empty(self, tmp_path: Path) -> None:
        out = tmp_path / "t.txt"
        write_txt([], out)
        assert out.read_text(encoding="utf-8") == ""

    def test_write_srt(self, tmp_path: Path, segments: list[Segment]) -> None:
        out = tmp_path / "t.srt"
        write_srt(segments, out)
        text = out.read_text(encoding="utf-8")
        # 첫 블록 형태
        assert text.startswith("1\n00:00:00,000 --> 00:00:02,500\n안녕하세요\n")
        # 인덱스가 3까지 존재
        assert "\n3\n" in text

    def test_write_vtt(self, tmp_path: Path, segments: list[Segment]) -> None:
        out = tmp_path / "t.vtt"
        write_vtt(segments, out)
        text = out.read_text(encoding="utf-8")
        assert text.startswith("WEBVTT\n\n")
        assert "00:00:00.000 --> 00:00:02.500" in text

    def test_write_json(self, tmp_path: Path, segments: list[Segment]) -> None:
        out = tmp_path / "t.json"
        meta = {"audio_sha1": "abc", "duration_sec": 3603.5, "model_size": "small"}
        write_json(segments, out, meta)
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["meta"]["audio_sha1"] == "abc"
        assert len(payload["segments"]) == 3
        assert payload["segments"][0]["text"] == "안녕하세요"
