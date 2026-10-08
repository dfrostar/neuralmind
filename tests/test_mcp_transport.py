"""Real stdio round-trip against ``neuralmind-mcp`` (Phase 0 of the perf spec).

The unit tests in ``test_mcp_server.py`` drive the handlers with a fake
``Server``; this one spawns the actual entry point and speaks JSON-RPC to it,
so a dropped SDK API (mcp 2.0.0 removed ``Server.list_tools``) fails here
instead of on a user's first ``pip install``. The same function runs in the
fresh-install CI job via ``scripts/mcp_stdio_smoke.py`` on both SDK lines,
against the installed wheel (``--require-wheel``).
"""

from __future__ import annotations

import importlib.util
import sys
import sysconfig
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = REPO_ROOT / "scripts" / "mcp_stdio_smoke.py"

try:
    import mcp  # noqa: F401

    MCP_INSTALLED = True
except ImportError:  # pragma: no cover - exercised only on stripped installs
    MCP_INSTALLED = False


def _load_smoke():
    spec = importlib.util.spec_from_file_location("mcp_stdio_smoke", SMOKE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
@pytest.mark.skipif(not MCP_INSTALLED, reason="mcp SDK not installed")
def test_mcp_server_answers_initialize_list_and_call_over_stdio(
    temp_project, tmp_path, monkeypatch
):
    # Called from a directory whose ``neuralmind`` refuses to import, as the
    # fresh-install job calls it from a checkout's root: the server must start
    # clear of the caller's working directory, or that job tests the source
    # tree instead of the wheel.
    (tmp_path / "neuralmind").mkdir()
    (tmp_path / "neuralmind" / "__init__.py").write_text(
        "raise ImportError('imported from the working directory')\n"
    )
    monkeypatch.chdir(tmp_path)

    smoke = _load_smoke()
    summary = smoke.run_smoke(timeout=90.0, project_path=str(temp_project))
    # An empty origin would resolve to the working directory and fail below
    # with a misleading path.
    assert summary["neuralmind_origin"], summary
    origin = Path(summary["neuralmind_origin"]).resolve()
    assert not origin.is_relative_to(tmp_path.resolve()), origin
    assert summary["tool_count"] >= 20
    assert summary["exit_code"] == 0, summary
    assert any(step.startswith("tools/call ok") for step in summary["steps"])
    assert any("validation error ok" in step for step in summary["steps"])
    assert summary["validation_layer"] in {"server", "sdk", "protocol"}


@pytest.mark.skipif(not MCP_INSTALLED, reason="mcp SDK not installed")
def test_require_wheel_fails_unless_the_server_imports_from_site_packages(
    tmp_path, monkeypatch, capsys
):
    """``--require-wheel`` (the fresh-install job) stops before any server
    starts when the server would import neuralmind from a source tree."""
    smoke = _load_smoke()
    purelib = Path(sysconfig.get_path("purelib"))
    assert smoke._in_site_packages(str(purelib / "neuralmind" / "__init__.py"))
    assert not smoke._in_site_packages(str(REPO_ROOT / "neuralmind" / "__init__.py"))

    (tmp_path / "neuralmind").mkdir()
    (tmp_path / "neuralmind" / "__init__.py").write_text("")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))  # ahead of site-packages
    assert smoke.main(["--require-wheel"]) == 1
    err = capsys.readouterr().err
    assert str(tmp_path / "neuralmind") in err and "site-packages" in err, err


def test_validate_tool_arguments_restores_schema_checks():
    """The 2.x SDK stopped validating; ``handle_tool_call`` must do it itself."""
    from neuralmind.mcp_server import handle_tool_call, validate_tool_arguments

    assert (
        validate_tool_arguments("neuralmind_query", {"project_path": "/p", "question": "q"}) is None
    )
    assert "question" in validate_tool_arguments("neuralmind_query", {"project_path": "/p"})
    assert "type string" in validate_tool_arguments(
        "neuralmind_query", {"project_path": "/p", "question": 3}
    )
    assert "type integer" in validate_tool_arguments(
        "neuralmind_search", {"project_path": "/p", "query": "x", "n": True}
    )
    assert (
        validate_tool_arguments("neuralmind_search", {"project_path": "/p", "query": "x", "n": 5})
        is None
    )
    assert validate_tool_arguments("not_a_tool", {"anything": 1}) is None
    assert "JSON object" in validate_tool_arguments("neuralmind_stats", ["not", "a", "dict"])

    import json

    reply = json.loads(handle_tool_call("neuralmind_query", {"project_path": "/p"}))
    assert reply["code"] == "invalid_request"
    assert "question" in reply["error"]
    # The pre-existing project_path message is preserved verbatim.
    reply = json.loads(handle_tool_call("neuralmind_query", {"question": "q"}))
    assert reply == {"error": "project_path is required", "code": "invalid_request"}


def test_site_packages_check_skips_a_scheme_path_that_is_none(monkeypatch):
    smoke = _load_smoke()
    purelib = sysconfig.get_path("purelib")
    real = sysconfig.get_path
    monkeypatch.setattr(
        smoke.sysconfig, "get_path", lambda key: None if key == "platlib" else real(key)
    )
    assert smoke._in_site_packages(str(Path(purelib) / "neuralmind" / "__init__.py"))
    assert not smoke._in_site_packages(str(Path.cwd() / "neuralmind" / "__init__.py"))
