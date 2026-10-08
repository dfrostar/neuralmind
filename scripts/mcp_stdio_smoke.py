#!/usr/bin/env python3
"""End-to-end smoke test for the NeuralMind MCP server over stdio.

Starts the server as an MCP client does (a child process speaking
newline-delimited JSON-RPC on stdin/stdout), then drives the four messages
every client sends first:

1. ``initialize``                 → must answer with ``serverInfo.name == "neuralmind"``
2. ``notifications/initialized``  → (no reply)
3. ``tools/list``                 → must list ``neuralmind_query``
4. ``tools/call``                 → must return ``content[0].text`` that parses as JSON

plus one call with a missing required argument, which must come back as an
``invalid_request`` error *inside* the result rather than as a transport-level
failure. That last check is what the MCP SDK 2.x migration lost: 1.x validated
arguments in the decorator, 2.x does not, and ``neuralmind.mcp_server`` now
does it itself.

The server is ``python -c "from neuralmind.mcp_server import main; main()"``
run with this interpreter, unless ``--entry-point`` is given. Then it is the
``neuralmind-mcp`` console script installed next to this interpreter, the
command MCP clients are configured with, and the fresh-install job passes it.
Only that tests the ``[project.scripts]`` declaration: ``python -c`` names its
own target, so an entry pointing at a function that doesn't exist installs
cleanly and passes, while the script clients run dies on startup. The script
is looked up next to the interpreter, not on PATH, where another
environment's ``neuralmind-mcp`` could answer.

Stdlib only, so the fresh-install CI job (a venv with no dev extras) can run it
against whichever ``mcp`` version the resolver picked. ``tests/test_mcp_transport.py``
wraps the same function under pytest. Exit code 0 on success, 1 on failure;
prints one line per step.

The server starts in an empty temporary directory, not the caller's. ``python
-c`` puts the working directory first on ``sys.path``, so a server started from
a checkout's root would import ``./neuralmind/`` instead of the installed
package, and the fresh-install job would test the source tree rather than the
wheel (Python 3.10 has no ``-P`` to switch that off). ``--require-wheel``, which
that job passes, also fails the run unless the server's ``neuralmind`` comes
from this interpreter's site-packages.

This exists because ``pip install neuralmind`` shipped a server that crashed on
startup for three weeks in 2026 (mcp 2.0.0 removed the decorator API) while the
CI smoke test only *imported* the module. Importing is not starting.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shlex
import subprocess
import sys
import sysconfig
import tempfile
import threading
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_TIMEOUT = 60.0
SERVER_CODE = "from neuralmind.mcp_server import main; main()"
# What pip installs for ``[project.scripts] neuralmind-mcp``.
SCRIPT_NAME = "neuralmind-mcp.exe" if sys.platform == "win32" else "neuralmind-mcp"
# Prints the file the server's ``import neuralmind`` loads, without importing it.
ORIGIN_CODE = (
    "import importlib.util as u; s = u.find_spec('neuralmind'); print(s.origin if s else '')"
)


class SmokeFailureError(RuntimeError):
    """A step of the round-trip did not produce the expected reply."""


def _reader(stream, out: queue.Queue[str | None]) -> None:
    for line in stream:
        out.put(line)
    out.put(None)


def _in_site_packages(path: str) -> bool:
    """Whether ``path`` is in this interpreter's site-packages: an installed
    wheel, not a source tree or an editable install."""
    if not path:
        return False
    resolved = Path(path).resolve()
    # A scheme can lack one of the two (get_path returns None): skip it.
    roots = [sysconfig.get_path(key) for key in ("purelib", "platlib")]
    return any(resolved.is_relative_to(Path(root).resolve()) for root in roots if root)


def console_script() -> Path:
    """The ``neuralmind-mcp`` console script installed next to this interpreter.

    ``sys.executable`` is not resolved: in a venv it can be a link to the base
    interpreter, whose directory holds that interpreter's scripts, not the venv's.
    """
    return Path(sys.executable).parent / SCRIPT_NAME


def run_smoke(
    timeout: float = DEFAULT_TIMEOUT,
    project_path: str | None = None,
    require_wheel: bool = False,
    entry_point: bool = False,
) -> dict[str, Any]:
    """Run the round-trip; return a summary dict; raise SmokeFailureError on any miss.

    The server runs in an empty temporary directory (see the module docstring),
    removed once it has exited. ``require_wheel`` fails before the round-trip
    unless the server's ``neuralmind`` comes from this interpreter's
    site-packages. ``entry_point`` starts the server with :func:`console_script`
    instead of ``python -c``.
    """
    with tempfile.TemporaryDirectory(
        prefix="neuralmind-smoke-", ignore_cleanup_errors=True
    ) as workdir:
        return _round_trip(workdir, timeout, project_path, require_wheel, entry_point)


def _round_trip(
    workdir: str,
    timeout: float,
    project_path: str | None,
    require_wheel: bool,
    entry_point: bool,
) -> dict[str, Any]:
    if entry_point:
        script = console_script()
        if not script.is_file():
            raise SmokeFailureError(f"{script.name} is not installed next to {sys.executable}")
        cmd = [str(script)]
    else:
        cmd = [sys.executable, "-c", SERVER_CODE]
    env = dict(os.environ)
    env.setdefault("NEURALMIND_ORT_THREADS", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    # Same interpreter, working directory and environment as the server, so the
    # same sys.path: this is the neuralmind the round-trip tests. The console
    # script runs this interpreter too, and differs only in putting its own
    # directory first on sys.path instead of the working directory; neither
    # directory holds a neuralmind.
    origin = subprocess.run(
        [sys.executable, "-c", ORIGIN_CODE],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    ).stdout.strip()
    if require_wheel and not _in_site_packages(origin):
        raise SmokeFailureError(
            f"the server would import neuralmind from {origin or '(not found)'}, "
            "not from this interpreter's site-packages"
        )
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
        cwd=workdir,
    )
    lines: queue.Queue[str | None] = queue.Queue()
    threading.Thread(target=_reader, args=(proc.stdout, lines), daemon=True).start()
    summary: dict[str, Any] = {"steps": [], "command": cmd, "neuralmind_origin": origin}

    def send(message: dict[str, Any]) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def recv(expect_id: int) -> dict[str, Any]:
        while True:
            try:
                line = lines.get(timeout=timeout)
            except queue.Empty as exc:
                raise SmokeFailureError(
                    f"no reply to request id={expect_id} within {timeout}s"
                ) from exc
            if line is None:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise SmokeFailureError(
                    f"server closed stdout before answering id={expect_id} "
                    f"(exit={proc.poll()}); stderr tail:\n{stderr[-2000:]}"
                )
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SmokeFailureError(f"non-JSON line on stdout: {line[:200]!r}") from exc
            if message.get("id") == expect_id:
                return message
            # Notifications or log messages from the server are allowed; skip them.

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "neuralmind-smoke", "version": "0"},
                },
            }
        )
        init = recv(1)
        result = init.get("result") or {}
        if (result.get("serverInfo") or {}).get("name") != "neuralmind":
            raise SmokeFailureError(f"unexpected initialize reply: {json.dumps(init)[:300]}")
        summary["protocolVersion"] = result.get("protocolVersion")
        summary["steps"].append("initialize ok")

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listing = recv(2)
        tools = [t.get("name") for t in (listing.get("result") or {}).get("tools", [])]
        if "neuralmind_query" not in tools:
            raise SmokeFailureError(f"tools/list did not include neuralmind_query: {tools}")
        summary["tool_count"] = len(tools)
        summary["steps"].append(f"tools/list ok ({len(tools)} tools)")

        with tempfile.TemporaryDirectory() as tmp:
            target = project_path or tmp
            send(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "neuralmind_stats", "arguments": {"project_path": target}},
                }
            )
            call = recv(3)
            content = (call.get("result") or {}).get("content") or []
            if not content or content[0].get("type") != "text":
                raise SmokeFailureError(
                    f"tools/call returned no text content: {json.dumps(call)[:300]}"
                )
            json.loads(content[0]["text"])  # must be the JSON string handle_tool_call produces
            summary["steps"].append("tools/call ok")

        send(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "neuralmind_query",
                    "arguments": {"project_path": "/nonexistent"},
                },
            }
        )
        bad = recv(4)
        bad_content = (bad.get("result") or {}).get("content") or []
        bad_payload: dict[str, Any] = {}
        if bad_content and bad_content[0].get("type") == "text":
            try:
                bad_payload = json.loads(bad_content[0]["text"])
            except json.JSONDecodeError:
                bad_payload = {}
        # Three acceptable shapes, one per layer that may catch it first:
        #   * a JSON-RPC ``error`` (protocol-level rejection);
        #   * mcp 1.x's own schema check: ``result.isError`` with a plain-text
        #     "Input validation error: 'question' is a required property";
        #   * mcp 2.x, which no longer validates, so ``handle_tool_call`` does and
        #     returns ``{"code": "invalid_request"}`` inside the text content.
        # A bare ``KeyError: 'question'`` string is none of these and fails.
        bad_result = bad.get("result") or {}
        sdk_validated = bool(bad_result.get("isError")) and bool(bad_content)
        if not (bad.get("error") or bad_payload.get("code") == "invalid_request" or sdk_validated):
            raise SmokeFailureError(
                "missing required argument was not reported as a validation error: "
                f"{json.dumps(bad)[:300]}"
            )
        layer = (
            "sdk"
            if sdk_validated and bad_payload.get("code") != "invalid_request"
            else ("protocol" if bad.get("error") else "server")
        )
        summary["validation_layer"] = layer
        summary["steps"].append(f"tools/call missing-argument → validation error ok ({layer})")
    finally:
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
            proc.wait()  # reaped before run_smoke removes its working directory
    summary["exit_code"] = proc.returncode
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the NeuralMind MCP server over stdio.")
    parser.add_argument(
        "--require-wheel",
        action="store_true",
        help="fail unless the server imports neuralmind from this interpreter's "
        "site-packages (an installed wheel, not a checkout or an editable install)",
    )
    parser.add_argument(
        "--entry-point",
        action="store_true",
        help=f"start the server with the {SCRIPT_NAME} console script installed next to "
        "this interpreter, as MCP clients do, instead of python -c; fails if it isn't there",
    )
    args = parser.parse_args(argv)
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("mcp SDK not importable; nothing to smoke-test", file=sys.stderr)
        return 1
    try:
        summary = run_smoke(require_wheel=args.require_wheel, entry_point=args.entry_point)
    except SmokeFailureError as exc:
        print(f"MCP stdio smoke FAILED: {exc}", file=sys.stderr)
        return 1
    try:
        from importlib.metadata import version as _dist_version

        version: str | None = _dist_version("mcp")
    except Exception:  # pragma: no cover - metadata missing in odd installs
        version = None
    print(f"[mcp-smoke] server: {shlex.join(summary['command'])}")
    print(f"[mcp-smoke] server's neuralmind: {summary['neuralmind_origin']}")
    for step in summary["steps"]:
        print(f"[mcp-smoke] {step}")
    print(
        f"[mcp-smoke] OK — mcp {version or 'unknown'}, protocol {summary.get('protocolVersion')}, "
        f"{summary.get('tool_count')} tools, server exit {summary.get('exit_code')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
