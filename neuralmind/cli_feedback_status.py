"""Feedback + status commands for the NeuralMind CLI.

Adds explicit good/bad feedback on the last query's reinforced edges,
and a status dashboard covering both halves of a project's state: what
is *indexed* (code nodes, ingested content, when it was last built) and
what has been *learned* (synapse edges, and an 'is it learning?'
diagnostic).

The index half answers "did my ingest actually land, and how stale is
it?" without running a query or a rebuild.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .content_manifest import ContentManifest
from .namespaces import resolve_namespace
from .synapses import LEARNING_RATE, SynapseStore, default_db_path

# An IR larger than this is summarized as "unknown" rather than parsed:
# `status` is a glance at project state and must stay fast.
MAX_IR_PARSE_BYTES = 64 * 1024 * 1024


def _get_last_reinforced(project_path: Path) -> tuple[list[str] | None, str]:
    """Read the last query's node ids from the recent-queries log.

    Returns (node_ids, error_message). On success error_message is "".
    """
    from .core import NeuralMind
    from .recent_queries import read_recent

    recent_path = project_path / ".neuralmind" / NeuralMind.RECENT_QUERIES_FILENAME
    records = read_recent(recent_path, n=1)
    if not records:
        return None, "No recent queries recorded. Run `neuralmind query <path> <question>` first."
    record = records[0]
    top_hits = record.get("top_hits", [])
    node_ids = [h["id"] for h in top_hits if h.get("id")]
    if len(node_ids) < 2:
        return (
            None,
            f"Last query ({record.get('question', '?')[:60]!r}) has <2 hits — nothing to adjust.",
        )
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
        print(
            f"No synapse store at {db}. Run `neuralmind build {project_path}` first.",
            file=sys.stderr,
        )
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
        print(
            f"No synapse store at {db}. Run `neuralmind build {project_path}` first.",
            file=sys.stderr,
        )
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


def _dir_size_bytes(path: Path) -> int:
    """Total size of the files under ``path``. 0 when unreadable."""
    total = 0
    try:
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError:
                continue
    except OSError:
        return 0
    return total


def _index_snapshot(project_path: Path) -> dict:
    """What the project currently has indexed, read straight off disk.

    Deliberately avoids importing the vector backend: `status` should
    answer in milliseconds, and the IR plus the content manifest already
    carry the counts and timestamps a user is asking about.
    """
    nm_dir = project_path / ".neuralmind"
    ir_path = nm_dir / "index_ir.json"
    snapshot: dict = {
        "exists": ir_path.exists(),
        "path": str(ir_path),
        "nodes": None,
        "edges": None,
        "built_at": None,
        "age_hours": None,
        "disk_mb": round(_dir_size_bytes(nm_dir) / (1024 * 1024), 2) if nm_dir.exists() else 0.0,
    }
    if not snapshot["exists"]:
        return snapshot

    try:
        stat = ir_path.stat()
    except OSError:
        return snapshot

    if stat.st_size <= MAX_IR_PARSE_BYTES:
        try:
            payload = json.loads(ir_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        if isinstance(payload, dict):
            nodes = payload.get("nodes")
            edges = payload.get("edges")
            snapshot["nodes"] = len(nodes) if isinstance(nodes, list) else None
            snapshot["edges"] = len(edges) if isinstance(edges, list) else None
            created = payload.get("created_at")
            if isinstance(created, str) and created:
                snapshot["built_at"] = created

    if not snapshot["built_at"]:
        snapshot["built_at"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    snapshot["age_hours"] = round((time.time() - stat.st_mtime) / 3600, 1)
    return snapshot


def _content_snapshot(project_path: Path) -> dict:
    """Ingested-content counts from the incremental manifest."""
    summary = ContentManifest.load(project_path).summary()
    summary["tracked"] = summary["files"] > 0
    return summary


def _print_index_section(index: dict, content: dict) -> None:
    """Render the index half of the status dashboard."""
    if not index["exists"]:
        print("  Index:        none — run `neuralmind build .` or `neuralmind ingest-content`")
    else:
        nodes = "unknown" if index["nodes"] is None else f"{index['nodes']}"
        edges = "unknown" if index["edges"] is None else f"{index['edges']}"
        age = "unknown" if index["age_hours"] is None else f"{index['age_hours']}h ago"
        # Named "code nodes" so it doesn't read as a total: a content-only
        # project legitimately has zero of these and thousands of chunks.
        suffix = " — content-only project" if index["nodes"] == 0 and content["tracked"] else ""
        print(f"  Code nodes:   {nodes} ({edges} edges){suffix}")
        print(f"  Last build:   {age}")
        print(f"  Disk:         {index['disk_mb']} MB")
    if content["tracked"]:
        last = content["last_indexed_at"] or "unknown"
        print(
            f"  Content:      {content['files']} file(s), "
            f"{content['chunks']} chunks, {content['nodes']} nodes"
        )
        print(f"  Last ingest:  {last}")


def cmd_status(args) -> None:
    """Index + synapse-memory dashboard, and an 'is it learning?' diagnostic.

    Two independent halves, both reported even when only one exists: a
    project can be freshly ingested with no synapses yet, or carry months
    of learned edges over an index that was never rebuilt.
    """
    project_path = Path(args.project_path).resolve()
    db = default_db_path(project_path)
    index = _index_snapshot(project_path)
    content = _content_snapshot(project_path)

    if not db.exists():
        result = {
            "status": "no_store",
            "project": project_path.name,
            "message": f"No synapse store at {db}. Run `neuralmind build {project_path}` to create one.",
            "is_learning": False,
            "index": index,
            "content": content,
        }
        if args.json:
            print(json.dumps(result, indent=2))
            return
        print(f"═══ NeuralMind Status — {project_path.name} ═══")
        _print_index_section(index, content)
        print()
        print(f"  No synapse memory yet. Run: neuralmind build {project_path}")
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
        "index": index,
        "content": content,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"═══ NeuralMind Status — {project_path.name} ═══")
    _print_index_section(index, content)
    print()
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
        print("\n  Top hubs:")
        for hub in result["top_hubs"][:5]:
            print(f"    {hub['node'][:40]:40s}  degree {hub['degree']}")
