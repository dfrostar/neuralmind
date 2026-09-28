"""Capture the Bash corpus for the compression benchmark.

    python -m evals.compression.capture_bash --work-dir .bench-work

Every entry is a command an agent plausibly runs during a coding session,
executed for real and saved verbatim under ``evals/compression/corpus/bash/``
(machine-specific path prefixes are replaced with ``<repo>``, ``<work>``,
``<venv>`` and ``<scratch>``). The benchmark replays these files, so its
numbers are byte-reproducible; re-capturing is only needed to refresh the
corpus, and a refreshed corpus must be committed together with a regenerated
``bench/compression/results.json``.

Each entry pre-registers ``must_keep`` patterns: the lines a reader of that
output cannot do without — the assertion detail of a failing test, a linter's
diagnostics, the changed lines of a diff, every hit of a search. They are
defined by the output type, not tuned to the compressor, the same way the
public benchmark pre-registers its queries. The benchmark reports what share of
those lines survive compression.

Pinned inputs: the four public-benchmark repos (``evals/public/manifest.json``)
are checked out at their pinned commits, and the git entries name fixed SHAs of
this repository.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from evals.public.run import ensure_checkout, load_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = Path(__file__).with_name("corpus") / "bash"

# A small module with deliberate bugs, so the failing-test entry is a real
# pytest run with real tracebacks rather than hand-written text.
_INVENTORY_PY = '''\
"""Tiny inventory module used to produce a realistic failing test run."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Item:
    sku: str
    name: str
    unit_price_cents: int
    quantity: int = 0


@dataclass
class Inventory:
    items: dict[str, Item] = field(default_factory=dict)

    def add(self, item: Item) -> None:
        self.items[item.sku] = item

    def restock(self, sku: str, quantity: int) -> int:
        item = self.items[sku]
        item.quantity += quantity
        return item.quantity

    def remove(self, sku: str, quantity: int) -> int:
        item = self.items[sku]
        if quantity > item.quantity:
            raise ValueError(f"only {item.quantity} of {sku} in stock")
        item.quantity -= quantity
        return item.quantity

    def total_value_cents(self) -> int:
        # Bug: ignores quantity for anything priced over ten dollars.
        return sum(
            i.unit_price_cents * (i.quantity if i.unit_price_cents <= 1000 else 1)
            for i in self.items.values()
        )

    def low_stock(self, threshold: int = 5) -> list[str]:
        # Bug: off by one — the threshold itself should count as low.
        return sorted(sku for sku, i in self.items.items() if i.quantity < threshold)

    def report(self) -> dict[str, dict[str, int]]:
        return {
            sku: {"qty": i.quantity, "value": i.unit_price_cents * i.quantity}
            for sku, i in self.items.items()
        }
'''

_TEST_INVENTORY_PY = """\
import pytest

from inventory import Inventory, Item


@pytest.fixture
def inv():
    inv = Inventory()
    inv.add(Item("A-100", "bolt", 25, 40))
    inv.add(Item("B-200", "bracket", 1250, 3))
    inv.add(Item("C-300", "hinge", 480, 5))
    inv.add(Item("D-400", "panel", 5600, 0))
    return inv


def test_add_and_count(inv):
    assert len(inv.items) == 4


def test_restock_increments(inv):
    assert inv.restock("C-300", 10) == 15


def test_remove_decrements(inv):
    assert inv.remove("A-100", 15) == 25


def test_remove_too_many_raises(inv):
    with pytest.raises(ValueError, match="only 3 of B-200"):
        inv.remove("B-200", 4)


def test_remove_unknown_sku_raises_value_error(inv):
    with pytest.raises(ValueError):
        inv.remove("Z-999", 1)


def test_total_value(inv):
    assert inv.total_value_cents() == 25 * 40 + 1250 * 3 + 480 * 5 + 5600 * 0


def test_low_stock_boundary(inv):
    assert inv.low_stock(threshold=5) == ["B-200", "C-300", "D-400"]


def test_low_stock_default_threshold(inv):
    assert "D-400" in inv.low_stock()


def test_report_shape(inv):
    assert inv.report() == {
        "A-100": {"qty": 40, "value": 1000},
        "B-200": {"qty": 3, "value": 3750},
        "C-300": {"qty": 5, "value": 2400},
        "D-400": {"qty": 0, "value": 0},
        "E-500": {"qty": 0, "value": 0},
    }


@pytest.mark.parametrize("qty", [1, 2, 3, 5, 8, 13])
def test_restock_is_additive(inv, qty):
    before = inv.items["A-100"].quantity
    assert inv.restock("A-100", qty) == before + qty
"""


def _entries(py: str, nm: str) -> list[dict[str, Any]]:
    """The corpus. ``cwd`` is a label resolved by :func:`_resolve_cwd`."""
    return [
        {
            "id": "pytest-verbose-pass",
            "category": "test run (passing, -v)",
            "cwd": "repo",
            "argv": [
                py,
                "-m",
                "pytest",
                "-v",
                "-p",
                "no:cacheprovider",
                # The repo's addopts carry -q, which cancels -v; clear them so
                # this is the verbose output a project without that config gets.
                "-o",
                "addopts=",
                "tests/test_compressors.py",
                "tests/test_hooks.py",
                "tests/test_output_cache.py",
                "tests/test_synapses.py",
            ],
            "must_keep": [r"\d+ passed"],
        },
        {
            "id": "pytest-quiet-pass",
            "category": "test run (passing, -q)",
            "cwd": "repo",
            "argv": [
                py,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "tests/test_compressors.py",
            ],
            # With the repo's own -q this is -qq: a progress line, no summary.
            "must_keep": [r"\d+ passed", r"\[\s*\d+%\]"],
        },
        {
            "id": "pytest-failures",
            "category": "test run (failing)",
            "cwd": "scratch",
            "argv": [py, "-m", "pytest", "-p", "no:cacheprovider", "test_inventory.py"],
            "must_keep": [r"^E\s", r"^FAILED ", r"\d+ failed"],
        },
        {
            "id": "pytest-collect",
            "category": "test listing",
            "cwd": "repo",
            "argv": [
                py,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                "tests/test_compressors.py",
                "tests/test_hooks.py",
                "tests/test_synapses.py",
            ],
            "must_keep": [r"::", r"tests? collected"],
        },
        {
            "id": "ruff-lint",
            "category": "linter (errors)",
            "cwd": "click",
            "argv": [
                "ruff",
                "check",
                "--no-cache",
                "--select",
                "E,W,F,B,SIM",
                "src/click",
            ],
            "must_keep": [r"^[A-Z]+\d+ ", r"^\s*--> ", r"Found \d+ errors?"],
        },
        {
            "id": "mypy-strict",
            "category": "type checker (errors)",
            "cwd": "requests",
            "argv": ["mypy", "--strict", "--no-color-output", "--no-incremental", "src/requests"],
            "must_keep": [r": error: ", r"Found \d+ errors?"],
        },
        {
            "id": "python-crash",
            "category": "crash traceback",
            "cwd": "scratch",
            "argv": [
                py,
                "-c",
                "import requests; requests.get('http://127.0.0.1:9/health', timeout=2)",
            ],
            "must_keep": [r"^Traceback", r"^[\w.]+(Error|Exception): "],
        },
        {
            "id": "pip-list",
            "category": "package listing",
            "cwd": "repo",
            "argv": [py, "-m", "pip", "list", "--disable-pip-version-check"],
            "must_keep": [r"^[A-Za-z0-9_.\-]+\s+\d"],
        },
        {
            "id": "next-build",
            "category": "build log",
            "cwd": "site",
            "argv": ["npm", "run", "build"],
            "must_keep": [r"^[├└┌]\s", r"Compiled successfully|Generating static pages"],
            "timeout": 600,
        },
        {
            "id": "neuralmind-build",
            "category": "indexer progress log",
            "cwd": "requests",
            "argv": [nm, "build", "src/requests", "--force"],
            "must_keep": [r"(?i)\b(nodes?|edges?|built|complete|success)\b"],
            "timeout": 600,
        },
        {
            "id": "git-log-stat",
            "category": "git history",
            "cwd": "repo",
            "argv": [
                "git",
                "log",
                "--stat",
                "-n",
                "12",
                "--format=commit %H%n%n    %s%n",
                "f69202cd7d990957fadddd71d9e98ca607c17037",
            ],
            "must_keep": [r"^commit [0-9a-f]{40}", r"files? changed"],
        },
        {
            "id": "git-diff",
            "category": "diff",
            "cwd": "repo",
            "argv": [
                "git",
                "diff",
                "ad49d3ba44bf5c4ea0e8b3d7f03eb975d49b5219",
                "f69202cd7d990957fadddd71d9e98ca607c17037",
                "--",
                "site/src/components/sections/CTA.tsx",
                "site/src/components/sections/FAQ.tsx",
                "site/src/components/sections/Hero.tsx",
            ],
            "must_keep": [r"^@@", r"^[+-](?![+-])"],
        },
        {
            "id": "grep-defs",
            "category": "search via shell",
            "cwd": "flask",
            "argv": ["grep", "-rn", "def ", "src/flask"],
            "must_keep": [r"^\S+:\d+:"],
        },
        {
            "id": "find-files",
            "category": "file listing",
            "cwd": "rich",
            "argv": ["sh", "-c", "find rich -name '*.py' | sort"],
            "must_keep": [r"\.py$"],
        },
        {
            "id": "cat-source",
            "category": "file dump",
            "cwd": "flask",
            "argv": ["cat", "src/flask/app.py"],
            "must_keep": [r"^\s*(async\s+)?def |^\s*class "],
        },
        {
            "id": "ls-long",
            "category": "directory listing",
            "cwd": "rich",
            "argv": ["ls", "-la", "rich"],
            "must_keep": [r"^[-dl][rwx-]{9}"],
        },
    ]


def _resolve_cwd(label: str, checkouts: dict[str, Path], scratch: Path) -> Path:
    if label == "repo":
        return REPO_ROOT
    if label == "site":
        return REPO_ROOT / "site"
    if label == "scratch":
        return scratch
    # Pinned public-benchmark repo: run from the clone root, not the subdir.
    return checkouts[label]


def _scrub(text: str, prefixes: list[tuple[str, str]]) -> str:
    for raw, label in prefixes:
        text = text.replace(raw, label)
    return text


def _version(argv: list[str], env: dict[str, str]) -> str:
    # Same environment as the captured commands, so PATH resolves the same
    # binary that produced the output.
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=60, env=env)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "unavailable"


def capture(work_dir: Path, out_dir: Path = CORPUS_DIR) -> dict[str, Any]:
    manifest = load_manifest()
    checkouts: dict[str, Path] = {}
    for repo in manifest["repos"]:
        src = ensure_checkout(repo, work_dir)
        if src is None:
            raise SystemExit(f"could not check out {repo['name']} at its pinned commit")
        checkouts[repo["name"]] = work_dir / repo["name"]
        # A previous benchmark run may have left NeuralMind indexes inside the
        # checkout; they are derived caches, and they would show up in the
        # grep/find/ls entries of a corpus meant to show a pristine repo.
        for index_dir in sorted(checkouts[repo["name"]].rglob(".neuralmind"), reverse=True):
            shutil.rmtree(index_dir, ignore_errors=True)

    py = sys.executable
    nm = shutil.which("neuralmind", path=str(Path(py).parent)) or "neuralmind"
    scratch = Path(tempfile.mkdtemp(prefix="nm-compression-"))
    (scratch / "inventory.py").write_text(_INVENTORY_PY, encoding="utf-8")
    (scratch / "test_inventory.py").write_text(_TEST_INVENTORY_PY, encoding="utf-8")

    prefixes = sorted(
        [
            (str(scratch.resolve()), "<scratch>"),
            (str(scratch), "<scratch>"),
            (str(work_dir.resolve()), "<work>"),
            (str(REPO_ROOT), "<repo>"),
            (sys.prefix, "<venv>"),
            (str(Path.home()), "~"),
        ],
        key=lambda p: -len(p[0]),
    )
    env = dict(os.environ)
    env.update(
        {
            "NO_COLOR": "1",
            "TERM": "dumb",
            "COLUMNS": "120",
            "PYTHONDONTWRITEBYTECODE": "1",
            "NEXT_TELEMETRY_DISABLED": "1",
        }
    )
    env.pop("FORCE_COLOR", None)
    # Resolve ruff, neuralmind and friends from the interpreter's environment.
    env["PATH"] = str(Path(py).parent) + os.pathsep + env.get("PATH", "")

    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for entry in _entries(py, nm):
        cwd = _resolve_cwd(entry["cwd"], checkouts, scratch)
        proc = subprocess.run(
            entry["argv"],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=entry.get("timeout", 300),
        )
        stdout = _scrub(proc.stdout, prefixes)
        stderr = _scrub(proc.stderr, prefixes)
        stdout_file = f"{entry['id']}.stdout.txt"
        (out_dir / stdout_file).write_text(stdout, encoding="utf-8")
        stderr_file = None
        if stderr:
            stderr_file = f"{entry['id']}.stderr.txt"
            (out_dir / stderr_file).write_text(stderr, encoding="utf-8")
        argv = [Path(a).name if a in (py, nm) else a for a in entry["argv"]]
        rows.append(
            {
                "id": entry["id"],
                "category": entry["category"],
                "cwd": entry["cwd"],
                "command": shlex.join(argv) if argv[:2] != ["sh", "-c"] else argv[2],
                "exit_code": proc.returncode,
                "stdout_file": stdout_file,
                "stderr_file": stderr_file,
                "must_keep": entry["must_keep"],
            }
        )
        print(
            f"{entry['id']:<22} exit={proc.returncode:<3} "
            f"stdout={len(stdout):>7} B  stderr={len(stderr):>6} B",
            file=sys.stderr,
        )
    shutil.rmtree(scratch, ignore_errors=True)

    doc = {
        "_about": (
            "Real command outputs replayed by evals/compression/run.py. Captured "
            "with evals/compression/capture_bash.py; cwd labels: repo = this "
            "repository, site = its site/ directory, scratch = a temp dir holding "
            "the generated inventory module and its tests, anything else = that "
            "public-benchmark repo at its pinned commit. must_keep patterns are "
            "pre-registered per output type."
        ),
        "captured_on": date.today().isoformat(),
        "tool_versions": {
            "python": platform.python_version(),
            "pytest": _version([py, "-m", "pytest", "--version"], env),
            "ruff": _version(["ruff", "--version"], env),
            "mypy": _version(["mypy", "--version"], env),
            "node": _version(["node", "--version"], env),
            "git": _version(["git", "--version"], env),
        },
        "pinned_repos": {r["name"]: r["commit"] for r in manifest["repos"]},
        "entries": rows,
    }
    (out_dir / "manifest.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Capture the Bash corpus for the compression benchmark"
    )
    ap.add_argument(
        "--work-dir", default=".bench-work", help="where the pinned repos are checked out"
    )
    args = ap.parse_args(argv)
    capture(Path(args.work_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
