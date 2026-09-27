#!/usr/bin/env python3
"""End-to-end smoke test for the NeuralMind MCP server over stdio.

Spawns ``neuralmind-mcp`` exactly as an MCP client would (a child process
speaking newline-delimited JSON-RPC on stdin/stdout), then drives the four
messages every client sends first:

1. ``initialize``                 → must answer with ``serverInfo.name == "neuralmind"``
2. ``notifications/initialized``  → (no reply)
3. ``tools/list``                 → must list ``neuralmind_query``
4. ``tools/call``                 → must return ``content[0].text`` that parses as JSON

plus one call with a missing required argument, which must come back as an
``invalid_request`` error *inside* the result rather than as a transport-level
failure. That last check is what the MCP SDK 2.x migration lost: 1.x validated
arguments in the decorator, 2.x does not, and ``neuralmind.mcp_server`` now
does it itself.

Stdlib only, so the fresh-install CI job (a venv with no dev extras) can run it
against whichever ``mcp`` version the resolver picked. ``tests/test_mcp_transport.py``
wraps the same function under pytest. Exit code 0 on success, 1 on failure;
prints one line per step.

This exists because ``pip install neuralmind`` shipped a server that crashed on
startup for three weeks in 2026 (mcp 2.0.0 removed the decorator API) while the
CI smoke test only *imported* the module. Importing is not starting.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_TIMEOUT = 60.0


class SmokeFailureError(RuntimeError):
    """A step of the round-trip did not produce the expected reply."""


def _reader(stream, out: queue.Queue[str | None]) -> None:
    for line in stream:
        out.put(line)
    out.put(None)


def run_smoke(timeout: float = DEFAULT_TIMEOUT, project_path: str | None = None) -> dict[str, Any]:
    """Run the round-trip; return a summary dict; raise SmokeFailureError on any miss."""
    env = dict(os.environ)
    env.setdefault("NEURALMIND_ORT_THREADS", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    cmd = [sys.executable, "-c", "from neuralmind.mcp_server import main; main()"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    lines: queue.Queue[str | None] = queue.Queue()
    threading.Thread(target=_reader, args=(proc.stdout, lines), daemon=True).start()
    summary: dict[str, Any] = {"steps": []}

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
    summary["exit_code"] = proc.returncode
    return summary


def main(argv: list[str] | None = None) -> int:
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("mcp SDK not importable; nothing to smoke-test", file=sys.stderr)
        return 1
    try:
        summary = run_smoke()
    except SmokeFailureError as exc:
        print(f"MCP stdio smoke FAILED: {exc}", file=sys.stderr)
        return 1
    try:
        from importlib.metadata import version as _dist_version

        version: str | None = _dist_version("mcp")
    except Exception:  # pragma: no cover - metadata missing in odd installs
        version = None
    for step in summary["steps"]:
        print(f"[mcp-smoke] {step}")
    print(
        f"[mcp-smoke] OK — mcp {version or 'unknown'}, protocol {summary.get('protocolVersion')}, "
        f"{summary.get('tool_count')} tools, server exit {summary.get('exit_code')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
