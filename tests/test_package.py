from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_release_files_and_manifest(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text("utf-8"))
        self.assertEqual(manifest["name"], "video2skill")
        self.assertEqual(manifest["license"], "MIT")
        self.assertEqual(manifest["version"], "0.2.2")
        self.assertTrue(re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]))
        for path in (
            ROOT / "LICENSE",
            ROOT / "SECURITY.md",
            ROOT / "PRIVACY.md",
            ROOT / "DEPENDENCIES.md",
            ROOT / "MIGRATION.md",
            ROOT / ".codexignore",
            ROOT / "assets" / "icon.svg",
            ROOT / ".github" / "workflows" / "hol-plugin-scanner.yml",
        ):
            self.assertTrue(path.is_file(), str(path))

    def test_python_sources_parse(self) -> None:
        for path in ROOT.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_no_internal_or_secret_markers(self) -> None:
        private_path = "C:" + "\\Users\\" + "70" + "895"
        old_media = "媒体" + "1.webm"
        old_project = "osworld" + "_video_annotation"
        forbidden = re.compile(
            re.escape(private_path)
            + "|"
            + re.escape(old_media)
            + "|"
            + re.escape(old_project)
            + "|"
            + r"sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}"
            + r"|\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
        )
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.assertIsNone(forbidden.search(text), str(path))


if __name__ == "__main__":
    unittest.main()
