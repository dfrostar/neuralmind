# SPDX-License-Identifier: MIT
"""prompt_recall.py — the code a prompt is about, for the per-turn hook.

The ``prompt-submit`` hook action (Claude Code's ``UserPromptSubmit``, the
Hermes plugin's ``pre_llm_call``) adds a short block to each prompt naming the
code it concerns. It used to list only the spreading-activation neighbours of
the prompt's four nearest index nodes, as raw node ids. Three things made that
weak on a freshly built index:

- Spreading activation returns a seed's *neighbours*, never the seeds, so the
  code that matched the prompt best was never named.
- Documentation headings are often the nearest matches to a question, and on a
  fresh index their only edges lead to the other headings of the same page.
  Those filled the list, with activations as low as 0.004 shown as ``0.00``.
- Node ids (``src_click_core_py__command_cls__make_parser_fn``) aren't paths,
  so the agent still had to work out which file to open.

The block now names files, each with its matching symbols and their lines, in
up to three parts:

- **Code matching this prompt.** A docstring (rationale) node counts as the
  symbol its ``rationale_for`` edge describes. Files rank by the summed scores
  of their matching symbols, so a file with several matches outranks a single
  stray one. Test files come after the code they test unless the prompt names
  a test, and are ranked so before the list is cut: they repeat the code's
  vocabulary, and a test file holds many functions that each match it, so they
  often outscore the code. A prompt that only mentions tests keeps one slot
  for its best test file.
  A matched test file also credits the code file it tests, found by name
  (``test_x.py`` tests ``x.py``), with ``TESTED_CODE_CREDIT`` of its best
  score, so the code under test is listed even when only its test matched.
- **Connected to it in the synapse graph.** Other files that the synapse
  graph links directly to the listed code, mostly code, though a doc that is
  edited with it (a runbook, say) can appear: structural edges (calls,
  imports, inheritance) on a fresh index, learned co-activation as the project
  is used. A hub's activation is damped the way :meth:`SynapseStore.spread`
  damps a hub's outgoing activation, and anything left below ``LINK_FLOOR`` of
  the strongest seed is dropped.
- **Docs:** one line naming the documentation files that match.

When one file clearly leads (its matches' summed score is at least
``EXCERPT_MARGIN`` times the next file's), the block also shows the code of its
best-matching symbol, from the working tree, at most ``EXCERPT_LINES`` lines,
secrets redacted. When a source file is listed, only source files compete for
it: the excerpt shows the agent what to edit, not the test that checks it. A
list of names alone didn't change what the agent did: in the task-outcome
pilot (``bench/task_outcome/pilot``) the hook named the file to fix in 17 of
20 tasks, and the agent searched before its first edit as much as it did
without NeuralMind. The margin is the confidence gate: on those 20 tasks'
prompts, a leading file was the one to fix in 7 of the 9 where it held,
against 10 of 20 for the top file overall. ``NEURALMIND_RECALL_EXCERPT=0``
turns the excerpt off.

**Lexical anchoring** (opt-in, ``NEURALMIND_RECALL_LEXICAL=1``). The prompt's
exact identifiers (backticked and quoted spans, ``--flags``, snake_case,
CamelCase and UPPER_CASE names) are looked up in the working tree's indexed
source with one ``git grep -F`` call, and each file found gets ``LEXICAL_WEIGHT``
times the sum, over the identifiers in it, of ``1 / ln(1 + files holding the
identifier)``, added to its summed match score through its own file node. So a
file no embedding hit is in can still be named: on the hermes-agent held-out
tasks the file to fix was among the hits on 4 of 12, while the exact strings
the prompt quoted were in it on 6 of 12
(``docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md``, 2026-11-01). Test files give no
lexical evidence unless the prompt names a test; an identifier in more than
``LEXICAL_MAX_FILES`` files is dropped as uninformative. The build's BM25 index
isn't used: it holds symbol names and docstrings, and the identifiers that find
a file are mostly string literals and constants.

When none of a prompt's matches is code (a book, a docs repository, or a
question only the docs answer), its document matches are the main list
instead. Nothing here writes to the index.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

# Nearest index nodes to read per prompt. Documentation headings crowd the top
# of the list for many questions, so the old four often held no code at all.
SEARCH_N = 16
# Seeds for spreading activation (as before: 4), from the files listed first.
SEED_K = 4
# One hop: the code linked directly to what's listed. Two hops named the same
# expected files on every measured prompt, but a depth-2 spread from a node in
# a much co-edited file reads the edges of its ~200 neighbours: 0.44 s against
# 0.03 s at depth 1, for each prompt that seeds there (Click, 2026-10-06).
SPREAD_DEPTH = 1
# Spreading-activation results to keep, counted after hub damping and after the
# ones in files already listed are dropped: co-editing links every node in a
# file to every other, so a large listed file's own nodes would fill the list
# by themselves.
SPREAD_CANDIDATES = 256
# Nodes the graph file lacks, fetched from the index this many at a time.
FETCH_CHUNK = 64
# Linked node ids the opt-in cohesion check reads (the old list's length).
COHESION_CLUSTER = 8
MATCH_FILES = 4
LINKED_FILES = 3
DOC_FILES = 3
SYMBOLS_PER_FILE = 3
# A linked file is named for being linked; two symbols say where.
LINKED_SYMBOLS = 2
# A linked node needs at least this fraction of the strongest seed's
# activation. A structural edge passes (base weight 0.25, shared-namespace
# factor 0.5, hop decay 0.6: 0.075 of the seed), as do learned co-activation
# edges, which carry more weight. A doc heading's edge to its page (0.146:
# 0.044) doesn't, nor does an edge that has decayed to a third of its weight.
LINK_FLOOR = 0.05
LABEL_MAX = 60
# A matched test file gives the code file it tests (by name: test_x.py tests
# x.py) this much of its best score. At 1.0 the code under test ranks with its
# test. On the hermes-agent screen's 5 prompts, which it was tuned on, it named
# the file to fix on one more (3 of 5); on 12 held-out ones it named no more,
# and one fewer block quoted the wrong file (bench/task_outcome/
# hermes-agent-test-ranking).
TESTED_CODE_CREDIT = 1.0
# The excerpt's confidence gate: the top file's summed match score against the
# next file's. Several strong matches in one file is what a 2:1 lead takes.
EXCERPT_MARGIN = 2.0
# Lines of the leading symbol's code to show, from its first line.
EXCERPT_LINES = 40
# Lexical anchoring, opt-in (see the module docstring and the 2026-11-01
# entry in docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md, which fixed these
# before any of it was measured).
LEXICAL_ENV = "NEURALMIND_RECALL_LEXICAL"
# What one unit of lexical evidence is worth on the embedding scale: an
# identifier found in one file scores 1 / ln 2 = 1.44, so at 0.5 it counts as
# one strong match (0.72). Chosen from {0.25, 0.5, 1.0} on the pilot's 20 tasks
# and the hermes-agent screen's 5, before the held-out replay.
LEXICAL_WEIGHT = 0.5
# An identifier in more files than this says nothing about which one.
LEXICAL_MAX_FILES = 60
# Identifiers looked up per prompt, in order of appearance: bounds the grep
# and what a pasted traceback can add.
LEXICAL_MAX_IDENTIFIERS = 24
# Shorter identifiers are mostly common words.
LEXICAL_MIN_LEN = 4
# A quoted span this long is a message or a value, not an apostrophe's doing.
LEXICAL_QUOTE_MIN = 8
# The greps' shared time limit, in seconds: an identifier still being looked
# up when it runs out gives no evidence.
LEXICAL_TIMEOUT = 10.0
# Identifiers looked up at once. git grep stops at a file's first match, so a
# call per identifier beats one call with every pattern, which git matches
# pattern by pattern on every line (16 identifiers on hermes-agent's 20,000
# files: 1.9 s on a pool of four against 10 s combined, M3, 2026-11-01).
LEXICAL_WORKERS = 4
# Control characters, including line and paragraph separators: a path or label
# containing one could otherwise forge extra lines in the injected block.
_CONTROL_RUN = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029]+")
# spread() costs the walk, not the cut: read every result, then cut.
_UNCUT = 1 << 30

# The node types a graph marks code with: the built-in generator's "code", and
# the older per-symbol types (TurboVecEmbedder.SCOPE_FILTERS["code"]).
_CODE_TYPES = frozenset({"code", "function", "class", "method", "module"})
# The types that mark prose (TurboVecEmbedder.SCOPE_FILTERS["content"]). A node
# of any other type, or none, is code when its file has a code suffix, as the
# index's own code scope decides.
_PROSE_TYPES = frozenset(
    {"document", "rationale", "content", "policy", "sop", "decision", "meeting_note"}
)
_TEST_DIRS = frozenset({"test", "tests", "__tests__", "spec", "specs"})
_TEST_STEM = re.compile(r"^tests?$|^test_|_tests?$|Tests?$")
_TEST_NAME = re.compile(r"\.(test|spec)\.")
_TEST_PROMPT = re.compile(r"\b(tests?|testing|specs?|pytest|unittest)\b", re.IGNORECASE)
# A prompt names a test with a test function or class (test_parse, parse_test,
# ParserTest) or a test file's path.
_TEST_IDENT = re.compile(r"\btest_\w|\w_tests?\b|\b[A-Za-z]\w*[a-z0-9]Tests?\b")
_PATH_TOKEN = re.compile(r"[\w.-]*[/\\][\w./\\-]*|[\w-]+\.[A-Za-z]\w*")
# What a test file's name adds to the name of the code it tests.
_TEST_AFFIX = re.compile(r"^tests?_|_tests?$|(?<=[a-z0-9])Tests?$")
# The exact identifiers a prompt quotes. A single-quoted span must start and end
# at a word's edge, or "doesn't ... user's" would quote the words between.
_BACKTICKED = re.compile(r"`([^`\n]+)`")
_QUOTED = re.compile(
    rf'"([^"`\n]{{{LEXICAL_QUOTE_MIN},}}?)"|(?<!\w)\'([^\'`\n]{{{LEXICAL_QUOTE_MIN},}}?)\'(?!\w)'
)
# Words inside a quoted span that look like identifiers: letters, digits, _ - .
_SPAN_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_\-.]{3,}")
_FLAG = re.compile(r"(?<![\w-])--[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_SNAKE = re.compile(r"\b_?[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_CAMEL = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
_UPPER = re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b")
# Words a prompt is phrased with, and the task-outcome benchmark's instruction,
# that name no particular file. Repository names aren't listed: a word in
# more than LEXICAL_MAX_FILES files is dropped anyway.
_LEXICAL_STOP = frozenset("""
    python pytest tests test testing json yaml file files path paths project projects
    error errors command commands option options default value values string strings
    line lines list lists return returns true false none null empty output input
    config settings setting run runs running result results call calls code index
    store data name names type types check checks message messages number user users
    time times case cases example agent session sessions gateway model tool tools
    function functions method methods class classes module modules repository
    source fix bug issue change changes version http https www
    """.split())
# A file's own node id, as the built-in generator derives it from the path.
_NON_ID = re.compile(r"[^A-Za-z0-9]")


@dataclass
class FileRecall:
    """One file in the block, with the symbols in it that the prompt reached."""

    path: str
    score: float = 0.0
    best: float = 0.0
    symbols: list[str] = field(default_factory=list)
    # The id of the file's best-scoring symbol (not the file's own node).
    top: str = ""


@dataclass
class Excerpt:
    """The leading symbol's code, as the block shows it."""

    path: str
    start: int
    end: int
    text: str


@dataclass
class PromptRecall:
    """What the hook injects for one prompt. Empty lists mean nothing to say."""

    similarity: float = 0.0
    matches: list[FileRecall] = field(default_factory=list)
    linked: list[FileRecall] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    # Node ids behind ``linked``, strongest first, for the opt-in cohesion check.
    linked_ids: list[str] = field(default_factory=list)
    code: bool = True
    excerpt: Excerpt | None = None
    # Lexical anchoring, when it's on: the identifiers looked up and the
    # lexical score of each file they were found in (before LEXICAL_WEIGHT).
    identifiers: list[str] = field(default_factory=list)
    lexical: dict[str, float] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """Files the block names."""
        return len(self.matches) + len(self.linked) + len(self.docs)


def recall(mind: Any, prompt: str) -> PromptRecall:
    """Search, then spread from the best code matches. Raises on index errors.

    ``mind`` is a loaded :class:`~neuralmind.core.NeuralMind`. ``similarity``
    is the best match's score over every node type: the value the hook's
    ``NEURALMIND_RECALL_MIN_SIMILARITY`` gate compares.
    """
    from .core import _rationale_owners, _spread_with_aliases, _synapse_node

    hits = mind.embedder.search(prompt, n=SEARCH_N)
    nodes = _node_index(mind)
    owners = _rationale_owners(mind)
    code: dict[str, float] = {}
    other: dict[str, float] = {}
    info: dict[str, dict] = {}
    # A rationale hit's own id and score, by the code node it belongs to.
    rationale_ids: dict[str, dict[str, float]] = {}
    # The raw best score: a cosine backend's can be negative.
    similarity: float | None = None
    for hit in hits or []:
        raw_id = hit.get("id")
        if not raw_id:
            continue
        score = float(hit.get("score", 0.0))
        similarity = score if similarity is None else max(similarity, score)
        node_id = _synapse_node(str(raw_id), owners)
        node = nodes.get(node_id)
        if node is None:
            node_id = str(raw_id)
            node = nodes.get(node_id) or dict(hit.get("metadata") or {})
        elif node_id != str(raw_id):
            own = rationale_ids.setdefault(node_id, {})
            own[str(raw_id)] = max(score, own.get(str(raw_id), score))
        info[node_id] = node
        bucket = code if is_code_node(node) else other
        bucket[node_id] = max(score, bucket.get(node_id, score))

    # Test words alone don't put the tests among the code, unlike in a query
    # (context_selector._asks_about_tests): a task prompt often says how to
    # check the work ("run the existing tests with pytest", "don't change the
    # tests"), and on the task-outcome benchmark that sentence put test files
    # among the code on every prompt. On hermes-agent (2026-10-25), 18 of the
    # 32 files the hook listed over 5 tasks were under tests/. Such a prompt
    # keeps one slot for its best test file: "fix the claims guard test" is
    # about one too.
    tests_last = not _names_a_test(prompt)
    test_slot = tests_last and bool(_TEST_PROMPT.search(prompt))
    if tests_last and TESTED_CODE_CREDIT > 0:
        _credit_tested_code(code, info, nodes)
    identifiers: list[str] = []
    lexical: dict[str, float] = {}
    if lexical_enabled():
        identifiers = extract_identifiers(prompt)
        lexical = _anchor_lexical(mind, identifiers, code, info, nodes, tests_last)
    result = PromptRecall(
        similarity=0.0 if similarity is None else similarity,
        code=bool(code),
        identifiers=identifiers,
        lexical=lexical,
    )
    primary, secondary = (code, other) if code else (other, {})
    result.matches = _by_file(
        primary, info, MATCH_FILES, tests_last=tests_last, test_slot=test_slot
    )
    if result.code and os.environ.get("NEURALMIND_RECALL_EXCERPT") != "0":
        result.excerpt = _excerpt(mind, result.matches, nodes, info)
    # Only the files the block lists: a match past MATCH_FILES can still be linked.
    matched = {entry.path for entry in result.matches}

    seeds = _seeds(primary, info, result.matches)
    store = getattr(mind, "synapses", None)
    if store is not None and seeds:
        # Query feedback can have learned edges on a docstring node's own id:
        # spread from it too, at its own score, without counting its symbol's
        # score twice.
        aliases = {nid: rationale_ids[nid] for nid, _ in seeds if nid in rationale_ids}
        spread = _spread_with_aliases(store, dict(seeds), aliases, depth=SPREAD_DEPTH, top_k=_UNCUT)
        floor = LINK_FLOOR * max(score for _, score in seeds)
        # Damping only lowers an activation: what starts under the floor stays there.
        ranked = _linked(store, [(nid, e) for nid, e in spread if e >= floor], floor)
        linked = _outside(mind, ranked, nodes, info, owners, matched)
        linked = _one_per_symbol(linked, owners, nodes, info)
        result.linked = _by_file(
            linked, info, LINKED_FILES, tests_last=tests_last, symbols=LINKED_SYMBOLS
        )
        # The cohesion check reads the cluster the block shows: only nodes in
        # the linked files it lists.
        listed = {entry.path for entry in result.linked}
        result.linked_ids = [nid for nid in linked if _path(info.get(nid)) in listed][
            :COHESION_CLUSTER
        ]

    shown = matched | {entry.path for entry in result.linked}
    docs = _by_file(secondary, info, DOC_FILES, shown, rank_by_best=True)
    result.docs = [entry.path for entry in docs]
    return result


def format_block(result: PromptRecall) -> str:
    """The markdown the hook injects, or '' when there is nothing to name."""
    if not result.count:
        return ""
    lines = ["## NeuralMind associative recall", ""]
    if result.matches:
        lines.append("Code matching this prompt:" if result.code else "Files matching this prompt:")
        lines.extend(_file_line(entry) for entry in result.matches)
    if result.excerpt:
        ex = result.excerpt
        fence = "`" * max(3, _longest_backtick_run(ex.text) + 1)
        # On a prompt about tests a test file can come first; it isn't quoted.
        where = "outside the tests " if ex.path != result.matches[0].path else ""
        lines.append(
            f"Most matches {where}are in {ex.path}. Its best match, L{ex.start}-L{ex.end} "
            "(read the file before you edit it):"
        )
        lines.extend([fence, ex.text, fence])
    if result.linked:
        lines.append("Connected to it in the synapse graph:")
        lines.extend(_file_line(entry) for entry in result.linked)
    if result.docs:
        lines.append("Docs: " + ", ".join(result.docs))
    return "\n".join(lines)


def is_code_node(node: dict) -> bool:
    """Whether an index node is code: by its type, else by its file's suffix."""
    kind = node.get("file_type")
    if kind in _CODE_TYPES:
        return True
    if kind in _PROSE_TYPES:
        return False
    from .graphgen import _CODE_SUFFIXES
    from .ir import CODE_SCOPE_EXTENSIONS

    suffix = os.path.splitext(str(node.get("source_file") or ""))[1].lower()
    # The index's code scope, and every language the built-in graph parses.
    return suffix in CODE_SCOPE_EXTENSIONS or suffix in _CODE_SUFFIXES


def is_test_path(path: str) -> bool:
    """Whether ``path`` looks like a test file in the common layouts."""
    parts = path.replace("\\", "/").split("/")
    if _TEST_DIRS.intersection(part.lower() for part in parts[:-1]):
        return True
    name = parts[-1]
    return bool(_TEST_STEM.search(name.split(".")[0]) or _TEST_NAME.search(name))


def lexical_enabled() -> bool:
    """Whether lexical anchoring is on (``NEURALMIND_RECALL_LEXICAL=1``); off by default."""
    return os.environ.get(LEXICAL_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def extract_identifiers(prompt: str) -> list[str]:
    """The exact identifiers a prompt quotes, in order of appearance, deduplicated.

    Each backticked span and each quoted span of ``LEXICAL_QUOTE_MIN``
    characters or more counts whole, and so does each identifier-like word in
    it; ``--flags``, snake_case, CamelCase and UPPER_CASE names count anywhere.
    Common words (``_LEXICAL_STOP``), URLs and anything shorter than
    ``LEXICAL_MIN_LEN`` are dropped, and the list is cut at
    ``LEXICAL_MAX_IDENTIFIERS``.
    """
    found: list[tuple[int, str]] = []
    spans = [(m.start(1), m.group(1)) for m in _BACKTICKED.finditer(prompt)]
    # Quotes inside a backticked span (a JSON value, say) would otherwise pair
    # with a later quote in the prose: blank those spans before pairing.
    prose = _BACKTICKED.sub(lambda m: " " * len(m.group(0)), prompt)
    for match in _QUOTED.finditer(prose):
        group = 1 if match.group(1) is not None else 2
        spans.append((match.start(group), match.group(group)))
    for start, span in spans:
        if span.lstrip().lower().startswith(("http://", "https://")):
            continue
        words = [(start + m.start(), m.group(0)) for m in _SPAN_WORD.finditer(span)]
        # A span of common words alone ("the config file") names nothing.
        if any(_keep(word) for _, word in words):
            found.append((start, span.strip()))
            found.extend(words)
    for pattern in (_FLAG, _SNAKE, _CAMEL, _UPPER):
        found.extend((m.start(), m.group(0)) for m in pattern.finditer(prompt))
    out: list[str] = []
    seen: set[str] = set()
    for _, token in sorted(found, key=lambda item: item[0]):
        token = token.strip().strip(".,;:")
        if token in seen or not _keep(token):
            continue
        seen.add(token)
        out.append(token)
        if len(out) == LEXICAL_MAX_IDENTIFIERS:
            break
    return out


def _keep(token: str) -> bool:
    """Whether an extracted token is worth looking up."""
    low = token.strip().strip(".,;:").lower()
    return (
        len(low) >= LEXICAL_MIN_LEN
        and low not in _LEXICAL_STOP
        and not low.startswith(("http://", "https://"))
        and "\n" not in low
    )


def lexical_file_scores(
    matches: dict[str, set[str]], max_files: int = LEXICAL_MAX_FILES
) -> dict[str, float]:
    """Each file's lexical score: the sum over the identifiers in it of ``1 / ln(1 + files)``.

    ``matches`` maps an identifier to the eligible files holding it. An
    identifier in more than ``max_files`` files says nothing about which one
    and is dropped. Strongest file first.
    """
    scores: dict[str, float] = {}
    for files in matches.values():
        if not files or len(files) > max_files:
            continue
        weight = 1.0 / math.log(1 + len(files))
        for path in files:
            scores[path] = scores.get(path, 0.0) + weight
    return dict(sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])))


def _anchor_lexical(
    mind: Any,
    identifiers: list[str],
    code: dict[str, float],
    info: dict[str, dict],
    nodes: dict[str, dict],
    tests_last: bool,
) -> dict[str, float]:
    """Add each lexically matched file to ``code`` through its file node; return the lexical scores.

    The files are the indexed code files in the project's working tree that
    hold an identifier (``_grep_files``), less the test files when the prompt
    names no test. A file's own node (the built-in generator derives its id
    from the path; otherwise the node labelled with the file's name) carries
    the evidence, so ``_by_file`` sums it with the file's matches and the file
    is named without a symbol when nothing else matched in it. Fails open to
    no evidence.
    """
    if not identifiers:
        return {}
    project = str(getattr(mind, "project_path", "") or "")
    if not project:
        return {}
    try:
        raw = _grep_files(project, identifiers, _code_suffixes())
    except Exception:
        return {}
    if not raw:
        return {}
    indexed = _IndexedFiles(nodes)
    matches: dict[str, set[str]] = {}
    for identifier, files in raw.items():
        kept = {
            path
            for path in files
            if indexed.node_of(path) is not None and not (tests_last and is_test_path(path))
        }
        if kept:
            matches[identifier] = kept
    scores = lexical_file_scores(matches)
    for path, score in scores.items():
        node_id = indexed.node_of(path)
        if node_id is None:  # pragma: no cover - filtered above
            continue
        info.setdefault(node_id, nodes.get(node_id) or {"id": node_id, "source_file": path})
        code[node_id] = max(code.get(node_id, 0.0), 0.0) + LEXICAL_WEIGHT * score
    return scores


class _IndexedFiles:
    """Which files the graph holds code nodes for, and each file's own node id.

    The built-in generator's file node id is the path with every other
    character as ``_``, lowercased (``src/a.py`` -> ``src_a_py``): an O(1)
    lookup. A graph that names files otherwise gets one pass over its nodes,
    made only when that lookup misses.
    """

    def __init__(self, nodes: dict[str, dict]):
        self._nodes = nodes
        self._by_path: dict[str, str | None] | None = None

    def node_of(self, path: str) -> str | None:
        guess = _NON_ID.sub("_", path).lower()
        node = self._nodes.get(guess)
        if node is not None and _path(node) == path:
            return guess
        if self._by_path is None:
            self._by_path = {}
            for node_id, node in self._nodes.items():
                file = _path(node)
                if not file or not is_code_node(node):
                    continue
                # The file's own node is labelled with its name; else any code node in it.
                if node.get("label") == os.path.basename(file) or file not in self._by_path:
                    self._by_path[file] = node_id
        return self._by_path.get(path)


def _code_suffixes() -> set[str]:
    """Every suffix the index treats as code, with the dot."""
    from .graphgen import _CODE_SUFFIXES
    from .ir import CODE_SCOPE_EXTENSIONS

    return {s if s.startswith(".") else "." + s for s in (*CODE_SCOPE_EXTENSIONS, *_CODE_SUFFIXES)}


def _grep_files(project: str, identifiers: list[str], suffixes: set[str]) -> dict[str, set[str]]:
    """The tracked files of ``project`` holding each identifier, by exact substring.

    One ``git grep -l -F`` per identifier over the files with a code suffix,
    ``LEXICAL_WORKERS`` at a time, all under ``LEXICAL_TIMEOUT`` together. A
    project that isn't a git work tree, a missing git, or an identifier whose
    grep runs past the deadline gives no files.
    """
    if not identifiers:
        return {}
    from concurrent.futures import ThreadPoolExecutor

    pathspec = sorted(f"*{suffix}" for suffix in suffixes)
    deadline = time.monotonic() + LEXICAL_TIMEOUT

    def files_of(identifier: str) -> set[str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return set()
        try:
            proc = subprocess.run(
                ["git", "grep", "-I", "-l", "-z", "-F", "-e", identifier, "--", *pathspec],
                cwd=project,
                capture_output=True,
                timeout=remaining,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return set()
        # 1 is "no match"; anything past that is an error (not a repository, say).
        if proc.returncode != 0:
            return set()
        return {
            part.decode("utf-8", "replace").replace("\\", "/")
            for part in proc.stdout.split(b"\0")
            if part
        }

    with ThreadPoolExecutor(max_workers=min(LEXICAL_WORKERS, len(identifiers))) as pool:
        found = pool.map(files_of, identifiers)
    return {
        identifier: files for identifier, files in zip(identifiers, found, strict=True) if files
    }


def _credit_tested_code(
    code: dict[str, float], info: dict[str, dict], nodes: dict[str, dict]
) -> None:
    """Give the code a matched test file tests its file node, at the test's best score.

    A prompt about a bug often matches the test file of the module to fix
    better than the module itself: the test spells out the behaviour in the
    prompt's words. On hermes-agent, a prompt about an NVIDIA error matched
    ``tests/agent/test_error_classifier.py`` and never the fix's
    ``agent/error_classifier.py``. The code under test is found by name only
    (see :func:`_tested_paths`), so a test with no counterpart credits nothing.
    """
    tests: dict[str, float] = {}
    for node_id, score in code.items():
        path = _path(info.get(node_id))
        if path and is_test_path(path):
            tests[path] = max(score, tests.get(path, score))
    wanted = {test: _tested_name(test) for test in tests}
    names = {name for name in wanted.values() if name}
    if not names:
        return
    # One pass, a set lookup per node: a large repository's graph holds
    # hundreds of thousands of nodes. A file's own node is labelled with its
    # file name.
    found: dict[str, dict[str, str]] = {}
    for node_id, node in nodes.items():
        label = node.get("label")
        if label not in names:
            continue
        path = _path(node)
        if os.path.basename(path) == label and not is_test_path(path) and is_code_node(node):
            found.setdefault(label, {}).setdefault(path, node_id)
    for test, name in wanted.items():
        target = _tested_paths(test, found.get(name, {}))
        if target:
            node_id = found[name][target]
            info.setdefault(node_id, nodes[node_id])
            credit = TESTED_CODE_CREDIT * max(tests[test], 0.0)
            code[node_id] = max(credit, code.get(node_id, credit))


def _tested_name(test: str) -> str:
    """The file name a test file's code would have: ``test_cli.py`` -> ``cli.py``."""
    name = test.replace("\\", "/").rsplit("/", 1)[-1]
    stem, dot, suffix = name.partition(".")
    suffix = _TEST_NAME.sub(".", "." + suffix)[1:] if dot else ""
    code_stem = _TEST_AFFIX.sub("", stem)
    if not suffix or not code_stem or (code_stem == stem and not _TEST_NAME.search(name)):
        return ""
    return f"{code_stem}.{suffix}"


def _tested_paths(test: str, candidates: dict[str, str]) -> str:
    """Which of the code files named like ``test``'s counterpart it tests, or ''.

    The one at the test's own path with the test folders taken out
    (``tests/agent/test_x.py`` -> ``agent/x.py``), else the only one there is.
    """
    parts = test.replace("\\", "/").split("/")
    mirror = "/".join(p for p in parts[:-1] if p.lower() not in _TEST_DIRS)
    same = [path for path in candidates if os.path.dirname(path) == mirror]
    if len(same) == 1:
        return same[0]
    return next(iter(candidates)) if len(candidates) == 1 else ""


def _names_a_test(prompt: str) -> bool:
    """Whether ``prompt`` names a test: a test function, class or file."""
    if _TEST_IDENT.search(prompt):
        return True
    return any(is_test_path(token) for token in _PATH_TOKEN.findall(prompt))


def _seeds(
    scored: dict[str, float], info: dict[str, dict], files: list[FileRecall]
) -> list[tuple[str, float]]:
    """The best node of each listed file, then their next best, up to ``SEED_K``.

    Seeding from the files the block names keeps "connected to it" true of the
    code listed above it. The top nodes overall can all sit in one file, or in
    a test file listed after the code it tests.
    """
    per_file: dict[str, list[tuple[str, float]]] = {f.path: [] for f in files}
    for node_id, score in sorted(scored.items(), key=lambda kv: kv[1], reverse=True):
        nodes = per_file.get(_path(info.get(node_id)))
        if nodes is not None:
            nodes.append((node_id, score))
    best = [nodes[0] for nodes in per_file.values() if nodes]
    rest = sorted(
        (n for nodes in per_file.values() for n in nodes[1:]), key=lambda kv: kv[1], reverse=True
    )
    return (best + rest)[:SEED_K]


def _linked(store: Any, spread: list[tuple[str, float]], floor: float) -> dict[str, float]:
    """Damp the hubs among spread results, drop what's under ``floor``, strongest first."""
    from .synapses import HUB_DEGREE

    if not spread:
        return {}
    degrees = store.degrees([nid for nid, _ in spread])
    damped = [
        (nid, energy * _hub_factor(degrees.get(nid, 0), HUB_DEGREE)) for nid, energy in spread
    ]
    kept = [(nid, energy) for nid, energy in damped if energy >= floor]
    return dict(sorted(kept, key=lambda kv: kv[1], reverse=True))


def _outside(
    mind: Any,
    ranked: dict[str, float],
    nodes: dict[str, dict],
    info: dict[str, dict],
    owners: dict[str, str],
    matched: set[str],
) -> dict[str, float]:
    """The ``SPREAD_CANDIDATES`` strongest links in files the block doesn't list yet.

    A node the graph file lacks is fetched from the index, ``FETCH_CHUNK`` at a
    time and only until enough are found: a much-linked seed can reach
    thousands of nodes, and some backends look each one up separately.
    """
    from .core import _synapse_node

    items = list(ranked.items())
    kept: dict[str, float] = {}
    for start in range(0, len(items), FETCH_CHUNK):
        chunk = items[start : start + FETCH_CHUNK]
        missing = [
            nid for nid, _ in chunk if nid not in nodes and _synapse_node(nid, owners) not in nodes
        ]
        for node in _fetch(mind, missing):
            nodes[node["id"]] = node
        for nid, energy in chunk:
            # Co-editing activates a function's docstring node too: name the function.
            info.setdefault(
                nid, nodes.get(_synapse_node(nid, owners)) or nodes.get(nid) or {"id": nid}
            )
            path = _path(info[nid])
            if path and path not in matched:
                kept[nid] = energy
                if len(kept) == SPREAD_CANDIDATES:
                    return kept
    return kept


def _one_per_symbol(
    linked: dict[str, float], owners: dict[str, str], nodes: dict[str, dict], info: dict[str, dict]
) -> dict[str, float]:
    """A function and its docstring node, both linked, count once: at the higher activation.

    Query feedback reinforces raw hit ids, so both can carry edges to a seed;
    the block shows them as one symbol, and summing them would promote its file.
    """
    from .core import _synapse_node

    merged: dict[str, float] = {}
    for nid, energy in linked.items():
        owner = _synapse_node(nid, owners)
        key = owner if owner in nodes else nid
        info.setdefault(key, nodes.get(key) or info.get(nid) or {"id": key})
        merged[key] = max(energy, merged.get(key, 0.0))
    return dict(sorted(merged.items(), key=lambda kv: kv[1], reverse=True))


def _excerpt(
    mind: Any, files: list[FileRecall], nodes: dict[str, dict], info: dict[str, dict]
) -> Excerpt | None:
    """The leading source file's best symbol, when it leads by ``EXCERPT_MARGIN``.

    The symbol runs from its own line to the line before the next symbol the
    graph records in the file, at most ``EXCERPT_LINES``. Read from the working
    tree, so it's what the agent would read; None when the file can't be read
    or the node has no line. Fails open.
    """
    # The listed source files compete for it; a test file only when none is listed.
    pool = [entry for entry in files if not is_test_path(entry.path)] or files
    if not pool or not pool[0].top:
        return None
    lead = pool[0]
    runner_up = pool[1].score if len(pool) > 1 else 0.0
    if runner_up > 0 and lead.score < EXCERPT_MARGIN * runner_up:
        return None
    start = _line_of(info.get(lead.top) or nodes.get(lead.top))
    if start is None:
        return None
    # Code nodes only: a docstring's node starts inside the symbol it documents.
    later = [
        line
        for node in nodes.values()
        if _path(node) == lead.path
        and is_code_node(node)
        and (line := _line_of(node)) is not None
        and line > start
    ]
    end = min([start + EXCERPT_LINES - 1] + [line - 1 for line in later])
    try:
        from .secret_scan import redact_text

        source = os.path.join(str(mind.project_path), lead.path)
        with open(source, encoding="utf-8", errors="replace") as fh:
            text = fh.read().splitlines()[start - 1 : end]
    except Exception:
        return None
    while text and not text[-1].strip():
        text.pop()
    if not text:
        return None
    scrubbed, _ = redact_text("\n".join(text))
    return Excerpt(path=lead.path, start=start, end=start + len(text) - 1, text=scrubbed)


def _line_of(node: dict | None) -> int | None:
    """The line a node's ``source_location`` (``L42``) starts on."""
    location = str((node or {}).get("source_location") or "")
    match = re.match(r"L(\d+)", location)
    return int(match.group(1)) if match else None


def _longest_backtick_run(text: str) -> int:
    return max((len(run) for run in re.findall(r"`+", text)), default=0)


def _hub_factor(degree: int, hub_degree: int) -> float:
    return math.sqrt(hub_degree / degree) if degree > hub_degree else 1.0


def _by_file(
    scored: dict[str, float],
    info: dict[str, dict],
    limit: int,
    exclude: set[str] | None = None,
    *,
    tests_last: bool = False,
    test_slot: bool = False,
    rank_by_best: bool = False,
    symbols: int = SYMBOLS_PER_FILE,
) -> list[FileRecall]:
    """Group scored nodes by source file, best files first, up to ``limit``.

    ``tests_last`` ranks test files after the others before the cut;
    ``test_slot`` then gives the best test file the last slot if code filled them.
    """
    files: dict[str, FileRecall] = {}
    for node_id, score in sorted(scored.items(), key=lambda kv: kv[1], reverse=True):
        node = info.get(node_id) or {}
        path = _path(node)
        if not path or (exclude and path in exclude):
            continue
        entry = files.setdefault(path, FileRecall(path=path))
        # A cosine score can be negative: a dissimilar hit isn't evidence
        # against the file its best match is in.
        entry.score += max(score, 0.0)
        entry.best = max(entry.best, score)
        symbol = _symbol(node, path)
        if symbol and not entry.top:
            entry.top = node_id
        if symbol and symbol not in entry.symbols and len(entry.symbols) < symbols:
            entry.symbols.append(symbol)

    def key(entry: FileRecall) -> tuple:
        rank = entry.best if rank_by_best else entry.score
        return (not (tests_last and is_test_path(entry.path)), rank)

    ranked = sorted(files.values(), key=key, reverse=True)
    listed = ranked[:limit]
    if test_slot and listed and not any(is_test_path(entry.path) for entry in listed):
        best_test = next((entry for entry in ranked[limit:] if is_test_path(entry.path)), None)
        if best_test is not None:
            listed[-1] = best_test
    return listed


def _path(node: dict | None) -> str:
    return _one_line(str((node or {}).get("source_file") or ""))


def _one_line(text: str) -> str:
    """Control characters become one space; other whitespace is kept (a path can hold it)."""
    return _CONTROL_RUN.sub(" ", text).strip()


def _file_line(entry: FileRecall) -> str:
    if not entry.symbols:
        return f"- {entry.path}"
    return f"- {entry.path}: " + ", ".join(entry.symbols)


def _symbol(node: dict, path: str) -> str:
    """``label Lnn`` for a symbol node; '' for the node that is the file itself."""
    label = " ".join(_one_line(str(node.get("label") or "")).split())
    if not label or label == os.path.basename(path):
        return ""
    if len(label) > LABEL_MAX:
        label = label[: LABEL_MAX - 1].rstrip() + "…"
    location = _one_line(str(node.get("source_location") or ""))
    return f"{label} {location}" if location.startswith("L") else label


def _node_index(mind: Any) -> dict[str, dict]:
    """The loaded graph's nodes by id (the hook has already loaded the graph)."""
    nodes = getattr(mind.embedder, "nodes", None) or []
    return {str(n["id"]): n for n in nodes if isinstance(n, dict) and n.get("id")}


def _fetch(mind: Any, node_ids: list[str]) -> list[dict]:
    """Nodes the graph file doesn't hold (ingested content), from the vector store."""
    if not node_ids:
        return []
    try:
        fetched = mind.embedder.get_nodes_by_ids(node_ids)
    except Exception:
        return []
    return [{"id": f["id"], **(f.get("metadata") or {})} for f in fetched if f.get("id")]
