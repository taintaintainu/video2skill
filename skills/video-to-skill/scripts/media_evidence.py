"""Optional per-step evidence-frame export."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable


def _flatten_steps(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step
        for subtask in trajectory.get("subtasks", [])
        for step in subtask.get("steps", [])
        if isinstance(step, dict)
    ]


def export_step_evidence(
    video: Path,
    trajectory: dict[str, Any],
    destination: Path,
    *,
    runner: Callable[[list[str]], Any],
    max_frames: int = 100,
    max_height: int = 1080,
) -> int:
    """Attach representative JPEGs to up to ``max_frames`` canonical steps."""
    if max_frames < 1 or max_height < 64:
        raise ValueError("evidence frame limits are invalid")
    all_steps = _flatten_steps(trajectory)
    if not all_steps:
        return 0
    if len(all_steps) <= max_frames:
        selected = list(enumerate(all_steps))
    elif max_frames == 1:
        selected = [(len(all_steps) // 2, all_steps[len(all_steps) // 2])]
    else:
        indexes = {
            round(position * (len(all_steps) - 1) / (max_frames - 1))
            for position in range(max_frames)
        }
        selected = [(index, all_steps[index]) for index in sorted(indexes)]

    destination.mkdir(parents=True, exist_ok=True)
    for ordinal, (index, step) in enumerate(selected, 1):
        start = float(step.get("start_sec") or 0)
        end = max(start, float(step.get("end_sec") or start))
        timestamp = max(0.0, (start + end) / 2)
        source_id = str(step.get("source_step_id") or f"canonical-{index + 1:04d}")
        digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:10]
        filename = f"step-{ordinal:04d}-{digest}.jpg"
        output = destination / filename
        runner(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                f"scale=-2:min(ih\\,{max_height})",
                "-q:v",
                "4",
                "-y",
                str(output),
            ]
        )
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg did not create evidence frame: {output}")
        step["evidence_frame"] = f"assets/evidence/{filename}"
    return len(selected)
