"""Public-benchmark harness — hermetic unit tests.

No network, no embedding stack: the real-repo run is exercised out-of-band
(`python -m evals.public.run`) and its output committed under `bench/public/`.
These tests pin the *scoring and assembly* logic so the published numbers can't
silently drift — they use a tiny synthetic repo and a fake retrieval backend.

    python -m pytest tests/test_public_benchmark.py
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from evals.public import backends, run
from evals.public.backends import RepoFiles


class _FakeNM:
    """Stand-in for NeuralMind: deterministic search() + query() over fixtures."""

    def __init__(self, search_hits, query_files, query_tokens):
        self._search = search_hits
        self._qfiles = query_files
        self._qtokens = query_tokens

    def search(self, question, n=8):  # noqa: ARG002
        return self._search[:n]

    def query(self, question):  # noqa: ARG002
        class _R:
            top_search_hits = [{"metadata": {"source_file": f}} for f in self._qfiles]
            tokens = self._qtokens

        return _R()


def _repo() -> RepoFiles:
    return RepoFiles(
        root=Path("/synthetic"),
        texts={
            "auth.py": "# HTTP basic authentication applied to an outgoing request\n"
            "class HTTPBasicAuth:\n    def __call__(self, r):\n        return r\n" * 3,
            "models.py": "# prepared request body and headers\n"
            "class PreparedRequest:\n    pass\n" * 5,
            "utils.py": "# small helper utilities\ndef helper():\n    return 1\n" * 4,
        },
    )


class BackendScoringTests(unittest.TestCase):
    def test_full_file_is_total_recall_at_total_cost(self) -> None:
        repo = _repo()
        r = backends.run_full_file("q", ["auth.py"], repo)
        self.assertEqual(r.recall, 1.0)
        self.assertTrue(r.found)
        # Cost is the sum of all files (the naive ceiling), > any single file.
        self.assertGreater(r.tokens, 0)
        self.assertEqual(set(r.context_files), set(repo.texts))

    def test_ripgrep_ranks_by_keyword_and_can_miss(self) -> None:
        repo = _repo()
        # "basic authentication" keywords hit auth.py only.
        hit = backends.run_ripgrep("q", "basic authentication callable", ["auth.py"], repo)
        self.assertIn("auth.py", hit.context_files)
        self.assertEqual(hit.recall, 1.0)
        # A query whose keywords appear nowhere → empty context → recall 0 (honest miss).
        miss = backends.run_ripgrep("q", "kubernetes sharding raft", ["auth.py"], repo)
        self.assertEqual(miss.context_files, [])
        self.assertEqual(miss.recall, 0.0)
        self.assertFalse(miss.found)

    def test_embedding_rag_uses_chunk_tokens_and_dedups_files(self) -> None:
        nm = _FakeNM(
            search_hits=[
                {"metadata": {"source_file": "models.py"}, "document": "class PreparedRequest"},
                {"metadata": {"source_file": "models.py"}, "document": "def prepare"},
                {"metadata": {"source_file": "auth.py"}, "document": "class HTTPBasicAuth"},
            ],
            query_files=[],
            query_tokens=0,
        )
        r = backends.run_embedding_rag("q", "prepared request", ["models.py"], nm)
        self.assertEqual(r.context_files, ["models.py", "auth.py"])  # dedup, rank-order
        self.assertEqual(r.recall, 1.0)
        self.assertGreater(r.tokens, 0)  # cost = retrieved chunk text

    def test_neuralmind_partial_recall_on_multifile_gold(self) -> None:
        nm = _FakeNM(search_hits=[], query_files=["sessions.py"], query_tokens=900)
        # Cross-file gold needs BOTH files; only one retrieved → recall 0.5, not found.
        r = backends.run_neuralmind(
            "q", "session sends via adapter", ["sessions.py", "adapters.py"], nm
        )
        self.assertAlmostEqual(r.recall, 0.5)
        self.assertFalse(r.found)
        self.assertEqual(r.tokens, 900)

    def test_recall_is_containment_not_capped_by_rank(self) -> None:
        # Gold present deep in the list still counts for containment recall.
        repo = _repo()
        r = backends.run_full_file("q", ["utils.py"], repo)
        self.assertEqual(r.recall, 1.0)


class ReportShapeTests(unittest.TestCase):
    def test_aggregate_and_render_are_consistent(self) -> None:
        repo = _repo()
        per_query = [
            backends.run_full_file("a", ["auth.py"], repo),
            backends.run_full_file("b", ["models.py"], repo),
        ]
        agg = run._aggregate(per_query)
        self.assertEqual(agg["n"], 2)
        self.assertEqual(agg["mean_recall"], 1.0)
        self.assertEqual(agg["found_rate"], 1.0)

    def test_render_markdown_reports_every_backend_and_losses(self) -> None:
        report = {
            "tokenizer": "tiktoken o200k_base",
            "oracle": "def-site",
            "backends": run.BACKEND_ORDER,
            "repos": [
                {
                    "name": "demo",
                    "commit": "deadbeef0000",
                    "n_queries": 1,
                    "retrieval_stack_available": True,
                    "summary": {
                        "full-file": {
                            "mean_recall": 1.0,
                            "found_rate": 1.0,
                            "mean_tokens": 40000,
                            "mean_mrr": 1.0,
                        },
                        "neuralmind": {
                            "mean_recall": 1.0,
                            "found_rate": 1.0,
                            "mean_tokens": 1000,
                            "mean_mrr": 0.9,
                        },
                    },
                    "queries": [],
                    "losses": [
                        {
                            "query_id": "x",
                            "backend": "neuralmind",
                            "gold_files": ["a.py", "b.py"],
                            "context_files": ["a.py"],
                            "found": False,
                        },
                    ],
                }
            ],
        }
        md = run.render_markdown(report)
        self.assertIn("gold-file recall", md)
        self.assertIn("40× fewer", md)  # 40000/1000
        self.assertIn("Where NeuralMind loses", md)
        self.assertIn("`x`", md)

    def test_degraded_env_does_not_claim_a_clean_sweep(self) -> None:
        # When the retrieval stack is unavailable NeuralMind never ran, so the
        # report must say "not evaluated", never "no misses".
        report = {
            "tokenizer": "approx",
            "oracle": "def-site",
            "backends": run.BACKEND_ORDER,
            "repos": [
                {
                    "name": "demo",
                    "commit": "deadbeef0000",
                    "n_queries": 1,
                    "retrieval_stack_available": False,
                    "summary": {
                        "full-file": {
                            "mean_recall": 1.0,
                            "found_rate": 1.0,
                            "mean_tokens": 40000,
                            "mean_mrr": 1.0,
                        },
                    },
                    "queries": [],
                    "losses": [],
                }
            ],
        }
        md = run.render_markdown(report)
        self.assertIn("not evaluated", md)
        self.assertNotIn("No NeuralMind gold-file misses", md)

    def test_run_all_forces_injection_off_and_restores(self) -> None:
        import os

        manifest = {"repos": []}  # no repos → no builds/network
        os.environ["NEURALMIND_SYNAPSE_INJECT"] = "1"
        try:
            report = run.run_all(manifest, only="none")
            # Even though the caller set =1, the public run pins it off and says so.
            self.assertEqual(report["synapse_injection"], "0")
            # ...and the caller's value is restored afterward (no global leak).
            self.assertEqual(os.environ["NEURALMIND_SYNAPSE_INJECT"], "1")
        finally:
            os.environ.pop("NEURALMIND_SYNAPSE_INJECT", None)

    def test_committed_results_match_manifest_repos(self) -> None:
        # The published snapshot must stay in sync with the manifest (no orphans).
        root = Path(__file__).resolve().parent.parent
        manifest = json.loads((root / "evals/public/manifest.json").read_text())
        results_path = root / "bench/public/results.json"
        if not results_path.exists():  # snapshot optional in a fresh checkout
            self.skipTest("no committed results snapshot")
        results = json.loads(results_path.read_text())
        manifest_names = {r["name"] for r in manifest["repos"]}
        result_names = {r["name"] for r in results["repos"]}
        self.assertTrue(result_names.issubset(manifest_names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
