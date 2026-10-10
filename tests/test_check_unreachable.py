"""scripts/check_unreachable.py: the guard against code stranded after a return.

Stdlib-only, like the other `scripts/check_*.py` guards.
"""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_unreachable", ROOT / "scripts" / "check_unreachable.py"
)
check_unreachable = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_unreachable)


def _find(src: str) -> list[tuple[int, str]]:
    return check_unreachable.find_unreachable(textwrap.dedent(src))


def test_flags_the_doctor_regression_shape():
    # v0.55.0: a helper inserted above cmd_doctor's last lines left them
    # after the helper's `return checks`.
    src = """
    def _tier2_doctor_checks(args):
        checks = []
        return checks

        if status == doctor.FAIL:
            sys.exit(1)
    """
    assert _find(src) == [(6, "return checks")]


def test_flags_code_after_sys_exit_raise_and_loop_jumps():
    src = """
    import sys

    def f(items):
        for item in items:
            if item:
                continue
                print("never")
            break
            print("never")
        try:
            raise ValueError
            print("never")
        except ValueError:
            sys.exit(2)
            print("never")
    """
    assert [term for _, term in _find(src)] == [
        "continue",
        "break",
        "raise ValueError",
        "sys.exit(2)",
    ]


def test_branches_that_both_return_are_not_flagged():
    src = """
    def f(x):
        if x:
            return 1
        else:
            return 2

    def g(x):
        if x:
            return 1
        return 2
    """
    assert _find(src) == []


def test_the_repository_has_no_unreachable_code(capsys):
    assert check_unreachable.main([]) == 0, capsys.readouterr().out
