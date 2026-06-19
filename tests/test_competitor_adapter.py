"""Competitor adapter — hermetic parsing/scoring tests (no binary, no network).

The live head-to-head runs out-of-band (`python -m evals.public.competitor`) and
its results are committed under `bench/public/competitor/`. These tests pin the
adapter's response parsing, retrieval-depth cap, keyword mapping, and scoring on
mocked competitor output so the published numbers can't silently drift.

    python -m pytest tests/test_competitor_adapter.py
"""

from __future__ import annotations

import json
import unittest

from evals.public import competitor
from evals.public.backends import RepoFiles


def _wrapped(inner: dict) -> dict:
    """Build the competitor's MCP `content[0].text` JSON envelope."""
    return {"content": [{"type": "text", "text": json.dumps(inner)}]}


class CompetitorAdapterTests(unittest.TestCase):
    def test_unwrap_mcp_envelope(self) -> None:
        inner = {"semantic_results": [{"file_path": "src/a.py", "score": 0.5}]}
        self.assertEqual(competitor._unwrap(_wrapped(inner)), inner)
        # A bare (already-unwrapped) dict passes through.
        self.assertEqual(competitor._unwrap(inner), inner)
        # Malformed text → None (fail-closed).
        self.assertIsNone(competitor._unwrap({"content": [{"text": "{ not json"}]}))

    def test_unwrap_rejects_error_envelopes(self) -> None:
        # `isError` envelope → None (fail-closed), even if the text parses.
        env = {
            "content": [{"text": json.dumps({"project": "p", "status": "error"})}],
            "isError": True,
        }
        self.assertIsNone(competitor._unwrap(env))
        # Inner error/status=error without the flag is rejected too.
        self.assertIsNone(
            competitor._unwrap(_wrapped({"error": "project not found", "available_projects": []}))
        )
        self.assertIsNone(competitor._unwrap(_wrapped({"status": "error"})))

    def test_index_repo_requires_indexed_status(self) -> None:
        orig = competitor._cli
        # Errored index (rejected by _unwrap) → None, no project name leaks.
        competitor._cli = lambda *a, **k: None  # noqa: ARG005
        try:
            self.assertIsNone(competitor.index_repo("/x", cache_dir=None))  # type: ignore[arg-type]
        finally:
            competitor._cli = orig
        # A result without status="indexed" is also rejected.
        competitor._cli = lambda *a, **k: {"project": "p", "status": "partial"}  # noqa: ARG005
        try:
            self.assertIsNone(competitor.index_repo("/x", cache_dir=None))  # type: ignore[arg-type]
        finally:
            competitor._cli = orig
        # A confirmed index returns the project name.
        competitor._cli = lambda *a, **k: {"project": "proj", "status": "indexed"}  # noqa: ARG005
        try:
            self.assertEqual(competitor.index_repo("/x", cache_dir=None), "proj")  # type: ignore[arg-type]
        finally:
            competitor._cli = orig

    def test_competitor_keywords_keeps_all_words(self) -> None:
        # The fair mapping: every word, no stopword filtering (best for the rival).
        kw = competitor.competitor_keywords("How is the HTTP basic auth applied?")
        self.assertEqual(kw, ["how", "is", "the", "http", "basic", "auth", "applied"])

    def test_semantic_files_caps_at_depth_and_dedups(self) -> None:
        # 10 ranked hits across 3 files; cap at SEM_LIMIT, dedup by basename,
        # preserve rank order. Patch the CLI to return a wrapped response.
        ranked = [{"file_path": f"src/f{i}.py", "score": 1.0 - i * 0.1} for i in range(10)]
        ranked[1]["file_path"] = "src/f0.py"  # duplicate basename of rank-0
        inner = {"semantic_results": ranked}
        orig = competitor._cli
        competitor._cli = lambda *a, **k: inner  # noqa: ARG005
        try:
            files = competitor.semantic_files("proj", ["x"], cache_dir=None)  # type: ignore[arg-type]
        finally:
            competitor._cli = orig
        # Only the first SEM_LIMIT (8) hits are considered, then dedup'd.
        self.assertLessEqual(len(files), competitor.SEM_LIMIT)
        self.assertEqual(files[0], "f0.py")
        self.assertEqual(len(files), len(set(files)))  # no dup basenames

    def test_empty_keywords_returns_no_files(self) -> None:
        self.assertEqual(competitor.semantic_files("proj", [], cache_dir=None), [])  # type: ignore[arg-type]

    def test_run_competitor_scores_like_other_backends(self) -> None:
        repo = RepoFiles(root=None, texts={"auth.py": "x" * 40, "utils.py": "y" * 40})  # type: ignore[arg-type]
        # Competitor surfaces utils.py (rank 1) then auth.py (rank 2).
        inner = {
            "semantic_results": [
                {"file_path": "src/utils.py", "score": 0.4},
                {"file_path": "src/auth.py", "score": 0.2},
            ]
        }
        orig = competitor._cli
        competitor._cli = lambda *a, **k: inner  # noqa: ARG005
        try:
            r = competitor.run_competitor(
                "basic-auth", "how is basic auth applied", ["auth.py"], "proj", repo, cache_dir=None  # type: ignore[arg-type]
            )
        finally:
            competitor._cli = orig
        self.assertEqual(r.backend, "competitor")
        self.assertEqual(r.context_files, ["utils.py", "auth.py"])
        self.assertEqual(r.recall, 1.0)  # gold present
        self.assertTrue(r.found)
        self.assertAlmostEqual(r.reciprocal_rank, 0.5)  # gold at rank 2
        self.assertGreater(r.tokens, 0)  # cost = surfaced files' tokens

    def test_committed_traces_match_manifest(self) -> None:
        # If the live snapshot is committed, its repos must be from the manifest.
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        results = root / "bench/public/competitor/results.json"
        if not results.exists():
            self.skipTest("no committed competitor snapshot")
        manifest = json.loads((root / "evals/public/manifest.json").read_text())
        names = {r["name"] for r in manifest["repos"]}
        rows = json.loads(results.read_text())
        self.assertTrue({r["name"] for r in rows}.issubset(names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
