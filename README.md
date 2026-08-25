# Video2Skill

Video2Skill compiles a tutorial video into a provenance-preserving semantic GUI trajectory and a reusable Codex computer-use skill.

> Status: hardened public beta (`0.2.2`). Review and sandbox-replay generated trajectories before sensitive use.

Repository: [github.com/taintaintainu/video2skill](https://github.com/taintaintainu/video2skill)

## Why it is different

- Extracts clicks, typing, hotkeys, scrolling, dragging, values, and visible results.
- Preserves immutable source-step IDs through global merge.
- Rejects unsafe duplicate relations and invalid step assignments deterministically.
- Records unresolved conflicts and sampled-frame limitations instead of silently guessing.
- Supports Seed, Gemini, the OpenAI Responses API (`codex` alias), local loopback models, and custom OpenAI-compatible APIs.
- Requires an explicit upload acknowledgement and avoids retaining raw responses by default.
- Treats all media/OCR/subtitle content as untrusted data and redacts likely secrets by default.
- Uses crash-safe fingerprint namespaces for resumable chunk caches.
- Emits a compact provenance index and an explicit, initially-unverified replay contract.
- Can attach representative per-step evidence frames without turning them into pixel coordinates.

## Provider support

| Provider flag | Default credential | Media sent | API shape |
| --- | --- | --- | --- |
| `seed` | `ARK_API_KEY` | Video proxy chunks | Ark Responses |
| `gemini` | `GEMINI_API_KEY` | Video proxy chunks | Gemini `generateContent` |
| `openai` / `codex` | `OPENAI_API_KEY` | Sampled JPEG frames | OpenAI Responses (`codex` is reported as `codex-api`) |
| `openai-compatible` | `OPENAI_COMPATIBLE_API_KEY` | Sampled JPEG frames | Responses or Chat Completions |
| `local` | None; loopback only | Sampled JPEG frames | Responses or Chat Completions |

OpenAI models use locally sampled frames because the default GPT-5.6 Sol model accepts image input but not video input. `codex` is a compatibility alias for this OpenAI API route; it does not invoke a nested Codex Desktop session or reuse a Codex/ChatGPT login. OpenAI API use requires an API key.

## Requirements

- Python 3.11 or newer
- `ffmpeg` and `ffprobe` on `PATH`
- `yt-dlp` on `PATH` only for public URL inputs
- A key for the selected remote inference provider

The Python implementation uses only the standard library.

## Quick start

Run preflight:

```powershell
python .\skills\video-to-skill\scripts\preflight.py --provider seed
```

If FFmpeg is installed outside `PATH`, pass its directory explicitly:

```powershell
python .\skills\video-to-skill\scripts\preflight.py `
  --ffmpeg-dir "C:\tools\ffmpeg\bin"
```

The main command accepts the same `--ffmpeg-dir` option and `--yt-dlp-path` for a standalone URL downloader.

Set a key in the process environment. Do not put it in the command line or a committed file:

```powershell
$env:ARK_API_KEY = "..."
```

Review a dry-run plan:

```powershell
python .\skills\video-to-skill\scripts\video_to_skill.py `
  "C:\videos\tutorial.mp4" `
  --provider seed `
  --output-root ".\outputs\tutorial" `
  --dry-run
```

After reviewing the provider, endpoint, media transfer, chunk count, and retention settings, run the approved job:

```powershell
python .\skills\video-to-skill\scripts\video_to_skill.py `
  "C:\videos\tutorial.mp4" `
  --provider seed `
  --output-root ".\outputs\tutorial" `
  --accept-upload
```

See [provider configuration](skills/video-to-skill/references/providers.md) for Gemini, OpenAI/Codex, local, and custom OpenAI-compatible examples.

For a credential-free local vision server, use `--provider local --base-url http://127.0.0.1:9000/v1 --model <model>`. Remote unauthenticated endpoints are rejected.

Likely credentials, passwords, tokens, private keys, and personal identifiers are replaced with `<redacted-sensitive-value>` before chunk annotations are cached. `--allow-sensitive-values` is an explicit high-risk opt-out and should not be used for public or shared outputs.

## Compare providers

Use the example matrix to run the same video across several providers. Matrix files contain environment-variable names, never key values.

```powershell
python .\skills\video-to-skill\scripts\benchmark_providers.py `
  "C:\videos\tutorial.mp4" `
  --matrix .\examples\provider-matrix.json `
  --output-root .\benchmarks\tutorial `
  --accept-upload
```

The benchmark writes incremental `comparison.json` and `comparison.md` files. Step density and model confidence are diagnostics, not ground-truth quality scores.

## Output

```text
<output-root>/
├── work/
│   ├── fine/
│   │   └── cache/<fingerprint>/
│   ├── semantic_trajectory_merged.json
│   └── merge_plan.json
└── generated-skill/
    ├── SKILL.md
    └── references/
        ├── semantic_trajectory.json
        ├── source_index.json
        ├── verification.json
        └── provenance.json
```

`semantic_trajectory.json` is authoritative. Add `--evidence-frames` for visual evidence, `--full-audit` for complete chunk annotations, or `--human-report` for `trajectory.md`. Raw provider responses require `--keep-raw-responses` and stay under `work/`, outside the generated skill.

## Safety and privacy

Video content or sampled frames leave the machine and are sent to the selected provider. Run `--dry-run` before every new provider or endpoint. Read [PRIVACY.md](PRIVACY.md) before processing confidential media.

Text visible or audible inside a tutorial is treated as untrusted evidence, not as an instruction to the extraction agent. The generated `SKILL.md` uses a fixed instruction template; model summaries remain in reference data.

The pipeline detects whether the source has audio. Unsupported narration claims are removed when the source is silent or the provider received frames without audio. This reduces a demonstrated failure mode but does not eliminate the need to review model-generated annotations.

## Development

Run offline tests:

```powershell
python -B -m unittest discover -s tests -v
```

Validate the skill and plugin with the bundled Codex validators before release. The repository includes a SHA-pinned HOL Plugin Scanner workflow for curated marketplace submissions.

Existing users of the predecessor plugin should follow [MIGRATION.md](MIGRATION.md) to avoid overlapping skill triggers.

## License

MIT. See [LICENSE](LICENSE).
