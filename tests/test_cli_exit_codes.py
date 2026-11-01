"""Exit codes are an interface: scripts and CI steps gate on them.

`neuralmind doctor` lost its documented `exit 1` in v0.55.0 and nobody
noticed for three months, because no test ran the command and read its exit
status. A lint pass deleted the then-unreachable `sys.exit(1)`, and a later
docs change described the regression as the design.

So this file holds two kinds of check:

- **Contract rows** run real CLI invocations through `main()` (including its
  exception-to-exit-code mapping) and assert the code the CLI reference
  documents for that case. Add a row when you document an exit code.
  `TEAM_CONTRACT` does the same for `neuralmind team ...` and `onboarding`,
  in `temp_seat_env`'s throwaway tier2 config dir with its own issuer key.
- **The global table** in `docs/wiki/CLI-Reference.md` ("## Exit Codes") must
  list only codes something in `neuralmind/` actually emits.

Codes that need a built index or a licence store are covered next to their
feature (`tests/test_index_freshness.py` for `build --strict` -> 3 and
`health` -> 1, and `doctor --stale-after` past its limit,
`tests/test_doctor.py` for doctor's OK/WARN results, `tests/test_audit_cli.py`
for `audit verify`, `tests/test_audit_checkpoint.py` for `audit keygen`,
`audit checkpoint` and `audit verify` against checkpoints,
`tests/test_audit_forward.py` for `audit forward` reaching its target,
`tests/test_hardening.py` for `hardening` passing every rule,
`tests/test_cli.py` (`TestCLIDemo`, `TestCLIDemoOffline`,
`TestCLIDemoWithoutTurbovec`) for `demo`).
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


def _audit_write_failed_and_log_unwritable(project: Path) -> None:
    state = project / ".neuralmind"
    state.mkdir()
    (state / "audit_write_failures.jsonl").write_text(
        '{"event": "query/query", "timestamp": "2026-10-18T00:00:00+00:00", "error": "x"}\n'
    )
    (state / "audit_events.jsonl").mkdir()  # a directory: the gap record can't be appended


def _forward_to_a_closed_port(project: Path) -> None:
    # Nothing listens on port 1 of the loopback address: the connection is refused.
    (project / "neuralmind-backend.yaml").write_text(
        "security:\n  audit_syslog: tcp://127.0.0.1:1\n"
    )
    state = project / ".neuralmind"
    state.mkdir()
    from neuralmind.audit import AuditTrail

    AuditTrail(project).append_event("query", "run")


def _every_account_a_reader(project: Path) -> None:
    path = project / "neuralmind-backend.yaml"
    path.write_text("security:\n  identity: os\n  default_role: reader\n")
    if sys.platform != "win32":
        path.chmod(0o644)


def _hermes_state_db(project: Path) -> None:
    """A Hermes state.db with the synthetic sessions of tests/test_exploration_share.py.

    They sit at epoch 1000-1990, so a window of 100000 days holds them and one of a day doesn't.
    """
    from tests.test_exploration_share import _hermes_db

    _hermes_db(project / "state.db")


MEASURE = ["measure", "sessions", "--claude-root", "{p}", "--hermes-db", "{p}/state.db"]

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
    # Under security.identity: os, a role without neuralmind_build can't build
    # from the CLI either.
    ("build-refused-by-role", ["build", "{p}"], _every_account_a_reader, {}, 1),
    ("unknown-option", ["health", "{p}", "--no-such-flag"], None, {}, 2),
    # v4.18.0: audit record-gap exits 1 when the gap record can't be written.
    ("audit-record-gap-nothing-to-record", ["audit", "record-gap", "{p}"], None, {}, 0),
    (
        "audit-record-gap-log-unwritable",
        ["audit", "record-gap", "{p}"],
        _audit_write_failed_and_log_unwritable,
        {},
        1,
    ),
    # v4.19.0: audit forward exits 1 when forwarding isn't set up or records are left.
    ("audit-forward-not-configured", ["audit", "forward", "{p}"], None, {}, 1),
    ("audit-forward-target-down", ["audit", "forward", "{p}"], _forward_to_a_closed_port, {}, 1),
    # v4.19.0: hardening exits 1 when a baseline rule fails; a default project fails several.
    ("hardening-baseline-not-met", ["hardening", "{p}"], None, {}, 1),
    # v4.24.0: measure sessions prints its report (0), exits 2 when no session started
    # in the window, and 1 when --rows can't be written. An empty --claude-root and the fixture state.db keep HOME out of it.
    (
        "measure-sessions-reports",
        [*MEASURE, "--since-days", "100000", "--estimate"],
        _hermes_state_db,
        {},
        0,
    ),
    ("measure-sessions-none-in-window", [*MEASURE, "--since-days", "1"], _hermes_state_db, {}, 2),
    (
        "measure-sessions-rows-unwritable",
        [*MEASURE, "--since-days", "100000", "--rows", "{p}/state.db/rows.jsonl"],
        _hermes_state_db,
        {},
        1,
    ),
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


# `neuralmind team ...` and `onboarding` return their exit code instead of
# calling sys.exit. Through v4.15.1 main() discarded it, so every failure row
# below exited 0.


def _signed_licence(env: dict, name: str, *, days: int, tamper: bool = False) -> None:
    """A Team licence signed by the test issuer, expiring `days` from now."""
    import json

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    now = datetime.now(timezone.utc)
    body = {
        "tier": "team",
        "seats": 5,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=days)).isoformat(),
        "issued_to": "example",
    }
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(env["private_key_hex"]))
    signed = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    licence = {**body, "signature": key.sign(signed).hex()}
    if tamper:
        licence["seats"] = 50  # changed after signing
    (env["config_dir"] / name).write_text(json.dumps(licence), encoding="utf-8")


def _seat_manifest(env: dict, *emails: str, days: int = 30, tamper: bool = False) -> None:
    """A seat manifest signed by the test issuer, written to manifest.json."""
    import json

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    now = datetime.now(timezone.utc)
    body = {
        "manifest_id": "sm_test",
        "version": 1,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=days)).isoformat(),
        "seats": [{"email": e, "role": "member", "added_at": now.isoformat()} for e in emails],
    }
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(env["private_key_hex"]))
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    manifest = {**body, "signature": key.sign(b"seat-manifest:v1" + canonical.encode()).hex()}
    if tamper:
        manifest["seats"].append({"email": "extra@example.com", "role": "admin"})
    (env["config_dir"] / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _answer(monkeypatch, *answers: str) -> None:
    """Run onboarding interactively, typing `answers` at its prompts in turn."""
    from neuralmind import onboarding

    replies = iter(answers)
    monkeypatch.setattr(onboarding, "_stdin_is_tty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(replies))


def _licence_path_is_a_directory(env: dict, monkeypatch) -> None:
    # Onboarding can neither read license.json nor replace it with the free one.
    (env["config_dir"] / "license.json").mkdir()


def _tampered_audit_log(env: dict, monkeypatch) -> None:
    import json

    from neuralmind.tier2.audit import AuditLog

    path = env["config_dir"] / "audit.db"
    AuditLog(path).log(actor="admin", action="seat_add", target="a@example.com")
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    entry["target"] = "b@example.com"  # rewritten after it was hashed
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")


_SYNC = ["team", "seats", "sync", "{d}/manifest.json"]

# (id, argv with {d} for the tier2 config dir, setup(env, monkeypatch),
#  expected code, text the output must contain so the row is known to have
#  failed for the reason it names)
TEAM_CONTRACT = [
    (
        "team-license-activate-missing-file",
        ["team", "license", "activate", "{d}/nope.json"],
        None,
        1,
        "License file not found",
    ),
    (
        "team-license-activate-expired",
        ["team", "license", "activate", "{d}/expired.json"],
        # Past the 30-day grace period too, which would report OFFLINE_OK.
        lambda env, mp: _signed_licence(env, "expired.json", days=-45),
        1,
        ": EXPIRED. Nothing was installed.",
    ),
    (
        "team-license-activate-tampered",
        ["team", "license", "activate", "{d}/tampered.json"],
        lambda env, mp: _signed_licence(env, "tampered.json", days=365, tamper=True),
        1,
        ": INVALID. Nothing was installed.",
    ),
    (
        "team-license-activate-valid",
        ["team", "license", "activate", "{d}/valid.json"],
        lambda env, mp: _signed_licence(env, "valid.json", days=365),
        0,
        "License activated: team tier, 5 seats",
    ),
    # `seats sync` runs on the free licence these rows auto-issue: one seat,
    # whose default admin is `self`.
    (
        "team-seats-sync-missing-manifest",
        [*_SYNC, "--admin", "self"],
        None,
        1,
        "Manifest not found",
    ),
    (
        "team-seats-sync-bad-signature",
        [*_SYNC, "--admin", "self"],
        lambda env, mp: _seat_manifest(env, "a@example.com", tamper=True),
        1,
        "Manifest signature invalid",
    ),
    (
        "team-seats-sync-expired-manifest",
        [*_SYNC, "--admin", "self"],
        lambda env, mp: _seat_manifest(env, "a@example.com", days=-1),
        1,
        "Manifest expired at",
    ),
    (
        "team-seats-sync-not-admin",
        [*_SYNC, "--admin", "intruder@example.com"],
        lambda env, mp: _seat_manifest(env, "a@example.com"),
        1,
        "Permission denied",
    ),
    (
        "team-seats-sync-ok",
        [*_SYNC, "--admin", "self"],
        lambda env, mp: _seat_manifest(env, "a@example.com"),
        0,
        '"status": "ok"',
    ),
    (
        "team-seats-sync-partial",
        [*_SYNC, "--admin", "self"],
        lambda env, mp: _seat_manifest(env, "a@example.com", "b@example.com"),
        2,
        '"status": "partial"',
    ),
    (
        "team-seats-remove-unknown",
        ["team", "seats", "remove", "nobody@example.com", "--admin", "self"],
        None,
        1,
        "Seat not found",
    ),
    (
        "team-seats-list-corrupt-licence",
        ["team", "seats", "list"],
        lambda env, mp: (env["config_dir"] / "license.json").write_text("{", encoding="utf-8"),
        1,
        "License file is corrupted",
    ),
    (
        "team-governance-remove-edge-not-admin",
        ["team", "governance", "remove-edge", "a.py", "b.py", "--project", "{d}"]
        + ["--admin", "intruder@example.com"],
        None,
        1,
        "Permission denied",
    ),
    ("team-audit-verify-tampered", ["team", "audit", "verify"], _tampered_audit_log, 1, "TAMPERED"),
    (
        "team-self-hosted-init-unwritable",
        ["team", "self-hosted", "init", "--data-dir", "{d}/a-file/data"],
        lambda env, mp: (env["config_dir"] / "a-file").write_text("", encoding="utf-8"),
        1,
        "Cannot create",
    ),
    (
        "onboarding-eula-declined",
        ["onboarding"],
        lambda env, mp: _answer(mp, "y", "n"),  # issue the free licence, decline the EULA
        1,
        "You must accept the EULA",
    ),
    (
        "onboarding-licence-unwritable",
        ["onboarding", "--quick"],
        _licence_path_is_a_directory,
        1,
        "Failed to create license",
    ),
]


@pytest.fixture
def tier2_env(isolated, temp_seat_env, monkeypatch):
    """`temp_seat_env`'s config dir and issuer key, everywhere the CLI reads them.

    `team seats` and onboarding copy TIER2_CONFIG_DIR at import, and `team
    license activate` the issuer key, so those copies are patched too.
    """
    from neuralmind import onboarding
    from neuralmind.tier2 import cli as tier2_cli

    monkeypatch.setattr(tier2_cli, "TIER2_CONFIG_DIR", temp_seat_env["config_dir"])
    monkeypatch.setattr(tier2_cli, "_ISSUER_PUBLIC_KEY_HEX", temp_seat_env["public_key_hex"])
    monkeypatch.setattr(onboarding, "TIER2_CONFIG_DIR", temp_seat_env["config_dir"])
    return temp_seat_env


@pytest.mark.parametrize(
    "argv, setup, expected, says",
    [row[1:] for row in TEAM_CONTRACT],
    ids=[row[0] for row in TEAM_CONTRACT],
)
def test_documented_team_exit_code(tier2_env, monkeypatch, capsys, argv, setup, expected, says):
    if setup:
        setup(tier2_env, monkeypatch)
    code = _exit_code([a.format(d=tier2_env["config_dir"]) for a in argv], monkeypatch)
    out = capsys.readouterr()
    assert code == expected, f"exit {code}, expected {expected}\n{out.out}\n{out.err}"
    assert says in out.out + out.err, f"{says!r} not in output\n{out.out}\n{out.err}"


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
