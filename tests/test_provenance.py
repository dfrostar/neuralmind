"""Tests for decision provenance capture (prototype).

Stdlib-only, like the rest of the synapse-layer tests: the parser and recall
are pure functions over ``(sha, message)`` tuples.
"""

from __future__ import annotations

from neuralmind.provenance import (
    format_decisions,
    parse_decision,
    parse_log,
    recall,
)

RESOLVE_MSG = """cli: resolve org id per handler

Decision: resolveOrgId is per-handler, not middleware — avoids Prisma on
          /health, /metrics, /token; keeps tests simple.
Subjects: `resolveOrgId`, `authMiddleware`
"""


def test_parses_multiline_decision_and_subjects():
    rec = parse_decision(RESOLVE_MSG, sha="ba25fedb7e36a08")
    assert rec is not None
    assert "per-handler" in rec.rationale
    assert "keeps tests simple" in rec.rationale  # continuation folded in
    assert rec.subjects == ("resolveOrgId", "authMiddleware")
    assert rec.short_sha == "ba25fed"


def test_backticked_symbols_become_subjects_without_explicit_trailer():
    msg = "fix: guard\n\nDecision: `validateSession` must call `resolveOrgId` too."
    rec = parse_decision(msg)
    assert rec is not None
    assert rec.subjects == ("validateSession", "resolveOrgId")


def test_no_trailer_is_none():
    assert parse_decision("chore: bump deps\n\nRoutine update.") is None


def test_empty_trailer_value_is_none():
    assert parse_decision("x\n\nDecision:   \n") is None


def test_parse_log_skips_non_decision_commits():
    log = [
        ("aaa", "chore: nothing here"),
        ("bbb", RESOLVE_MSG),
        ("ccc", "feat: also nothing"),
    ]
    records = parse_log(log)
    assert len(records) == 1
    assert records[0].sha == "bbb"


def test_recall_surfaces_decision_when_subject_lights_up():
    records = parse_log([("bbb", RESOLVE_MSG)])
    hit = recall(records, "why is resolveOrgId per-handler?")
    assert len(hit) == 1
    assert hit[0].subjects[0] == "resolveOrgId"


def test_recall_is_quiet_for_unrelated_query():
    records = parse_log([("bbb", RESOLVE_MSG)])
    assert recall(records, "how does the embedder cache work?") == []


def test_format_empty_when_nothing():
    assert format_decisions([]) == ""


def test_format_names_subjects_rationale_and_commit():
    records = parse_log([("ba25fedb7e", RESOLVE_MSG)])
    text = format_decisions(records)
    assert "resolveOrgId" in text
    assert "keeps tests simple" in text
    assert "ba25fed" in text
    assert "decision provenance" in text.lower()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
