"""SWE-bench retrieval harness — hermetic tests (no network, no heavy deps).

The real run (`python -m evals.swe_bench.runner --run`) clones repos and needs the
retrieval stack; these tests pin the patch→gold-files parser, the fixture schema,
and the offline self-check so the harness can't silently drift.

    python -m pytest tests/test_swe_bench_harness.py
"""

from __future__ import annotations

import unittest

from evals.swe_bench import runner


class GoldPatchParserTests(unittest.TestCase):
    def test_basic_git_diff(self) -> None:
        patch = (
            "diff --git a/src/pkg/sessions.py b/src/pkg/sessions.py\n"
            "--- a/src/pkg/sessions.py\n"
            "+++ b/src/pkg/sessions.py\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        self.assertEqual(runner.gold_files_from_patch(patch), ["sessions.py"])

    def test_multiple_files_ordered_and_deduped(self) -> None:
        patch = (
            "+++ b/a/one.py\n"
            "+++ b/b/two.py\n"
            "+++ b/a/one.py\n"  # duplicate basename collapses
        )
        self.assertEqual(runner.gold_files_from_patch(patch), ["one.py", "two.py"])

    def test_dev_null_skipped(self) -> None:
        # A pure deletion has a /dev/null post-image — not a gold file to retrieve.
        patch = "--- a/gone.py\n+++ /dev/null\n"
        self.assertEqual(runner.gold_files_from_patch(patch), [])

    def test_non_git_diff_with_timestamp(self) -> None:
        patch = "+++ b/pkg/exceptions.py\t2026-01-01 00:00:00\n"
        self.assertEqual(runner.gold_files_from_patch(patch), ["exceptions.py"])

    def test_empty_patch(self) -> None:
        self.assertEqual(runner.gold_files_from_patch(""), [])


class FixtureAndSelfcheckTests(unittest.TestCase):
    def test_fixture_matches_parser(self) -> None:
        data = runner.load_fixture()
        self.assertTrue(data["tasks"])
        for t in data["tasks"]:
            self.assertEqual(
                runner.gold_files_from_patch(t["patch"]),
                t["expected_gold_files"],
                msg=f"fixture {t['instance_id']} gold parse drifted",
            )

    def test_selfcheck_passes_offline(self) -> None:
        self.assertEqual(runner.selfcheck(), 0)

    def test_main_default_is_selfcheck(self) -> None:
        self.assertEqual(runner.main([]), 0)
        self.assertEqual(runner.main(["--selfcheck"]), 0)


if __name__ == "__main__":
    unittest.main()
