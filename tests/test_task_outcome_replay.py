"""The prompt-recall replay gate's scoring, on hand-written hook blocks. Stdlib-only."""

from __future__ import annotations

from evals.task_outcome import replay

TASK = {"gold_files": ["pkg/cli.py"]}
FIX = {"pkg/cli.py": [(40, 42)]}

BLOCK = """## NeuralMind associative recall

Code matching this prompt:
- pkg/cli.py: run() L30, main() L90
- pkg/util.py
Most matches are in pkg/cli.py. Its best match, L30-L45 (read the file before you edit it):
```
def run():
```
Connected to it in the synapse graph:
- pkg/other.py: helper() L3"""


def test_a_block_naming_the_gold_file_first_with_an_excerpt_on_the_fix() -> None:
    record = replay.score(BLOCK, TASK, FIX)
    assert record["listed"] == ["pkg/cli.py", "pkg/util.py", "pkg/other.py"]
    assert record["named"] and record["first"]
    assert record["excerpt"] == ["pkg/cli.py", 30, 45]
    assert record["excerpt_on_gold"] and record["excerpt_on_fix"]


def test_an_excerpt_beside_the_fix_is_on_the_gold_file_but_not_on_the_fix() -> None:
    record = replay.score(BLOCK, TASK, {"pkg/cli.py": [(46, 50)]})
    assert record["excerpt_on_gold"] and not record["excerpt_on_fix"]


def test_a_gold_file_only_linked_is_named_not_first() -> None:
    record = replay.score(BLOCK, {"gold_files": ["pkg/other.py"]}, {})
    assert record["named"] and not record["first"]
    assert not record["excerpt_on_gold"]


def test_an_excerpt_from_after_a_listed_test_file_is_scored() -> None:
    block = BLOCK.replace(
        "- pkg/cli.py:", "- tests/test_cli.py: test_run() L5\n- pkg/cli.py:"
    ).replace("Most matches are in", "Most matches outside the tests are in")
    record = replay.score(block, TASK, FIX)
    assert record["named"] and not record["first"]
    assert record["excerpt"] == ["pkg/cli.py", 30, 45] and record["excerpt_on_fix"]


def test_an_empty_block_names_nothing() -> None:
    record = replay.score("", TASK, FIX)
    assert record["listed"] == [] and not record["named"] and not record["excerpt_shown"]


def test_floors_fail_low_counts_but_not_a_missing_excerpt() -> None:
    records = [replay.score(BLOCK, TASK, FIX)] * 3 + [replay.score("", TASK, FIX)] * 17
    summary = replay.summarize(records)
    assert summary["named"] == 3 and summary["excerpt_on_gold_share"] == 1.0
    assert "named 3 < floor" in " ".join(replay.below_floors(summary))
    no_excerpt = replay.summarize([replay.score("", TASK, FIX)] * 20)
    assert no_excerpt["excerpt_on_gold_share"] is None
    assert not any("excerpt" in f for f in replay.below_floors(no_excerpt))
