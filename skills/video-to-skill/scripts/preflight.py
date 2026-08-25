#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from core import plan_chunks, resolve_executable, transcode_slot
from providers import DEFAULT_KEY_ENVS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        choices=["seed", "gemini", "openai", "codex", "openai-compatible", "local"],
    )
    parser.add_argument("--require-url-input", action="store_true")
    parser.add_argument("--ffmpeg-dir", type=Path)
    parser.add_argument("--yt-dlp-path", type=Path)
    parser.add_argument("--api-key-env")
    args = parser.parse_args()

    if args.ffmpeg_dir:
        os.environ["VIDEO2SKILL_FFMPEG_DIR"] = str(args.ffmpeg_dir.expanduser().resolve())
    if args.yt_dlp_path:
        os.environ["VIDEO2SKILL_YTDLP"] = str(args.yt_dlp_path.expanduser().resolve())

    errors: list[str] = []
    for executable in ("ffmpeg", "ffprobe"):
        resolved = resolve_executable(executable)
        print(f"{executable}: {resolved or 'NOT FOUND'}")
        if not resolved:
            errors.append(f"{executable} missing")
    yt_dlp = resolve_executable("yt-dlp")
    print(f"yt-dlp: {yt_dlp or 'not found (only needed for URL inputs)'}")
    if args.require_url_input and not yt_dlp:
        errors.append("yt-dlp missing")

    if args.provider and args.provider != "local":
        key_env = args.api_key_env or DEFAULT_KEY_ENVS[args.provider]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_env):
            errors.append("api key environment-variable name is invalid")
        print(f"{key_env}: {'set' if os.getenv(key_env) else 'NOT SET'}")
        if not os.getenv(key_env):
            errors.append(f"{key_env} missing")
    elif not args.provider:
        print("provider key: not checked (pass --provider to require one)")
    else:
        print("provider key: not required for loopback-only local provider")

    try:
        with tempfile.TemporaryDirectory() as directory:
            os.environ["VIDEO2SEMANTIC_TRANSCODE_LOCK_DIR"] = directory
            with transcode_slot():
                pass
        print("cross-platform lock: OK")
    except Exception as exc:
        errors.append(f"lock failed: {exc}")
    try:
        chunks = plan_chunks(200.0)
        assert chunks[0].start_sec == 0 and chunks[-1].end_sec == 200.0
        print("chunk planner: OK")
    except Exception as exc:
        errors.append(f"chunk planner failed: {exc}")

    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(1)
    print("Video2Skill preflight: PASS")


if __name__ == "__main__":
    main()
