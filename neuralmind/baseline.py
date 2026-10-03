"""baseline.py — one measured baseline for every reduction NeuralMind reports.

Every reduction ratio is "tokens without NeuralMind ÷ tokens with it". Before
v4.5.0 the numerator was a fixed 50,000-token guess in ``benchmark``,
``savings`` and ``cost``, and a third, lines × 25 estimate in
``build --dry-run`` — three commands, three baselines, none of them this
project. On a 1.3M-token repo, "47× reduction" was really ~1,600×; on a small
one it overstated.

The baseline is now the **measured token count of the code the index
covers**: every distinct ``source_file`` in the graph that is code, read from
disk. Prose — Markdown, reStructuredText, plain text — is left out when the
index holds code, as ``build --dry-run`` always left it out: a changelog is not
part of what a code question would load, and counting it would inflate every
ratio. A prose-only index (a book, a docs corpus) is measured over its
documents instead.

It is counted at the same ~4 chars/token as the context it is divided by
(``ContextSelector`` estimates every layer that way), so a ratio is a ratio of
characters and doesn't move with whether tiktoken happens to be installed —
on ``psf/requests``, tiktoken counts the code 8.5% lower than chars/4 does,
and the ratio would have shifted by as much.

``build`` measures it and caches it in ``.neuralmind/baseline.json``;
``build --dry-run`` measures the files a build would index. The fixed constant
stays available only as the labelled ``--naive-50k`` option, for comparison
with older numbers.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .paths import baseline_path

NAIVE_BASELINE_TOKENS = 50_000

NAIVE_LABEL = "fixed 50K-token naive estimate (--naive-50k)"

# Measured only when an index holds no code. Images and PDFs a graphify graph
# can name are neither prose nor code, so they are never read as text.
PROSE_SUFFIXES = frozenset({".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc"})


def count_file_tokens(paths: Iterable[Path]) -> int:
    """Tokens of ``paths`` concatenated, at the context's ~4 chars/token."""
    from .context_selector import ContextSelector

    chars = 0
    for path in paths:
        try:
            chars += _char_count(Path(path))
        except OSError:
            continue
    return chars // ContextSelector.CHARS_PER_TOKEN


def baseline_files(project: str | Path, nodes: Iterable[Any]) -> tuple[list[Path], str]:
    """The files the baseline is measured over, and their scope.

    A file is code when a node naming it has ``file_type: "code"`` (graphify's
    and the built-in parser's convention) or its suffix is one the built-in
    parser handles. Returns ``(files, scope)`` with scope ``"code"``,
    ``"documents"`` (a prose-only index) or ``"none"``.
    """
    from .freshness import normalize_source_path
    from .graphgen import SUPPORTED_SUFFIXES

    root = Path(project).resolve()
    named: dict[str, bool] = {}  # relative path -> named by a code node
    normalized: dict[str, str] = {}
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        raw = node.get("source_file")
        if not raw:
            continue
        raw = str(raw)
        rel = normalized.get(raw)
        if rel is None:
            rel = normalized[raw] = normalize_source_path(raw, root)
        if rel:
            named[rel] = named.get(rel, False) or node.get("file_type") == "code"

    def suffix(rel: str) -> str:
        return PurePosixPath(rel).suffix.lower()

    rels = [rel for rel, code in named.items() if code or suffix(rel) in SUPPORTED_SUFFIXES]
    scope = "code"
    if not rels:
        rels = [rel for rel in named if suffix(rel) in PROSE_SUFFIXES]
        scope = "documents"
    # Keyed by the resolved path, so two spellings of one file count once.
    files: dict[Path, None] = {}
    for rel in sorted(rels):
        path = _inside(root, rel)
        if path is not None and path.is_file():
            files[path] = None
    return list(files), (scope if files else "none")


def measure_graph_files(project: str | Path, graph: dict) -> dict:
    """Measure the code (or, for a prose-only index, the documents) the graph covers."""
    files, scope = baseline_files(project, graph.get("nodes", []) or [])
    return {
        "tokens": count_file_tokens(files),
        "files": len(files),
        "scope": scope,
        "measured_at": datetime.now().isoformat(timespec="seconds"),
    }


def save(project: str | Path, measured: dict) -> None:
    path = baseline_path(project)
    if not path.parent.exists():
        return
    try:
        path.write_text(json.dumps(measured, indent=2), encoding="utf-8")
    except OSError:
        pass


def load(project: str | Path) -> dict | None:
    """The cached measurement from the last build, or None.

    A cache without ``scope`` was written before the baseline counted code
    only, at the context's chars/token; it is ignored rather than mixed in.
    """
    try:
        data = json.loads(baseline_path(project).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or int(data.get("tokens", 0) or 0) <= 0:
        return None
    if "scope" not in data:
        return None
    return data


def describe(measured: dict) -> dict:
    """A measurement in the shape :func:`resolve` returns."""
    tokens = int(measured["tokens"])
    files = int(measured.get("files", 0) or 0)
    scope = str(measured.get("scope") or "code")
    kind = "document" if scope == "documents" else "code"
    return {
        "tokens": tokens,
        "source": "measured",
        "files": files,
        "scope": scope,
        "label": f"measured: {tokens:,} tokens in {files:,} indexed {kind} files",
    }


def resolve(project: str | Path, *, naive_50k: bool = False) -> dict:
    """The baseline every reduction ratio should divide.

    Returns ``{"tokens", "source", "label", "files"}`` (plus ``scope`` when
    measured): the measured count from the last build, or the fixed 50K
    estimate when asked for (``naive_50k``) or when nothing has been measured
    yet — labelled so a reader can always tell which one a number used.
    """
    if not naive_50k:
        measured = load(project)
        if measured is not None:
            return describe(measured)
        return {
            "tokens": NAIVE_BASELINE_TOKENS,
            "source": "naive-50k",
            "files": 0,
            "label": "fixed 50K-token estimate (no measured baseline yet — run neuralmind build)",
        }
    return {
        "tokens": NAIVE_BASELINE_TOKENS,
        "source": "naive-50k",
        "files": 0,
        "label": NAIVE_LABEL,
    }


def ratio(baseline_tokens: int, used_tokens: int) -> float:
    return round(baseline_tokens / used_tokens, 1) if used_tokens > 0 else 0.0


def _inside(root: Path, rel: str) -> Path | None:
    """``rel`` resolved under ``root``, or None when it points outside it.

    A repository can commit its graph, so a node naming ``../../etc/passwd``
    or an absolute path elsewhere must not be opened. Symlinks are resolved
    before the check for the same reason.
    """
    path = Path(rel)
    if not path.is_absolute():
        path = root / path
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved


def _char_count(path: Path) -> int:
    """Characters in a text file, as the agent would read it.

    UTF-8 with undecodable bytes replaced, and universal newlines so a CRLF
    checkout measures the same as an LF one. Read in chunks: the index can
    hold a large generated file.
    """
    total = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        while chunk := fh.read(1 << 20):
            total += len(chunk)
    return total
