from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "video-to-skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import benchmark_providers


class BenchmarkTests(unittest.TestCase):
    def test_matrix_accepts_key_environment_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(
                json.dumps(
                    {
                        "runs": [
                            {
                                "label": "local",
                                "provider": "openai-compatible",
                                "model": "vision",
                                "base_url": "http://localhost:9000/v1",
                                "api_key_env": "LOCAL_API_KEY",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            runs = benchmark_providers.load_matrix(path)
            self.assertEqual(runs[0]["api_key_env"], "LOCAL_API_KEY")

    def test_matrix_rejects_key_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(
                json.dumps(
                    {
                        "runs": [
                            {
                                "label": "unsafe",
                                "provider": "seed",
                                "api_key": "not-allowed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                benchmark_providers.load_matrix(path)

    def test_matrix_accepts_boolean_local_no_auth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(
                json.dumps({"runs": [{
                    "label": "local",
                    "provider": "openai-compatible",
                    "model": "vision",
                    "base_url": "http://127.0.0.1:9000/v1",
                    "no_auth": True,
                }]}),
                encoding="utf-8",
            )
            self.assertTrue(benchmark_providers.load_matrix(path)[0]["no_auth"])


if __name__ == "__main__":
    unittest.main()
