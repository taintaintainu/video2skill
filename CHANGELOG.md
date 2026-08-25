# Changelog

## 0.2.2 - 2026-08-24

- Added loopback-only, credential-free local OpenAI-compatible inference.
- Made generated skills compact by default with `source_index.json`; full annotations and Markdown are opt-in.
- Added optional per-step evidence frames and an explicit unverified computer-use replay contract.
- Consolidated HTTP/retry logic and split security, artifacts, evidence, and merge contracts into focused modules.
- Added predecessor-plugin migration guidance and expanded offline coverage to local auth and replay artifacts.

## 0.2.1 - 2026-08-24

- Removed reconstructible credential material from release tests.
- Added an explicit untrusted-media boundary and a fixed generated-skill instruction template.
- Added default credential and personal-identifier redaction with an explicit opt-out.
- Namespaced resumable caches by complete fingerprint and validated every cache envelope.
- Enforced adaptive chunk limits and strict local trajectory/merge validation.
- Preserved source annotations and merged context-note provenance in generated skills.
- Hardened URL metadata, redirects, subprocess timeouts, retries, and custom endpoint authentication.
- Reported Seed remote-file cleanup outcomes and cleaned failed preprocessing uploads.
- Corrected Gemini inline sizing for base64 expansion and added a shorter default chunk duration.

## 0.2.0 - 2026-08-24

- Added Seed, Gemini, OpenAI/Codex, and custom OpenAI-compatible providers.
- Added Responses API and Chat Completions compatibility modes.
- Added dry-run upload disclosure and bounded duration/chunk controls.
- Added audio-stream detection and deterministic removal of unsupported narration claims.
- Added cache fingerprints covering video, provider, model, prompt, schema, frames, and chunk policy.
- Removed absolute local source paths from generated provenance.
- Disabled raw-response retention by default and added best-effort Seed file cleanup.
- Added public-release metadata, privacy/security documentation, CI, and offline tests.
- Added a key-free provider matrix format and incremental multi-provider benchmark report.
