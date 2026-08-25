#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "video_to_skill.py"
ALLOWED_FIELDS = {
    "label",
    "provider",
    "model",
    "base_url",
    "api_key_env",
    "api_mode",
    "structured_output",
    "auth_header",
    "auth_scheme",
    "seed_endpoint_profile",
    "frame_fps",
    "max_frames",
    "fine_workers",
    "no_auth",
}


def load_matrix(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    runs = value.get("runs") if isinstance(value, dict) else None
    if not isinstance(runs, list) or not runs:
        raise ValueError("matrix must contain a non-empty runs array")
    labels: set[str] = set()
    safe_labels: set[str] = set()
    validated = []
    for item in runs:
        if not isinstance(item, dict):
            raise ValueError("each matrix run must be an object")
        unknown = set(item) - ALLOWED_FIELDS
        if unknown:
            raise ValueError(f"unsupported matrix fields: {sorted(unknown)}")
        if any("key" in field.casefold() and field != "api_key_env" for field in item):
            raise ValueError("matrix files may contain key environment names, never key values")
        if "no_auth" in item and not isinstance(item["no_auth"], bool):
            raise ValueError("no_auth must be a boolean")
        label = str(item.get("label") or "").strip()
        provider = str(item.get("provider") or "").strip()
        if not label or not provider:
            raise ValueError("each run requires label and provider")
        if label in labels:
            raise ValueError(f"duplicate run label: {label}")
        normalized_label = safe_label(label)
        if normalized_label in safe_labels:
            raise ValueError(f"run labels collide after filename normalization: {label}")
        if provider not in {
            "seed", "gemini", "openai", "codex", "openai-compatible", "local"
        }:
            raise ValueError(f"unsupported provider: {provider}")
        labels.add(label)
        safe_labels.add(normalized_label)
        validated.append(item)
    return validated


def safe_label(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.") or "run"


def summarize_trajectory(path: Path) -> dict[str, Any]:
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    steps = [
        step
        for subtask in trajectory.get("subtasks", [])
        for step in subtask.get("steps", [])
    ]
    confidence = [float(step.get("confidence", 0)) for step in steps]
    merge = trajectory.get("llm_merge") or {}
    extraction = trajectory.get("extraction") or {}
    return {
        "provider": extraction.get("provider"),
        "model": extraction.get("model"),
        "status": merge.get("status"),
        "step_count": len(steps),
        "subtask_count": len(trajectory.get("subtasks", [])),
        "context_note_count": len(trajectory.get("context_notes", [])),
        "mean_step_confidence": round(statistics.fmean(confidence), 4) if confidence else None,
        "min_step_confidence": round(min(confidence), 4) if confidence else None,
        "low_confidence_steps_lt_0_7": sum(value < 0.7 for value in confidence),
        "unresolved_conflict_count": len(merge.get("unresolved_conflicts", [])),
        "quality_flags": extraction.get("quality_flags", []),
    }


def write_markdown(results: list[dict[str, Any]], path: Path) -> None:
    columns = [
        ("Run", "label"),
        ("Provider", "provider"),
        ("Model", "model"),
        ("Result", "result"),
        ("Elapsed s", "elapsed_seconds"),
        ("Steps", "step_count"),
        ("Notes", "context_note_count"),
        ("Mean conf", "mean_step_confidence"),
        ("Conflicts", "unresolved_conflict_count"),
    ]
    lines = [
        "# Video2Skill provider benchmark",
        "",
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for result in results:
        lines.append(
            "| " + " | ".join(str(result.get(key, "")) for _, key in columns) + " |"
        )
    lines += [
        "",
        "Step density and self-reported confidence are diagnostics, not ground-truth accuracy. Review trajectories and replay outcomes before choosing a provider.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Local video path or public tutorial URL")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("provider-benchmark"))
    parser.add_argument("--title")
    parser.add_argument("--ffmpeg-dir", type=Path)
    parser.add_argument("--yt-dlp-path", type=Path)
    parser.add_argument("--accept-upload", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--keep-raw-responses", action="store_true")
    args = parser.parse_args()
    if not args.accept_upload:
        raise SystemExit(
            "Benchmark not started. Review the matrix and pass --accept-upload to approve all listed provider calls."
        )

    runs = load_matrix(args.matrix)
    root = args.output_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for run in runs:
        label = str(run["label"])
        run_root = root / safe_label(label)
        command = [
            sys.executable,
            str(RUNNER),
            args.input,
            "--output-root",
            str(run_root),
            "--provider",
            str(run["provider"]),
            "--accept-upload",
        ]
        option_map = {
            "model": "--model",
            "base_url": "--base-url",
            "api_key_env": "--api-key-env",
            "api_mode": "--api-mode",
            "structured_output": "--structured-output",
            "auth_header": "--auth-header",
            "auth_scheme": "--auth-scheme",
            "seed_endpoint_profile": "--seed-endpoint-profile",
            "frame_fps": "--frame-fps",
            "max_frames": "--max-frames",
            "fine_workers": "--fine-workers",
        }
        for field, option in option_map.items():
            if run.get(field) is not None:
                command += [option, str(run[field])]
        if run.get("no_auth"):
            command.append("--no-auth")
        if args.title:
            command += ["--title", args.title]
        if args.ffmpeg_dir:
            command += ["--ffmpeg-dir", str(args.ffmpeg_dir)]
        if args.yt_dlp_path:
            command += ["--yt-dlp-path", str(args.yt_dlp_path)]
        if args.keep_raw_responses:
            command.append("--keep-raw-responses")

        started = time.perf_counter()
        completed = subprocess.run(command, text=True)
        elapsed = round(time.perf_counter() - started, 3)
        result: dict[str, Any] = {
            "label": label,
            "provider": run["provider"],
            "model": run.get("model"),
            "elapsed_seconds": elapsed,
            "exit_code": completed.returncode,
        }
        trajectory_path = run_root / "generated-skill" / "references" / "semantic_trajectory.json"
        if completed.returncode == 0 and trajectory_path.is_file():
            result.update({"result": "success", **summarize_trajectory(trajectory_path)})
        else:
            result["result"] = "failed"
        results.append(result)
        (root / "comparison.json").write_text(
            json.dumps({"runs": results}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_markdown(results, root / "comparison.md")
        if completed.returncode != 0 and not args.continue_on_error:
            raise SystemExit(completed.returncode)

    print(root / "comparison.md")


if __name__ == "__main__":
    main()
