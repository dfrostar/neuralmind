"""Tests for MCP auto-detection + registration (neuralmind/mcp_install.py).

Pure stdlib — loaded in isolation so it runs without the retrieval stack, with a
fake HOME so the user-scoped client paths are sandboxed.

    python tests/test_mcp_install.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "neuralmind_mcp_install", _REPO / "neuralmind" / "mcp_install.py"
)
assert _spec and _spec.loader
mcp_install = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = mcp_install
_spec.loader.exec_module(mcp_install)


class MergeTests(unittest.TestCase):
    def test_install_into_empty(self) -> None:
        cfg, action = mcp_install.merge_server({})
        self.assertEqual(action, "installed")
        self.assertIn("neuralmind", cfg["mcpServers"])
        self.assertEqual(cfg["mcpServers"]["neuralmind"]["command"], "neuralmind-mcp")

    def test_preserves_other_servers(self) -> None:
        cfg = {"mcpServers": {"other": {"command": "x"}}}
        cfg, action = mcp_install.merge_server(cfg)
        self.assertEqual(action, "installed")
        self.assertIn("other", cfg["mcpServers"])
        self.assertIn("neuralmind", cfg["mcpServers"])

    def test_idempotent(self) -> None:
        cfg, _ = mcp_install.merge_server({})
        cfg, action = mcp_install.merge_server(cfg)
        self.assertEqual(action, "already-present")

    def test_updates_changed_entry(self) -> None:
        cfg = {"mcpServers": {"neuralmind": {"command": "old", "args": []}}}
        cfg, action = mcp_install.merge_server(cfg)
        self.assertEqual(action, "updated")
        self.assertEqual(cfg["mcpServers"]["neuralmind"]["command"], "neuralmind-mcp")

    def test_non_dict_mcpservers_is_replaced(self) -> None:
        cfg, action = mcp_install.merge_server({"mcpServers": "garbage"})
        self.assertEqual(action, "installed")
        self.assertIsInstance(cfg["mcpServers"], dict)

    def test_snippet_is_valid_json(self) -> None:
        data = json.loads(mcp_install.snippet())
        self.assertEqual(data["mcpServers"]["neuralmind"]["command"], "neuralmind-mcp")


class PathTests(unittest.TestCase):
    def test_project_scoped_paths(self) -> None:
        proj = Path("/tmp/proj")
        self.assertEqual(mcp_install.config_path("claude-code", proj), proj / ".mcp.json")
        self.assertEqual(mcp_install.config_path("cursor", proj), proj / ".cursor" / "mcp.json")

    def test_unknown_client_raises(self) -> None:
        with self.assertRaises(ValueError):
            mcp_install.config_path("emacs", Path("/tmp/proj"))


class InstallTests(unittest.TestCase):
    def test_install_writes_and_merges(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            # Pre-existing config with another server must be preserved.
            (proj / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
            result = mcp_install.install("claude-code", proj)
            self.assertEqual(result.action, "installed")
            data = json.loads((proj / ".mcp.json").read_text())
            self.assertIn("other", data["mcpServers"])
            self.assertIn("neuralmind", data["mcpServers"])
            # Second run is idempotent and writes nothing new.
            again = mcp_install.install("claude-code", proj)
            self.assertEqual(again.action, "already-present")

    def test_cursor_creates_nested_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            result = mcp_install.install("cursor", proj)
            self.assertTrue(result.path.exists())
            self.assertEqual(result.path, proj / ".cursor" / "mcp.json")

    def test_detect_clients_with_fake_home(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "proj"
            proj.mkdir()
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(Path(d) / "home")
            try:
                # Nothing present yet.
                self.assertEqual(mcp_install.detect_clients(proj), [])
                # A project .mcp.json makes claude-code detected.
                mcp_install.install("claude-code", proj)
                self.assertIn("claude-code", mcp_install.detect_clients(proj))
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    os.environ.pop("HOME", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
