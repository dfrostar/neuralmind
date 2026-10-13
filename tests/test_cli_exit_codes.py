"""Exit codes are an interface: scripts and CI steps gate on them.

`neuralmind doctor` lost its documented `exit 1` in v0.55.0 and nobody
noticed for three months, because no test ran the command and read its exit
status. A lint pass deleted the then-unreachable `sys.exit(1)`, and a later
docs change described the regression as the design.

So this file holds two kinds of check:

- **Contract rows** run real CLI invocations through `main()` (including its
  exception-to-exit-code mapping) and assert the code the CLI reference
  documents for that case. Add a row when you document an exit code.
- **The global table** in `docs/wiki/CLI-Reference.md` ("## Exit Codes") must
  list only codes something in `neuralmind/` actually emits.

Codes that need a built index or a licence store are covered next to their
feature (`tests/test_index_freshness.py` for `build --strict` -> 3 and
`health` -> 1, and `doctor --stale-after` past its limit,
`tests/test_doctor.py` for doctor's OK/WARN results, `tests/test_audit_cli.py`
for `audit verify`, `tests/test_audit_checkpoint.py` for `audit keygen`,
`audit checkpoint` and `audit verify` against checkpoints).
"""

from __future__ import annotations

import ast
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from neuralmind import cli

ROOT = Path(__file__).resolve().parent.parent
CLI_REFERENCE = ROOT / "docs" / "wiki" / "CLI-Reference.md"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """A fresh project dir, with HOME and the daemon home kept out of ~."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", str(home / ".neuralmind"))
    monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")
    project = tmp_path / "proj"
    project.mkdir()
    return project


def _exit_code(argv: list[str], monkeypatch) -> int:
    """Run `neuralmind <argv>` in-process and return its exit status."""
    monkeypatch.setattr(sys, "argv", ["neuralmind", *argv])
    try:
        cli.main()
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    return 0


def _seed_licences(project: Path, **customers: object) -> None:
    """Write Team licence records with expiries relative to now.

    Each value is days until expiry, or a string stored as-is (an unreadable
    expiry). The store lives under HOME, which `isolated` points at tmp.
    """
    from neuralmind.tier2.operations import LicenseOperations

    now = datetime.now(timezone.utc)
    ops = LicenseOperations("", Path.home() / ".neuralmind")
    ops._save_customers(
        {
            "customers": {
                name: {
                    "customer_id": f"cus_{name}",
                    "license_id": f"lic_{name}",
                    "seats": 5,
                    "tier": "team",
                    "status": "active",
                    "expires_at": (
                        when if isinstance(when, str) else (now + timedelta(days=when)).isoformat()
                    ),
                }
                for name, when in customers.items()
            }
        }
    )


def _three_hours_behind(project: Path) -> None:
    """An index whose graph has never seen one file, last written 3h ago."""
    import json
    import os
    import time

    rels = [f"m{i}.py" for i in range(20)]
    for rel in [*rels, "new.py"]:
        (project / rel).write_text(f"def {rel[:-3]}_fn():\n    return 1\n", encoding="utf-8")
    then = time.time() - 3 * 3600
    os.utime(project / "new.py", (then, then))
    graph = {
        "nodes": [
            {"id": rel, "label": rel, "file_type": "code", "source_file": rel, "community": 0}
            for rel in rels
        ],
        "links": [],
    }
    (project / "graphify-out").mkdir()
    (project / "graphify-out" / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (project / ".neuralmind").mkdir()
    (project / ".neuralmind" / "index_ir.json").write_text('{"node_count": 20}', encoding="utf-8")


def _with_aws_key(project: Path) -> None:
    # Split so this file doesn't itself look like it holds a key.
    (project / ".env").write_text("AWS_ACCESS_KEY_ID=AKIA" + "IOSFODNN7EXAMPLE\n")


def _cui_profile(project: Path) -> None:
    (project / "neuralmind-backend.yaml").write_text("security:\n  profile: cui\n")


# (id, argv with {p} for the project dir, setup, env, expected code)
CONTRACT = [
    # The regression this file exists for: no graph -> the code-graph check
    # fails -> exit 1, in text and --json (v0.55.0 through v4.12.0 exited 0).
    ("doctor-unbuilt-project", ["doctor", "{p}"], None, {}, 1),
    ("doctor-unbuilt-project-json", ["doctor", "{p}", "--json"], None, {}, 1),
    ("health-no-index", ["health", "{p}"], None, {}, 2),
    # v4.13.0: drift younger than --stale-after is "catching up" (0); older is stale (1).
    ("health-behind-no-grace", ["health", "{p}"], _three_hours_behind, {}, 1),
    (
        "health-behind-within-stale-after",
        ["health", "{p}", "--stale-after", "1d"],
        _three_hours_behind,
        {},
        0,
    ),
    (
        "health-behind-past-stale-after",
        ["health", "{p}", "--stale-after", "30m"],
        _three_hours_behind,
        {},
        1,
    ),
    ("health-stale-after-needs-a-unit", ["health", "{p}", "--stale-after", "30"], None, {}, 2),
    ("scan-clean", ["scan-for-secrets", "{p}"], None, {}, 0),
    ("scan-high-confidence", ["scan-for-secrets", "{p}"], _with_aws_key, {}, 1),
    ("scan-missing-path", ["scan-for-secrets", "{p}/does-not-exist"], None, {}, 2),
    ("feedback-memory-off", ["feedback", "good", "{p}"], None, {"NEURALMIND_MEMORY": "0"}, 1),
    ("daemon-status-not-running", ["daemon", "status"], None, {}, 3),
    # security.profile: cui refuses a listener beyond loopback before it builds or binds.
    (
        "serve-refused-by-cui-profile",
        ["serve", "{p}", "--host", "0.0.0.0", "--no-browser"],
        _cui_profile,
        {},
        1,
    ),
    ("unknown-option", ["health", "{p}", "--no-such-flag"], None, {}, 2),
    (
        "license-expiring-none-due",
        ["license", "expiring"],
        lambda p: _seed_licences(p, healthy=300),
        {},
        0,
    ),
    (
        "license-expiring-renewal-due",
        ["license", "expiring"],
        lambda p: _seed_licences(p, healthy=300, soon=20),
        {},
        6,
    ),
    (
        "license-expiring-already-expired",
        ["license", "expiring"],
        lambda p: _seed_licences(p, soon=20, lapsed=-10),
        {},
        7,
    ),
    (
        "license-expiring-unreadable-expiry",
        ["license", "expiring"],
        lambda p: _seed_licences(p, garbled="not a date"),
        {},
        7,
    ),
]


@pytest.mark.parametrize(
    "argv, setup, env, expected",
    [row[1:] for row in CONTRACT],
    ids=[row[0] for row in CONTRACT],
)
def test_documented_exit_code(isolated, monkeypatch, capsys, argv, setup, env, expected):
    if setup:
        setup(isolated)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    code = _exit_code([a.format(p=isolated) for a in argv], monkeypatch)
    out = capsys.readouterr()
    assert code == expected, f"exit {code}, expected {expected}\n{out.out}\n{out.err}"


def _global_table_codes() -> dict[int, str]:
    text = CLI_REFERENCE.read_text(encoding="utf-8")
    section = text.split("\n## Exit Codes\n", 1)[1].split("\n## ", 1)[0]
    return {
        int(m.group(1)): m.group(2).strip()
        for m in re.finditer(r"^\|\s*(\d+)\s*\|(.*)\|\s*$", section, re.M)
    }


def _int_arg(call: ast.Call) -> int | None:
    if call.args and isinstance(call.args[0], ast.Constant):
        value = call.args[0].value
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _emitted_codes() -> set[int]:
    """Literal exit codes in neuralmind/'s executable code.

    Parsed, not grepped: `sys.exit(4)` in a comment, docstring or message
    string must not count as emitting 4. Collects the literal argument of
    `sys.exit(...)` / `SystemExit(...)` calls and the value of
    `{"exit_code": N}` entries (`build --strict` returns its code that way).
    """
    codes = {0, 2}  # 0 on success; argparse exits 2 on a usage error
    for path in (ROOT / "neuralmind").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
            if isinstance(node, ast.Call):
                func = node.func
                is_exit = (
                    isinstance(func, ast.Attribute)
                    and func.attr == "exit"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "sys"
                ) or (isinstance(func, ast.Name) and func.id == "SystemExit")
                if is_exit and (code := _int_arg(node)) is not None:
                    codes.add(code)
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values, strict=True):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "exit_code"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, int)
                    ):
                        codes.add(value.value)
    return codes


def test_global_exit_code_table_lists_only_emitted_codes():
    table = _global_table_codes()
    assert table, "could not find the '## Exit Codes' table in CLI-Reference.md"
    unused = {code: meaning for code, meaning in table.items() if code not in _emitted_codes()}
    assert not unused, (
        f"CLI-Reference.md documents exit codes nothing in neuralmind/ emits: {unused}. "
        "Remove them from the table, or make the code emit them (with a test)."
    )
