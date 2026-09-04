"""Hermetic contract tests for additive scene detection in analysis jobs."""

import asyncio
import inspect
import os
import threading
from pathlib import Path

import pytest
import starlette.routing

os.environ.setdefault("R2_ENDPOINT", "https://test.invalid")
for _name in ("R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
    os.environ.setdefault(_name, "test")
pytest.importorskip("faster_whisper")
pytest.importorskip("yt_dlp")

# The bundled Windows runtime can pair an older FastAPI with a newer Starlette.
# Keep this compatibility shim test-only; production uses its pinned image.
_import_patches = pytest.MonkeyPatch()

if "on_startup" not in inspect.signature(starlette.routing.Router.__init__).parameters:
    _router_init = starlette.routing.Router.__init__

    def _router_init_compat(self, *args, **kwargs):
        kwargs.pop("on_startup", None)
        kwargs.pop("on_shutdown", None)
        kwargs.pop("lifespan", None)
        return _router_init(self, *args, **kwargs)

    _import_patches.setattr(starlette.routing.Router, "__init__", _router_init_compat)

    def _add_event_handler_compat(self, event_type, func):
        handlers = getattr(self, "_compat_event_handlers", [])
        handlers.append((event_type, func))
        self._compat_event_handlers = handlers

    _import_patches.setattr(starlette.routing.Router, "add_event_handler", _add_event_handler_compat, raising=False)

# main.py keeps /app/temp as its container default. Suppress creation of that
# unavailable Windows root during import; every test swaps TEMP_DIR to tmp_path.
_path_mkdir = Path.mkdir


def _path_mkdir_compat(self, *args, **kwargs):
    if str(self).replace("\\", "/") == "/app/temp":
        return None
    return _path_mkdir(self, *args, **kwargs)


_import_patches.setattr(Path, "mkdir", _path_mkdir_compat)

try:
    import main  # noqa: E402
finally:
    _import_patches.undo()

JOB_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
def job_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "TEMP_DIR", tmp_path)
    return tmp_path


def test_job_response_exposes_scenes_and_keeps_historical_jobs_compatible():
    response = main.JobResponse(
        job_id="x",
        status="done",
        scenes=[{"index": 0, "start": 0.0, "end": 1.0, "duration": 1.0, "keyframe": None}],
    )

    assert response.scenes[0]["duration"] == 1.0
    assert main.JobResponse(job_id="legacy", status="done").scenes is None


def test_scene_detection_is_disabled_without_calling_detector(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SCENE_DETECTION_ENABLED", False)
    monkeypatch.setattr(
        main.scene_detection,
        "detect_scenes",
        lambda *args, **kwargs: pytest.fail("detector must stay off by default"),
    )

    assert main._detect_scenes_best_effort(tmp_path / "video.mp4") == []


def test_scene_detection_failure_returns_empty_without_raising(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SCENE_DETECTION_ENABLED", True)

    def boom(*args, **kwargs):
        raise RuntimeError("unsupported codec")

    monkeypatch.setattr(main.scene_detection, "detect_scenes", boom)

    assert main._detect_scenes_best_effort(tmp_path / "video.mp4") == []


def test_scene_detection_forwards_window_without_rebasing_timestamps(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SCENE_DETECTION_ENABLED", True)
    monkeypatch.setattr(main, "SCENE_DETECT_THRESHOLD", 31.0)
    monkeypatch.setattr(main, "SCENE_MIN_LEN_FRAMES", 20)
    captured = {}

    def detect(video_path, **kwargs):
        captured["video_path"] = video_path
        captured.update(kwargs)
        return [{"index": 0, "start": 12.0, "end": 15.0, "duration": 3.0}]

    monkeypatch.setattr(main.scene_detection, "detect_scenes", detect)

    scenes = main._detect_scenes_best_effort(tmp_path / "video.mp4", start_s=10.0, end_s=20.0)

    assert captured == {
        "video_path": tmp_path / "video.mp4",
        "start_s": 10.0,
        "end_s": 20.0,
        "threshold": 31.0,
        "min_scene_len": 20,
    }
    assert scenes[0]["start"] == 12.0
    assert scenes[0]["end"] == 15.0


def test_scene_keyframe_extraction_caps_selected_images_and_keeps_all_intervals(monkeypatch, job_dir):
    video_path = job_dir / "video.mp4"
    video_path.write_bytes(b"video")
    scenes = [
        {"index": index, "start": float(index), "end": float(index + 1), "duration": 1.0}
        for index in range(121)
    ]

    def fake_run(cmd, **kwargs):
        Path(cmd[-2]).write_bytes(b"jpeg")
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    result = main._extract_scene_keyframes(video_path, JOB_ID, scenes, max_keyframes=120)

    assert len(result) == 121
    assert sum(scene["keyframe"] is not None for scene in result) == 120
    assert {scene["index"] for scene in result if scene["keyframe"] is None} == {60}
    assert (job_dir / JOB_ID / "scene_frames" / "scene_000.jpg").exists()


def test_scene_keyframe_env_cap_is_strictly_120(monkeypatch, job_dir):
    monkeypatch.setenv("SCENE_MAX_KEYFRAMES", "999")
    effective_cap = main._scene_max_keyframes_from_env()
    assert effective_cap == 120

    video_path = job_dir / "video.mp4"
    video_path.write_bytes(b"video")
    scenes = [
        {"index": index, "start": float(index), "end": float(index + 1), "duration": 1.0}
        for index in range(240)
    ]

    def fake_run(cmd, **kwargs):
        Path(cmd[-2]).write_bytes(b"jpeg")
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(main.subprocess, "run", fake_run)
    result = main._extract_scene_keyframes(video_path, JOB_ID, scenes, max_keyframes=effective_cap)

    assert sum(scene["keyframe"] is not None for scene in result) == 120


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [("0", 0), ("-2", 0), ("not-an-int", 120)],
)
def test_scene_keyframe_env_values_remain_safe(monkeypatch, raw_value, expected):
    monkeypatch.setenv("SCENE_MAX_KEYFRAMES", raw_value)

    assert main._scene_max_keyframes_from_env() == expected


def test_scene_keyframe_extraction_retries_invalid_color_then_keeps_following_scene(monkeypatch, job_dir):
    video_path = job_dir / "video.mp4"
    video_path.write_bytes(b"video")
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        if len(commands) == 1:
            return type("Result", (), {"returncode": 1, "stderr": "Invalid color space"})()
        if len(commands) == 2:
            return type("Result", (), {"returncode": 1, "stderr": "still broken"})()
        Path(cmd[-2]).write_bytes(b"jpeg")
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(main.subprocess, "run", fake_run)
    scenes = [
        {"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0},
        {"index": 1, "start": 2.0, "end": 4.0, "duration": 2.0},
    ]

    result = main._extract_scene_keyframes(video_path, JOB_ID, scenes, max_keyframes=120)

    assert [scene["keyframe"] for scene in result] == [None, "scene_001.jpg"]
    assert any("hevc_metadata=colour_primaries=1" in arg for arg in commands[1])


def test_scene_keyframe_setup_failure_keeps_detected_intervals(monkeypatch, job_dir):
    scenes = [
        {"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0},
        {"index": 1, "start": 2.0, "end": 4.0, "duration": 2.0},
    ]

    def boom(_job_id):
        raise OSError("read-only temp directory")

    monkeypatch.setattr(main, "_scene_frames_dir", boom)

    assert main._extract_scene_keyframes(job_dir / "video.mp4", JOB_ID, scenes, 120) == [
        {**scenes[0], "keyframe": None},
        {**scenes[1], "keyframe": None},
    ]


def test_scene_keyframe_selector_failure_keeps_detected_intervals(monkeypatch, job_dir):
    scenes = [{"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0}]

    def boom(*args):
        raise RuntimeError("selector failure")

    monkeypatch.setattr(main.scene_detection, "select_keyframe_indices", boom)

    assert main._extract_scene_keyframes(job_dir / "video.mp4", JOB_ID, scenes, 120) == [
        {**scenes[0], "keyframe": None}
    ]


def test_scene_keyframe_timestamp_failure_keeps_detected_intervals(monkeypatch, job_dir):
    scenes = [{"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0}]
    monkeypatch.setattr(main.scene_detection, "keyframe_time", lambda scene: (_ for _ in ()).throw(ValueError("bad time")))

    assert main._extract_scene_keyframes(job_dir / "video.mp4", JOB_ID, scenes, 120) == [
        {**scenes[0], "keyframe": None}
    ]


def test_scene_keyframe_extraction_ignores_malformed_detector_entries(monkeypatch, job_dir):
    valid = {"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0}
    monkeypatch.setattr(main.scene_detection, "select_keyframe_indices", lambda *args: set())

    assert main._extract_scene_keyframes(job_dir / "video.mp4", JOB_ID, [valid, None, {"start": "bad"}], 120) == [
        {**valid, "keyframe": None}
    ]


def test_resolve_frames_presigns_scene_keys_only_after_job_completion(monkeypatch):
    monkeypatch.setattr(main, "_presign_key", lambda key: f"signed:{key}")
    local = {"status": "frames_ready", "frames": ["frame_001.jpg"], "scenes": [{"keyframe": "scene_000.jpg"}]}
    done = {
        "status": "done",
        "frames": [f"{JOB_ID}/frame_001.jpg"],
        "scenes": [{"keyframe": f"{JOB_ID}/scenes/scene_000.jpg"}, {"keyframe": None}],
    }

    assert main._resolve_frames(JOB_ID, local) == local
    assert main._resolve_frames(JOB_ID, done) == {
        "status": "done",
        "frames": [f"signed:{JOB_ID}/frame_001.jpg"],
        "scenes": [{"keyframe": f"signed:{JOB_ID}/scenes/scene_000.jpg"}, {"keyframe": None}],
    }


def test_local_scene_keyframe_route_uses_scene_directory_and_blocks_traversal(job_dir):
    frames_dir = job_dir / JOB_ID / "frames"
    frames_dir.mkdir(parents=True)
    regular_path = frames_dir / "frame_001.jpg"
    regular_path.write_bytes(b"jpeg")
    scene_dir = job_dir / JOB_ID / "scene_frames"
    scene_dir.mkdir(parents=True)
    scene_path = scene_dir / "scene_000.jpg"
    scene_path.write_bytes(b"jpeg")
    (job_dir / JOB_ID / "audio.mp3").write_bytes(b"audio")

    regular_response = asyncio.run(main.get_local_frame(JOB_ID, "frame_001.jpg"))
    response = asyncio.run(main.get_local_frame(JOB_ID, "scene_000.jpg"))

    assert Path(regular_response.path) == regular_path
    assert Path(response.path) == scene_path
    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.get_local_frame(JOB_ID, "../audio.mp3"))
    assert exc.value.status_code == 404


@pytest.mark.parametrize("bad_job_id", ["..", r"..\secret", "%2e%2e"])
def test_job_paths_and_local_route_reject_non_uuid_job_ids(job_dir, bad_job_id):
    outside_scene_dir = job_dir.parent / "scene_frames"
    outside_scene_dir.mkdir(parents=True, exist_ok=True)
    (outside_scene_dir / "scene_000.jpg").write_bytes(b"outside")

    for path_helper in (main._job_file, main._frames_dir, main._scene_frames_dir):
        with pytest.raises(main.HTTPException) as exc:
            path_helper(bad_job_id)
        assert exc.value.status_code == 404

    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.get_local_frame(bad_job_id, "scene_000.jpg"))
    assert exc.value.status_code == 404


@pytest.mark.parametrize("status", ["done", "error"])
def test_delete_job_removes_every_r2_object_under_job_prefix(monkeypatch, job_dir, status):
    (job_dir / JOB_ID).mkdir()
    main._save_job(JOB_ID, {"status": status, "frames": [], "scenes": []})
    deleted = []

    class FakeS3:
        def list_objects_v2(self, **kwargs):
            assert kwargs["Prefix"] == f"{JOB_ID}/"
            return {
                "Contents": [
                    {"Key": f"{JOB_ID}/frame_000.jpg"},
                    {"Key": f"{JOB_ID}/scenes/scene_000.jpg"},
                ],
                "IsTruncated": False,
            }

        def delete_objects(self, **kwargs):
            deleted.extend(item["Key"] for item in kwargs["Delete"]["Objects"])

    monkeypatch.setattr(main, "s3", FakeS3())

    asyncio.run(main.delete_job(JOB_ID))

    assert deleted == [f"{JOB_ID}/frame_000.jpg", f"{JOB_ID}/scenes/scene_000.jpg"]
    assert not (job_dir / JOB_ID).exists()


def test_partial_scene_upload_is_cleaned_after_concurrent_job_failure(monkeypatch, job_dir):
    (job_dir / JOB_ID).mkdir()
    main._save_job(JOB_ID, {"status": "pending", "frames": [], "url": "https://example.com/video"})
    video_path = job_dir / JOB_ID / "video.mp4"
    video_path.write_bytes(b"video")
    scene_uploaded = threading.Event()
    deleted = []

    def extract_frames(video, output_dir, *args):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "frame_001.jpg").write_bytes(b"frame")
        return ["frame_001.jpg"]

    def upload_frames(*args):
        assert scene_uploaded.wait(2)
        raise RuntimeError("regular upload failed")

    def upload_scene(found_job_id, scenes):
        scene_uploaded.set()
        return [{**scenes[0], "keyframe": f"{found_job_id}/scenes/scene_000.jpg"}]

    class FakeS3:
        def list_objects_v2(self, **kwargs):
            return {
                "Contents": [
                    {"Key": f"{JOB_ID}/frame_001.jpg"},
                    {"Key": f"{JOB_ID}/scenes/scene_000.jpg"},
                ],
                "IsTruncated": False,
            }

        def delete_objects(self, **kwargs):
            deleted.extend(item["Key"] for item in kwargs["Delete"]["Objects"])

    monkeypatch.setattr(main, "_download_video", lambda *args: (video_path, 20.0, "author", {}))
    monkeypatch.setattr(main, "_extract_frames", extract_frames)
    monkeypatch.setattr(main, "_dedup_frames", lambda _dir, names: names)
    monkeypatch.setattr(
        main,
        "_detect_scenes_best_effort",
        lambda *args: [{"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0}],
    )
    monkeypatch.setattr(
        main,
        "_extract_scene_keyframes",
        lambda *args: [{"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0, "keyframe": "scene_000.jpg"}],
    )
    monkeypatch.setattr(main, "_upload_frames", upload_frames)
    monkeypatch.setattr(main, "_upload_scene_keyframes", upload_scene)
    monkeypatch.setattr(main, "_ocr_main_and_hook", lambda *args: (("", []), ("", [])))
    monkeypatch.setattr(main, "_write_script", lambda *args: None)
    monkeypatch.setattr(main, "_write_audio", lambda *args: None)
    monkeypatch.setattr(main, "s3", FakeS3())

    asyncio.run(main._run_job(JOB_ID, "https://example.com/video", 1.0, transcribe=False))
    assert main._load_job(JOB_ID)["status"] == "error"
    assert scene_uploaded.is_set()

    asyncio.run(main.delete_job(JOB_ID))

    assert deleted == [f"{JOB_ID}/frame_001.jpg", f"{JOB_ID}/scenes/scene_000.jpg"]


def test_transcribe_false_still_processes_and_uploads_scenes(monkeypatch, job_dir):
    job_id = JOB_ID
    (job_dir / job_id).mkdir()
    main._save_job(job_id, {"status": "pending", "frames": [], "url": "https://example.com/video"})
    video_path = job_dir / job_id / "video.mp4"
    video_path.write_bytes(b"video")
    calls = []

    def extract_frames(video, output_dir, *args):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "frame_001.jpg").write_bytes(b"frame")
        return ["frame_001.jpg"]

    def detect_scenes(video, start_s, end_s):
        calls.append(("detect", start_s, end_s))
        return [{"index": 0, "start": 12.0, "end": 14.0, "duration": 2.0}]

    def extract_scenes(video, found_job_id, scenes, max_keyframes):
        calls.append(("extract", max_keyframes))
        return [{**scenes[0], "keyframe": "scene_000.jpg"}]

    def upload_scenes(found_job_id, scenes):
        calls.append(("upload-scenes", found_job_id))
        return [{**scenes[0], "keyframe": f"{found_job_id}/scenes/scene_000.jpg"}]

    monkeypatch.setattr(main, "_download_video", lambda *args: (video_path, 20.0, "author", {}))
    monkeypatch.setattr(main, "_extract_audio", lambda *args: pytest.fail("audio must not be extracted"))
    monkeypatch.setattr(main, "_extract_frames", extract_frames)
    monkeypatch.setattr(main, "_dedup_frames", lambda _dir, names: names)
    monkeypatch.setattr(main, "_detect_scenes_best_effort", detect_scenes)
    monkeypatch.setattr(main, "_extract_scene_keyframes", extract_scenes)
    monkeypatch.setattr(main, "_upload_frames", lambda *args: [f"{job_id}/frame_001.jpg"])
    monkeypatch.setattr(main, "_upload_scene_keyframes", upload_scenes)
    monkeypatch.setattr(main, "_ocr_main_and_hook", lambda *args: (("", []), ("", [])))
    monkeypatch.setattr(main, "_write_script", lambda *args: None)
    monkeypatch.setattr(main, "_write_audio", lambda *args: None)

    asyncio.run(main._run_job(job_id, "https://example.com/video", 1.0, 10.0, 15.0, transcribe=False))

    job = main._load_job(job_id)
    assert job["status"] == "done"
    assert job["frames"] == [f"{JOB_ID}/frame_001.jpg"]
    assert job["scenes"] == [
        {"index": 0, "start": 12.0, "end": 14.0, "duration": 2.0, "keyframe": f"{JOB_ID}/scenes/scene_000.jpg"}
    ]
    assert ("detect", 10.0, 15.0) in calls
    assert ("extract", main.SCENE_MAX_KEYFRAMES) in calls
    assert not (job_dir / job_id / "scene_frames").exists()


def test_scene_selector_failure_leaves_job_done(monkeypatch, job_dir):
    job_id = JOB_ID
    (job_dir / job_id).mkdir()
    main._save_job(job_id, {"status": "pending", "frames": [], "url": "https://example.com/video"})
    video_path = job_dir / job_id / "video.mp4"
    video_path.write_bytes(b"video")

    def extract_frames(video, output_dir, *args):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "frame_001.jpg").write_bytes(b"frame")
        return ["frame_001.jpg"]

    monkeypatch.setattr(main, "_download_video", lambda *args: (video_path, 20.0, "author", {}))
    monkeypatch.setattr(main, "_extract_frames", extract_frames)
    monkeypatch.setattr(main, "_dedup_frames", lambda _dir, names: names)
    monkeypatch.setattr(
        main,
        "_detect_scenes_best_effort",
        lambda *args: [{"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0}],
    )
    monkeypatch.setattr(
        main.scene_detection,
        "select_keyframe_indices",
        lambda *args: (_ for _ in ()).throw(RuntimeError("selector failure")),
    )
    monkeypatch.setattr(main, "_upload_frames", lambda *args: [f"{job_id}/frame_001.jpg"])
    monkeypatch.setattr(main, "_ocr_main_and_hook", lambda *args: (("", []), ("", [])))
    monkeypatch.setattr(main, "_write_script", lambda *args: None)
    monkeypatch.setattr(main, "_write_audio", lambda *args: None)

    asyncio.run(main._run_job(job_id, "https://example.com/video", 1.0, transcribe=False))

    job = main._load_job(job_id)
    assert job["status"] == "done"
    assert job["scenes"] == [{"index": 0, "start": 0.0, "end": 2.0, "duration": 2.0, "keyframe": None}]


def test_download_requests_video_and_audio_merge(monkeypatch, tmp_path):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def extract_info(self, url, download):
            assert url == "https://example.com/video"
            assert download is True
            return {"id": "video123", "ext": "mp4", "duration": 10}

    monkeypatch.setattr(main.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    video_path, duration, _, _ = main._download_video("https://example.com/video", tmp_path)

    assert video_path == tmp_path / "video123.mp4"
    assert duration == 10.0
    assert captured["opts"]["format"] == (
        "bestvideo[height<=1080]+bestaudio/"
        "best[height<=1080][vcodec^=h264][acodec!=none]/"
        "best[height<=1080][acodec!=none]/best"
    )
    assert captured["opts"]["merge_output_format"] == "mp4"
