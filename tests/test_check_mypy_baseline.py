"""scripts/check_mypy_baseline.py: CI's Type Check job fails on any mypy error not in the baseline.

Stdlib only: mypy itself is replaced by canned output, so these run without it.
"""

from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_mypy_baseline.py"
_spec = importlib.util.spec_from_file_location("check_mypy_baseline", _SCRIPT)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

OUTPUT = """\
neuralmind/a.py:10: error: Returning Any from function declared to return "int"  [no-any-return]
neuralmind/a.py:12: note: See https://mypy.rtfd.io
neuralmind\\b.py:40: error: Name "x" already defined on line 3  [no-redef]
neuralmind/a.py:90: error: Returning Any from function declared to return "int"  [no-any-return]
Found 3 errors in 2 files (checked 2 source files)
"""


@pytest.fixture
def baseline(tmp_path, monkeypatch):
    path = tmp_path / "mypy-baseline.txt"
    monkeypatch.setattr(check, "BASELINE", path)
    monkeypatch.setattr(check, "ROOT", tmp_path)
    return path


def _mypy_says(monkeypatch, output):
    monkeypatch.setattr(check, "run_mypy", lambda: output)


def test_errors_are_parsed_and_notes_skipped():
    errors = check.parse(OUTPUT)
    assert [(path, line) for path, line, _ in errors] == [
        ("neuralmind/a.py", 10),
        ("neuralmind/b.py", 40),  # a Windows path, written with /
        ("neuralmind/a.py", 90),
    ]


def test_a_line_number_inside_a_message_doesnt_change_the_match():
    moved = check.fingerprint("neuralmind/b.py", 'Name "x" already defined on line 7  [no-redef]')
    original = check.fingerprint(
        "neuralmind/b.py", 'Name "x" already defined on line 3  [no-redef]'
    )
    assert moved == original


def test_the_same_error_twice_in_a_file_counts_twice(baseline, monkeypatch):
    # A baseline holding it once doesn't cover a second copy.
    _mypy_says(monkeypatch, OUTPUT)
    assert check.main(["--rebaseline"]) == 0
    lines = [line for line in baseline.read_text().splitlines() if not line.startswith("#")]
    assert len(lines) == 3
    one_less = "\n".join(lines[:1] + lines[2:])
    baseline.write_text(one_less + "\n")
    assert check.main([]) == 1


def test_matching_the_baseline_passes(baseline, monkeypatch, capsys):
    _mypy_says(monkeypatch, OUTPUT)
    check.main(["--rebaseline"])
    assert check.main([]) == 0
    assert "3 errors, all in the baseline" in capsys.readouterr().out


def test_a_new_error_fails_and_is_named_with_its_line(baseline, monkeypatch, capsys):
    _mypy_says(monkeypatch, OUTPUT)
    check.main(["--rebaseline"])
    extra = "neuralmind/c.py:5: error: Missing return statement  [return]\n"
    _mypy_says(monkeypatch, extra + OUTPUT)
    assert check.main([]) == 1
    out = capsys.readouterr().out
    assert "1 mypy error(s) not in the baseline" in out
    assert "neuralmind/c.py:5: Missing return statement" in out


def test_moving_a_known_error_to_another_line_still_passes(baseline, monkeypatch):
    _mypy_says(monkeypatch, OUTPUT)
    check.main(["--rebaseline"])
    _mypy_says(monkeypatch, OUTPUT.replace("a.py:10:", "a.py:11:").replace("line 3", "line 4"))
    assert check.main([]) == 0


def test_a_fixed_error_fails_until_the_baseline_is_lowered(baseline, monkeypatch, capsys):
    _mypy_says(monkeypatch, OUTPUT)
    check.main(["--rebaseline"])
    fixed = "\n".join(line for line in OUTPUT.splitlines() if "b.py" not in line)
    _mypy_says(monkeypatch, fixed)
    assert check.main([]) == 1
    assert "--update" in capsys.readouterr().out
    assert check.main(["--update"]) == 0
    assert check.main([]) == 0
    assert "# 2 errors" in baseline.read_text()


def test_update_wont_trade_a_fixed_error_for_new_ones(baseline, monkeypatch, capsys):
    # Fixing b.py's error while adding two in c.py: --update refuses and keeps the file.
    _mypy_says(monkeypatch, OUTPUT)
    check.main(["--rebaseline"])
    before = baseline.read_text()
    traded = "\n".join(line for line in OUTPUT.splitlines() if "b.py" not in line)
    traded = (
        "neuralmind/c.py:5: error: Missing return statement  [return]\n"
        "neuralmind/c.py:9: error: Missing return statement  [return]\n" + traded
    )
    _mypy_says(monkeypatch, traded)
    assert check.main(["--update"]) == 1
    assert "baseline is unchanged" in capsys.readouterr().out
    assert baseline.read_text() == before
    assert check.main(["--rebaseline"]) == 0  # an upgrade's new errors, on purpose
    assert check.main([]) == 0


def test_update_and_rebaseline_dont_combine():
    with pytest.raises(SystemExit):
        check.main(["--update", "--rebaseline"])


def test_mypy_that_doesnt_run_is_exit_2(baseline, monkeypatch):
    _mypy_says(monkeypatch, None)
    assert check.main([]) == 2


def test_compare_is_a_multiset_difference():
    new, fixed = check.compare(Counter({"a": 2, "b": 1}), Counter({"a": 1, "c": 1}))
    assert new == Counter({"a": 1, "b": 1})
    assert fixed == Counter({"c": 1})


def test_the_committed_baseline_parses():
    entries = check.read_baseline(_SCRIPT.parent / "mypy-baseline.txt")
    assert entries and all(entry.startswith("neuralmind/") for entry in entries)
