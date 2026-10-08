"""Pin ``scripts/check_public_bench_drift.py`` against the committed run.

``bench-public-drift.yml`` used to diff the fresh public benchmark against
``docs/benchmarks/public.md`` with an inline parser that never matched the
file's format (``### `` headings, backticked backend names, ``100%`` and
``41,729``). It found no committed numbers, printed a warning, and exited 0,
so drift was never detected. Its cost tolerance was also an absolute 0.10
tokens, so a working parser would have flagged every run on rounding alone.

These tests run the extracted comparison against the committed
``bench/public/results.json`` so neither bug can come back quietly: the parse
must find every repo and backend, and the gate must pass on the committed
numbers and fail on an altered one.

Stdlib-only, like the other claims guards, so it runs without the full dep set.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_public_bench_drift.py"
COMMITTED = REPO_ROOT / "bench" / "public" / "results.json"

REPOS = {"requests", "click", "flask", "rich"}
BACKENDS = {"full-file", "ripgrep", "embedding-rag", "neuralmind"}


def _load_script():
    spec = importlib.util.spec_from_file_location("check_public_bench_drift", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


drift = _load_script()


def _report() -> dict:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


def _summary(report: dict, repo: str, backend: str) -> dict:
    entry = next(r for r in report["repos"] if r["name"] == repo)
    return entry["summary"][backend]


def _run_main(fresh: dict, committed: dict) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = Path(tmp) / "fresh.json"
        committed_path = Path(tmp) / "committed.json"
        fresh_path.write_text(json.dumps(fresh), encoding="utf-8")
        committed_path.write_text(json.dumps(committed), encoding="utf-8")
        return drift.main(["--fresh", str(fresh_path), "--committed", str(committed_path)])


def test_committed_run_parses_every_repo_and_backend() -> None:
    committed = drift.load(COMMITTED)
    assert set(committed) == REPOS
    for repo, backends in committed.items():
        assert set(backends) == BACKENDS, repo


def test_committed_run_is_within_tolerance_of_itself() -> None:
    committed = drift.load(COMMITTED)
    ok, failures = drift.compare(committed, committed)
    assert not failures
    assert len(ok) == len(REPOS) * len(BACKENDS)
    assert drift.main(["--fresh", str(COMMITTED), "--committed", str(COMMITTED)]) == 0


def test_altered_recall_beyond_five_points_is_drift() -> None:
    report = _report()
    fresh = copy.deepcopy(report)
    _summary(fresh, "flask", "neuralmind")["mean_recall"] -= 0.06
    assert _run_main(fresh, report) == 1

    within = copy.deepcopy(report)
    _summary(within, "flask", "neuralmind")["mean_recall"] -= 0.05
    assert _run_main(within, report) == 0


def test_cost_tolerance_is_relative_to_committed_tokens() -> None:
    report = _report()
    # requests/neuralmind is committed at 927.9 tokens; the old absolute 0.10
    # tolerance flagged a 928 here. Rounding must pass, 9% must pass, 11% must not.
    for factor, expected in ((928 / 927.9, 0), (1.09, 0), (1.11, 1), (0.89, 1)):
        fresh = copy.deepcopy(report)
        _summary(fresh, "requests", "neuralmind")["mean_tokens"] *= factor
        assert _run_main(fresh, report) == expected, factor


def test_nothing_to_compare_fails_instead_of_passing() -> None:
    report = _report()
    assert _run_main(report, {"repos": []}) == 1
    assert _run_main(report, {}) == 1


def test_repo_skipped_by_the_fresh_run_fails() -> None:
    report = _report()
    fresh = copy.deepcopy(report)
    for repo in fresh["repos"]:
        if repo["name"] == "rich":
            repo.clear()
            repo.update({"name": "rich", "skipped": "checkout unavailable (no network?)"})
    _, failures = drift.compare(drift.extract(fresh), drift.extract(report))
    assert len(failures) == len(BACKENDS)
    assert all(f.startswith("rich/") for f in failures)
    assert _run_main(fresh, report) == 1


def test_numbers_the_committed_run_does_not_publish_fail() -> None:
    # A repo added to the manifest, or a backend added to the run, without
    # regenerating results.json: the snapshot no longer covers everything the
    # benchmark measures. This used to pass as "NEW, not compared".
    report = _report()
    without_rich = copy.deepcopy(report)
    without_rich["repos"] = [r for r in without_rich["repos"] if r["name"] != "rich"]
    _, failures = drift.compare(drift.extract(report), drift.extract(without_rich))
    assert len(failures) == len(BACKENDS)
    assert all(f.startswith("rich/") for f in failures)
    assert _run_main(report, without_rich) == 1

    without_backend = copy.deepcopy(report)
    flask = next(r for r in without_backend["repos"] if r["name"] == "flask")
    del flask["summary"]["embedding-rag"]
    _, failures = drift.compare(drift.extract(report), drift.extract(without_backend))
    assert [f.split(":")[0] for f in failures] == ["flask/embedding-rag"]
    assert _run_main(report, without_backend) == 1


def test_drift_message_names_the_pair_and_how_to_regenerate(capsys) -> None:
    report = _report()
    fresh = copy.deepcopy(report)
    _summary(fresh, "rich", "neuralmind")["mean_recall"] -= 0.1
    assert _run_main(fresh, report) == 1
    out = capsys.readouterr().out
    assert "rich/neuralmind: recall 0.9000 vs committed 1.0000" in out
    assert "python -m evals.public.run --out bench/public" in out
    # The surfaces that must change with the snapshot, and the tests that say so.
    assert "site/claims.json" in out and "tests/test_site_claims.py" in out


# --------------------------------------------------------------------------- #
# NeuralMind against the plain vector baseline (embedding-rag)
# --------------------------------------------------------------------------- #
def test_committed_run_is_at_or_above_the_vector_baseline() -> None:
    committed = drift.load(COMMITTED)
    ok, failures = drift.vector_floor(committed, committed)
    assert not failures
    assert len(ok) == len(REPOS) + 1  # every repo's recall, plus the pooled MRR gap


def test_recall_below_the_vector_baseline_fails_the_gate() -> None:
    # v4.10.0's shape: click 0.86 for NeuralMind against 1.00 for its own index.
    fresh = copy.deepcopy(_report())
    _summary(fresh, "click", "neuralmind")["mean_recall"] = 0.8571
    _summary(fresh, "click", "embedding-rag")["mean_recall"] = 1.0
    ok, failures = drift.vector_floor(drift.extract(fresh), drift.load(COMMITTED))
    assert [f for f in failures if f.startswith("click:")]
    # Within the drift tolerance of the committed run (−14 points is not), so
    # isolate the floor: commit the same numbers and it still fails.
    assert _run_main(fresh, fresh) == 1


def test_pooled_mrr_gap_may_widen_only_by_the_tolerance() -> None:
    committed = _report()
    small, large = copy.deepcopy(committed), copy.deepcopy(committed)
    # rich has 9 of the 40 queries: widening its gap by d widens the pool's by 9d/40.
    for report, delta in ((small, 0.04 * 40 / 9), (large, 0.06 * 40 / 9)):
        _summary(report, "rich", "neuralmind")["mean_mrr"] -= delta
    base = drift.load(COMMITTED)
    assert not drift.vector_floor(drift.extract(small), base)[1]
    failures = drift.vector_floor(drift.extract(large), base)[1]
    assert any("pooled MRR gap" in f for f in failures)
