"""Label-free retrieval self-probe: does the index retrieve its own symbols?

Token reduction proves NeuralMind is *cheap*. The golden-suite quality eval
(``evals/quality``) proves the ranking is *good* — but only against a set of
hand-labeled ``expected_modules`` that ship with the source repo. Neither one
answers the question a user actually has: **on my codebase, can the agent find
the right file when it asks about a symbol?**

This module is that missing, label-free probe. It samples indexed symbols,
synthesizes a natural-language query from each symbol's own identity (the
humanized label — never its node id), asks the index to retrieve it back, and
scores whether the symbol's source file came up in the top-k. No fixtures, no
hand labeling: it works on any built project.

The idea is borrowed from long-context "needle-in-a-haystack" evals (e.g.
S-NIAH in the Recursive Language Models paper): rather than measuring cost, it
measures whether the right node still surfaces as the index grows — the
retrieval analog of context rot. The most useful output is the **blind-spot
list**: sampled symbols whose own file the index failed to retrieve, i.e. the
places an agent would come up empty.

Pure + stdlib-only (query synthesis, sampling, scoring), mirroring the synapse,
IR, and quality layers: the embedding round trip is injected as a callable, so
everything here is testable without the vector stack. The metric math is reused
wholesale from :mod:`neuralmind.quality`.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from . import quality

# Default retrieval depth and the cutoffs we report. Mirrors evals/quality so a
# probe number is comparable to the golden-suite numbers.
DEFAULT_K = 10
DEFAULT_KS: tuple[int, ...] = (1, 3, 5)
DEFAULT_SAMPLE_SIZE = 50

# Code-like extensions we strip off a file-level label so "auth.py" probes as
# "auth", not "auth py".
_CODE_EXTENSIONS = (
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".php",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cs",
    ".kt",
    ".swift",
    ".md",
)

# camelCase / PascalCase boundary: a lower/digit followed by an upper, or an
# acronym run followed by a Capitalized word (HTTPServer -> HTTP, Server).
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
# Everything that isn't alphanumeric is a separator (dotted qualnames, slashes,
# snake_case underscores, etc.).
_NON_WORD_RE = re.compile(r"[^0-9A-Za-z]+")


def humanize_label(label: str) -> str:
    """Turn a code identifier into the words a developer would actually type.

    ``authenticate_user`` -> ``"authenticate user"``,
    ``HTTPServerFactory`` -> ``"http server factory"``,
    ``auth.py`` -> ``"auth"``. Returns ``""`` when nothing survives (e.g. a
    label that is all punctuation), which the sampler treats as not probeable.
    """
    if not label:
        return ""
    base = label
    for ext in _CODE_EXTENSIONS:
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
            break
    words: list[str] = []
    for chunk in _NON_WORD_RE.split(base):
        if not chunk:
            continue
        for word in _CAMEL_RE.split(chunk):
            word = word.strip()
            if word:
                words.append(word.lower())
    return " ".join(words)


def synthesize_query(node: dict) -> str:
    """Build the probe query for one node from its identity, never its id.

    Prefers the humanized label; falls back to the humanized file stem so a
    node with an opaque label (but a real source file) is still probeable.
    """
    query = humanize_label(str(node.get("label", "")))
    if query:
        return query
    source = str(node.get("source_file", ""))
    stem = source.replace("\\", "/").rsplit("/", 1)[-1]
    return humanize_label(stem)


def is_probeable(node: dict) -> bool:
    """A node can be probed when it has a source file and a non-empty query.

    Rationale/doc pseudo-nodes without a ``source_file`` are skipped — there's
    no module to retrieve back for them.
    """
    if not node.get("source_file"):
        return False
    return bool(synthesize_query(node))


def sample_nodes(
    nodes: Iterable[dict],
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    *,
    seed: int = 0,
    code_only: bool = True,
) -> list[dict]:
    """Deterministically sample probeable nodes.

    ``code_only`` keeps the probe focused on code symbols (``file_type ==
    "code"``) when any exist, falling back to every probeable node otherwise so
    a docs-only or oddly-typed graph still yields a sample. The sample is
    reproducible for a given ``seed`` so a probe number is stable across runs
    and comparable over time.
    """
    pool = [n for n in nodes if is_probeable(n)]
    if code_only:
        code = [n for n in pool if n.get("file_type") == "code"]
        if code:
            pool = code
    if sample_size <= 0 or sample_size >= len(pool):
        # Sort for determinism before returning the whole pool — embedder node
        # order is insertion order, which is stable, but be explicit.
        return sorted(pool, key=lambda n: str(n.get("id", "")))
    rng = random.Random(seed)
    return rng.sample(pool, sample_size)


@dataclass
class ProbeReport:
    """Result of a retrieval self-probe over a project's own symbols."""

    suite: quality.SuiteQuality
    blind_spots: list[dict]
    index_size: int
    k: int
    sample_size: int = 0
    blind_spot_total: int = 0

    def to_dict(self) -> dict:
        d = self.suite.to_dict()
        # Rename the inherited "suite" label to something honest for this view.
        d["suite"] = "self-probe"
        d["index_size"] = self.index_size
        d["k"] = self.k
        d["sample_size"] = self.sample_size
        d["blind_spots"] = self.blind_spots
        d["blind_spot_total"] = self.blind_spot_total
        return d


# Cap on how many blind spots we keep in the report so a pathological index
# (everything misses) can't produce an unbounded blob. The total count is
# always reported via ``blind_spot_total``.
MAX_BLIND_SPOTS = 25


def run_probe(
    samples: list[dict],
    retrieve: Callable[[str], list[str]],
    *,
    ks: tuple[int, ...] = DEFAULT_KS,
    k: int = DEFAULT_K,
    index_size: int = 0,
) -> ProbeReport:
    """Score a sampled self-probe.

    ``retrieve`` maps a query string to a ranked list of source-file modules
    (the embedding round trip, injected so this stays testable). For each
    sample the relevant set is the symbol's own source file; answerability is
    measured at ``k`` (the retrieval depth). Returns a :class:`ProbeReport`
    whose ``suite`` carries the aggregate metrics and whose ``blind_spots``
    names the samples whose file never surfaced.
    """
    per_query: list[quality.QueryQuality] = []
    blind_spots: list[dict] = []
    for node in samples:
        query = synthesize_query(node)
        relevant = str(node.get("source_file", ""))
        ranked = retrieve(query)
        qq = quality.evaluate_query(
            str(node.get("id", "")),
            ranked,
            [relevant],
            ks=ks,
            answer_k=k,
        )
        per_query.append(qq)
        if not qq.answerable:
            if len(blind_spots) < MAX_BLIND_SPOTS:
                blind_spots.append(
                    {
                        "id": str(node.get("id", "")),
                        "label": str(node.get("label", "")),
                        "source_file": relevant,
                        "query": query,
                    }
                )
    agg = quality.aggregate("self-probe", per_query, ks=ks)
    return ProbeReport(
        suite=agg,
        blind_spots=blind_spots,
        index_size=index_size,
        k=k,
        sample_size=len(samples),
        blind_spot_total=sum(1 for q in per_query if not q.answerable),
    )
