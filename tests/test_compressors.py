"""Tests for neuralmind.compressors — Pith-parity output transforms."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from neuralmind.compressors import (
    cap_search_results,
    compress_bash,
    offload_if_large,
)


class TestCompressBash:
    def test_empty_output(self):
        result = compress_bash("", "", 0)
        assert "empty" in result.lower() or result == "(empty output)"

    def test_small_successful_passes_through(self):
        """Small clean output shouldn't be modified."""
        stdout = "hello\nworld\n"
        result = compress_bash(stdout, "", 0)
        assert "hello" in result and "world" in result
        # No compression marker on clean short output
        assert "[neuralmind:" not in result

    def test_verbose_pytest_compressed(self):
        """A long pytest-style output should be compressed."""
        stdout = "\n".join(
            [f"tests/test_{i}.py::test_thing PASSED" for i in range(200)]
            + ["===== 200 passed, 0 failed ====="]
        )
        result = compress_bash(stdout, "", 0)
        # Summary line preserved
        assert "200 passed" in result
        # Compression marker present
        assert "[neuralmind:" in result

    def test_errors_preserved(self):
        stdout = "running tests\n" * 100
        stderr = "ERROR: test_foo failed with IndexError"
        result = compress_bash(stdout, stderr, 1)
        assert "ERROR" in result
        assert "exit=1" in result

    def test_exit_code_captured(self):
        result = compress_bash("stdout line 1\n" * 100, "", 127)
        assert "exit=127" in result

    def test_bypass_env(self, monkeypatch):
        """NEURALMIND_BYPASS=1 should still pass through shorter outputs."""
        monkeypatch.setenv("NEURALMIND_BYPASS", "1")
        # compress_bash doesn't check the env (it's the hook layer that does)
        # but tiny successful bash still passes through
        result = compress_bash("short output", "", 0)
        assert "short output" in result


class TestCapSearchResults:
    def test_under_limit_unchanged(self):
        """Output with fewer matches than the cap is returned as-is."""
        output = "\n".join(f"file_{i}.py:10: match" for i in range(5))
        result = cap_search_results(output, max_matches=25)
        assert result == output

    def test_over_limit_truncated(self):
        """Output with more matches than cap gets truncated with summary."""
        output = "\n".join(f"file_{i}.py:10: match" for i in range(50))
        result = cap_search_results(output, max_matches=25)
        assert "capped at 25" in result
        assert "25 more hidden" in result
        # First 25 are preserved
        assert "file_0.py" in result
        assert "file_24.py" in result
        # Should not contain later matches
        assert "file_49.py" not in result

    def test_empty_input(self):
        assert cap_search_results("") == ""

    def test_bypass_env(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_BYPASS", "1")
        output = "\n".join(f"match_{i}" for i in range(100))
        result = cap_search_results(output, max_matches=5)
        # Bypass returns original
        assert result == output


class TestOffloadIfLarge:
    def test_small_content_not_offloaded(self):
        content = "a" * 500
        msg, path = offload_if_large(content, threshold=10_000)
        assert msg == content
        assert path is None

    def test_large_content_offloaded(self, tmp_path, monkeypatch):
        """Large content should be written to tmp and return a pointer."""
        content = "x" * 20_000
        msg, path = offload_if_large(content, threshold=10_000)
        assert path is not None
        assert path.exists()
        assert "offloaded" in msg
        assert str(path) in msg
        # Verify file contains the full content
        assert path.read_text() == content
        # Cleanup
        path.unlink(missing_ok=True)

    def test_bypass_env(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_BYPASS", "1")
        content = "x" * 20_000
        msg, path = offload_if_large(content, threshold=1000)
        assert msg == content
        assert path is None


class TestCompressReadBasic:
    """compress_read needs a built graph; we test the fail-open behavior here."""

    def test_no_graph_passes_through(self, tmp_path):
        """Without an indexed project, raw content is returned unchanged."""
        from neuralmind.compressors import compress_read

        fake_file = tmp_path / "foo.py"
        fake_file.write_text("# a file\n" * 500)
        content = fake_file.read_text()

        result = compress_read(str(fake_file), content)
        # No graph → returns original
        assert result == content

    def test_small_file_passes_through(self, tmp_path):
        """Files under the threshold aren't compressed even with a graph."""
        from neuralmind.compressors import compress_read

        tiny = "x = 1\n"
        result = compress_read("/nonexistent/foo.py", tiny)
        assert result == tiny
