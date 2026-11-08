"""Keep the Claude Code plugin in step with what it packages.

``integrations/claude-code/neuralmind/`` is a copy, in Claude Code's plugin
format, of what ``neuralmind install-hooks`` and ``neuralmind install-mcp
--client claude-code`` write. A copy drifts: the skill manifest's version sat
three majors behind the package until a test checked it
(``tests/test_skill_manifest.py``). So this file checks each copied piece
against its source, and the version against release-please's wiring, since a
plugin whose ``version`` doesn't change reaches nobody: Claude Code keeps
users on the copy it cached until the string changes.

The runtime half, the plugin's copy of a hook standing aside when a settings
file registers the same one, is tested in ``tests/test_hooks.py``
(``TestPluginCopyStandsAside``).

Stdlib-only by repo convention: the two modules it compares against are
loaded from their files, without importing the package.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "integrations" / "claude-code" / "neuralmind"
PLUGIN_REL = "integrations/claude-code/neuralmind"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

REGENERATE_HOOKS = (
    f"put neuralmind.hooks._hook_block(), without its BLOCK_KEY entry, under "
    f'"hooks" in {PLUGIN_REL}/hooks/hooks.json'
)


def _load(name: str):
    module_name = f"_plugin_test_{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name, REPO_ROOT / "neuralmind" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # @dataclass looks its class's module up in sys.modules.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_plugin_hooks_are_the_block_install_hooks_writes() -> None:
    hooks = _load("hooks")
    expected = hooks._hook_block()
    expected.pop(hooks.BLOCK_KEY)
    document = _json(PLUGIN_DIR / "hooks" / "hooks.json")
    # Claude Code refuses a plugin hooks file without the "hooks" wrapper.
    assert set(document) <= {"description", "hooks"}
    assert document["hooks"] == expected, f"hooks.json drifted; regenerate: {REGENERATE_HOOKS}"


def test_plugin_mcp_server_is_the_entry_install_mcp_writes() -> None:
    mcp_install = _load("mcp_install")
    servers = _json(PLUGIN_DIR / ".mcp.json")["mcpServers"]
    # Claude Code suppresses a plugin server whose command a project's
    # .mcp.json already starts, which only holds while the launch spec matches.
    assert servers == {mcp_install.SERVER_NAME: mcp_install.server_entry()}


def test_plugin_name_is_the_one_the_hook_guard_checks() -> None:
    hooks = _load("hooks")
    manifest = _json(PLUGIN_DIR / ".claude-plugin" / "plugin.json")
    assert manifest["name"] == hooks.PLUGIN_NAME


def test_plugin_version_is_the_release_and_release_please_bumps_it() -> None:
    manifest = _json(PLUGIN_DIR / ".claude-plugin" / "plugin.json")
    release = _json(REPO_ROOT / ".release-please-manifest.json")["."]
    assert manifest["version"] == release
    extra = _json(REPO_ROOT / "release-please-config.json")["packages"]["."]["extra-files"]
    assert {
        "type": "json",
        "path": f"{PLUGIN_REL}/.claude-plugin/plugin.json",
        "jsonpath": "$.version",
    } in extra


def test_marketplace_lists_the_plugin_without_a_second_version() -> None:
    marketplace = _json(MARKETPLACE)
    manifest = _json(PLUGIN_DIR / ".claude-plugin" / "plugin.json")
    (entry,) = marketplace["plugins"]
    assert entry["name"] == manifest["name"]
    # Relative sources resolve from the marketplace root, the repo root here.
    assert entry["source"] == f"./{PLUGIN_REL}"
    assert (REPO_ROOT / entry["source"]).resolve() == PLUGIN_DIR.resolve()
    # plugin.json's version wins silently over an entry's, so a second copy
    # could only ever be wrong.
    assert "version" not in entry


def test_marketplace_name_gives_the_documented_install_id() -> None:
    # The docs say /plugin install neuralmind@neuralmind; the part after @ is
    # the marketplace's name field, not the repository's name.
    assert _json(MARKETPLACE)["name"] == "neuralmind"
