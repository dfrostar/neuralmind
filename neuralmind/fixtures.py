# neuralmind/fixtures.py — Fixture query loader for tuner live eval (T1).
#
# Provides deterministic fixture queries the tuner uses to measure
# real retrieval_quality and session_health per candidate. Part of
# Wave 5 — closing the tuner faithfulness gap.

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

FIXTURE_QUERIES_FILE = ".neuralmind/fixture_queries.json"


@dataclass(frozen=True)
class FixtureQuery:
    """One fixture query with expected results for success measurement."""
    query: str
    expected_node_ids: tuple[str, ...]


def load_fixture_queries(
    project_path: str | Path,
    n: int = 20,
) -> list[FixtureQuery]:
    """Load fixture queries for tuner live eval.

    Order of preference:
    1. <project>/.neuralmind/fixture_queries.json (operator-curated)
    2. Synthetic queries generated from graph node labels (auto-derivation)
    3. Empty list (fail-open — no fixtures = no promotion)

    Results are deterministically sorted by query string for reproducibility.
    """
    project_path = Path(project_path)
    file_path = project_path / FIXTURE_QUERIES_FILE

    if file_path.exists():
        queries = _load_from_file(file_path)
    else:
        queries = _generate_from_graph(project_path)

    # Deterministic: sort by query string, take first n
    queries.sort(key=lambda q: q.query)
    return queries[:n]


def _load_from_file(file_path: Path) -> list[FixtureQuery]:
    """Load fixture queries from a JSON file."""
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        queries = []
        for item in data:
            if isinstance(item, str):
                queries.append(FixtureQuery(query=item, expected_node_ids=()))
            elif isinstance(item, dict):
                q = item.get("query", "")
                if q:
                    expected = tuple(item.get("expected_node_ids", []))
                    queries.append(FixtureQuery(query=q, expected_node_ids=expected))
        return queries
    except Exception as exc:
        log.debug("Failed to load fixture queries: %s", exc)
        return []


def _generate_from_graph(project_path: Path) -> list[FixtureQuery]:
    """Auto-derive fixture queries from graph node labels.

    Uses the existing graph's node labels as queries — if embeddings are
    well-formed, searching for a node's own label should retrieve that node.
    """
    try:
        from .embedder import GraphEmbedder
        embedder = GraphEmbedder(str(project_path))
        if not embedder.load_graph():
            return []

        queries: list[FixtureQuery] = []
        seen: set[str] = set()
        for node in embedder.nodes:
            label = node.get("label", "")
            node_id = node.get("id", "")
            # Skip duplicates and empty labels
            if label and label not in seen and node_id:
                seen.add(label)
                queries.append(FixtureQuery(
                    query=label,
                    expected_node_ids=(node_id,),
                ))
            if len(queries) >= 50:
                break
        return queries
    except Exception as exc:
        log.debug("Failed to generate fixture queries from graph: %s", exc)
        return []


def save_fixture_queries(
    project_path: str | Path,
    queries: list[FixtureQuery],
) -> bool:
    """Persist fixture queries to the project's .neuralmind dir.

    Returns False on any error (fail-open — never raises).
    """
    try:
        file_path = Path(project_path) / FIXTURE_QUERIES_FILE
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {"query": q.query, "expected_node_ids": list(q.expected_node_ids)}
            for q in queries
        ]
        file_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception as exc:
        log.warning("Failed to save fixture queries: %s", exc)
        return False
