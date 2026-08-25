from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "video-to-skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from artifacts import build_source_index, build_verification_manifest
from core import validate_fine
from media_evidence import export_step_evidence


def sample() -> tuple[list[dict], dict]:
    step = {
        "action_description": "Click Save",
        "interaction_type": "click",
        "target": "Save",
        "typed_value_or_hotkey": "",
        "visible_result": "Saved appears",
        "start_sec": 1.0,
        "end_sec": 2.0,
        "confidence": 0.9,
    }
    chunks = [{
        "chunk_id": "chunk_000",
        "chunk_start_sec": 0.0,
        "chunk_end_sec": 10.0,
        "subtasks": [{"subtask": "Save", "steps": [dict(step)]}],
    }]
    canonical = dict(step)
    canonical["source_step_id"] = "chunk_000:s00:p000"
    trajectory = {
        "summary": "Save a file",
        "subtasks": [{"subtask": "Save", "steps": [canonical]}],
        "context_notes": [],
    }
    return chunks, trajectory


class ArtifactTests(unittest.TestCase):
    def test_source_index_is_compact_and_maps_canonical_step(self) -> None:
        chunks, trajectory = sample()
        index = build_source_index(chunks, trajectory)
        record = index["steps"]["chunk_000:s00:p000"]
        self.assertEqual(record["retained_as"], ["chunk_000:s00:p000"])
        self.assertNotIn("target", record)
        self.assertNotIn("typed_value_or_hotkey", record)
        self.assertNotIn("visible_result", record)

    def test_verification_manifest_never_claims_replay(self) -> None:
        _, trajectory = sample()
        trajectory["subtasks"][0]["steps"][0]["action_description"] = "Delete account"
        manifest = build_verification_manifest(trajectory)
        self.assertEqual(manifest["status"], "unverified")
        self.assertEqual(
            manifest["manual_review_steps"][0]["source_step_id"],
            "chunk_000:s00:p000",
        )
        self.assertEqual(manifest["summary"]["verified"], 0)

    def test_evidence_export_attaches_only_created_frames(self) -> None:
        _, trajectory = sample()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def runner(command: list[str]) -> None:
                Path(command[-1]).write_bytes(b"jpeg")

            count = export_step_evidence(
                root / "video.webm",
                trajectory,
                root / "assets" / "evidence",
                runner=runner,
                max_frames=1,
            )
            self.assertEqual(count, 1)
            relative = trajectory["subtasks"][0]["steps"][0]["evidence_frame"]
            self.assertTrue((root / relative).is_file())
            validate_fine(trajectory)


if __name__ == "__main__":
    unittest.main()
