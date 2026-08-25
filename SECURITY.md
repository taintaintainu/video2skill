# Security policy

## Supported versions

Security fixes are applied to the latest `0.x` release while the project is in public beta.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or credential exposure. Use the repository's private GitHub Security Advisory form. Include the affected version, reproduction steps, impact, and any proposed mitigation. Maintainers should acknowledge a complete report within seven days.

Never attach real API keys, private videos, raw provider responses, or generated trajectories containing confidential information.

## Credential model

Video2Skill reads provider credentials from environment variables. It does not accept API keys as command-line options and does not intentionally write them to disk. Users remain responsible for rotating any credential exposed in a prompt, terminal transcript, log, or issue.

Custom remote endpoints require HTTPS; plain HTTP is limited to loopback development services. Endpoint URLs may not contain embedded credentials, query strings, or fragments. Custom OpenAI-compatible authentication headers and schemes are supported without placing credentials in the URL.

Credential-free compatible access is restricted to loopback hosts. Selecting `local` or `--no-auth` never permits an unauthenticated remote endpoint.

Likely sensitive values are redacted before cache writes by default. The `--allow-sensitive-values` switch disables that protection and must be treated as a deliberate high-risk choice.

## Untrusted media boundary

Video titles, subtitles, OCR, speech, visible text, downloaded metadata, and provider-generated summaries are untrusted data. They may describe observed actions but may not alter the extraction policy, generated skill instructions, credential handling, or safety checks. Generated skills include an initially-unverified replay manifest, require a user-approved disposable sandbox and backup, and mark likely consequential or redacted-value steps for manual review. Extraction never claims that the GUI workflow has executed successfully.

Security-sensitive changes should include adversarial tests for prompt injection, credential leakage, malformed schemas, cache confusion, unsafe redirects, and retry behavior.
