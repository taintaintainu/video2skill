# Full semantic trajectory

The generated skill preserves the complete merged trajectory.

Important step fields:
- `action_description`
- `interaction_type`
- `target`
- `typed_value_or_hotkey`
- `visible_result`
- `start_sec`
- `end_sec`
- `confidence`
- `source_chunk_id`
- `source_step_id`
- `merged_source_step_ids`
- `replaces_broad_step_ids`

Important context fields:
- `note`
- `kind`
- `start_sec`
- `end_sec`
- `evidence`
- `confidence`
- `source_chunk_id`
- `merged_source_chunk_ids`

Top-level fields also include:

- `coverage.duration_seconds`
- `extraction.provider`
- `extraction.model`
- `extraction.quality_flags`
- `llm_merge.status`
- `llm_merge.unresolved_conflicts`
- `llm_merge.review_recommended`

Sensitive-looking values are replaced with the literal marker `<redacted-sensitive-value>` by default. Replayers must never type that marker as if it were a real value.

`semantic_trajectory.json` remains authoritative. Optional `evidence_frame` fields point to generated JPEGs and never encode click coordinates.

`source_index.json` (`source_index_v1`) maps each pre-merge source ID to its chunk, time range, and one or more canonical `retained_as` IDs. For dropped or replaced records it also keeps interaction and target hints; canonical details remain only in the authoritative trajectory. `--full-audit` additionally writes `source_annotations.json`; `--human-report` writes `trajectory.md`. These are review aids, not competing authorities.

`verification.json` (`replay_verification_v1`) starts with top-level status `unverified`. All trajectory steps are pending until an actual replay; only exceptional `manual_review_steps` are repeated in the manifest. Observed outcomes belong in the initially empty `results` map after computer-use replay and visible-result checks. `provenance.json` records provider, retention, optional-artifact, and cleanup outcomes.
