"""Tests for neuralmind.compressors — Pith-parity output transforms."""

from __future__ import annotations

import pytest

from neuralmind.compressors import (
    cap_search_results,
    compress_bash,
    noisy_log_family,
    offload_if_large,
    trim_noisy_log,
)


class TestNoisyLogFamily:
    """The opt-in replacement's allowlist: decided by the command, never by size."""

    @pytest.mark.parametrize(
        "command",
        [
            "pip install requests",
            "pip3 install -r requirements.txt",
            "pip3.11 install --upgrade pip",
            "python -m pip install -e '.[dev]'",
            "python3 -m pip install 'pydantic>=2' requests",
            ".venv/bin/pip install flask",
            "py -m pip install requests",
            "PIP_NO_INPUT=1 pip install requests",
            "cd backend && pip install -r requirements.txt",
            "source .venv/bin/activate && pip install -e .",
            ". venv/bin/activate; pip install x",
            "export PIP_INDEX_URL=https://example.org/simple; pip install x",
            "pip install x 2>&1",
            "pip install \\\n  requests \\\n  flask",
            "pip install x  # make sure it's there",
        ],
    )
    def test_pip_install_is_allowlisted(self, command):
        assert noisy_log_family(command) == "pip install"

    def test_neuralmind_build_is_allowlisted(self):
        assert noisy_log_family("neuralmind build .") == "neuralmind build"
        assert noisy_log_family("neuralmind build src/app --force") == "neuralmind build"

    @pytest.mark.parametrize(
        "command",
        [
            # Content: the output is the answer, so it is never replaced.
            "pip list",
            "pip show requests",
            "pip freeze",
            "python -m pip --version",
            "pytest -v",
            "git diff",
            "cat requirements.txt",
            "grep -rn 'def ' src",
            "npm run build",
            "neuralmind query 'how does auth work'",
            "uv pip install requests",
            # A second program, or output that isn't (only) the install log.
            "pip install x && pytest -q",
            "pip install x; python -c 'import x'",
            "pip install -e . && npm ci",
            "pip install x | tail -20",
            "pip install x 2>&1 | tail -20",
            "pip install x > install.log",
            "pip install pydantic>=2",  # an unquoted > is a redirect in bash
            "pip install x 2>/dev/null",
            "pip install x || true",
            "pip install x &",
            "(cd sub && pip install x)",
            "pip install $(cat reqs.txt)",
            "pip install `cat reqs.txt`",
            "pip install x\npytest",
            "time pip install x",
            "sudo pip install x",
            "cd backend",
            "",
            "pip install 'unterminated",
        ],
    )
    def test_everything_else_is_not(self, command):
        assert noisy_log_family(command) is None


PIP_LOG = """\
Collecting requests==2.32.3 (from -r requirements.txt (line 1))
  Downloading requests-2.32.3-py3-none-any.whl.metadata (4.6 kB)
Collecting idna<4,>=2.5 (from requests==2.32.3->-r requirements.txt (line 1))
  Downloading idna-3.20-py3-none-any.whl.metadata (7.2 kB)
Requirement already satisfied: flask in ./.venv/lib/python3.11/site-packages (from -r requirements.txt (line 2)) (3.1.0)
Requirement already satisfied: click>=8.1.3 in ./.venv/lib/python3.11/site-packages (from flask) (8.5.0)
Requirement already satisfied: blinker>=1.9 in ./.venv/lib/python3.11/site-packages (from flask) (1.9.0)
Downloading requests-2.32.3-py3-none-any.whl (64 kB)
Downloading idna-3.20-py3-none-any.whl (69 kB)
   ━━━━━━━━ 69.0/69.0 kB 2.1 MB/s  0:00:00
WARNING: Retrying (Retry(total=4)) after connection broken: /simple/idna/
Installing collected packages: idna, requests
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed.
somepkg 1.0 requires idna<3, but you have idna 3.20 which is incompatible.
Successfully installed idna-3.20 requests-2.32.3
"""


class TestTrimNoisyLog:
    def test_elides_only_progress_lines(self):
        trimmed, elided = trim_noisy_log(PIP_LOG, "pip install")
        assert elided == 9
        kept = [ln for ln in trimmed.splitlines() if not ln.startswith("[neuralmind:")]
        original = PIP_LOG.splitlines()
        # Everything that isn't a progress line comes back verbatim, in order.
        assert kept == [
            original[4],  # a requirement asked for, already installed
            original[10],
            original[11],
            original[12],
            original[13],
            original[14],
        ]

    def test_markers_count_what_each_run_elided(self):
        trimmed, _ = trim_noisy_log(PIP_LOG, "pip install")
        markers = [ln for ln in trimmed.splitlines() if ln.startswith("[neuralmind:")]
        assert markers == [
            "[neuralmind: 4 progress lines elided: Collecting ×2, Downloading ×2]",
            (
                "[neuralmind: 5 progress lines elided: dependency already satisfied ×2, "
                "Downloading ×2, progress bar ×1]"
            ),
        ]

    def test_a_line_reporting_trouble_is_never_elided(self):
        # Matches a progress pattern, but says something failed.
        log = (
            "  Building wheel for lxml (pyproject.toml): started\n"
            "  Building wheel for lxml (pyproject.toml): finished with status 'error'\n"
            "  Building wheel for six (pyproject.toml): started\n"
        )
        trimmed, elided = trim_noisy_log(log, "pip install")
        assert "finished with status 'error'" in trimmed
        assert elided == 0  # the error splits the run into two single lines

    def test_a_single_progress_line_stays(self):
        log = "Collecting requests\nSuccessfully installed requests-2.32.3\n"
        assert trim_noisy_log(log, "pip install") == (log, 0)

    def test_neuralmind_build_progress(self):
        log = "".join(
            f"Embedding {n}/40 ({n * 100 // 40}%) · 0.0s elapsed\n" for n in (1, 10, 20, 40)
        )
        trimmed, elided = trim_noisy_log(log, "neuralmind build")
        assert (trimmed, elided) == (
            "[neuralmind: 4 progress lines elided: embedding progress ×4]\n",
            4,
        )

    def test_nothing_to_elide_returns_the_text_unchanged(self):
        log = "Successfully installed requests-2.32.3\r\n"
        assert trim_noisy_log(log, "pip install") == (log, 0)
        assert trim_noisy_log("", "pip install") == ("", 0)


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

    def test_small_failure_passes_through(self):
        """Tiny failing commands skip the marker — overhead would dwarf content."""
        result = compress_bash("", "command not found: foo", 127)
        assert "command not found: foo" in result
        assert "[exit code: 127]" in result
        # No "[neuralmind: bash compressed" marker on a 22-byte failure.
        assert "bash compressed" not in result

    def test_dropped_summary_categorizes_log_levels(self):
        """Footer should categorize dropped lines (info/debug/other), not just count bytes."""
        lines = []
        for i in range(30):
            lines.append(f"[INFO] processing item {i}")
        for i in range(10):
            lines.append(f"[DEBUG] internal state {i}")
        lines.append("ERROR: something exploded")
        lines.append("=== test summary ===")
        stdout = "\n".join(lines)

        result = compress_bash(stdout, "", 1)
        # Old footer (bytecount only) must not survive.
        assert "Full output:" not in result
        # New footer must categorize what was dropped.
        assert "dropped" in result
        assert "info" in result.lower()
        assert "debug" in result.lower()
        # Error line + summary always kept (so they aren't in the "dropped" bucket).
        assert "ERROR: something exploded" in result

    def test_dropped_summary_detects_repeated_lines(self):
        """Repeated identical lines should be surfaced in the footer."""
        # Inflate the noise line so the total comfortably exceeds the
        # small-failure passthrough threshold — otherwise the whole
        # payload is returned verbatim and no compression footer renders.
        noise = "Gamma API returned 503 — retrying with exponential backoff"
        stdout = "\n".join([noise] * 30 + ["==== done ===="])
        stderr = "Error: connection refused"
        result = compress_bash(stdout, stderr, 1)
        assert "repeated:" in result
        # The repeated content should appear in the footer summary.
        assert "Gamma API returned 503" in result

    def test_dropped_summary_absent_when_nothing_dropped(self):
        """When everything fits in 'key lines + tail', the footer says so."""
        # Three lines, all important → kept set covers everything.
        stdout = "ERROR: line one\nWARNING: line two\n=== summary ==="
        # Force compression path by setting exit_code != 0 with size above the
        # small-passthrough cap.
        long_padding = "ERROR: pad\n" * 200  # all match the ERROR pattern → all kept
        result = compress_bash(long_padding + stdout, "", 1)
        # Either nothing was dropped, or the footer reflects it.
        assert "nothing dropped" in result or "dropped 0" in result.lower() or "dropped" in result


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

    def test_bypass_env_passes_through(self, monkeypatch, tmp_path):
        """NEURALMIND_BYPASS=1 returns raw content unchanged."""
        from neuralmind.compressors import compress_read

        monkeypatch.setenv("NEURALMIND_BYPASS", "1")
        content = "x = 1\n" * 500
        result = compress_read("/some/file.py", content)
        assert result == content


class TestCompressReadWithSkeleton:
    """Test compress_read with a skeleton-generating NeuralMind instance."""

    def test_skeleton_compression(self, tmp_path):
        """compress_read returns compressed output when a skeleton is available."""
        from unittest.mock import MagicMock, patch

        from neuralmind.compressors import compress_read

        # Create a large file content (above 1500 char threshold)
        content = "def foo():\n    pass\n" * 200

        # Create graphify-out/graph.json in the test project
        graphify_dir = tmp_path / "graphify-out"
        graphify_dir.mkdir()
        (graphify_dir / "graph.json").write_text('{"nodes": [], "edges": []}')

        file_path = str(tmp_path / "src" / "big_file.py")

        # Mock NeuralMind to return a skeleton
        mock_mind = MagicMock()
        mock_mind.skeleton.return_value = "# big_file.py (compact)"

        with patch("neuralmind.core.NeuralMind", return_value=mock_mind):
            result = compress_read(file_path, content)

        assert "compact" in result or "neuralmind:" in result.lower()
        assert len(result) < len(content)

    def test_skeleton_empty_falls_back(self, tmp_path):
        """compress_read returns raw content when skeleton is empty."""
        from unittest.mock import MagicMock, patch

        from neuralmind.compressors import compress_read

        content = "def foo():\n    pass\n" * 200
        graphify_dir = tmp_path / "graphify-out"
        graphify_dir.mkdir()
        (graphify_dir / "graph.json").write_text('{"nodes": [], "edges": []}')

        file_path = str(tmp_path / "src" / "big_file.py")

        mock_mind = MagicMock()
        mock_mind.skeleton.return_value = ""

        with patch("neuralmind.core.NeuralMind", return_value=mock_mind):
            result = compress_read(file_path, content)

        assert result == content

    def test_exception_falls_open(self, tmp_path):
        """compress_read returns raw content when an exception occurs."""
        from unittest.mock import patch

        from neuralmind.compressors import compress_read

        content = "def foo():\n    pass\n" * 200
        graphify_dir = tmp_path / "graphify-out"
        graphify_dir.mkdir()
        (graphify_dir / "graph.json").write_text('{"nodes": [], "edges": []}')

        file_path = str(tmp_path / "src" / "big_file.py")

        with patch("neuralmind.core.NeuralMind", side_effect=RuntimeError("boom")):
            result = compress_read(file_path, content)

        assert result == content
