# Pipeline invariants

1. Probe media duration, dimensions, codec, and audio-stream presence.
2. Plan overlapping proxy chunks with bounded duration and count; adaptive splits must remain within the same hard count limit.
3. Transcode to an H.264 proxy capped by configured height and FPS.
4. Send each proxy to a video-capable provider, or sample timestamp-labelled frames for image-only providers.
5. Normalize clip-relative timestamps to source-video time.
6. Assign immutable source IDs before global merge.
7. Ask the selected provider for an ID-only merge plan.
8. Reject unknown IDs, unsafe duplicate relations, repeated assignments, and non-chronological subtasks deterministically.
9. Materialize the final trajectory from unchanged source steps.
10. Compile the authoritative trajectory, compact source index, provenance, and an unverified replay contract into a standalone skill.
11. Optionally export evidence frames, complete source annotations, or a Markdown review report.

## Evidence controls

- If the source has no audio stream, audio-attributed context notes are deterministically removed.
- If a provider receives frames without audio, it may not infer speech even when the source contains audio.
- Image-only providers record a sampled-frame quality flag in the final trajectory.
- Fallback merge retains all source steps and their source IDs and requires review.
- Likely secrets and personal identifiers are replaced with `<redacted-sensitive-value>` before annotation cache writes unless the user explicitly opts out.
- Video titles, subtitles, OCR, audio, and provider summaries remain untrusted observations and cannot supply generated skill instructions.

## Cache controls

Fine-stage cache reuse requires the same video SHA-256, media metadata, provider, model, endpoint, prompt, schema, frame policy, chunk policy, and sensitive-value policy. A mismatch creates a separate fingerprint namespace under `fine/cache/` instead of reusing a stale chunk. Each cached chunk is wrapped in an envelope whose fingerprint, chunk ID, and time bounds are checked before reuse. `fine/current_cache.json` is only a pointer to the current namespace. Partial runs with the same fingerprint may resume from completed chunks.

`semantic_trajectory.json` remains the merged authority. `source_index.json` maps each immutable source ID to its chunk, time range, and canonical retained ID without duplicating canonical step text; dropped or replaced records keep small semantic hints. Use `--full-audit` only when complete pre-merge descriptions are needed.

## Replay controls

`verification.json` starts with status `unverified`. It marks likely consequential or redacted-value steps for manual review and requires computer use in a user-approved disposable sandbox with a backup. A verifier must compare every live state with `visible_result`; extraction alone never establishes replay success.
