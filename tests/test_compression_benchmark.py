"""The committed compression benchmark has to describe the hooks as they are.

``bench/compression/results.json`` is what the docs quote about PostToolUse
compression. These checks recompute everything that needs no network — the Bash
corpus is committed — and fail when the hooks no longer behave the way the
committed run recorded. A change to the compressors or the hook wiring therefore
ships with a regenerated benchmark::

    python -m evals.compression.run --out bench/compression

rather than leaving the docs quoting numbers from before it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.compression import run as bench
from evals.public.tokens import tokenizer_name
from neuralmind import compressors

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS = REPO_ROOT / "bench" / "compression" / "results.json"
# The run that measured the hooks as v4.3.4 shipped them — the reason they no
# longer inject context. It is a fixed record: never regenerated.
V434 = REPO_ROOT / "bench" / "compression" / "results-v4.3.4.json"
DOC = REPO_ROOT / "docs" / "benchmarks" / "compression.md"

REGENERATE = (
    "re-run `python -m evals.compression.run --out bench/compression` and commit the result"
)


@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def test_the_corpus_is_the_one_the_results_were_computed_from(committed):
    assert (
        bench._corpus_digest(bench.CORPUS_DIR) == committed["meta"]["bash_corpus_sha256"]
    ), f"evals/compression/corpus/bash changed since the committed run; {REGENERATE}"


def test_the_compressor_defaults_are_the_ones_measured(committed):
    measured = committed["meta"]["compressor_thresholds"]
    current = {
        "bash_max_chars": compressors.BASH_MAX_CHARS,
        "bash_small_passthrough": compressors.BASH_SMALL_PASSTHROUGH,
        "bash_tail_lines": compressors.BASH_TAIL_LINES,
        "search_max_matches": compressors.SEARCH_MAX_MATCHES,
        "read_min_chars": measured["read_min_chars"],
    }
    assert current == measured, f"compressor defaults changed; {REGENERATE}"


def test_bash_results_match_what_the_hooks_do_today(committed, tmp_path):
    fresh = {row["id"]: row for row in bench.bash_samples(bench.CORPUS_DIR, tmp_path)}
    recorded = {s["id"]: s for s in committed["samples"] if s["tool"] == "Bash"}
    assert fresh.keys() == recorded.keys()

    fields = [
        "event",
        "hook_fired",
        "hook_json_valid",
        "compressor_reachable",
        "must_keep_lines",
        "must_keep_kept",
        "as_shipped_sha256",
        "compressor_only_sha256",
    ]
    # Token counts are only comparable under the tokenizer that produced them;
    # the digests above pin the delivered text exactly either way.
    if tokenizer_name() == committed["meta"]["tokenizer"]:
        fields += ["baseline_tokens", "as_shipped_tokens", "compressor_only_tokens"]
    drift = [
        f"{cid}.{field}: committed {recorded[cid][field]!r}, now {fresh[cid][field]!r}"
        for cid in sorted(fresh)
        for field in fields
        if fresh[cid][field] != recorded[cid][field]
    ]
    assert not drift, "the Bash hook no longer does what the committed run recorded:\n  " + (
        "\n  ".join(drift) + f"\n{REGENERATE}"
    )


def test_the_read_hook_still_handles_claude_codes_payload_as_recorded(
    committed, tmp_path, monkeypatch
):
    # Claude Code gives PostToolUse the Read tool's structured output, with the
    # text under file.content. The committed run records whether the hook acts
    # on that payload. Stub the compressor wherever a hook might reach it, so
    # the check needs no index: a hook that compresses Reads again would return
    # the stub's output as its response.
    stub = lambda *a, **k: "stubbed skeleton"  # noqa: E731
    monkeypatch.setattr("neuralmind.hooks.compress_read", stub, raising=False)
    monkeypatch.setattr("neuralmind.compressors.compress_read", stub)
    path = tmp_path / "module.py"
    text = "def f():\n    return 1\n" * 200
    path.write_text(text, encoding="utf-8")
    lines = len(text.splitlines())
    payload = {
        "hook_event_name": "PostToolUse",
        "cwd": str(tmp_path),
        "tool_name": "Read",
        "tool_input": {"file_path": str(path)},
        "tool_response": {
            "type": "text",
            "file": {
                "filePath": str(path),
                "content": text,
                "numLines": lines,
                "startLine": 1,
                "totalLines": lines,
            },
        },
    }
    fires_now = bench.drive_hook("compress-read", payload) is not None
    fired_then = committed["summary"]["Read"]["hook_fired"] > 0
    assert fires_now == fired_then, (
        f"the Read hook's handling of Claude Code's payload changed "
        f"(fired then: {fired_then}, fires now: {fires_now}); {REGENERATE}"
    )


def _pct(value: float) -> str:
    return f"{value:+.1f}%"


def test_the_docs_quote_the_committed_figures(committed):
    s = committed["summary"]
    expected = {
        "Read, as shipped": _pct(s["Read"]["as_shipped_change_pct"]),
        "Bash, as shipped": _pct(s["Bash"]["as_shipped_change_pct"]),
        "Grep content mode, as shipped": _pct(
            s["Grep"]["per_mode"]["content"]["as_shipped_change_pct"]
        ),
        "Read, compressor only": _pct(s["Read"]["compressor_only_change_pct"]),
        "Bash, compressor only": _pct(s["Bash"]["compressor_only_change_pct"]),
        "Grep content mode, compressor only": _pct(
            s["Grep"]["per_mode"]["content"]["compressor_only_change_pct"]
        ),
    }
    before = json.loads(V434.read_text(encoding="utf-8"))["summary"]
    expected.update(
        {
            "Bash, v4.3.4 hooks": _pct(before["Bash"]["as_shipped_change_pct"]),
            "Grep content mode, v4.3.4 hooks": _pct(
                before["Grep"]["per_mode"]["content"]["as_shipped_change_pct"]
            ),
        }
    )
    doc = DOC.read_text(encoding="utf-8").replace("−", "-")
    missing = [f"{label} ({value})" for label, value in expected.items() if value not in doc]
    assert not missing, f"{DOC.relative_to(REPO_ROOT)} doesn't quote: {', '.join(missing)}"
