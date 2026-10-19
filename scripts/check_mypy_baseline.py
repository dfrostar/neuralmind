#!/usr/bin/env python3
"""Fail when mypy finds an error that isn't in the baseline, or the baseline lists one it no longer finds.

mypy reported over 300 errors when it was made a check, too many to fix before
it could block a merge, so CI ran it with ``continue-on-error`` and the count
could only grow. This check makes it a ratchet instead: every error mypy
reports today is listed in ``scripts/mypy-baseline.txt``, CI fails on any
error not listed there, and it fails too when a listed error is gone, so the
file is lowered in the same change that fixes one. The count can only go down.

An error is matched by file, message and error code, not by line number, so
editing a file doesn't move its known errors out of the baseline. A ``line N``
inside a message (``already defined on line 40``) is ignored for the same
reason.

The baseline is only as stable as what mypy checks against: mypy is pinned in
CI, but a dependency release that adds or removes type hints can change the
list. When that happens, the new or vanished errors name the dependency's
types; refresh the baseline in its own commit, saying which upgrade changed it.

Usage:
    python scripts/check_mypy_baseline.py            # check (CI)
    python scripts/check_mypy_baseline.py --update   # rewrite the baseline after fixing errors

Exit codes: 0 matches the baseline, 1 new or fixed errors, 2 mypy didn't run.
"""

from __future__ import annotations

import argparse
import re
import subprocess  # nosec B404 - runs mypy, a fixed argument list
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "mypy-baseline.txt"
# The Type Check job's arguments; the rest of the configuration is
# [tool.mypy] in pyproject.toml.
MYPY_ARGS = [
    "neuralmind",
    "--ignore-missing-imports",
    "--disable-error-code=no-untyped-def",
    "--implicit-optional",
]
_ERROR = re.compile(r"^(?P<path>[^:\n]+):(?P<line>\d+)(?::\d+)?: error: (?P<message>.+)$")
_LINE_REF = re.compile(r"\bline \d+\b")
_SUMMARY = re.compile(r"^(Found \d+ errors? in \d+ files?|Success: no issues found)")


def parse(output: str) -> list[tuple[str, int, str]]:
    """(path, line, message) for each error in mypy's output, paths with forward slashes."""
    errors = []
    for raw in output.splitlines():
        match = _ERROR.match(raw.strip())
        if match:
            errors.append(
                (
                    match["path"].replace("\\", "/"),
                    int(match["line"]),
                    match["message"].strip(),
                )
            )
    return errors


def fingerprint(path: str, message: str) -> str:
    return f"{path}: {_LINE_REF.sub('line N', message)}"


def compare(current: Counter[str], baseline: Counter[str]) -> tuple[Counter[str], Counter[str]]:
    """(errors not in the baseline, baseline entries mypy no longer reports)."""
    return current - baseline, baseline - current


def read_baseline(path: Path | None = None) -> Counter[str]:
    try:
        lines = (path or BASELINE).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return Counter()
    return Counter(line for line in lines if line.strip() and not line.startswith("#"))


def write_baseline(current: Counter[str], path: Path | None = None) -> None:
    header = [
        "# Known mypy errors: CI fails on any error not listed here, and on any",
        "# listed error mypy no longer reports. Regenerate after fixing errors with",
        "#   python scripts/check_mypy_baseline.py --update",
        f"# {sum(current.values())} errors",
    ]
    entries = sorted(current.elements())
    (path or BASELINE).write_text("\n".join(header + entries) + "\n", encoding="utf-8")


def run_mypy() -> str | None:
    """mypy's output, or None if it didn't get as far as a result."""
    result = subprocess.run(  # nosec B603 - fixed argument list, no shell
        [sys.executable, "-m", "mypy", *MYPY_ARGS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode not in (0, 1) or not any(
        _SUMMARY.match(line) for line in output.splitlines()
    ):
        print(output, file=sys.stderr)
        return None
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    args = parser.parse_args(argv)

    output = run_mypy()
    if output is None:
        print("mypy didn't run to completion; see its output above.", file=sys.stderr)
        return 2
    errors = parse(output)
    current = Counter(fingerprint(path, message) for path, _, message in errors)

    if args.update:
        write_baseline(current)
        print(f"Wrote {BASELINE.relative_to(ROOT)}: {len(errors)} errors.")
        return 0

    baseline = read_baseline()
    new, fixed = compare(current, baseline)
    if new:
        print(f"{sum(new.values())} mypy error(s) not in the baseline:")
        unshown = new.copy()
        for path, line, message in errors:
            key = fingerprint(path, message)
            if unshown[key] > 0:
                print(f"  {path}:{line}: {message}")
                unshown[key] -= 1
        print("Fix them; the baseline lists errors that predate this check, not new ones.")
    if fixed:
        print(f"{sum(fixed.values())} baseline error(s) mypy no longer reports:")
        for entry in sorted(fixed.elements()):
            print(f"  {entry}")
        print("Lower the baseline in this change: python scripts/check_mypy_baseline.py --update")
    if new or fixed:
        return 1
    print(f"mypy: {len(errors)} errors, all in the baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
