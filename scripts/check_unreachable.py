#!/usr/bin/env python3
"""Fail on statements that can never run.

`neuralmind doctor` lost its documented `exit 1` this way. In v0.55.0 a new
helper was inserted between the end of `cmd_doctor` and its final
`if status == FAIL: sys.exit(1)`, so those lines ended up after the helper's
`return checks`, where they could never run. Nothing flagged it, and a later
lint pass deleted them as dead code. ruff has no unreachable-code rule (its
preview `PLW0101` was dropped), so this stdlib-only check runs in CI's Lint job.

It flags any statement that follows, in the same block, a `return`, `raise`,
`continue`, `break`, or a call to `sys.exit` / `os._exit`. That is a
syntactic check: it doesn't follow `if`/`else` branches that both return.
A false positive is fixed by deleting the dead lines or moving them to where
they were meant to run, never by suppressing the check.

Usage: python scripts/check_unreachable.py [path ...]   (default: neuralmind tests evals scripts)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATHS = ["neuralmind", "tests", "evals", "scripts"]
_BLOCK_FIELDS = ("body", "orelse", "finalbody")


def _terminates(stmt: ast.stmt) -> bool:
    if isinstance(stmt, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        func = stmt.value.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            return (func.value.id, func.attr) in {("sys", "exit"), ("os", "_exit")}
    return False


def _blocks(node: ast.AST):
    # ast.walk visits except handlers and match cases as nodes of their own,
    # so their `body` is reached here without special-casing them.
    for field in _BLOCK_FIELDS:
        block = getattr(node, field, None)
        if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
            yield block


def find_unreachable(source: str, filename: str = "<string>") -> list[tuple[int, str]]:
    """Return (line, terminator) for the first dead statement of each block."""
    tree = ast.parse(source, filename=filename)
    found = []
    for node in ast.walk(tree):
        for block in _blocks(node):
            for stmt, nxt in zip(block, block[1:], strict=False):
                if _terminates(stmt):
                    found.append((nxt.lineno, ast.unparse(stmt).split("\n")[0]))
                    break
    return sorted(found)


def main(argv: list[str]) -> int:
    targets = [ROOT / p for p in (argv or DEFAULT_PATHS)]
    problems = []
    for target in targets:
        files = [target] if target.is_file() else sorted(target.rglob("*.py"))
        for path in files:
            if "fixtures" in path.parts:
                continue
            try:
                hits = find_unreachable(path.read_text(encoding="utf-8"), str(path))
            except SyntaxError as e:
                problems.append(f"{path}: cannot parse ({e.msg})")
                continue
            rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            problems += [f"{rel}:{line}: unreachable after `{term}`" for line, term in hits]
    if problems:
        print("\n".join(problems))
        print(
            f"\n{len(problems)} unreachable statement(s). Move them to where they were "
            "meant to run, or delete them in their own commit that says why."
        )
        return 1
    print("unreachable-code check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
