"""Tests for the backend parity gate logic (evals/parity/run.py).

Loaded in isolation (not via ``import neuralmind``) so the suite runs without
chromadb/tree-sitter — the same dependency-light philosophy as the synapse,
graphgen, and faithfulness tests. Only the *gate math + rendering* are exercised
here (pure, no I/O); the build-and-measure path needs the full retrieval stack
and is covered by the CI parity job.

    python tests/test_parity_gate.py
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Import run.py in isolation. Its module-level imports are stdlib-only
# (json/os/shutil/subprocess/tempfile) — harness/neuralmind are imported lazily
# inside measure() — so this loads with no heavy deps installed.
_spec = importlib.util.spec_from_file_location(
    "neuralmind_parity_run", _REPO / "evals" / "parity" / "run.py"
)
assert _spec and _spec.loader
parity = importlib.util.module_from_spec(_spec)
# Register before exec: the @dataclass decorator resolves the module via
# sys.modules (for KW_ONLY detection) under `from __future__ import annotations`.
sys.modules[_spec.name] = parity
_spec.loader.exec_module(parity)


def _measurement(backend: str, **overrides):
    """A BackendMeasurement with sensible defaults, overridable per field."""
    defaults = {
        "backend": backend,
        "generated_by": "graphify" if backend == "graphify" else "neuralmind.graphgen",
        "code_nodes": 64,
        "mean_reduction": 6.5,
        "faithfulness_delta": 0.20,
        "nm_mean_recall": 0.75,
        "naive_mean_recall": 0.55,
        "nm_mean_grounding": 0.9,
        "n_queries": 9,
    }
    defaults.update(overrides)
    return parity.BackendMeasurement(**defaults)


class GateTests(unittest.TestCase):
    def test_builtin_at_parity_passes(self) -> None:
        g = _measurement("graphify")
        b = _measurement("builtin")  # identical metrics → trivially within tolerance
        checks = parity.evaluate_gate(g, b)
        self.assertTrue(all(c.passed for c in checks))

    def test_builtin_slightly_below_within_tolerance_passes(self) -> None:
        g = _measurement(
            "graphify", mean_reduction=6.5, faithfulness_delta=0.20, nm_mean_recall=0.75
        )
        # ~17% lower reduction (< 25% tol), 5 points lower faithfulness (< 0.10).
        b = _measurement(
            "builtin", mean_reduction=5.4, faithfulness_delta=0.15, nm_mean_recall=0.70
        )
        checks = parity.evaluate_gate(g, b)
        self.assertTrue(all(c.passed for c in checks), [c.detail for c in checks if not c.passed])

    def test_reduction_regression_fails(self) -> None:
        g = _measurement("graphify", mean_reduction=6.5)
        b = _measurement("builtin", mean_reduction=2.0)  # far below tol and floor
        checks = {c.name: c.passed for c in parity.evaluate_gate(g, b)}
        self.assertFalse(checks["reduction within tolerance of graphify"])
        self.assertFalse(checks["reduction ≥ absolute floor"])

    def test_reduction_floor_independent_of_graphify(self) -> None:
        # Even if graphify itself were weak, the built-in must clear the floor.
        g = _measurement("graphify", mean_reduction=4.2)
        b = _measurement("builtin", mean_reduction=3.5)  # within 25% of 4.2 but < floor 4.0
        checks = {c.name: c.passed for c in parity.evaluate_gate(g, b)}
        self.assertTrue(checks["reduction within tolerance of graphify"])
        self.assertFalse(checks["reduction ≥ absolute floor"])

    def test_faithfulness_regression_fails(self) -> None:
        g = _measurement("graphify", faithfulness_delta=0.20)
        b = _measurement("builtin", faithfulness_delta=0.05)  # 15 points lower > 0.10 tol
        checks = {c.name: c.passed for c in parity.evaluate_gate(g, b)}
        self.assertFalse(checks["faithfulness delta within tolerance of graphify"])

    def test_negative_faithfulness_delta_fails_floor(self) -> None:
        g = _measurement("graphify", faithfulness_delta=-0.02)
        # Within tolerance of graphify's (also negative) delta, but below the
        # absolute floor of 0.0 → must still fail.
        b = _measurement("builtin", faithfulness_delta=-0.05)
        checks = {c.name: c.passed for c in parity.evaluate_gate(g, b)}
        self.assertFalse(checks["faithfulness delta ≥ absolute floor"])

    def test_recall_regression_fails(self) -> None:
        g = _measurement("graphify", nm_mean_recall=0.80)
        b = _measurement("builtin", nm_mean_recall=0.60)  # 20 points lower > 0.10 tol
        checks = {c.name: c.passed for c in parity.evaluate_gate(g, b)}
        self.assertFalse(checks["fact recall within tolerance of graphify"])


class LanguageCoverageTests(unittest.TestCase):
    """The multi-language structural parity check (TS/Go) gate logic."""

    def _cov(self, **kw):
        defaults = {
            "language": "typescript",
            "graphify_symbols": 54,
            "builtin_symbols": 60,
            "covered": 54,
            "dangling": 0,
        }
        defaults.update(kw)
        return parity.LanguageCoverage(**defaults)

    def test_full_coverage_passes(self) -> None:
        checks = parity.evaluate_language_gate(self._cov())
        self.assertTrue(all(c.passed for c in checks))

    def test_coverage_ratio(self) -> None:
        self.assertAlmostEqual(self._cov(graphify_symbols=50, covered=45).coverage, 0.9)
        self.assertEqual(self._cov(graphify_symbols=0, covered=0).coverage, 0.0)

    def test_below_floor_fails(self) -> None:
        checks = {
            c.name: c.passed
            for c in parity.evaluate_language_gate(
                self._cov(graphify_symbols=54, covered=40)  # ~74% < 90%
            )
        }
        self.assertFalse(checks["typescript: symbol coverage ≥ floor"])

    def test_dangling_fails(self) -> None:
        checks = {c.name: c.passed for c in parity.evaluate_language_gate(self._cov(dangling=3))}
        self.assertFalse(checks["typescript: no dangling edges"])


class RenderTests(unittest.TestCase):
    def test_pass_banner_and_metrics(self) -> None:
        g = _measurement("graphify")
        b = _measurement("builtin")
        checks = parity.evaluate_gate(g, b)
        md = parity.render_markdown(g, b, checks)
        self.assertIn("✅ PASS", md)
        self.assertIn("mean reduction", md)
        self.assertIn("graphify vs built-in", md)

    def test_fail_banner(self) -> None:
        g = _measurement("graphify", mean_reduction=6.5)
        b = _measurement("builtin", mean_reduction=1.0)
        checks = parity.evaluate_gate(g, b)
        md = parity.render_markdown(g, b, checks)
        self.assertIn("❌ FAIL", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
