# Privacy and data handling

Video2Skill is a local command-line pipeline that calls the inference provider selected by the user. It is not an offline video processor.

## Data sent

| Provider | Default endpoint | Media sent |
| --- | --- | --- |
| Seed | `ark.cn-beijing.volces.com` | Transcoded video proxy chunks, including audio when present |
| Gemini | `generativelanguage.googleapis.com` | Inline transcoded video proxy chunks, including audio when present |
| OpenAI / `codex` API alias | `api.openai.com` | Sampled JPEG frames and prompts; no video or audio |
| OpenAI-compatible | User-supplied | Sampled JPEG frames and prompts; no video or audio |
| Local loopback | User-supplied loopback service | Sampled JPEG frames and prompts remain on the host unless that service forwards them |

The selected provider receives the extraction prompt, trajectory schema, and merge-plan material. Video titles, subtitles, OCR, audio, and all provider output are treated as untrusted data, not executable instructions. Consult that provider's terms, regional processing, retention, and training policies before sending sensitive material.

Custom remote endpoints must use HTTPS. Plain HTTP and credential-free mode are accepted only for `localhost`, `127.0.0.1`, or `::1` services.

## Consent and retention defaults

- `--dry-run` prints the transfer plan without calling an inference provider.
- `--accept-upload` or `VIDEO2SKILL_ACCEPT_UPLOAD=1` is required for inference.
- Raw provider responses are not saved unless `--keep-raw-responses` is used.
- Likely credentials, passwords, tokens, private keys, and personal identifiers are replaced with `<redacted-sensitive-value>` before annotations enter the cache. `--allow-sensitive-values` is an explicit high-risk opt-out.
- Seed Files API uploads are deleted after inference by default. Cleanup is best-effort because a network failure can prevent deletion; the generated provenance records the actual cleanup result and quality flags record failures without persisting provider response bodies.
- Generated provenance stores source filename, media metadata, and SHA-256, but not the local absolute source path.
- URL query strings, fragments, and embedded credentials are stripped from stored provenance and error messages. Download-side metadata files are removed after the small required metadata subset is extracted.
- Proxy media, uniquely namespaced downloaded URL sources, fingerprinted annotation caches, and sampled frames remain under the chosen output directory until the user removes them.
- The generated skill includes a compact `source_index.json`. Complete `source_annotations.json`, a Markdown report, and evidence frames are opt-in.

Do not process videos containing secrets, personal data, confidential customer information, or third-party copyrighted material unless you have authority and the selected provider is approved for that data.
