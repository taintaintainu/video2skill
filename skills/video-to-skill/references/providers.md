# Inference providers

Video2Skill uses one provider for both fine annotation and immutable-ID merge planning. API keys are read from environment variables only.

When FFmpeg is not on `PATH`, pass `--ffmpeg-dir <directory>`. For URL inputs with a standalone downloader, pass `--yt-dlp-path <file>`.

## Seed

- Provider: `seed`
- Default key variable: `ARK_API_KEY`
- Optional large-file key: `ARK_FILES_API_KEY`
- Media sent: transcoded video proxy chunks; audio is included when present.
- Large uploaded files are deleted after inference by default. Use `--keep-remote-files` only when the user explicitly wants retention.
- The default `agent-plan` profile uses `https://ark.cn-beijing.volces.com/api/plan/v3`. For standard pay-as-you-go Ark credentials, pass `--seed-endpoint-profile standard`, which uses `/api/v3`.

```powershell
$env:ARK_API_KEY = "..."
python scripts/video_to_skill.py tutorial.mp4 --provider seed --dry-run
```

Always confirm which Ark product issued the credential. An explicit `--base-url` overrides the profile.

## Gemini

- Provider: `gemini`
- Default key variable: `GEMINI_API_KEY`
- Media sent: inline video proxy chunks, including audio when present.
- Chunks that exceed the inline limit are bisected automatically.
- The default Gemini chunk duration is 55 seconds. Inline admission accounts for base64 expansion and total JSON request overhead, not only the raw file size.

```powershell
$env:GEMINI_API_KEY = "..."
python scripts/video_to_skill.py tutorial.mp4 --provider gemini --model gemini-2.5-pro --dry-run
```

## OpenAI / Codex API alias

- Provider: `openai` or compatibility alias `codex`; generated provenance reports the alias as `codex-api`.
- Default key variable: `OPENAI_API_KEY`
- Default endpoint: `https://api.openai.com/v1/responses`
- Media sent: sampled JPEG frames with approximate timestamps. Video and audio are not sent because current Codex models accept image rather than video input.
- API use requires an OpenAI API key. This route does not invoke a nested Codex Desktop/CLI session and does not reuse a Codex app or ChatGPT login session.

```powershell
$env:OPENAI_API_KEY = "..."
python scripts/video_to_skill.py tutorial.mp4 --provider codex --model gpt-5.6-sol --dry-run
```

Use `--frame-fps` and `--max-frames` to trade action recall against image-token cost.

## OpenAI-compatible

- Provider: `openai-compatible`
- Default key variable: `OPENAI_COMPATIBLE_API_KEY`; override with `--api-key-env`.
- Requires `--base-url` and `--model`.
- Supports Responses API and Chat Completions request shapes.
- Media sent: sampled JPEG frames; video and audio are not sent.
- Remote base URLs must use HTTPS. Plain HTTP is accepted only for loopback development endpoints.
- Base URLs containing credentials, query parameters, or fragments are rejected and redirects are not followed.

Responses API example:

```powershell
$env:MY_PROVIDER_KEY = "..."
python scripts/video_to_skill.py tutorial.mp4 `
  --provider openai-compatible `
  --base-url https://provider.example/v1 `
  --model vision-model `
  --api-key-env MY_PROVIDER_KEY `
  --api-mode responses `
  --dry-run
```

For Chat Completions, use `--api-mode chat-completions`. `--structured-output auto` first requests JSON Schema and falls back to schema-in-prompt JSON when a compatible endpoint rejects the structured-output field. Use `--structured-output prompt` for servers known not to support JSON Schema.

Bearer authorization is the default. Compatible services that require a raw key header can use environment-only credential values:

```powershell
$env:AZURE_STYLE_KEY = "..."
python scripts/video_to_skill.py tutorial.mp4 `
  --provider openai-compatible `
  --base-url https://provider.example/openai/v1 `
  --model vision-model `
  --api-key-env AZURE_STYLE_KEY `
  --auth-header api-key `
  --auth-scheme "" `
  --dry-run
```

Compatible Responses endpoints that reject the optional `store` field automatically retry once without it. Authentication, permission, invalid-model, and other deterministic client errors are not repeatedly retried.

## Local loopback

- Provider: `local`
- Requires `--base-url` and `--model`; no API key is read.
- Only `localhost`, `127.0.0.1`, and `::1` are accepted.
- Uses the same sampled-frame Responses or Chat Completions adapter as compatible services.
- The local model must accept image data URLs. Video audio is not sent.

```powershell
python scripts/video_to_skill.py tutorial.mp4 `
  --provider local `
  --base-url http://127.0.0.1:9000/v1 `
  --model local-vision-model `
  --api-mode chat-completions `
  --dry-run
```

`--no-auth` provides the same loopback-only behavior for `openai-compatible`. It is rejected for remote hosts and cannot be combined with `--api-key-env`.

## Retention and cost controls

- `--dry-run` never calls an inference provider and does not require a key.
- `--accept-upload` is required before inference.
- `--max-duration-seconds` and `--max-chunks` bound accidental jobs.
- Raw provider responses are not retained unless `--keep-raw-responses` is set.
- Likely credentials and personal identifiers are redacted before annotations are cached. `--allow-sensitive-values` is an explicit high-risk opt-out.
- Generated provenance records the source filename and SHA-256, not its local absolute path.
- Retained URL metadata removes user information, query parameters, and fragments; temporary downloader metadata is deleted after the required fields are extracted.
- Generated skills retain compact source provenance by default. `--full-audit`, `--human-report`, and `--evidence-frames` are opt-in size/cost tradeoffs.
