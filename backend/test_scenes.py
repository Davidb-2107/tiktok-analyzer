import sys
import types
from pathlib import Path

import pytest

import scenes


def test_keyframe_time_is_scene_midpoint():
    assert scenes.keyframe_time({"start": 1.0, "end": 5.0}) == pytest.approx(3.0)


def test_keyframe_selection_keeps_all_small_jobs():
    assert scenes.select_keyframe_indices(3, max_keyframes=120) == {0, 1, 2}


def test_keyframe_selection_is_even_when_scene_count_exceeds_cap():
    selected = scenes.select_keyframe_indices(240, max_keyframes=120)
    assert len(selected) == 120
    assert min(selected) == 0
    assert max(selected) == 239


def test_keyframe_selection_handles_single_keyframe_cap():
    assert scenes.select_keyframe_indices(5, max_keyframes=1) == {2}


def test_keyframe_time_handles_short_scene():
    assert scenes.keyframe_time({"start": 2.0, "end": 2.1}) == pytest.approx(2.05)


class FakeFrameTimecode:
    def __init__(self, seconds):
        self.seconds = seconds

    def get_seconds(self):
        return self.seconds


def test_detect_scenes_forwards_options_and_normalizes(monkeypatch):
    captured = {}

    class FakeContentDetector:
        def __init__(self, **kwargs):
            captured["detector"] = kwargs

    def fake_detect(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return [
            (FakeFrameTimecode(1.234), FakeFrameTimecode(4.567)),
            (FakeFrameTimecode(4.567), FakeFrameTimecode(6.0)),
        ]

    fake_scenedetect = types.SimpleNamespace(
        ContentDetector=FakeContentDetector,
        detect=fake_detect,
    )
    monkeypatch.setitem(sys.modules, "scenedetect", fake_scenedetect)

    result = scenes.detect_scenes(
        Path("video.mp4"),
        start_s=1.5,
        end_s=8.25,
        threshold=31.0,
        min_scene_len=20,
    )

    assert captured["detector"] == {"threshold": 31.0, "min_scene_len": 20}
    assert captured["args"][0] == "video.mp4"
    assert captured["args"][1].__class__.__name__ == "FakeContentDetector"
    assert captured["kwargs"] == {
        "show_progress": False,
        "start_time": 1.5,
        "end_time": 8.25,
        "start_in_scene": True,
    }
    assert result == [
        {"index": 0, "start": 1.23, "end": 4.57, "duration": 3.34},
        {"index": 1, "start": 4.57, "end": 6.0, "duration": 1.43},
    ]


def test_detect_scenes_drops_null_and_inverted_scenes(monkeypatch):
    class FakeContentDetector:
        def __init__(self, **kwargs):
            pass

    fake_scenedetect = types.SimpleNamespace(
        ContentDetector=FakeContentDetector,
        detect=lambda *args, **kwargs: [
            (FakeFrameTimecode(2.0), FakeFrameTimecode(2.0)),
            (FakeFrameTimecode(5.0), FakeFrameTimecode(4.0)),
            (FakeFrameTimecode(7.0), FakeFrameTimecode(8.0)),
        ],
    )
    monkeypatch.setitem(sys.modules, "scenedetect", fake_scenedetect)

    assert scenes.detect_scenes(Path("video.mp4")) == [
        {"index": 2, "start": 7.0, "end": 8.0, "duration": 1.0},
    ]
