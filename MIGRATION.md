# Migrating from video2semantic-cua

`video2skill` replaces the earlier `video2semantic-cua` plugin. Installing both can produce overlapping skill triggers even though their package names differ.

1. Back up any generated skills or trajectories you want to keep. Plugin cache folders are disposable and should not be edited as source.
2. Install and validate `video2skill` under its distinct plugin name.
3. Confirm the `video-to-skill` skill is available and run one dry-run.
4. Only then disable or remove `video2semantic-cua` in Codex plugin settings.

Existing generated skills remain standalone. They are not rewritten automatically. Regenerate them with `video2skill` when you want the compact source index, optional evidence frames, local provider support, or replay verification manifest.
