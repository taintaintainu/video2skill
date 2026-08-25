# Public release checklist

## Required before the first public tag

- [ ] Revoke any provider key previously pasted into chat, logs, or terminal transcripts.
- [ ] Confirm the project has the right to publish all source code under MIT.
- [ ] Confirm the GitHub repository is public and visible at <https://github.com/taintaintainu/video2skill>.
- [x] Add the real `repository` URL to `.codex-plugin/plugin.json`.
- [x] Replace the placeholder publisher identity with `taintaintainu`.
- [ ] Run the offline test suite and both bundled Codex validators.
- [ ] Run the generic secret scanner against the source tree and the exact release archive.
- [ ] Confirm the HOL Plugin Scanner workflow passes with score 80 or higher and no high/critical findings.
- [ ] Run opt-in live smoke tests with newly issued Seed, Gemini, and OpenAI keys.
- [ ] Review one generated trajectory and replay it in a disposable GUI sandbox.
- [ ] Verify Seed cleanup, redaction, cache isolation, adaptive bounds, compact source index, and unverified replay manifest on representative fixtures.
- [ ] Exercise local no-auth on loopback and confirm the same configuration is rejected for a remote host.
- [ ] Confirm the default generated skill omits full annotations, Markdown, raw responses, and evidence frames.
- [ ] Tag `v0.2.2` as public beta; do not label it stable `1.0.0` yet.

## Recommended before 1.0

- [ ] Maintain a representative evaluation set across applications, languages, audio states, interaction types, video lengths, and operating systems.
- [ ] Track action recall, incorrect actions, replay success, final-state match, human corrections, latency, and provider cost.
- [ ] Document provider-specific retention and regional-processing links.
- [ ] Establish a release and vulnerability-response owner.
