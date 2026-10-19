# SPDX-License-Identifier: MIT
"""Health check command for NeuralMind CLI + MCP.

Provides a lightweight health signal for CI/CD, Docker healthchecks,
and systemd ExecStartPre. Returns index age, node count, last build
time, and disk usage.

Exit codes:
    0 = healthy (index exists and the code graph matches the files on disk)
    1 = stale (the freshness check WARNs or FAILs: files missing from the
        graph, deleted files still indexed, files changed since the graph,
        or a graph built on another OS)
    2 = no index

With ``--stale-after`` (or ``stale_after`` in ``.neuralmind.yaml``) drift
younger than that is "catching up" and exits 0: a watcher or a background
rebuild gets that long to catch the index up before the gate trips. Drift
with no date (files gone from disk, a graph built on another OS) still exits 1.

Index age is still reported, but it no longer decides staleness: a
day-old index of unchanged code is current, and an hour-old index that
misses new files is not.
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

    try:
        last_build = float(last_build)
    except (TypeError, ValueError):
        last_build = ir_path.stat().st_mtime
    age_hours = (time.time() - last_build) / 3600 if last_build else float("inf")

    # No report (no graph to compare, or the check failed) is "unknown", never
    # healthy: nothing confirmed the index matches the code.
    freshness = None
    try:
        from neuralmind.freshness import graph_freshness

        freshness = graph_freshness(project_path, check_index=True)
    except Exception:
        freshness = None
    from neuralmind.freshness import format_age, format_duration, health_status, track_drift

    stale_after = _stale_after(args, project_path)
    invalid = None if stale_after is not None else _invalid_stale_after(project_path)
    if invalid is not None:
        # Without a limit any drift exits 1, so this errs strict, but say so.
        print(
            f"neuralmind health: stale_after: {invalid!r} in .neuralmind.yaml isn't a "
            "duration (use s, m, h or d, e.g. 30m); no grace period applies",
            file=sys.stderr,
        )
    if stale_after is not None:
        track_drift(project_path, freshness)
    status = health_status(freshness, stale_after)
    unknown = status == "unknown"
    catching_up = status == "catching_up"
    drifted = status != "healthy"
    is_stale = status in ("stale", "unknown")

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

    behind = freshness.behind_seconds() if freshness is not None else None
    result = {
        "status": status,
        "healthy": not is_stale,
        "exit_code": 1 if is_stale else 0,
        "index": {
            "path": str(ir_path),
            "node_count": node_count,
            "last_build": last_build,
            "age_hours": round(age_hours, 1),
            "stale": is_stale,
        },
        "freshness": freshness.to_dict() if freshness is not None else None,
        "stale_after_seconds": stale_after,
        "stale_after_invalid": invalid,
        "behind_seconds": round(behind, 1) if behind is not None else None,
        "disk_usage_mb": round(disk_mb, 2),
        "synapse_edges": synapse_count,
    }

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        status_icon = "🟢" if not is_stale else "🟡"
        if unknown:
            status_text = "unknown (no readable code graph to check the index against)"
        elif catching_up:
            status_text = (
                f"catching up (behind {format_age(behind or 0)}, within "
                f"stale_after {format_duration(stale_after)})"
            )
        elif is_stale:
            status_text = "stale (graph out of step with the code)"
            if behind is not None:
                status_text += f", behind {format_age(behind)}"
            if stale_after is not None:
                status_text += f"; {freshness.overdue_reason(stale_after)}"
        else:
            status_text = "healthy"
        print(f"{status_icon} NeuralMind Health — {project_path.name}")
        print(f"  Status:       {status_text}")
        print(f"  Nodes:        {node_count}")
        print(
            f"  Last build:    {time.strftime('%Y-%m-%d %H:%M', time.localtime(last_build)) if last_build else 'unknown'}"
        )
        print(f"  Index age:    {age_hours:.1f} hours")
        print(f"  Synapse edges: {synapse_count}")
        print(f"  Disk usage:   {disk_mb:.1f} MB")
        if drifted and freshness is not None:
            print()
            print("  " + freshness.render(str(project_path), indent="    ").replace("\n", "\n  "))

    sys.exit(1 if is_stale else 0)


def _invalid_stale_after(project_path: Path) -> str | None:
    try:
        from neuralmind.neuralmind_config import NeuralmindConfig

        return NeuralmindConfig.load(project_path).stale_after_invalid
    except Exception:
        return None


def _stale_after(args, project_path: Path) -> float | None:
    """``--stale-after``, else ``stale_after`` from ``.neuralmind.yaml``."""
    raw = getattr(args, "stale_after", None)
    if raw is not None:
        return raw  # parsed by argparse
    try:
        from neuralmind.neuralmind_config import NeuralmindConfig

        return NeuralmindConfig.load(project_path).stale_after
    except Exception:
        return None
