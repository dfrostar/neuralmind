"""Pin ``evals/compression/drift.py``, the comparison behind the networked check.

``bench-public-drift.yml`` re-runs the compression benchmark over the pinned
public-benchmark repos, rebuilding each index, and compares the fresh
``results.json`` with the committed one. That is the only check on the Read and
Grep arms: ``tests/test_compression_benchmark.py`` can recompute Bash alone.
These tests run the comparison on the committed file. It has to pass on an
identical run, ignore the run date and package version, and fail on any other
change to any sample, starting with an edited Read digest.

Stdlib-only, like the other claims guards, so it runs without the full dep set.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
from pathlib import Path

from evals.compression import drift

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMITTED = REPO_ROOT / "bench" / "compression" / "results.json"


def _committed() -> dict:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


def _first(report: dict, tool: str) -> dict:
    return next(s for s in report["samples"] if s["tool"] == tool)


def _changed(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 1
    if value is None:
        return 0.5
    return f"{value}-edited"


def _run(fresh: dict) -> tuple[int, str]:
    """``drift.main`` on ``fresh`` against the committed file: (exit code, output)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "results.json"
        path.write_text(json.dumps(fresh), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = drift.main(["--fresh", str(path), "--committed", str(COMMITTED)])
    return code, out.getvalue()


def test_the_committed_run_matches_itself() -> None:
    committed = _committed()
    assert drift.compare(committed, committed) == []
    code, out = _run(committed)
    assert code == 0, out
    assert f"All {len(committed['samples'])} calls match" in out


def test_an_edited_read_digest_fails_and_says_how_to_fix_it() -> None:
    fresh = _committed()
    read = _first(fresh, "Read")
    read["compressor_only_sha256"] = "0" * 64
    code, out = _run(fresh)
    assert code == 1
    assert f"Read[{read['id']}].compressor_only_sha256: committed " in out
    assert "python -m evals.compression.run --out bench/compression" in out
    assert "commit the result" in out


def test_every_field_of_every_kind_of_call_is_compared() -> None:
    committed = _committed()
    for tool in ("Read", "Grep", "Bash"):
        for field in _first(committed, tool):
            if field in ("tool", "id"):
                continue  # these name the call; renaming one is a missing call plus a new one
            fresh = copy.deepcopy(committed)
            sample = _first(fresh, tool)
            was, sample[field] = sample[field], _changed(sample[field])
            expected = f"{tool}[{sample['id']}].{field}: committed {was!r}, now {sample[field]!r}"
            assert drift.compare(committed, fresh) == [expected], (tool, field)


def test_the_run_date_and_package_version_are_not_compared() -> None:
    committed = _committed()
    fresh = copy.deepcopy(committed)
    fresh["meta"]["generated"] = "2099-01-01"
    fresh["meta"]["neuralmind_version"] = "99.0.0"
    assert drift.compare(committed, fresh) == []


def test_the_rest_of_the_metadata_is_compared() -> None:
    # The tokenizer above all: tiktoken falls back to an approximation when it
    # can't load o200k_base, and every token count would then move.
    committed = _committed()
    for key in committed["meta"]:
        if key in drift.IGNORED_META:
            continue
        fresh = copy.deepcopy(committed)
        fresh["meta"][key] = "edited"
        assert drift.compare(committed, fresh), key


def test_a_missing_or_new_call_is_drift() -> None:
    committed = _committed()
    fresh = copy.deepcopy(committed)
    grep = fresh["samples"].pop(
        next(i for i, s in enumerate(fresh["samples"]) if s["tool"] == "Grep")
    )
    assert drift.compare(committed, fresh) == [
        f"Grep[{grep['id']}]: committed, but this run has no such call"
    ]
    assert drift.compare(fresh, committed) == [
        f"Grep[{grep['id']}]: in this run, not in the committed one"
    ]


def test_the_order_of_the_calls_does_not_matter() -> None:
    committed = _committed()
    fresh = copy.deepcopy(committed)
    fresh["samples"].reverse()
    assert drift.compare(committed, fresh) == []


def test_the_summary_is_compared() -> None:
    # The docs quote the summary; it's computed from the samples, so it can only
    # move on its own if the aggregation changes, and then it has to be redone too.
    committed = _committed()
    fresh = copy.deepcopy(committed)
    was = committed["summary"]["Read"]["compressor_only_change_pct"]
    fresh["summary"]["Read"]["compressor_only_change_pct"] = was + 1
    expected = f"summary.Read.compressor_only_change_pct: committed {was!r}, now {was + 1!r}"
    assert drift.compare(committed, fresh) == [expected]


def test_a_skeleton_change_is_reported_without_flooding_the_log() -> None:
    # A change to the skeleton format moves every compressed Read at once.
    fresh = _committed()
    reads = [s for s in fresh["samples"] if s["tool"] == "Read"]
    for read in reads:
        read["compressor_only_sha256"] = "0" * 64
    code, out = _run(fresh)
    assert code == 1
    assert f"{len(reads)} difference(s)" in out
    assert f"... and {len(reads) - drift.SHOWN} more" in out
