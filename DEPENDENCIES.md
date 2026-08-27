# Dependencies

Video2Skill has no third-party Python package dependencies.

`requirements-lock.txt` is intentionally package-free and records this zero-dependency runtime state for release scanners.

Runtime requirements:

- Python 3.11 or newer
- `ffmpeg` and `ffprobe`
- `yt-dlp` only for public URL inputs

The repository's release validators may use their own isolated dependencies; none are imported by the runtime pipeline.
