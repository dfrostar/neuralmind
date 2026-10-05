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


class UnparsableConfigTests(unittest.TestCase):
    """A config that isn't strict JSON is never rewritten.

    It used to be read as ``{}``, so one trailing comma made install replace
    every other MCP server (and the tokens in their ``env``) with just ours.
    """

    USER_CONFIG = (
        '{"mcpServers": {"filesystem": {"command": "npx"}, '
        '"github": {"command": "gh-mcp", "env": {"GITHUB_TOKEN": "x"}},}}\n'
    )

    def _assert_untouched(self, client: str, rel: str, text: str) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            path = proj / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            result = mcp_install.install(client, proj)
            self.assertTrue(result.action.startswith("skipped"), result.action)
            self.assertTrue(result.detail)
            self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_trailing_comma_claude_code(self) -> None:
        self._assert_untouched("claude-code", ".mcp.json", self.USER_CONFIG)

    def test_trailing_comma_cursor(self) -> None:
        self._assert_untouched("cursor", ".cursor/mcp.json", self.USER_CONFIG)

    def test_trailing_comma_claude_desktop(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = home
            try:
                path = mcp_install.config_path("claude-desktop", Path(home))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(self.USER_CONFIG, encoding="utf-8")
                result = mcp_install.install("claude-desktop", Path(home))
                self.assertEqual(result.action, "skipped-jsonc")
                self.assertEqual(path.read_text(encoding="utf-8"), self.USER_CONFIG)
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    os.environ.pop("HOME", None)

    def test_non_object_top_level_is_untouched(self) -> None:
        self._assert_untouched("claude-code", ".mcp.json", "[1, 2]\n")

    def test_empty_file_is_treated_as_new(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / ".mcp.json").write_text("\n", encoding="utf-8")
            result = mcp_install.install("claude-code", proj)
            self.assertEqual(result.action, "installed")
            data = json.loads((proj / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("neuralmind", data["mcpServers"])

    def test_skip_detail_carries_a_pasteable_snippet(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / ".mcp.json").write_text(self.USER_CONFIG, encoding="utf-8")
            result = mcp_install.install("claude-code", proj)
            self.assertIn('"neuralmind"', result.detail)
            self.assertEqual(result.to_dict()["detail"], result.detail)


class CustomisedEntryTests(unittest.TestCase):
    """Re-running install keeps what the user customised in our own entry.

    It used to reset any entry that wasn't byte-for-byte the default, so an
    absolute venv command (MCP clients often launch with a minimal PATH) and
    the entry's `env` were lost on every re-run.
    """

    def test_absolute_venv_command_and_env_are_kept(self) -> None:
        mine = {
            "command": "/opt/venv/bin/neuralmind-mcp",
            "args": [],
            "env": {"NEURALMIND_NO_LEARN": "1"},
        }
        cfg, action = mcp_install.merge_server({"mcpServers": {"neuralmind": dict(mine)}})
        self.assertEqual(action, "already-present")
        self.assertEqual(cfg["mcpServers"]["neuralmind"], mine)

    def test_python_module_launch_is_kept(self) -> None:
        mine = {"command": "python3", "args": ["-m", "neuralmind.mcp_server"]}
        cfg, action = mcp_install.merge_server({"mcpServers": {"neuralmind": dict(mine)}})
        self.assertEqual(action, "already-present")
        self.assertEqual(cfg["mcpServers"]["neuralmind"], mine)

    def test_stale_command_is_updated_but_env_survives(self) -> None:
        cfg = {"mcpServers": {"neuralmind": {"command": "old", "args": ["x"], "env": {"A": "1"}}}}
        cfg, action = mcp_install.merge_server(cfg)
        self.assertEqual(action, "updated")
        entry = cfg["mcpServers"]["neuralmind"]
        self.assertEqual(entry["command"], "neuralmind-mcp")
        self.assertEqual(entry["args"], [])
        self.assertEqual(entry["env"], {"A": "1"})

    def test_vscode_nested_servers_get_the_entry(self) -> None:
        cfg = {"mcp": {"servers": {"other": {"command": "x"}}}, "editor.fontSize": 14}
        cfg, action = mcp_install.merge_server_vscode(cfg)
        self.assertEqual(action, "installed")
        self.assertNotIn("mcp.servers", cfg)
        self.assertIn("neuralmind", cfg["mcp"]["servers"])
        self.assertIn("other", cfg["mcp"]["servers"])

    def test_vscode_nested_entry_is_already_present(self) -> None:
        cfg = {"mcp": {"servers": {"neuralmind": mcp_install.server_entry()}}}
        cfg, action = mcp_install.merge_server_vscode(cfg)
        self.assertEqual(action, "already-present")
        self.assertNotIn("mcp.servers", cfg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
