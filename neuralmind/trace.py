"""Retrieval trace: per-layer explainability for a query (PRD 3).

NeuralMind's retrieval blends layered summaries, community/cluster selection,
semantic search, and learned synapse boosts. When a result is surprising,
"why did *this* come back?" is hard to answer after the fact. A
:class:`RetrievalTrace` records, layer by layer, what each stage saw and did —
candidate generation, cluster scoring, synapse boost attribution, the final
ranked hits, and the token/compression budget — so a wrong result can be
pinned to the stage that caused it.

Pure and stdlib-only. The selector populates a trace **only when asked**
(tracing off by default = zero overhead), and every record site is guarded, so
this never changes retrieval behavior.

Design notes:
- **Bounded.** Candidate/hit lists are capped (:data:`MAX_ITEMS`) so a trace
  attached to an MCP response or a CLI ``--json`` payload stays small.
- **Redactable.** ``to_dict(redact=True)`` strips directory paths to basenames
  so a trace can be shared in a bug report without leaking a tree layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Per-list cap so a trace stays small enough to ride along in an MCP response
# or a CLI JSON payload.
MAX_ITEMS = 25


def _basename(path: str) -> str:
    if not path:
        return path
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def _redact_value(key: str, value: Any) -> Any:
    """Redact path-like fields to their basename; recurse into nested data."""
    if isinstance(value, dict):
        return {k: _redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(key, v) for v in value]
    if isinstance(value, str) and key in ("source_file", "module", "path"):
        return _basename(value)
    return value


@dataclass
class TraceEvent:
    """One thing that happened in one retrieval layer."""

    layer: str  # candidates | L2 | synapse | L3 | compose
    kind: str  # search | cluster_scores | synapse_boost | hits | budget
    summary: str  # one-line human description
    data: dict = field(default_factory=dict)

    def to_dict(self, redact: bool = False) -> dict:
        data = _redact_value("", self.data) if redact else self.data
        return {"layer": self.layer, "kind": self.kind, "summary": self.summary, "data": data}


@dataclass
class RetrievalTrace:
    """Accumulates per-layer trace events for one query."""

    query: str
    verbose: bool = False
    events: list[TraceEvent] = field(default_factory=list)

    # -- recording (all called from guarded selector sites) ---------------- #
    def add(self, layer: str, kind: str, summary: str, **data: Any) -> None:
        self.events.append(TraceEvent(layer=layer, kind=kind, summary=summary, data=data))

    def record_candidates(self, results: list[dict]) -> None:
        """Vector-search candidate pool (the raw ranked hits before selection).

        Keeps the longest pool seen (L2 fetches 5, L3 fetches 4, both share one
        cached search), so the trace shows the full candidate set once.
        """
        existing = next(
            (e for e in self.events if e.layer == "candidates" and e.kind == "search"), None
        )
        items = [
            {
                "id": str(r.get("id", "")),
                "label": r.get("metadata", {}).get("label", r.get("id", "")),
                "source_file": r.get("metadata", {}).get("source_file", ""),
                "score": round(float(r.get("score", 0.0)), 4),
            }
            for r in results[:MAX_ITEMS]
        ]
        if existing is not None:
            if len(items) > len(existing.data.get("candidates", [])):
                existing.data["candidates"] = items
                existing.summary = f"{len(items)} vector candidates"
            return
        self.add(
            "candidates",
            "search",
            f"{len(items)} vector candidates",
            candidates=items,
        )

    def record_cluster_scores(
        self,
        vector_scores: dict[int, float],
        boosted_scores: dict[int, float],
        selected: list[int],
        budget: int,
    ) -> None:
        clusters = []
        for comm in sorted(boosted_scores, key=lambda c: boosted_scores[c], reverse=True)[
            :MAX_ITEMS
        ]:
            vec = round(vector_scores.get(comm, 0.0), 4)
            total = round(boosted_scores.get(comm, 0.0), 4)
            clusters.append(
                {
                    "cluster": comm,
                    "vector_score": vec,
                    "synapse_boost": round(total - vec, 4),
                    "total_score": total,
                    "selected": comm in selected,
                }
            )
        self.add(
            "L2",
            "cluster_scores",
            f"selected {len(selected)} of {len(boosted_scores)} clusters (budget {budget})",
            clusters=clusters,
            selected=list(selected),
        )

    def record_synapse_boost(
        self, seeds: list[str], comm: int, energy: float, weighted: float
    ) -> None:
        self.add(
            "synapse",
            "synapse_boost",
            f"cluster {comm} boosted +{weighted:.4f} from co-activation",
            seeds=seeds[:MAX_ITEMS],
            cluster=comm,
            energy=round(energy, 4),
            weighted_boost=round(weighted, 4),
        )

    def record_hits(self, results: list[dict]) -> None:
        items = []
        for r in results[:MAX_ITEMS]:
            items.append(
                {
                    "id": str(r.get("id", "")),
                    "label": r.get("metadata", {}).get("label", r.get("id", "")),
                    "source_file": r.get("metadata", {}).get("source_file", ""),
                    "score": round(float(r.get("score", 0.0)), 4),
                    "synapse_recalled": bool(r.get("_synapse_recalled", False)),
                }
            )
        recalled = sum(1 for i in items if i["synapse_recalled"])
        self.add(
            "L3",
            "hits",
            f"{len(items)} final hits ({recalled} synapse-recalled)",
            hits=items,
        )

    def record_budget(self, layers_used: list[str], budget: Any, reduction_ratio: float) -> None:
        self.add(
            "compose",
            "budget",
            f"{len(layers_used)} layers, {getattr(budget, 'total', 0)} tokens, "
            f"{reduction_ratio:.1f}x reduction",
            layers_used=list(layers_used),
            tokens={
                "l0": getattr(budget, "l0_identity", 0),
                "l1": getattr(budget, "l1_summary", 0),
                "l2": getattr(budget, "l2_ondemand", 0),
                "l3": getattr(budget, "l3_search", 0),
                "total": getattr(budget, "total", 0),
            },
            reduction_ratio=round(reduction_ratio, 2),
        )

    # -- export ------------------------------------------------------------ #
    def to_dict(self, redact: bool = False) -> dict:
        # Non-verbose trims the candidate list to the top 10 to stay compact;
        # verbose keeps everything (up to MAX_ITEMS).
        out_events = []
        for e in self.events:
            ed = e.to_dict(redact=redact)
            if not self.verbose and e.kind == "search":
                ed["data"]["candidates"] = ed["data"].get("candidates", [])[:10]
            out_events.append(ed)
        return {
            "query": _basename(self.query) if redact else self.query,
            "verbose": self.verbose,
            "events": out_events,
        }

    def render_text(self) -> str:
        """Compact human-readable rendering for the CLI."""
        lines = [f"Retrieval trace for: {self.query}", "=" * 60]
        for e in self.events:
            lines.append(f"[{e.layer}/{e.kind}] {e.summary}")
            if self.verbose:
                for key in ("candidates", "clusters", "hits"):
                    for item in e.data.get(key, [])[:MAX_ITEMS]:
                        lines.append(f"    - {item}")
        return "\n".join(lines)
