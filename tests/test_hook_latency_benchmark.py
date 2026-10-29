"""The hook-latency benchmark times the hook, not a failed start (tests/benchmark/hook_latency.py)."""

from __future__ import annotations

import os
import stat
import sys

import pytest

from tests.benchmark import hook_latency


def test_a_child_that_fails_is_an_error_not_a_sample():
    with pytest.raises(RuntimeError, match="exited with status 3"):
        hook_latency._child(sys.executable, "-c", "raise SystemExit(3)", env=dict(os.environ))


@pytest.mark.skipif(sys.platform == "win32", reason="a shell-script interpreter")
def test_an_interpreter_without_safe_path_runs_without_it(tmp_path, monkeypatch):
    # Python 3.10 refuses -P: the benchmark must run it without, not time its error.
    fake = tmp_path / "python3.10"
    fake.write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do [ "$a" = "-P" ] && { echo "Unknown option: -P" >&2; exit 2; }; done\n'
        f'exec "{sys.executable}" "$@"\n'
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(hook_latency, "_SAFE_PATH", {})
    out, seconds = hook_latency._child(
        str(fake), "-c", "import os; print(os.listdir('.'))", env=dict(os.environ)
    )
    # Run from an empty directory, so no checkout sits first on sys.path.
    assert out.strip() == "[]"
    assert seconds > 0
    assert hook_latency._SAFE_PATH == {str(fake): False}
