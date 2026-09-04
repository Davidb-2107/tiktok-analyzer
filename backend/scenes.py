from pathlib import Path


def detect_scenes(
    video_path: Path,
    start_s: float | None = None,
    end_s: float | None = None,
    threshold: float = 27.0,
    min_scene_len: int = 15,
) -> list[dict]:
    from scenedetect import ContentDetector, detect

    raw_scenes = detect(
        str(video_path),
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len),
        show_progress=False,
        start_time=start_s,
        end_time=end_s,
        start_in_scene=True,
    )
    result = []
    for index, (start, end) in enumerate(raw_scenes):
        start_sec = round(float(start.get_seconds()), 2)
        end_sec = round(float(end.get_seconds()), 2)
        if end_sec > start_sec:
            result.append(
                {
                    "index": index,
                    "start": start_sec,
                    "end": end_sec,
                    "duration": round(end_sec - start_sec, 2),
                }
            )
    return result


def select_keyframe_indices(scene_count: int, max_keyframes: int = 120) -> set[int]:
    if scene_count <= 0 or max_keyframes <= 0:
        return set()
    if scene_count <= max_keyframes:
        return set(range(scene_count))
    if max_keyframes == 1:
        return {scene_count // 2}

    return {
        round(index * (scene_count - 1) / (max_keyframes - 1))
        for index in range(max_keyframes)
    }


def keyframe_time(scene: dict) -> float:
    start = float(scene["start"])
    end = float(scene["end"])
    midpoint = (start + end) / 2
    return max(start, min(midpoint, end))
