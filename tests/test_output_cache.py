"""Tests for neuralmind.output_cache — single-slot bash output recovery cache."""

from __future__ import annotations

import json

from neuralmind.output_cache import (
    cache_path,
    read_last_output,
    write_last_output,
)
from tests.secret_fixtures import ANTHROPIC_KEY, AWS_KEY_ID, GITHUB_TOKEN


class TestWriteLastOutput:
    def test_round_trip(self, tmp_path):
        """A simple write/read round-trip preserves all fields."""
        target = write_last_output(
            tmp_path,
            stdout="line one\nline two\n",
            stderr="warning: x\n",
            exit_code=0,
            command="echo hello",
        )
        assert target is not None
        assert target == cache_path(tmp_path)
        assert target.exists()

        data = read_last_output(tmp_path)
        assert data is not None
        assert data["stdout"] == "line one\nline two\n"
        assert data["stderr"] == "warning: x\n"
        assert data["exit_code"] == 0
        assert data["command"] == "echo hello"
        assert isinstance(data["ts"], float)

    def test_creates_dotdir_if_missing(self, tmp_path):
        """The .neuralmind directory is created on first write."""
        assert not (tmp_path / ".neuralmind").exists()
        write_last_output(tmp_path, "x", "", 0)
        assert (tmp_path / ".neuralmind").is_dir()

    def test_overwrites_previous(self, tmp_path):
        """Single-slot: a second write replaces the first."""
        write_last_output(tmp_path, "first run", "", 0, command="cmd1")
        write_last_output(tmp_path, "second run", "", 1, command="cmd2")
        data = read_last_output(tmp_path)
        assert data["stdout"] == "second run"
        assert data["exit_code"] == 1
        assert data["command"] == "cmd2"

    def test_size_cap_truncates_oversized(self, tmp_path):
        """Payloads above the cap are truncated keeping head + tail."""
        big = "x" * 100_000
        write_last_output(tmp_path, big, "", 0, max_bytes=10_000)
        data = read_last_output(tmp_path)
        # The stored stdout is at or under the cap (plus the small elision marker).
        assert len(data["stdout"]) < len(big)
        # Head + tail should both be preserved — first and last 'x' survive.
        assert data["stdout"].startswith("x")
        assert data["stdout"].endswith("x")
        # An elision marker tells the reader what happened.
        assert "elided by output cache" in data["stdout"]

    def test_size_cap_splits_between_streams(self, tmp_path):
        """When both streams contribute to oversize, both get budget."""
        big_out = "a" * 50_000
        big_err = "b" * 50_000
        write_last_output(tmp_path, big_out, big_err, 1, max_bytes=10_000)
        data = read_last_output(tmp_path)
        assert "a" in data["stdout"]
        assert "b" in data["stderr"]
        # Each stream got non-trivial budget (the 1KB floor).
        assert len(data["stdout"]) >= 1024
        assert len(data["stderr"]) >= 1024

    def test_command_truncated(self, tmp_path):
        """Pathological command lines (huge one-liners) are capped."""
        write_last_output(tmp_path, "ok", "", 0, command="x" * 5000)
        data = read_last_output(tmp_path)
        assert len(data["command"]) == 500

    def test_disabled_via_env(self, tmp_path, monkeypatch):
        """NEURALMIND_OUTPUT_CACHE=0 disables the cache entirely."""
        monkeypatch.setenv("NEURALMIND_OUTPUT_CACHE", "0")
        result = write_last_output(tmp_path, "ignored", "", 0)
        assert result is None
        assert not cache_path(tmp_path).exists()

    def test_atomic_write_does_not_leave_tmp_files(self, tmp_path):
        """The atomic write should clean up after itself — no .tmp leftovers."""
        write_last_output(tmp_path, "ok", "", 0)
        tmp_leftovers = list((tmp_path / ".neuralmind").glob(".last_output.*.tmp"))
        assert tmp_leftovers == []


class TestReadLastOutput:
    def test_missing_file_returns_none(self, tmp_path):
        assert read_last_output(tmp_path) is None

    def test_corrupt_json_returns_none(self, tmp_path):
        target = cache_path(tmp_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{not valid json")
        assert read_last_output(tmp_path) is None

    def test_wrong_shape_returns_none(self, tmp_path):
        """JSON arrays / non-dict payloads → None (defensive)."""
        target = cache_path(tmp_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps([1, 2, 3]))
        assert read_last_output(tmp_path) is None


class TestSecretRedaction:
    """The cache records raw command output, so it must scrub credentials.

    Without this, `printenv` or a curl with an Authorization header lands a
    live key in a plaintext file inside the project.
    """

    def test_secret_in_stdout_is_redacted(self, tmp_path):
        write_last_output(
            tmp_path,
            stdout=f"ANTHROPIC_API_KEY={ANTHROPIC_KEY}\n",
            stderr="",
            exit_code=0,
            command="printenv",
        )
        data = read_last_output(tmp_path)
        assert ANTHROPIC_KEY not in data["stdout"]
        assert "[REDACTED:anthropic-api-key]" in data["stdout"]
        assert data["redacted"] == ["anthropic-api-key"]

    def test_secret_in_stderr_is_redacted(self, tmp_path):
        write_last_output(
            tmp_path,
            stdout="",
            stderr=f"auth failed for {AWS_KEY_ID}\n",
            exit_code=1,
        )
        data = read_last_output(tmp_path)
        assert AWS_KEY_ID not in data["stderr"]
        assert data["redacted"] == ["aws-access-key-id"]

    def test_secret_in_command_is_redacted(self, tmp_path):
        """The command line leaks too — `curl -H "Authorization: Bearer ..."`."""
        write_last_output(
            tmp_path,
            stdout="ok\n",
            stderr="",
            exit_code=0,
            command=f'curl -H "Authorization: Bearer {GITHUB_TOKEN}" u',
        )
        data = read_last_output(tmp_path)
        assert GITHUB_TOKEN not in data["command"]
        assert "github-token" in data["redacted"]

    def test_raw_file_on_disk_holds_no_secret(self, tmp_path):
        """Belt and braces: assert against the bytes, not the parsed payload."""
        secret = ANTHROPIC_KEY
        write_last_output(tmp_path, stdout=f"KEY={secret}\n", stderr="", exit_code=0)
        assert secret not in cache_path(tmp_path).read_text()

    def test_clean_output_is_untouched(self, tmp_path):
        write_last_output(tmp_path, stdout="7 passed\n", stderr="", exit_code=0)
        data = read_last_output(tmp_path)
        assert data["stdout"] == "7 passed\n"
        assert data["redacted"] == []

    def test_redaction_can_be_disabled(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_OUTPUT_REDACT", "0")
        write_last_output(tmp_path, stdout=f"KEY={AWS_KEY_ID}\n", stderr="", exit_code=0)
        assert AWS_KEY_ID in read_last_output(tmp_path)["stdout"]

    def test_secret_survives_nothing_under_truncation(self, tmp_path):
        """Redaction runs before truncation, so no secret hides in a kept slice."""
        secret = AWS_KEY_ID
        noise = "x" * 5000
        write_last_output(
            tmp_path,
            stdout=f"{secret}\n{noise}\n{secret}\n",
            stderr="",
            exit_code=0,
            max_bytes=2048,
        )
        assert secret not in cache_path(tmp_path).read_text()

    def test_cache_directory_is_self_ignoring(self, tmp_path):
        """Writing the cache must also drop the .gitignore guard."""
        write_last_output(tmp_path, stdout="hi\n", stderr="", exit_code=0)
        guard = tmp_path / ".neuralmind" / ".gitignore"
        assert guard.exists()
        assert "*" in guard.read_text().splitlines()
