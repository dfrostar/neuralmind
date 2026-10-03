"""baseline.py — one measured baseline for every reduction NeuralMind reports.

Every reduction ratio is "tokens without NeuralMind ÷ tokens with it". Before
v4.5.0 the numerator was a fixed 50,000-token guess in ``benchmark``,
``savings`` and ``cost``, and a third, lines × 25 estimate in
``build --dry-run`` — three commands, three baselines, none of them this
project. On a 1.3M-token repo, "47× reduction" was really ~1,600×; on a small
one it overstated.

The baseline is now the **measured token count of the files the index
covers**: every distinct ``source_file`` in the graph, counted with the same
tokenizer as context budgets (tiktoken ``cl100k_base``, ~4 chars/token
fallback). ``build`` measures it and caches it in
``.neuralmind/baseline.json``; ``build --dry-run`` measures the files a build
would index. The fixed constant stays available only as the labelled
``--naive-50k`` option, for comparison with older numbers.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .paths import baseline_path

NAIVE_BASELINE_TOKENS = 50_000

NAIVE_LABEL = "fixed 50K-token naive estimate (--naive-50k)"


def count_file_tokens(paths: list[Path]) -> int:
    """Token count of ``paths`` concatenated, with the context-budget tokenizer."""
    from .context_budget import count_tokens

    total = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += count_tokens(text)
    return total


def measure_graph_files(project: str | Path, graph: dict) -> dict:
    """Measure the tokens of every file the graph covers that exists on disk."""
    from .freshness import normalize_source_path

    root = Path(project).resolve()
    rels: set[str] = set()
    for node in graph.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        raw = node.get("source_file")
        if raw:
            rel = normalize_source_path(str(raw), root)
            if rel:
                rels.add(rel)
    files = sorted(root / rel for rel in rels if (root / rel).is_file())
    return {
        "tokens": count_file_tokens(files),
        "files": len(files),
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
    """The cached measurement from the last build, or None."""
    try:
        data = json.loads(baseline_path(project).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or int(data.get("tokens", 0) or 0) <= 0:
        return None
    return data


def resolve(project: str | Path, *, naive_50k: bool = False) -> dict:
    """The baseline every reduction ratio should divide.

    Returns ``{"tokens", "source", "label", "files"}``: the measured count
    from the last build, or the fixed 50K estimate when asked for
    (``naive_50k``) or when nothing has been measured yet — labelled so a
    reader can always tell which one a number used.
    """
    if not naive_50k:
        measured = load(project)
        if measured is not None:
            tokens = int(measured["tokens"])
            files = int(measured.get("files", 0) or 0)
            return {
                "tokens": tokens,
                "source": "measured",
                "files": files,
                "label": f"measured: {tokens:,} tokens in {files:,} indexed files",
            }
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
