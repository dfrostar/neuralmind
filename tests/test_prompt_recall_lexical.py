"""Tests for prompt_recall's lexical anchoring (``NEURALMIND_RECALL_LEXICAL=1``).

The exact identifiers a prompt quotes, found in the working tree's indexed
source, add evidence to the block's file ranking, so a file no embedding hit
is in can still be named. Pre-registered in
docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md (2026-11-01); off by default, and
with the flag unset nothing here runs.
"""

from __future__ import annotations

import math
import subprocess

import pytest

from neuralmind import prompt_recall
from neuralmind.prompt_recall import (
    extract_identifiers,
    format_block,
    lexical_file_scores,
    recall,
)
from tests.test_prompt_recall import _Mind, _node

BENCH_TAIL = (
    "You are working in a checkout of the hermes-agent repository. Find the cause and fix it "
    "in the source code. Don't add or change tests: the fix is judged by tests you can't see. "
    "You can run the existing tests with `python -m pytest <path>`. Stop when the fix is done."
)


@pytest.fixture
def lexical_on(monkeypatch):
    monkeypatch.setenv(prompt_recall.LEXICAL_ENV, "1")


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def test_backticked_spans_count_whole_and_by_word():
    prompt = "Only a raw socket error gives the retryable `503 owner_unreachable` back."
    assert extract_identifiers(prompt) == ["503 owner_unreachable", "owner_unreachable"]


def test_quoted_messages_flags_and_names_are_found_in_order():
    prompt = (
        'The dashboard answers 409 ("Gateway connection failed; no local fallback") when '
        "`hermes dashboard --no-fallback` runs; WebSocketClient and permission_denied and "
        "OPENROUTER_API_KEY are involved."
    )
    assert extract_identifiers(prompt) == [
        "Gateway connection failed; no local fallback",
        "connection",
        "failed",
        "local",
        "fallback",
        "hermes dashboard --no-fallback",
        "hermes",
        "dashboard",
        "--no-fallback",
        "no-fallback",
        "WebSocketClient",
        "permission_denied",
        "OPENROUTER_API_KEY",
    ]


def test_common_words_short_tokens_urls_and_spans_of_common_words_are_dropped():
    prompt = "see `run` and `the config file` at `https://example.com/x_y` and `tests`"
    assert extract_identifiers(prompt) == []
    # One identifier-like word keeps the span, and the span keeps its words.
    assert extract_identifiers("see `the config file for x_val`") == [
        "the config file for x_val",
        "x_val",
    ]


def test_an_apostrophe_is_not_a_quote():
    prompt = "it doesn't work when the user's name is long, and `foo_bar` fails"
    assert extract_identifiers(prompt) == ["foo_bar"]


def test_quotes_inside_a_backticked_span_dont_pair_with_the_prose():
    # A JSON value in backticks holds quotes; the prose after it holds more.
    prompt = (
        'A call like `{"action": "remove", "old_text": "port 8080"}` renders as `memory ?` '
        'and the old shape `-memory: "port 8080"` still works, as in "the usual way of it".'
    )
    assert extract_identifiers(prompt) == [
        '{"action": "remove", "old_text": "port 8080"}',
        "action",
        "remove",
        "old_text",
        "port",
        "memory ?",
        "memory",
        '-memory: "port 8080"',
        "the usual way of it",
        "usual",
    ]


def test_the_benchmarks_instruction_adds_nothing():
    assert extract_identifiers(BENCH_TAIL) == []


def test_a_leading_underscore_and_camel_case_count():
    prompt = "TypeError: _build_sandbox_env() got multiple values; see ErrorClassifier"
    assert extract_identifiers(prompt) == ["TypeError", "_build_sandbox_env", "ErrorClassifier"]


def test_identifiers_are_capped_in_order_of_appearance():
    prompt = " ".join(f"name_{i:02d}" for i in range(40))
    found = extract_identifiers(prompt)
    assert len(found) == prompt_recall.LEXICAL_MAX_IDENTIFIERS
    assert found[0] == "name_00" and found[-1] == "name_23"


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def test_an_identifier_is_worth_the_inverse_log_of_the_files_holding_it():
    scores = lexical_file_scores(
        {
            "only_here": {"a.py"},
            "two_files": {"a.py", "b.py"},
            "everywhere": {f"f{i}.py" for i in range(100)},
        }
    )
    assert scores["a.py"] == pytest.approx(1 / math.log(2) + 1 / math.log(3))
    assert scores["b.py"] == pytest.approx(1 / math.log(3))
    # The identifier in 100 files said nothing about any of them.
    assert "f0.py" not in scores
    assert list(scores) == ["a.py", "b.py"]


def test_the_common_identifier_cut_is_a_parameter():
    scores = lexical_file_scores({"x": {"a.py", "b.py", "c.py"}}, max_files=2)
    assert scores == {}


# --------------------------------------------------------------------------- #
# The grep
# --------------------------------------------------------------------------- #
def _repo(tmp_path, files: dict[str, str]):
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "i"],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def test_the_grep_finds_exact_case_sensitive_substrings_in_code_files(tmp_path):
    repo = _repo(
        tmp_path,
        {
            "pkg/a.py": "STATUS = {'storage_unavailable': 503}\n",
            "pkg/b.py": "x = 'Storage_Unavailable'\nmsg = 'no local fallback here'\n",
            "docs/notes.md": "storage_unavailable is a code\n",
            "pkg/c.ts": "const k = 'storage_unavailable';\n",
        },
    )
    found = prompt_recall._grep_files(
        str(repo), ["storage_unavailable", "no local fallback", "absent_token"], {".py", ".ts"}
    )
    assert found == {
        "storage_unavailable": {"pkg/a.py", "pkg/c.ts"},
        "no local fallback": {"pkg/b.py"},
    }


def test_a_directory_that_isnt_a_repository_gives_nothing(tmp_path):
    (tmp_path / "a.py").write_text("storage_unavailable\n")
    assert prompt_recall._grep_files(str(tmp_path), ["storage_unavailable"], {".py"}) == {}


def test_a_grep_past_the_deadline_gives_nothing(tmp_path, monkeypatch):
    repo = _repo(tmp_path, {"a.py": "token_here\n"})
    monkeypatch.setattr(prompt_recall, "LEXICAL_TIMEOUT", 0.0)
    assert prompt_recall._grep_files(str(repo), ["token_here"], {".py"}) == {}


# --------------------------------------------------------------------------- #
# Fusion with the embedding ranking
# --------------------------------------------------------------------------- #
NODES = [
    _node("agent_display_py", "agent/display.py", "display.py"),
    _node("agent_display_py__render_fn", "agent/display.py", "render()", 40),
    _node("agent_memory_manager_py", "agent/memory_manager.py", "memory_manager.py"),
    _node("agent_memory_manager_py__write_fn", "agent/memory_manager.py", "write()", 10),
    _node("tools_memory_tool_py__run_fn", "tools/memory_tool.py", "run()", 5),
    _node("tests_agent_test_display_py__test_fn", "tests/agent/test_display.py", "test()", 1),
    _node("docs_memory_md__h1", "docs/memory.md", "Memory", 1, "document"),
]
HITS = [("agent_memory_manager_py__write_fn", 0.6), ("tools_memory_tool_py__run_fn", 0.5)]


class _RootedMind(_Mind):
    def __init__(self, root, **kwargs):
        super().__init__(None, **kwargs)
        self.project_path = str(root)


def _canned(matches: dict[str, set[str]]):
    """A ``_grep_files`` that returns ``matches`` and records what it was asked."""
    calls: list[list[str]] = []

    def grep(project, identifiers, suffixes):
        calls.append(list(identifiers))
        return {k: set(v) for k, v in matches.items() if k in identifiers}

    grep.calls = calls
    return grep


def test_off_by_default_the_grep_never_runs_and_the_block_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.delenv(prompt_recall.LEXICAL_ENV, raising=False)

    def boom(*args):
        raise AssertionError("lexical anchoring ran with the flag off")

    monkeypatch.setattr(prompt_recall, "_grep_files", boom)
    result = recall(_RootedMind(tmp_path, hits=HITS, nodes=NODES), "the `old_text` key is lost")
    assert [f.path for f in result.matches] == ["agent/memory_manager.py", "tools/memory_tool.py"]
    assert result.identifiers == [] and result.lexical == {}


def test_a_file_no_hit_is_in_is_named_through_its_file_node(lexical_on, monkeypatch, tmp_path):
    grep = _canned({"old_text": {"agent/display.py", "tools/memory_tool.py"}})
    monkeypatch.setattr(prompt_recall, "_grep_files", grep)
    mind = _RootedMind(tmp_path, hits=HITS, nodes=NODES)
    result = recall(mind, "the `old_text` key is lost. " + BENCH_TAIL)
    assert grep.calls == [["old_text"]]
    lexical = prompt_recall.LEXICAL_WEIGHT / math.log(3)
    by_path = {f.path: f for f in result.matches}
    # display.py is named on lexical evidence alone, with no symbol to show.
    assert by_path["agent/display.py"].symbols == []
    assert by_path["agent/display.py"].score == pytest.approx(lexical)
    # memory_tool.py's hit and its lexical evidence add up.
    assert by_path["tools/memory_tool.py"].score == pytest.approx(0.5 + lexical)
    assert result.identifiers == ["old_text"]
    assert result.lexical == {
        "agent/display.py": pytest.approx(1 / math.log(3)),
        "tools/memory_tool.py": pytest.approx(1 / math.log(3)),
    }
    assert "- agent/display.py" in format_block(result).splitlines()


def test_lexical_evidence_can_put_a_file_first(lexical_on, monkeypatch, tmp_path):
    # Two identifiers found only in display.py outweigh one 0.6 hit elsewhere.
    grep = _canned({"old_text": {"agent/display.py"}, "memory ?": {"agent/display.py"}})
    monkeypatch.setattr(prompt_recall, "_grep_files", grep)
    mind = _RootedMind(tmp_path, hits=HITS, nodes=NODES)
    result = recall(mind, "`old_text` renders as `memory ?`. " + BENCH_TAIL)
    assert [f.path for f in result.matches][0] == "agent/display.py"
    assert result.matches[0].score == pytest.approx(2 * prompt_recall.LEXICAL_WEIGHT / math.log(2))


def test_test_files_give_no_lexical_evidence_unless_the_prompt_names_a_test(
    lexical_on, monkeypatch, tmp_path
):
    grep = _canned({"old_text": {"tests/agent/test_display.py", "agent/display.py"}})
    monkeypatch.setattr(prompt_recall, "_grep_files", grep)
    mind = _RootedMind(tmp_path, hits=HITS, nodes=NODES)
    result = recall(mind, "the `old_text` key is lost. " + BENCH_TAIL)
    assert "tests/agent/test_display.py" not in {f.path for f in result.matches}
    # The test file wasn't an eligible file, so display.py's identifier was in one file.
    assert result.lexical == {"agent/display.py": pytest.approx(1 / math.log(2))}
    result = recall(mind, "why does test_display fail on `old_text`")
    assert "tests/agent/test_display.py" in {f.path for f in result.matches}


def test_files_the_index_doesnt_hold_give_no_evidence(lexical_on, monkeypatch, tmp_path):
    grep = _canned({"old_text": {"agent/display.py", "vendor/other.py", "docs/memory.md"}})
    monkeypatch.setattr(prompt_recall, "_grep_files", grep)
    result = recall(_RootedMind(tmp_path, hits=HITS, nodes=NODES), "`old_text` is lost")
    assert set(result.lexical) == {"agent/display.py"}
    assert "vendor/other.py" not in format_block(result)


def test_a_file_whose_node_id_doesnt_follow_the_path_is_found_by_label(
    lexical_on, monkeypatch, tmp_path
):
    nodes = [
        _node("file-node-42", "src/Widgets.cs", "Widgets.cs"),
        _node("sym-7", "src/Widgets.cs", "Widget", 3),
        _node("other", "src/Other.cs", "other()", 1),
    ]
    grep = _canned({"WidgetFactory": {"src/Widgets.cs"}})
    monkeypatch.setattr(prompt_recall, "_grep_files", grep)
    result = recall(_RootedMind(tmp_path, hits=[("other", 0.4)], nodes=nodes), "WidgetFactory")
    assert [f.path for f in result.matches][0] == "src/Widgets.cs"


def test_no_identifiers_means_no_grep(lexical_on, monkeypatch, tmp_path):
    grep = _canned({})
    monkeypatch.setattr(prompt_recall, "_grep_files", grep)
    recall(_RootedMind(tmp_path, hits=HITS, nodes=NODES), "why is this slow")
    assert grep.calls == []


def test_a_grep_failure_leaves_the_ranking_as_it_was(lexical_on, monkeypatch, tmp_path):
    def boom(*args):
        raise OSError("no git")

    monkeypatch.setattr(prompt_recall, "_grep_files", boom)
    result = recall(_RootedMind(tmp_path, hits=HITS, nodes=NODES), "`old_text` is lost")
    assert [f.path for f in result.matches] == ["agent/memory_manager.py", "tools/memory_tool.py"]
    assert result.lexical == {}


def test_end_to_end_on_a_repository(lexical_on, tmp_path):
    repo = _repo(
        tmp_path,
        {
            "agent/display.py": "def render(op):\n    return f'{op}' if op else 'memory ?'\n",
            "agent/memory_manager.py": "def write(): pass\n",
            "tools/memory_tool.py": "def run(): pass\n",
            "tests/agent/test_display.py": "def test(): assert 'memory ?'\n",
        },
    )
    result = recall(
        _RootedMind(repo, hits=HITS, nodes=NODES), "the line reads `memory ?`. " + BENCH_TAIL
    )
    # `memory ?` whole and its word `memory`, each in display.py alone (the test file doesn't count).
    assert result.lexical == {"agent/display.py": pytest.approx(2 / math.log(2))}
    assert "agent/display.py" in {f.path for f in result.matches}
