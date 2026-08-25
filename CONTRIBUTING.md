# Contributing

Contributions are welcome through focused pull requests.

1. Do not commit API keys, real private videos, provider responses, or generated user trajectories.
2. Preserve the provider-neutral trajectory schema and immutable source-step IDs.
3. Add or update offline tests for behavior changes.
4. Run `python -m unittest discover -s tests -v`.
5. Run the Codex plugin and skill validators documented in the release checklist.

Provider integrations should use environment-variable credentials, TLS by default, bounded retries, explicit upload disclosure, and payload-shape tests that do not call paid APIs.

Changes touching media text, generated instructions, schemas, caching, retries, downloads, or authentication must include adversarial coverage where applicable. Useful cases include prompt-injection text in titles/OCR, secret-shaped values, malformed provider fields, cache fingerprint mismatches, redirects, non-retryable authentication failures, oversized payloads, and unexpected endpoint capabilities.
