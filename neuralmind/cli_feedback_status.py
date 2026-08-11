"""Feedback + status commands for the NeuralMind CLI.

Adds explicit good/bad feedback on the last query's reinforced edges,
and a synapse-memory health dashboard with an 'is it learning?'
diagnostic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .synapses import LEARNING_RATE, SynapseStore, default_db_path
from .namespaces import resolve_namespace


def _get_last_reinforced(project_path: Path) -> tuple[list[str] | None, str]:
    """Read the last query's node ids from the recent-queries log.

    Returns (node_ids, error_message). On success error_message is "".
    """
    from .recent_queries import read_recent
    from .core import NeuralMind

    recent_path = project_path / ".neuralmind" / NeuralMind.RECENT_QUERIES_FILENAME
    records = read_recent(recent_path, n=1)
    if not records:
        return None, "No recent queries recorded. Run `neuralmind query <path> <question>` first."
    record = records[0]
    top_hits = record.get("top_hits", [])
    node_ids = [h["id"] for h in top_hits if h.get("id")]
    if len(node_ids) < 2:
        return None, f"Last query ({record.get('question', '?')[:60]!r}) has <2 hits — nothing to adjust."
    return node_ids, ""


def cmd_feedback_good(args) -> None:
    """Boost the last query's reinforced edges."""
    project_path = Path(args.project_path).resolve()
    node_ids, err = _get_last_reinforced(project_path)
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)

    db = default_db_path(project_path)
    if not db.exists():
        print(f"No synapse store at {db}. Run `neuralmind build {project_path}` first.", file=sys.stderr)
        sys.exit(1)

    ns = resolve_namespace(project_path)
    store = SynapseStore(db, namespace=ns)
    # Boost: reinforce with strength=2.0
    pairs = store.reinforce(node_ids, strength=2.0)
    delta = LEARNING_RATE * 2.0

    result = {
        "feedback": "good",
        "node_count": len(node_ids),
        "pairs_adjusted": pairs,
        "adjustment_per_edge": delta,
        "namespace": ns,
    }
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"✓ Boosted {pairs} edges from last query (+0.60 each).")
    print(f"  Nodes: {len(node_ids)} • Namespace: {ns}")


def cmd_feedback_bad(args) -> None:
    """Penalize the last query's reinforced edges."""
    project_path = Path(args.project_path).resolve()
    node_ids, err = _get_last_reinforced(project_path)
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)

    db = default_db_path(project_path)
    if not db.exists():
        print(f"No synapse store at {db}. Run `neuralmind build {project_path}` first.", file=sys.stderr)
        sys.exit(1)

    ns = resolve_namespace(project_path)
    store = SynapseStore(db, namespace=ns)
    penalty = LEARNING_RATE  # 0.30
    pairs = store.penalize(node_ids, penalty=penalty)

    result = {
        "feedback": "bad",
        "node_count": len(node_ids),
        "pairs_adjusted": pairs,
        "adjustment_per_edge": -penalty,
        "namespace": ns,
    }
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"✓ Penalized {pairs} edges from last query (-{penalty:.2f} each).")
    print(f"  Nodes: {len(node_ids)} • Namespace: {ns}")
    print("  Those edges will surface less on future similar queries.")


def cmd_status(args) -> None:
    """Synapse memory health dashboard + 'is it learning?' diagnostic."""
    project_path = Path(args.project_path).resolve()
    db = default_db_path(project_path)

    if not db.exists():
        result = {
            "status": "no_store",
            "project": project_path.name,
            "message": f"No synapse store at {db}. Run `neuralmind build {project_path}` to create one.",
            "is_learning": False,
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"No synapse memory yet for {project_path.name}.")
            print(f"  Run: neuralmind build {project_path}")
        return

    ns = resolve_namespace(project_path)
    store = SynapseStore(db, namespace=ns)
    stats = store.stats()

    # Derive learning health signals
    edges = stats.get("edges", 0)
    transitions = stats.get("transitions", 0)
    ltp_edges = stats.get("ltp_edges", 0)
    nodes = stats.get("nodes", 0)
    total_weight = stats.get("total_weight", 0.0)

    # "Is it learning?" diagnostic
    if edges == 0:
        is_learning = False
        learning_status = "dormant"
        diagnosis = "No edges yet. Run some queries or edit files to seed the synapse layer."
    elif edges < 10:
        is_learning = True
        learning_status = "warming_up"
        diagnosis = f"Only {edges} edges — too few for reliable retrieval boost. Keep querying."
    elif ltp_edges == 0:
        is_learning = True
        learning_status = "learning"
        diagnosis = f"{edges} edges, none LTP-protected yet. Edges need ≥5 activations to lock in."
    elif transitions < 5:
        is_learning = True
        learning_status = "partially_active"
        diagnosis = f"{edges} edges ({ltp_edges} LTP), but only {transitions} transitions. Sequential patterns still sparse."
    else:
        is_learning = True
        learning_status = "active"
        diagnosis = f"Healthy: {edges} edges ({ltp_edges} LTP), {transitions} transitions, {nodes} nodes firing."

    # Weight distribution bucket
    avg_weight = total_weight / edges if edges else 0.0

    result = {
        "status": learning_status,
        "is_learning": is_learning,
        "diagnosis": diagnosis,
        "project": project_path.name,
        "namespace": ns,
        "stats": {
            "edges": edges,
            "ltp_edges": ltp_edges,
            "transitions": transitions,
            "nodes": nodes,
            "total_weight": round(total_weight, 3),
            "avg_weight": round(avg_weight, 4),
            "db_path": str(db),
        },
        "top_hubs": [{"node": n, "degree": d} for n, d in stats.get("top_hubs", [])],
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"═══ NeuralMind Synapse Status — {project_path.name} ═══")
    print(f"  Status:       {'🟢' if is_learning else '🟡'} {learning_status}")
    print(f"  Namespace:    {ns}")
    print(f"  Edges:        {edges} ({ltp_edges} LTP-protected)")
    print(f"  Transitions:  {transitions}")
    print(f"  Active nodes: {nodes}")
    print(f"  Avg weight:   {avg_weight:.4f}")
    print(f"  DB:           {db}")
    print()
    print(f"  {diagnosis}")
    if result["top_hubs"]:
        print(f"\n  Top hubs:")
        for hub in result["top_hubs"][:5]:
            print(f"    {hub['node'][:40]:40s}  degree {hub['degree']}")
