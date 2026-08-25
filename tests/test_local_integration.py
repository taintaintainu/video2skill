from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "video-to-skill" / "scripts" / "video_to_skill.py"
VIDEO = Path(os.getenv("VIDEO2SKILL_TEST_VIDEO", ""))
FFMPEG_DIR = Path(os.getenv("VIDEO2SKILL_FFMPEG_DIR", ""))
FFMPEG_NAME = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


class _CompatibleHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_POST(self) -> None:
        size = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(size))
        schema_name = (
            (payload.get("response_format") or {}).get("json_schema") or {}
        ).get("name")
        if schema_name == "semantic_trajectory_v2":
            result = {
                "summary": "Open settings",
                "subtasks": [{
                    "subtask": "Open settings",
                    "steps": [{
                        "action_description": "Click Settings",
                        "interaction_type": "click",
                        "target": "Settings",
                        "typed_value_or_hotkey": "",
                        "visible_result": "Settings opens",
                        "start_sec": 1.0,
                        "end_sec": 2.0,
                        "confidence": 0.9,
                    }],
                }],
                "context_notes": [],
            }
        elif schema_name == "semantic_trajectory_merge_plan_v1":
            text = "\n".join(
                str(item.get("text") or "")
                for item in payload["messages"][0]["content"]
                if item.get("type") == "text"
            )
            match = re.search(
                r"<untrusted_annotation_data>\s*(.*?)\s*</untrusted_annotation_data>",
                text,
                flags=re.DOTALL,
            )
            if not match:
                self.send_error(400, "merge material missing")
                return
            material = json.loads(match.group(1))
            ids = [
                step["step_id"]
                for subtask in material["local_subtasks"]
                for step in subtask["steps"]
            ]
            result = {
                "summary": "Open settings",
                "duplicate_groups": [],
                "compound_replacements": [],
                "subtasks": [{"title": "Open settings", "step_ids": ids}],
                "unresolved_conflicts": [],
            }
        else:
            self.send_error(400, "unknown schema")
            return
        body = json.dumps({"choices": [{"message": {"content": json.dumps(result)}}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@unittest.skipUnless(
    VIDEO.is_file() and (FFMPEG_DIR / FFMPEG_NAME).is_file(),
    "set VIDEO2SKILL_TEST_VIDEO and VIDEO2SKILL_FFMPEG_DIR for the real-media integration test",
)
class LocalIntegrationTests(unittest.TestCase):
    def test_real_video_local_loopback_generates_compact_skill(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _CompatibleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "output"
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(RUNNER),
                        str(VIDEO),
                        "--output-root",
                        str(output),
                        "--provider",
                        "local",
                        "--base-url",
                        f"http://127.0.0.1:{server.server_port}/v1",
                        "--model",
                        "fixture-vision",
                        "--api-mode",
                        "chat-completions",
                        "--chunk-seconds",
                        "400",
                        "--frame-fps",
                        "0.01",
                        "--max-frames",
                        "2",
                        "--ffmpeg-dir",
                        str(FFMPEG_DIR),
                        "--evidence-frames",
                        "--max-evidence-frames",
                        "2",
                        "--accept-upload",
                    ],
                    text=True,
                    capture_output=True,
                    timeout=180,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
                generated = output / "generated-skill"
                references = generated / "references"
                for name in (
                    "semantic_trajectory.json",
                    "source_index.json",
                    "verification.json",
                    "provenance.json",
                ):
                    self.assertTrue((references / name).is_file(), name)
                self.assertFalse((references / "source_annotations.json").exists())
                self.assertFalse((references / "trajectory.md").exists())
                verification = json.loads((references / "verification.json").read_text("utf-8"))
                self.assertEqual(verification["status"], "unverified")
                self.assertTrue(list((generated / "assets" / "evidence").glob("*.jpg")))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
