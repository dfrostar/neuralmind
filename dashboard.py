"""dashboard.py — Read-only Agency OS dashboard data layer.

Materializes the metrics a team needs to see at a glance:
  - Project status (built/unbuilt, last build, node/edge counts)
  - Synapse memory (namespace breakdown, LTP count, decay health)
  - Document ingestion (files ingested, by framework, last ingested)
  - Savings & performance (reduction ratio, tokens saved, latency trends)
  - Recent queries (newest first, with reduction ratios)
  - Communities (size distribution, top labels)
  - Agent OS (tenants, signals, experiments)

Read-only: every function takes a NeuralMind (or project_path) and returns
a dict. No writes, no side effects, safe to call from HTTP handlers.

Design: fail-open. If the index isn't built or a data source is missing,
return zeros/empty lists rather than raising. The UI renders "no data"
states from that.

For Agent OS sections, pass the shared daemon instances via agent_os_context
so the dashboard reflects real state (signals fired, experiments run).
When called without context, falls back to empty data.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .metrics_pipeline import MetricsCollector
from .savings import compute_savings


def project_status(mind=None, project_path: str | Path | None = None) -> dict[str, Any]:
    """High-level status card: built/unbuilt, node/edge counts, backend."""
    if mind is not None:
        path = mind.project_path
        built = mind._built
        stats = mind.get_stats() if built else {"built": False, "project": path.name}
    else:
        path = Path(project_path) if project_path else Path(".")
        built = False
        stats = {"built": False, "project": path.name}

    result = {
        "project": stats.get("project", path.name),
        "built": built,
        "backend": stats.get("backend", "unknown"),
        "nodes": stats.get("nodes", 0),
        "communities": stats.get("communities", 0),
        "build_stats": stats.get("build_stats", {}),
    }

    # Surface IR metadata (validation, version) if available
    ir_meta = stats.get("ir")
    if ir_meta:
        result["ir"] = {
            "version": ir_meta.get("version"),
            "validation": ir_meta.get("validation", {}),
        }

    return result


def synapse_summary(mind=None, project_path: str | Path | None = None) -> dict[str, Any]:
    """Synapse memory health: namespace breakdown, LTP count, decay info."""
    if mind is not None and mind.enable_synapses and mind.synapses is not None:
        try:
            store = mind.synapses
            stats = store.stats()
            top_edges = []
            try:
                for a, b, w, c in store.edges(min_weight=0.1, limit=10):
                    top_edges.append({"a": a, "b": b, "weight": round(w, 3), "count": c})
            except Exception:
                pass

            transitions = stats.get("transitions", 0)
            edges = stats.get("edges", 0)

            return {
                "namespace": stats.get("namespace", "personal"),
                "namespaces": stats.get("namespaces", {}),
                "total_edges": edges,
                "total_transitions": transitions,
                "ltp_count": stats.get("ltp_edges", 0),
                "top_edges": top_edges,
                "has_data": edges > 0,
            }
        except Exception:
            pass
    elif project_path is not None:
        # Try reading the synapse DB directly when no mind instance is given
        path = Path(project_path)
        synapse_db = path / ".neuralmind" / "synapses.db"
        if synapse_db.exists():
            try:
                from .synapses import SynapseStore, default_db_path

                store = SynapseStore(default_db_path(path), namespace="personal")
                stats = store.stats()
                top_edges = []
                try:
                    for a, b, w, c in store.edges(min_weight=0.1, limit=10):
                        top_edges.append({"a": a, "b": b, "weight": round(w, 3), "count": c})
                except Exception:
                    pass

                return {
                    "namespace": stats.get("namespace", "personal"),
                    "namespaces": stats.get("namespaces", {}),
                    "total_edges": stats.get("edges", 0),
                    "total_transitions": stats.get("transitions", 0),
                    "ltp_count": stats.get("ltp_edges", 0),
                    "top_edges": top_edges,
                    "has_data": stats.get("edges", 0) > 0,
                }
            except Exception:
                pass

    # No synapse store or disabled
    if project_path or mind is not None:
        path = Path(project_path) if project_path else mind.project_path
        synapse_db = path / ".neuralmind" / "synapses.db"
        has_data = synapse_db.exists()
    else:
        has_data = False

    return {
        "namespace": "personal",
        "namespaces": {},
        "total_edges": 0,
        "total_transitions": 0,
        "ltp_count": 0,
        "top_edges": [],
        "has_data": has_data,
    }


def ingestion_status(mind=None, project_path: str | Path | None = None) -> dict[str, Any]:
    """Document ingestion summary: what frameworks are loaded, when, how many nodes."""
    path = Path(project_path) if project_path else (mind.project_path if mind else Path("."))
    nm_dir = path / ".neuralmind"

    result: dict[str, Any] = {
        "ingested_files": [],
        "frameworks": {},
        "total_doc_nodes": 0,
        "last_ingested_at": None,
        "has_data": False,
    }

    # Scan audit_events.jsonl for ingestion events
    audit_file = nm_dir / "audit_events.jsonl"
    if not audit_file.exists():
        return result

    ingested = []
    frameworks: dict[str, int] = {}
    last_ts = None

    try:
        for line in audit_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue

            action = rec.get("action", "")
            if action not in ("ingest_document", "ingest_cmmc", "ingest_directory"):
                continue

            details = rec.get("details", {})
            node_count = details.get("node_count", 0)
            source = details.get("source", details.get("file", ""))
            framework = details.get("framework", "unknown")
            ts = rec.get("timestamp") or rec.get("ts")

            entry = {
                "action": action,
                "source": str(source),
                "framework": framework,
                "node_count": node_count,
                "timestamp": ts,
            }
            ingested.append(entry)

            if framework:
                frameworks[framework] = frameworks.get(framework, 0) + node_count

            if node_count:
                result["total_doc_nodes"] += node_count

            if ts and (last_ts is None or ts > last_ts):
                last_ts = ts

    except Exception:
        pass

    result["ingested_files"] = ingested[-20:]  # last 20
    result["frameworks"] = frameworks
    result["last_ingested_at"] = last_ts
    result["has_data"] = len(ingested) > 0

    return result


def savings_summary(project_path: str | Path | None = None) -> dict[str, Any]:
    """Token reduction & cost savings from logged query events."""
    if project_path is None:
        path = Path(".")
    else:
        path = Path(project_path)

    report = compute_savings(path)

    # Strip per-query detail for the summary; the UI only needs aggregates
    report.pop("recent_queries", None)
    return report


def performance_summary(project_path: str | Path | None = None, days: int = 7) -> dict[str, Any]:
    """Aggregated metrics from .neuralmind/metrics/ JSONL files."""
    if project_path is None:
        path = Path(".")
    else:
        path = Path(project_path)

    collector = MetricsCollector(path)
    return collector.summarize(days=days, event_type="query")


def recent_queries(mind=None, project_path: str | Path | None = None, n: int = 20) -> list[dict]:
    """Recent queries from the replay log (newest first)."""
    if mind is not None:
        try:
            return mind.recent_queries(n=n)
        except Exception:
            return []

    path = Path(project_path) if project_path else Path(".")
    log_file = path / ".neuralmind" / "recent_queries.jsonl"
    if not log_file.exists():
        return []

    try:
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        records = []
        for line in reversed(lines[-n:]):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
        return records
    except Exception:
        return []


def communities(mind=None, project_path: str | Path | None = None) -> list[dict]:
    """Community size distribution with top labels per community."""
    if mind is not None and mind._built:
        try:
            data = mind.graph_data()
        except Exception:
            return []
    else:
        # Try loading graph_data directly from embedder
        return []

    nodes = data.get("nodes", [])
    if not nodes:
        return []

    # Group by community
    comm: dict[int, dict] = {}
    for n in nodes:
        cid = n.get("community", -1)
        if cid not in comm:
            comm[cid] = {"id": cid, "size": 0, "labels": []}
        comm[cid]["size"] += 1
        label = n.get("label", "")
        if label:
            comm[cid]["labels"].append(label)

    result = []
    for cid in sorted(comm, key=lambda c: -comm[c]["size"]):
        entry = comm[cid]
        result.append(
            {
                "id": entry["id"],
                "size": entry["size"],
                "top_labels": entry["labels"][:5],
            }
        )

    return result


# --------------------------------------------------------------------------- #
# Agent OS sections
# --------------------------------------------------------------------------- #


def agent_os_tenants(tenants_dir: Path | None = None) -> dict[str, Any]:
    """Agent OS tenant summary for dashboard display."""
    try:
        from .agent_os import TenantRegistry

        registry = TenantRegistry(tenants_dir) if tenants_dir else TenantRegistry()
        tenants = registry.list_tenants()

        tiers: dict[str, int] = {}
        for t in tenants:
            tiers[t.tier] = tiers.get(t.tier, 0) + 1

        return {
            "total_tenants": len(tenants),
            "tiers": tiers,
            "recent": [t.to_dict() for t in tenants[:5]],
            "has_data": len(tenants) > 0,
        }
    except Exception:
        return {"total_tenants": 0, "tiers": {}, "recent": [], "has_data": False}


def agent_os_signals(signal_detector: Any = None) -> dict[str, Any]:
    """Agent OS signal summary for dashboard display.

    Args:
        signal_detector: Shared SignalDetector instance from the daemon.
            If None, falls back to an empty summary.
    """
    try:
        if signal_detector is None:
            return {"tracked_metrics": 0, "metrics": {}, "has_data": False}

        metrics = signal_detector.list_metrics()
        stats = {}
        for m in metrics:
            s = signal_detector.get_stats(m)
            if s:
                stats[m] = s

        return {
            "tracked_metrics": len(metrics),
            "metrics": stats,
            "has_data": len(metrics) > 0,
        }
    except Exception:
        return {"tracked_metrics": 0, "metrics": {}, "has_data": False}


def agent_os_experiments(promotion_engine: Any = None) -> dict[str, Any]:
    """Agent OS experiment summary for dashboard display.

    Args:
        promotion_engine: Shared PromotionEngine instance from the daemon.
            If None, falls back to an empty summary.
    """
    try:
        if promotion_engine is None:
            return {
                "total_experiments": 0,
                "verdicts": {},
                "recent": [],
                "promotions": 0,
                "rollbacks": 0,
                "has_data": False,
            }

        history = promotion_engine.get_history()

        verdicts: dict[str, int] = {}
        for r in history:
            # PromotionRecord has status, not verdict
            v = r.status.value if hasattr(r.status, "value") else str(r.status)
            verdicts[v] = verdicts.get(v, 0) + 1

        return {
            "total_experiments": len(history),
            "verdicts": verdicts,
            "recent": [r.to_dict() for r in history[:10]],
            "promotions": verdicts.get("shipped", 0),
            "rollbacks": verdicts.get("rolled_back", 0),
            "has_data": len(history) > 0,
        }
    except Exception:
        return {
            "total_experiments": 0,
            "verdicts": {},
            "recent": [],
            "promotions": 0,
            "rollbacks": 0,
            "has_data": False,
        }


def full_dashboard(
    mind=None,
    project_path: str | Path | None = None,
    days: int = 7,
    *,
    agent_os_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose all sections into one payload for the dashboard frontend.

    Args:
        mind: NeuralMind instance (optional).
        project_path: Project path (used if mind not given).
        days: Number of days for performance summary.
        agent_os_context: Shared daemon state for Agent OS sections.
            Keys: signal_detector, promotion_engine, tenant_registry.
            When provided, dashboard reflects real-time daemon state.
    """
    path = Path(project_path) if project_path else (mind.project_path if mind else Path("."))

    # Extract Agent OS shared instances from context
    signal_detector = agent_os_context.get("signal_detector") if agent_os_context else None
    promotion_engine = agent_os_context.get("promotion_engine") if agent_os_context else None

    return {
        "generated_at": time.time(),
        "project_path": str(path.resolve()),
        "status": project_status(mind, path),
        "synapses": synapse_summary(mind, path),
        "ingestion": ingestion_status(mind, path),
        "savings": savings_summary(path),
        "performance": performance_summary(path, days=days),
        "queries": {"recent": recent_queries(mind, path)},
        "communities": communities(mind, mind.project_path if mind else path) if mind else [],
        "agent_os": {
            "tenants": agent_os_tenants(),
            "signals": agent_os_signals(signal_detector=signal_detector),
            "experiments": agent_os_experiments(promotion_engine=promotion_engine),
        },
    }
