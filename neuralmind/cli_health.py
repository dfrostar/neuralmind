"""Health check command for NeuralMind CLI + MCP.

Provides a lightweight health signal for CI/CD, Docker healthchecks,
and systemd ExecStartPre. Returns index age, node count, last build
time, and disk usage.

Exit codes:
    0 = healthy (index exists, < 24h old)
    1 = stale (index exists, >= 24h old)
    2 = no index
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def cmd_health(args) -> None:
    """Check NeuralMind health — lightweight signal for CI/CD."""
    project_path = Path(args.project_path).resolve()
    nm_dir = project_path / ".neuralmind"

    # Check for index
    ir_path = nm_dir / "index_ir.json"
    if not ir_path.exists():
        result = {
            "status": "no_index",
            "healthy": False,
            "exit_code": 2,
            "message": f"No index found at {ir_path}. Run `neuralmind build {project_path}` first.",
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("✗ No index")
            print(f"  Run: neuralmind build {project_path}")
        sys.exit(2)

    # Index exists — check age
    try:
        ir_meta = json.loads(ir_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ir_meta = {}

    # Get last build time from IR metadata or file mtime
    last_build = ir_meta.get("built_at", 0)
    if not last_build:
        last_build = ir_path.stat().st_mtime

    age_hours = (time.time() - last_build) / 3600 if last_build else float("inf")
    is_stale = age_hours >= 24

    # Node count (IR stores nodes as a list under "nodes")
    node_count = ir_meta.get("node_count", len(ir_meta.get("nodes", [])))

    # Disk usage
    disk_usage = sum(f.stat().st_size for f in nm_dir.rglob("*") if f.is_file())
    disk_mb = disk_usage / (1024 * 1024)

    # Synapse stats
    synapse_path = nm_dir / "synapses.db"
    synapse_count = 0
    if synapse_path.exists():
        try:
            from neuralmind.synapses import SynapseStore
            stats = SynapseStore(synapse_path).stats()
            synapse_count = stats.get("edges", 0)
        except Exception:
            pass

    result = {
        "status": "stale" if is_stale else "healthy",
        "healthy": not is_stale,
        "exit_code": 1 if is_stale else 0,
        "index": {
            "path": str(ir_path),
            "node_count": node_count,
            "last_build": last_build,
            "age_hours": round(age_hours, 1),
            "stale": is_stale,
        },
        "disk_usage_mb": round(disk_mb, 2),
        "synapse_edges": synapse_count,
    }

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        status_icon = "🟢" if not is_stale else "🟡"
        print(f"{status_icon} NeuralMind Health — {project_path.name}")
        print(f"  Status:       {'healthy' if not is_stale else 'stale (index >= 24h old)'}")
        print(f"  Nodes:        {node_count}")
        print(f"  Last build:    {time.strftime('%Y-%m-%d %H:%M', time.localtime(last_build)) if last_build else 'unknown'}")
        print(f"  Index age:    {age_hours:.1f} hours")
        print(f"  Synapse edges: {synapse_count}")
        print(f"  Disk usage:   {disk_mb:.1f} MB")
        if is_stale:
            print(f"\n  💡 Rebuild: neuralmind build {project_path}")

    sys.exit(1 if is_stale else 0)
