"""Context-assembly backends for the public benchmark.

Each backend answers one question: *given a natural-language query and a repo,
which files would end up in the agent's context, and at what token cost?* We
then score **gold-file recall** (did the objectively-correct file make it in)
against that cost. The backends are deliberately simple and disclosed — a
skeptic can read exactly how each baseline is configured:

- ``full_file``   — the naive ceiling: put every source file in context. Recall
  is trivially 1.0; cost is the whole repo. This is the honest upper bound the
  "just paste the files" workflow pays.
- ``ripgrep``     — extract query keywords, rank files by match count, open the
  top-N **whole files** (what "just grep it and read the files" actually costs).
- ``embedding_rag`` — top-k function/class **chunks** retrieved by the same
  encoder NeuralMind uses, sending only the retrieved chunks (a strong, cheap
  vector-RAG baseline). Isolates what NeuralMind adds *over* plain vector search.
- ``neuralmind``  — ``NeuralMind.query`` progressive L0–L3 disclosure + synapse
  recall; cost is the assembled compact context.

Scoring reuses ``neuralmind.quality`` verbatim — no metric math is invented
here — so the public numbers are the same numbers CI gates on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neuralmind import quality

from .tokens import count_tokens

# Conventional baseline knobs, disclosed in the report. Top-N for the keyword
# and vector baselines is the retrieval depth a typical agent would open.
RIPGREP_TOP_N = 5
RAG_TOP_K = 8

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "is",
    "are",
    "how",
    "what",
    "where",
    "does",
    "do",
    "for",
    "in",
    "on",
    "with",
    "from",
    "that",
    "this",
    "used",
    "use",
    "across",
    "into",
    "out",
    "over",
    "when",
    "which",
    "its",
    "it",
    "be",
    "by",
    "as",
    "at",
    "via",
}


@dataclass
class BackendResult:
    """One backend's answer for one query: which files, at what cost, was it right."""

    backend: str
    query_id: str
    gold_files: list[str]
    context_files: list[str]  # ordered, dedup'd files the backend puts in context
    tokens: int
    # Derived (filled by __post_init__).
    recall: float = 0.0  # containment: fraction of gold files present in context
    found: bool = False  # all gold files present
    recall_at_5: float = 0.0  # ranked recall@5 (quality.py) for ordered backends
    reciprocal_rank: float = 0.0

    def __post_init__(self) -> None:
        gold = set(self.gold_files)
        present = gold & set(self.context_files)
        self.recall = len(present) / len(gold) if gold else 0.0
        self.found = bool(gold) and present == gold
        q = quality.evaluate_query(self.query_id, self.context_files, self.gold_files, ks=(1, 3, 5))
        self.recall_at_5 = q.recall.get(5, 0.0)
        self.reciprocal_rank = q.reciprocal_rank

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "query_id": self.query_id,
            "gold_files": self.gold_files,
            "context_files": self.context_files,
            "tokens": self.tokens,
            "recall": round(self.recall, 4),
            "found": self.found,
            "recall_at_5": round(self.recall_at_5, 4),
            "reciprocal_rank": round(self.reciprocal_rank, 4),
        }


@dataclass
class RepoFiles:
    """Source files of a repo checkout, keyed by basename (the gold-file key)."""

    root: Path
    texts: dict[str, str] = field(default_factory=dict)  # basename -> file text

    @classmethod
    def load(cls, root: str | Path) -> RepoFiles:
        root = Path(root)
        texts: dict[str, str] = {}
        for p in sorted(root.rglob("*.py")):
            if "graphify-out" in p.parts or p.name.startswith("test_"):
                continue
            try:
                texts[p.name] = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
        return cls(root=root, texts=texts)


def _keywords(question: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]+", question.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #


def run_full_file(query_id: str, gold_files: list[str], repo: RepoFiles) -> BackendResult:
    """Naive ceiling: every source file in context (recall 1.0, max cost)."""
    files = sorted(repo.texts)
    tokens = sum(count_tokens(t) for t in repo.texts.values())
    # Put gold files first only so the ranked metric is well-defined; recall is
    # containment over the whole set either way (every file is present).
    ordered = [f for f in files if f in set(gold_files)] + [
        f for f in files if f not in set(gold_files)
    ]
    return BackendResult("full-file", query_id, gold_files, ordered, tokens)


def run_ripgrep(
    query_id: str, question: str, gold_files: list[str], repo: RepoFiles
) -> BackendResult:
    """Keyword search → rank files by match count → open the top-N whole files."""
    terms = _keywords(question)
    scores: dict[str, int] = {}
    for name, text in repo.texts.items():
        low = text.lower()
        hits = sum(len(re.findall(r"\b" + re.escape(t) + r"\b", low)) for t in terms)
        if hits:
            scores[name] = hits
    ranked = sorted(scores, key=lambda n: (-scores[n], n))[:RIPGREP_TOP_N]
    tokens = sum(count_tokens(repo.texts[n]) for n in ranked)
    return BackendResult("ripgrep", query_id, gold_files, ranked, tokens)


def run_embedding_rag(
    query_id: str, question: str, gold_files: list[str], nm: Any
) -> BackendResult:
    """Top-k function/class chunks via the same encoder; cost = retrieved chunks."""
    hits = nm.search(question, n=RAG_TOP_K)
    files: list[str] = []
    tokens = 0
    for h in hits:
        meta = h.get("metadata", {}) or {}
        src = meta.get("source_file")
        if src:
            files.append(Path(str(src)).name)
        # Cost of a chunk-RAG is the retrieved chunk text, not whole files.
        doc = h.get("document") or h.get("text") or ""
        tokens += count_tokens(str(doc))
    # Dedup files preserving rank; tokens already summed over all retrieved chunks.
    seen: set[str] = set()
    ordered = [f for f in files if not (f in seen or seen.add(f))]
    return BackendResult("embedding-rag", query_id, gold_files, ordered, tokens)


def run_neuralmind(query_id: str, question: str, gold_files: list[str], nm: Any) -> BackendResult:
    """NeuralMind progressive disclosure + synapse recall; cost = assembled context."""
    result = nm.query(question)
    files: list[str] = []
    for h in getattr(result, "top_search_hits", []) or []:
        meta = h.get("metadata", {}) or {}
        src = meta.get("source_file")
        if src:
            files.append(Path(str(src)).name)
    seen: set[str] = set()
    ordered = [f for f in files if not (f in seen or seen.add(f))]
    tokens = int(getattr(result, "tokens", 0) or 0)
    return BackendResult("neuralmind", query_id, gold_files, ordered, tokens)
