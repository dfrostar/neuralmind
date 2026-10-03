"""Check a fresh compression-benchmark run against the committed one.

    python -m evals.compression.run --work-dir .bench-work --out "$RUNNER_TEMP/compression"
    python -m evals.compression.drift --fresh "$RUNNER_TEMP/compression/results.json"

``tests/test_compression_benchmark.py`` recomputes the Bash arm offline, from
the committed corpus. The Read and Grep arms need the public-benchmark repos at
their pinned commits and a NeuralMind index per repo, so only a networked job
(``bench-public-drift.yml``) can recompute them; this is its comparison.

Every field of every sample is a function of the code and those pinned inputs,
and the text each arm delivers is covered by a SHA-256 digest, so the
comparison is exact, with no tolerances. Only provenance is ignored: the run
date, and the package version, which a release bumps without changing anything
the benchmark measures. Samples are matched by tool and id, so a reordered run
is not drift.

Stdlib only, so its test runs without the benchmark's dependencies.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED = REPO_ROOT / "bench" / "compression" / "results.json"
IGNORED_META = ("generated", "neuralmind_version")
REGENERATE = (
    "re-run `python -m evals.compression.run --out bench/compression` and commit the result"
)
# Differences printed before the rest are only counted: one change to the
# skeleton format moves the digests of every compressed Read at once.
SHOWN = 50


class _Missing:
    def __repr__(self) -> str:
        return "nothing"


MISSING = _Missing()


def _leaves(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    """Every non-dict value under ``value`` with its key path; lists count as values."""
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from _leaves(item, (*path, str(key)))
    else:
        yield path, value


def _diff(prefix: str, committed: Any, fresh: Any) -> list[str]:
    old, new = dict(_leaves(committed)), dict(_leaves(fresh))
    return [
        f"{'.'.join((prefix, *path)) if prefix else '.'.join(path)}: "
        f"committed {old.get(path, MISSING)!r}, now {new.get(path, MISSING)!r}"
        for path in sorted(old.keys() | new.keys())
        if old.get(path, MISSING) != new.get(path, MISSING)
    ]


def compare(committed: dict[str, Any], fresh: dict[str, Any]) -> list[str]:
    """One line per difference between two ``results.json`` reports.

    Metadata first, then calls (``Read[click/core.py].compressor_only_sha256``),
    then the summary computed from them.
    """

    def meta(report: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in report.get("meta", {}).items() if k not in IGNORED_META}

    def calls(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {f"{s['tool']}[{s['id']}]": s for s in report.get("samples", [])}

    def rest(report: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in report.items() if k not in ("meta", "samples")}

    old, new = calls(committed), calls(fresh)
    lines = _diff("meta", meta(committed), meta(fresh))
    lines += [
        f"{c}: committed, but this run has no such call" for c in sorted(old.keys() - new.keys())
    ]
    lines += [
        f"{c}: in this run, not in the committed one" for c in sorted(new.keys() - old.keys())
    ]
    for call in sorted(old.keys() & new.keys()):
        lines += _diff(call, old[call], new[call])
    lines += _diff("", rest(committed), rest(fresh))
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--fresh",
        required=True,
        type=Path,
        help="results.json from `python -m evals.compression.run --out DIR`",
    )
    ap.add_argument(
        "--committed",
        default=COMMITTED,
        type=Path,
        help="committed results.json to compare against (default: bench/compression/results.json)",
    )
    args = ap.parse_args(argv)

    committed = json.loads(args.committed.read_text(encoding="utf-8"))
    fresh = json.loads(args.fresh.read_text(encoding="utf-8"))
    differences = compare(committed, fresh)
    try:
        name = args.committed.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        name = str(args.committed)
    ignored = ", ".join(f"meta.{k}" for k in IGNORED_META)
    if not differences:
        print(f"All {len(fresh['samples'])} calls match {name} ({ignored} not compared).")
        return 0
    print(
        f"The compression benchmark no longer matches {name}: "
        f"{len(differences)} difference(s) ({ignored} not compared)."
    )
    for line in differences[:SHOWN]:
        print(f"  {line}")
    if len(differences) > SHOWN:
        print(f"  ... and {len(differences) - SHOWN} more")
    print(
        "The docs quote these results, so they have to describe the hooks, compressors and "
        f"index as they are now: {REGENERATE}. If the change is to how indexes are built, "
        "delete .bench-work first: a re-run updates the indexes it finds there incrementally, "
        "which keeps parts of the old graph."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
