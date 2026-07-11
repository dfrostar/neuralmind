"""Tests for the optional SCIP precision pass (neuralmind/precision.py).

Loaded in isolation (no chromadb): the protobuf decoder + descriptor parser are
pure stdlib and always run; the refine-on-a-real-graph tests need tree-sitter
(to build the graph) and skip cleanly without it. Exercises the committed SCIP
fixture under tests/fixtures/scip_precision/.

    python tests/test_precision.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


precision = _load("neuralmind_precision", "neuralmind/precision.py")
graphgen = _load("neuralmind_graphgen", "neuralmind/graphgen.py")

FIXTURE = _REPO / "tests" / "fixtures" / "scip_precision"
INDEX = FIXTURE / "index.scip"


class DecoderTests(unittest.TestCase):
    """Pure-stdlib protobuf decode + descriptor parsing."""

    def test_parse_committed_index(self) -> None:
        idx = precision.parse_scip_index(INDEX.read_bytes())
        self.assertEqual(len(idx.documents), 1)
        doc = idx.documents[0]
        self.assertEqual(doc.relative_path, "app.py")
        self.assertEqual(len(doc.occurrences), 4)
        defs = [o for o in doc.occurrences if o.is_definition]
        refs = [o for o in doc.occurrences if not o.is_definition]
        self.assertEqual(len(defs), 3)
        self.assertEqual(len(refs), 1)
        # The run() definition carries an enclosing (body) range.
        run = next(o for o in defs if o.symbol.endswith("run()."))
        self.assertTrue(run.enclosing_range)

    def test_descriptor_parser(self) -> None:
        self.assertEqual(
            precision._parse_descriptor("scip-python python . . app/A#handle()."),
            ("A", "handle", True),
        )
        self.assertEqual(
            precision._parse_descriptor("scip-python python . . app/run()."),
            (None, "run", True),
        )
        self.assertEqual(
            precision._parse_descriptor("scip-python python . . app/A#"),
            (None, "A", False),
        )

    def test_disabled_by_default(self) -> None:
        # No NEURALMIND_PRECISION in the environment → off.
        os.environ.pop("NEURALMIND_PRECISION", None)
        self.assertFalse(precision.is_enabled())
        graph = {"nodes": [], "links": []}
        out, stats = precision.maybe_refine(FIXTURE, graph)
        self.assertIs(out, graph)
        self.assertIsNone(stats)

    def test_find_scip_index(self) -> None:
        self.assertEqual(precision.find_scip_index(FIXTURE), INDEX)


@unittest.skipUnless(graphgen.is_available(), "tree-sitter not installed")
class RefineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = graphgen.build_graph(FIXTURE)
        cls.index = precision.parse_scip_index(INDEX.read_bytes())

    def _calls(self, graph) -> set[tuple[str, str]]:
        return {(e["source"], e["target"]) for e in graph["links"] if e["relation"] == "calls"}

    def test_heuristic_links_wrong_method(self) -> None:
        """Baseline: the bare-name heuristic links run() to B.handle (the first
        same-named method), which is wrong."""
        calls = self._calls(self.graph)
        self.assertIn(("app_py__run_fn", "app_py__b_cls__handle_fn"), calls)
        self.assertNotIn(("app_py__run_fn", "app_py__a_cls__handle_fn"), calls)

    def test_precision_corrects_the_call(self) -> None:
        graph = graphgen.build_graph(FIXTURE)  # fresh copy
        refined, stats = precision.refine_graph(graph, self.index)
        calls = self._calls(refined)
        # Now run() → A.handle (correct), and the wrong B.handle edge is gone.
        self.assertIn(("app_py__run_fn", "app_py__a_cls__handle_fn"), calls)
        self.assertNotIn(("app_py__run_fn", "app_py__b_cls__handle_fn"), calls)
        self.assertEqual(stats.calls_added, 1)
        self.assertEqual(stats.heuristic_calls_removed, 1)

    def test_refine_only_touches_covered_files(self) -> None:
        """build_index.py isn't in the SCIP index, so its heuristic call edges
        survive untouched (precision is scoped to covered files)."""
        graph = graphgen.build_graph(FIXTURE)
        before = {
            (e["source"], e["target"])
            for e in graph["links"]
            if e["relation"] == "calls" and e["source_file"] != "app.py"
        }
        refined, _ = precision.refine_graph(graph, self.index)
        after = {
            (e["source"], e["target"])
            for e in refined["links"]
            if e["relation"] == "calls" and e["source_file"] != "app.py"
        }
        self.assertEqual(before, after)

    def test_no_dangling_edges_after_refine(self) -> None:
        graph = graphgen.build_graph(FIXTURE)
        refined, _ = precision.refine_graph(graph, self.index)
        ids = {n["id"] for n in refined["nodes"]}
        for e in refined["links"]:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)

    def test_maybe_refine_runs_when_enabled(self) -> None:
        os.environ["NEURALMIND_PRECISION"] = "1"
        try:
            graph = graphgen.build_graph(FIXTURE)
            refined, stats = precision.maybe_refine(FIXTURE, graph)
            self.assertIsNotNone(stats)
            calls = self._calls(refined)
            self.assertIn(("app_py__run_fn", "app_py__a_cls__handle_fn"), calls)
        finally:
            os.environ.pop("NEURALMIND_PRECISION", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
