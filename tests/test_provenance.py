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


def test_harvest_parses_decisions_via_injected_reader():
    from neuralmind.provenance import harvest

    fake_log = [("aaa", "chore: x"), ("bbb", RESOLVE_MSG)]
    records = harvest(project_path=".", log_reader=lambda p, n: fake_log)
    assert len(records) == 1
    assert records[0].subjects[0] == "resolveOrgId"


def test_harvest_fails_open_when_reader_raises():
    from neuralmind.provenance import harvest

    def boom(_p, _n):
        raise RuntimeError("no git here")

    assert harvest(project_path=".", log_reader=boom) == []


def test_read_git_log_returns_list_on_real_repo():
    # Integration: runs against this checkout; must not raise and must return
    # (sha, message) tuples. Decision count may be zero — that's fine.
    from neuralmind.provenance import harvest, read_git_log

    entries = read_git_log(".", limit=10)
    assert isinstance(entries, list)
    assert isinstance(harvest("."), list)  # fails open even if 0 decisions


# --------------------------------------------------------------------------- #
# Lifecycle — the decision store's status applied before recall
# --------------------------------------------------------------------------- #


def test_trailer_id_survives_a_rewritten_commit():
    from neuralmind.provenance import trailer_decision_id

    a = parse_decision(RESOLVE_MSG, sha="aaa")
    b = parse_decision(RESOLVE_MSG.replace("          /health", "  /health"), sha="bbb")
    assert trailer_decision_id(a) == trailer_decision_id(b)
    other = parse_decision("x\n\nDecision: `retry` lives in the uploader.", sha="aaa")
    assert trailer_decision_id(other) != trailer_decision_id(a)


def test_invalidated_decision_is_not_recalled():
    from neuralmind.provenance import apply_lifecycle, trailer_decision_id

    records = parse_log([("bbb", RESOLVE_MSG)])
    statuses = {trailer_decision_id(records[0]): "INVALIDATED"}
    assert recall(apply_lifecycle(records, statuses), "why is resolveOrgId per-handler?") == []


def test_stale_decision_is_recalled_with_a_warning():
    from neuralmind.provenance import apply_lifecycle, trailer_decision_id

    records = parse_log([("bbb", RESOLVE_MSG)])
    statuses = {trailer_decision_id(records[0]): "STALE"}
    hits = recall(apply_lifecycle(records, statuses), "why is resolveOrgId per-handler?")
    assert [h.status for h in hits] == ["STALE"]
    assert "[STALE:" in format_decisions(hits)


def test_unknown_to_the_store_stays_active():
    from neuralmind.provenance import apply_lifecycle

    records = parse_log([("bbb", RESOLVE_MSG)])
    assert apply_lifecycle(records, {}) == records
    assert "STALE" not in format_decisions(records)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
