from __future__ import annotations

from whisper_rabbit.recommend import (
    CPU_RTF,
    GPU_RTF,
    Recommendation,
    recommend,
)


class TestRecommend:
    def test_gpu_picks_large_v3(self) -> None:
        r = recommend(60 * 30, "cuda")
        assert r.recommended_model == "large-v3"
        assert "정확도 최우선" in r.reason

    def test_cpu_short_picks_small(self) -> None:
        r = recommend(60 * 20, "cpu")
        assert r.recommended_model == "small"

    def test_cpu_medium_meeting_warns(self) -> None:
        r = recommend(60 * 90, "cpu")  # 90분
        assert r.recommended_model == "small"
        assert any("30분+" in n or "30분+" in r.reason for n in [r.reason] + r.notes)

    def test_cpu_long_meeting_picks_base(self) -> None:
        r = recommend(60 * 200, "cpu")  # 200분
        assert r.recommended_model == "base"

    def test_estimated_seconds_matches_rtf(self) -> None:
        duration = 600.0  # 10분
        r = recommend(duration, "cpu")
        expected = duration * CPU_RTF[r.recommended_model]
        assert abs(r.estimated_seconds - expected) < 0.01

    def test_gpu_estimated_uses_gpu_rtf(self) -> None:
        duration = 3600.0
        r = recommend(duration, "cuda")
        expected = duration * GPU_RTF["large-v3"]
        assert abs(r.estimated_seconds - expected) < 0.01

    def test_returns_dataclass(self) -> None:
        r = recommend(300, "cpu")
        assert isinstance(r, Recommendation)
        assert r.duration_seconds == 300
        assert r.compute_type == "int8"


class TestRtfTables:
    def test_all_models_in_both_tables(self) -> None:
        models = {"tiny", "base", "small", "medium", "large-v3", "distil-large-v3"}
        assert set(CPU_RTF) == models
        assert set(GPU_RTF) == models

    def test_gpu_is_faster_than_cpu(self) -> None:
        for m in CPU_RTF:
            assert GPU_RTF[m] < CPU_RTF[m], f"{m}: GPU RTF must be < CPU RTF"

    def test_larger_model_is_slower(self) -> None:
        order = ["tiny", "base", "small", "medium", "large-v3"]
        for i in range(len(order) - 1):
            assert CPU_RTF[order[i]] < CPU_RTF[order[i + 1]]
            assert GPU_RTF[order[i]] < GPU_RTF[order[i + 1]]
