#!/usr/bin/env python3
"""
cli.py - NeuralMind Command Line Interface
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neuralmind import __version__, memory
from neuralmind.audit import AuditTrail
from neuralmind.core import GraphNotBuiltError, NeuralMind, create_mind
from neuralmind.doc_evolver import BlindSpot, DocEvolver
from neuralmind.metrics_pipeline import MetricsCollector
from neuralmind.onboarding import cmd_onboarding
from neuralmind.tier2.config import TIER2_CONFIG_DIR
from neuralmind.tier2.license import issue_free_license

# Upgrade conversion state — tracks usage count for CTA trigger
_UPGRADE_CTA_STATE_PATH = TIER2_CONFIG_DIR / ".cta_state.json"


def _get_wakeup_count() -> int:
    """Return cumulative wakeup/query count (for upgrade CTA gating)."""
    if _UPGRADE_CTA_STATE_PATH.exists():
        try:
            data = json.loads(_UPGRADE_CTA_STATE_PATH.read_text(encoding="utf-8"))
            return data.get("count", 0)
        except (OSError, ValueError):
            return 0
    return 0


def _increment_wakeup_count() -> int:
    """Increment usage counter and return new value. Triggers CTA at 10."""
    count = _get_wakeup_count() + 1
    _UPGRADE_CTA_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _UPGRADE_CTA_STATE_PATH.write_text(json.dumps({"count": count}), encoding="utf-8")
    # Fire the CTA exactly once when we cross the threshold
    if count == 10:
        print(
            "NeuralMind Team: $29/user/mo — shared memory, governance, seat management.\n"
            "See neuralmind.uk/pricing or run `neuralmind onboarding`."
        )
    return count


def _force_utf8_io() -> None:
    """Force UTF-8 on stdout/stderr so non-ASCII output (arrows, em-dashes,
    box-drawing glyphs in the context/report) doesn't crash on Windows consoles,
    which default to the cp1252 codec and raise UnicodeEncodeError.

    No-op where it isn't needed or possible: streams already UTF-8 (Linux/macOS)
    or that lack ``reconfigure`` (e.g. pytest capture objects).
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


_LANG_EXTS: dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
}

_IGNORED_DIRS = {
    ".git",
    ".neuralmind",
    "graphify-out",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
}


def _dry_run_scan(project_path: str) -> dict:
    """Scan a project and estimate NeuralMind token savings without building."""
    path = Path(project_path).resolve()
    lang_counts: dict[str, int] = {}
    total_lines = 0
    total_files = 0

    for f in path.rglob("*"):
        if any(part in _IGNORED_DIRS for part in f.parts):
            continue
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext not in _LANG_EXTS:
            continue
        lang = _LANG_EXTS[ext]
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        total_files += 1
        try:
            total_lines += sum(1 for _ in f.open("rb"))
        except OSError:
            pass

    # Estimate node count: ~10 nodes per code file (functions, classes, etc.)
    est_nodes = total_files * 10
    # Estimate full-codebase tokens: ~25 tokens per line on average
    est_full_tokens = max(total_lines * 25, est_nodes * 40)
    # NeuralMind progressive context: L0+L1+L2+L3 ≈ 600-2400 tokens
    est_query_tokens = min(2400, max(600, est_nodes * 2))
    est_wakeup_tokens = min(800, max(150, est_nodes))
    est_reduction = round(est_full_tokens / max(est_query_tokens, 1), 1)

    return {
        "project": path.name,
        "total_files": total_files,
        "total_lines": total_lines,
        "languages": lang_counts,
        "est_nodes": est_nodes,
        "est_full_tokens": est_full_tokens,
        "est_wakeup_tokens": est_wakeup_tokens,
        "est_query_tokens": est_query_tokens,
        "est_reduction_ratio": est_reduction,
    }


def _check_version_mismatch(project_path: str) -> str | None:
    """Return a warning string if the project's ir_meta.json was built with
    a different NeuralMind version than the running one, else None.

    A missing file or a file without a version stamp (pre-v0.46.0 builds)
    yields None — we only warn when there is a concrete mismatch, so users
    who upgrade don't get false alarms on actively-built projects.
    """
    ir_meta_path = Path(project_path) / ".neuralmind" / "ir_meta.json"
    if not ir_meta_path.exists():
        return None
    try:
        meta = json.loads(ir_meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    stored = meta.get("neuralmind_version")
    if stored and stored != __version__:
        return (
            f"This project was indexed with NeuralMind v{stored}.\n"
            f"v{__version__} requires a one-time reindex.\n"
            f"Run: neuralmind build --force"
        )
    return None


def cmd_build(args):
    project_path = args.project_path or "."

    if getattr(args, "dry_run", False) is True:
        path = Path(project_path)
        if not path.exists():
            print(f"Dry-run failed: path does not exist: {project_path}")
            sys.exit(1)
        scan = _dry_run_scan(project_path)
        if args.json:
            print(json.dumps(scan, indent=2))
            return
        print(f"NeuralMind dry run — {scan['project']}")
        print(f"  Files scanned : {scan['total_files']}")
        print(f"  Lines of code : {scan['total_lines']:,}")
        if scan["languages"]:
            langs = ", ".join(
                f"{v} {k}" for k, v in sorted(scan["languages"].items(), key=lambda kv: -kv[1])
            )
            print(f"  Languages     : {langs}")
        print()

        print(f"  Estimated nodes       : {scan['est_nodes']:,}")
        print(f"  Est. full-codebase    : ~{scan['est_full_tokens']:,} tokens")
        print(f"  Est. wake-up context  : ~{scan['est_wakeup_tokens']:,} tokens")
        print(f"  Est. query context    : ~{scan['est_query_tokens']:,} tokens")
        print(f"  Est. token reduction  : ~{scan['est_reduction_ratio']}x per query")
        print()

        print("No index was built. Run `neuralmind build .` to activate these savings.")
        return

    force = args.force
    print(f"Building NeuralMind index for: {project_path}")
    print(f"Force rebuild: {force}")
    print()

    path = Path(project_path)
    if not path.exists():
        print(f"Build failed: project path does not exist: {project_path}")
        sys.exit(1)
    if not path.is_dir():
        print(f"Build failed: project path is not a directory: {project_path}")
        sys.exit(1)

    # Migration check: surface mismatched version before slow reindex
    _migrate_warning = _check_version_mismatch(project_path)
    if _migrate_warning:
        print(
            f"\n⚠  {_migrate_warning}\n",
            file=sys.stderr,
        )

    mind = NeuralMind(project_path)
    # Wire --bootstrap into the NeuralMind instance
    if getattr(args, "bootstrap", None):
        mind._bootstrap_bundle_path = args.bootstrap
    result = mind.build(force=force)
    if result.get("success"):
        print("Build successful!")
        print(f"   Project: {result.get('project')}")
        print(f"   Nodes: {result.get('nodes_total')}")
        print(f"   Communities: {result.get('communities')}")
        ir_meta = result.get("ir")
        if isinstance(ir_meta, dict) and "ir_version" in ir_meta:
            val = ir_meta.get("validation", {})
            status = "valid" if val.get("ok", True) else f"{val.get('errors', 0)} error(s)"
            print(f"   IR: v{ir_meta['ir_version']} ({status})")
        print(f"   Duration: {result.get('duration_seconds')}s")
    else:
        print(f"Build failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


def _try_daemon():
    """Return a connected DaemonClient, or None to fall back to direct mode.

    Honors NEURALMIND_NO_DAEMON=1 to force direct mode. Never raises — any
    discovery/connection problem degrades to direct mode silently.
    """
    if os.environ.get("NEURALMIND_NO_DAEMON") == "1":
        return None
    try:
        from neuralmind.daemon_client import connect

        return connect()
    except Exception:
        return None


def _print_trace(trace: dict | None) -> None:
    """Render a retrieval trace as a compact, human-readable block."""
    if not trace:
        return
    print("-" * 60)
    print(f"Retrieval trace ({len(trace.get('events', []))} events):")
    for e in trace.get("events", []):
        print(f"  [{e.get('layer')}/{e.get('kind')}] {e.get('summary')}")


def _print_explain(result) -> None:
    """Render a human-friendly explanation of why this context was selected.

    Shows token savings, which synapse pairs fired, which communities were
    loaded, and how many nodes were brought in via spreading activation.
    The goal is to make the token savings claim verifiable at a glance.
    """
    print("-" * 60)
    print("Why this context?")
    print()

    # Token savings
    budget = result.budget
    est_full = 50_000  # NeuralMind's internal reference baseline
    saved = est_full - budget.total
    print("  Token budget breakdown:")
    if budget.l0_identity:
        print(f"    L0 identity   : {budget.l0_identity:>6} tokens")
    if budget.l1_summary:
        print(f"    L1 summary    : {budget.l1_summary:>6} tokens")
    if budget.l2_ondemand:
        print(f"    L2 communities: {budget.l2_ondemand:>6} tokens")
    if budget.l3_search:
        print(f"    L3 search     : {budget.l3_search:>6} tokens")
    print(f"    Total used    : {budget.total:>6} tokens")
    print(f"    Est. saved    : {saved:>6} tokens  ({result.reduction_ratio:.1f}x reduction)")
    print()

    # Layers used
    if result.layers_used:
        print(f"  Layers activated : {', '.join(result.layers_used)}")

    # Communities loaded
    if result.communities_loaded:
        print(f"  Communities loaded: {result.communities_loaded}")
    print()

    # Top search hits (L3)
    hits = result.top_search_hits or []
    if hits:
        print(f"  Top search hits (L3, {len(hits)} nodes):")
        for h in hits[:5]:
            label = h.get("label") or h.get("id", "?")
            src = h.get("source_file", "")
            score = h.get("score", 0.0)
            src_str = f"  ({src})" if src else ""
            print(f"    {score:.3f}  {label}{src_str}")
        print()

    # Synapse trace (if --trace was also requested)
    trace = result.trace
    if trace and trace.get("events"):
        synapse_events = [e for e in trace["events"] if "synapse" in (e.get("kind") or "")]
        if synapse_events:
            print(f"  Synapses that fired ({len(synapse_events)} events):")
            for e in synapse_events[:5]:
                print(f"    {e.get('summary', '')}")
            print()
    elif not trace:
        print("  Tip: add --trace to see per-layer synapse firing detail.")


def cmd_query(args):
    _maybe_prompt_for_memory_opt_in()
    _increment_wakeup_count()

    # Migration check: warn on version mismatch before slow reindex
    _migrate_warning = _check_version_mismatch(args.project_path or ".")
    if _migrate_warning:
        print(
            f"\n⚠  {_migrate_warning}\n",
            file=sys.stderr,
        )

    trace = getattr(args, "trace", False) is True
    trace_verbose = getattr(args, "trace_verbose", False) is True
    relevance = getattr(args, "relevance", False) is True
    explain = getattr(args, "explain", False) is True
    # --explain needs trace data to show synapse firings; enable it implicitly
    if explain and not trace:
        trace = True

    # --relevance (sidecar from ContextResult.top_search_hits) and --explain
    # (full per-layer breakdown) both need the full result object, which the
    # daemon's thin query response does not carry — fall back to direct mode
    # when either is requested.
    client = None if (relevance or explain) else _try_daemon()
    if client is not None:
        try:
            out = client.query(
                str(Path(args.project_path).resolve()),
                args.question,
                trace=trace,
                trace_verbose=trace_verbose,
            )
            if not out.get("error"):
                if args.json:
                    print(
                        json.dumps(
                            {
                                "query": args.question,
                                "tokens": out.get("tokens"),
                                "reduction_ratio": out.get("reduction_ratio"),
                                "layers": out.get("layers"),
                                "context": out.get("context", ""),
                                "trace": out.get("trace"),
                                "via": "daemon",
                            },
                            indent=2,
                        )
                    )
                else:
                    print(f"Query: {args.question}  (via daemon)")
                    print(f"Tokens: {out.get('tokens')} ({out.get('reduction_ratio')}x reduction)")
                    print("=" * 60)
                    print(out.get("context", ""))
                    print("=" * 60)
                    if trace:
                        _print_trace(out.get("trace"))
                return
        except Exception:
            pass  # fall through to direct mode

    mind = create_mind(args.project_path, auto_build=True)
    result = mind.query(args.question, trace=trace, trace_verbose=trace_verbose)
    if args.json:
        output = {
            "query": args.question,
            "tokens": result.budget.total,
            "reduction_ratio": round(result.reduction_ratio, 1),
            "layers": result.layers_used,
            "context": result.context,
            "trace": result.trace,
        }
        if relevance:
            from .relevance import build_relevance_sidecar

            output["relevance"] = build_relevance_sidecar(result.top_search_hits, mind)
        print(json.dumps(output, indent=2))
    else:
        print(f"Query: {args.question}")
        print(f"Tokens: {result.budget.total} ({result.reduction_ratio:.1f}x reduction)")
        print("=" * 60)
        print(result.context)
        print("=" * 60)
        if explain:
            _print_explain(result)
        elif trace:
            _print_trace(result.trace)


def _maybe_prompt_for_memory_opt_in():
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    if not memory.should_prompt_for_consent(is_tty=is_tty):
        return

    print(
        "NeuralMind can keep local query memory (project + global JSONL) "
        "to improve future retrieval."
    )
    enabled = memory.prompt_for_memory_consent()
    memory.write_consent_sentinel(enabled)
    if enabled:
        print("NeuralMind memory logging enabled.")
    else:
        print("NeuralMind memory logging disabled.")


def cmd_wakeup(args):
    mind = create_mind(args.project_path, auto_build=True)
    result = mind.wakeup()
    is_json = args.json

    # Auto-issue free license on first run
    license_path = TIER2_CONFIG_DIR / "license.json"
    if not license_path.exists():
        issue_free_license(license_path)
        if not is_json:
            print(
                "✓ Free tier activated — run `neuralmind onboarding` to configure,\n"
                "  `neuralmind team license status` to view."
            )

    _increment_wakeup_count()

    if not is_json:
        _maybe_prompt_for_memory_opt_in()

    if is_json:
        output = {
            "type": "wakeup",
            "tokens": result.budget.total,
            "context": result.context,
        }
        print(json.dumps(output, indent=2))
    else:
        print(
            f"Wake-up Context ({result.budget.total} tokens, {result.reduction_ratio:.1f}x reduction)"
        )
        print(result.context)


def cmd_savings(args):
    """Show cumulative token savings from the local query event log.

    Reads the audit_events.jsonl (and fallback to memory query_events.jsonl)
    to compute how many tokens NeuralMind has saved across all logged queries.
    This lets you verify the savings claim against your own real usage.

    The aggregation lives in neuralmind.savings.compute_savings so the MCP
    server and daemon can serve the same report.
    """
    from neuralmind.savings import BASELINE_TOKENS_PER_QUERY, compute_savings

    project_path = Path(getattr(args, "project_path", ".")).resolve()
    use_global = getattr(args, "global_", False)

    report = compute_savings(
        project_path,
        use_global=use_global,
        cost=getattr(args, "cost", False),
        model=getattr(args, "model", None),
        queries_per_day=getattr(args, "queries_per_day", 100),
    )

    error = report.get("error")
    if error:
        if error.startswith("could not read"):
            print(error[0].upper() + error[1:], file=sys.stderr)
            sys.exit(1)
        # "no event log found" falls through to the friendly hint below.
        if args.json:
            print(json.dumps(report))
        else:
            print(f"No savings log found at {report['path']}")
            print("Run some queries first to generate audit data.")
        return

    if "total_queries" not in report:
        # Zero events logged.
        if args.json:
            print(json.dumps({"queries": 0, "total_tokens_saved": 0}))
        else:
            print("No events logged yet. Run some queries to start tracking savings.")
        return

    if args.json:
        print(json.dumps(report, indent=2))
        return

    est_full = BASELINE_TOKENS_PER_QUERY
    dollar_info = report.get("dollar_savings")
    print(f"NeuralMind token savings — {report['scope']}")
    print()
    print(f"  Queries logged    : {report['total_queries']}")
    print(f"  Wakeups logged    : {report['total_wakeups']}")
    print(f"  Avg reduction     : {report['avg_reduction_ratio']:.1f}x")
    print()
    print(f"  Tokens actually used : {report['total_tokens_used']:>10,}")
    print(
        f"  Est. cost without NM : {report['est_total_full_cost']:>10,}  "
        f"(at {est_full:,} tokens/query)"
    )
    print(f"  Tokens saved         : {report['total_tokens_saved']:>10,}")
    if dollar_info:
        print()
        print(
            f"  Dollar savings — {dollar_info['model']} "
            f"@ ${dollar_info['price_per_mtok']}/MTok input"
        )
        print(f"    Cost without NM (est): ${dollar_info['baseline_cost_total']:>10,.2f}")
        print(f"    Cost with NM         : ${dollar_info['actual_cost_total']:>10,.2f}")
        print(f"    Saved (est)          : ${dollar_info['saved_total']:>10,.2f}")
        print(
            f"    Projected (est)      : ${dollar_info['daily_saved']:,.2f}/day · "
            f"${dollar_info['monthly_saved']:,.2f}/month  "
            f"(at {dollar_info['queries_per_day']} queries/day)"
        )
        print(f"    (without-NM estimated from {est_full:,} tok/query baseline)")
    recent = report.get("recent_queries") or []
    if recent:
        print()
        print("  Most recent queries:")
        for q in recent:
            ratio_str = f"{q['ratio']:.1f}x" if q["ratio"] else "?"
            ts = q["ts"][:10] if q["ts"] else ""
            label = q["query"][:55] + "…" if len(q["query"]) > 55 else q["query"]
            print(f"    {ts}  [{q['tokens']:>5} tok / {ratio_str:>5}]  {label}")


def cmd_review(args):
    """Warn about co-breakage risk before a commit or when reviewing a diff.

    Finds files changed in the current git diff (or a specified base ref),
    runs spreading activation through the learned synapse graph to find
    strongly associated files that are NOT in the diff, and reports them as
    likely co-break candidates — files that have historically changed together
    with the ones you're touching now.

    Use this before committing to catch forgotten test files, config updates,
    or tightly-coupled modules that the agent didn't include.
    """
    import subprocess

    project_path = Path(getattr(args, "project_path", ".")).resolve()
    base = getattr(args, "base", None) or "HEAD"
    top_k = int(getattr(args, "top_k", 10))

    # Get changed files from git
    try:
        cmd = ["git", "-C", str(project_path), "diff", "--name-only", base]
        changed_raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        changed_files = [
            str(project_path / p.strip()) for p in changed_raw.splitlines() if p.strip()
        ]
    except subprocess.CalledProcessError:
        # Try staged changes
        try:
            cmd = ["git", "-C", str(project_path), "diff", "--cached", "--name-only"]
            changed_raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
            changed_files = [
                str(project_path / p.strip()) for p in changed_raw.splitlines() if p.strip()
            ]
        except Exception as exc:
            print(f"review: could not read git diff: {exc}", file=sys.stderr)
            sys.exit(1)
    except Exception as exc:
        print(f"review: {exc}", file=sys.stderr)
        sys.exit(1)

    if not changed_files:
        if args.json:
            print(json.dumps({"changed_files": [], "at_risk": [], "message": "no changed files"}))
        else:
            print(f"review: no changed files in diff against {base}")
        return

    # Load NeuralMind and run spreading activation from the changed files
    try:
        mind = create_mind(str(project_path), auto_build=True)
    except Exception as exc:
        print(f"review: could not load NeuralMind index: {exc}", file=sys.stderr)
        sys.exit(1)

    changed_set = set(changed_files)
    # Map file paths to node IDs so we can seed the spread
    seed_ids: list[tuple[str, float]] = []
    for fpath in changed_files:
        try:
            for node in mind.embedder.get_file_nodes(fpath):
                nid = node.get("id")
                if nid:
                    seed_ids.append((str(nid), 1.0))
        except Exception:
            continue

    at_risk: list[dict] = []
    if seed_ids and mind.synapses is not None:
        try:
            neighbors = mind.synapses.spread(seed_ids, depth=2, top_k=top_k * 2)
            # Resolve node ids back to file paths
            seen_files: set[str] = set()
            for node_id, weight in neighbors:
                # Find the file for this node id via the embedder's node list
                node_file = None
                try:
                    all_nodes = getattr(mind.embedder, "nodes", []) or []
                    for n in all_nodes:
                        if str(n.get("id", "")) == node_id:
                            node_file = n.get("metadata", {}).get("source_file") or n.get(
                                "source_file", ""
                            )
                            break
                except Exception:
                    pass
                if not node_file:
                    continue
                abs_file = (
                    str(project_path / node_file)
                    if not Path(node_file).is_absolute()
                    else node_file
                )
                if abs_file in changed_set or abs_file in seen_files:
                    continue
                seen_files.add(abs_file)
                rel = str(Path(abs_file).relative_to(project_path))
                at_risk.append({"file": rel, "synapse_weight": round(weight, 3)})
                if len(at_risk) >= top_k:
                    break
        except Exception:
            pass

    if args.json:
        changed_rel = [str(Path(f).relative_to(project_path)) for f in changed_files]
        print(
            json.dumps({"changed_files": changed_rel, "at_risk": at_risk, "base": base}, indent=2)
        )
        return

    changed_rel = [str(Path(f).relative_to(project_path)) for f in changed_files]
    print(f"NeuralMind review — {project_path.name}  (diff against: {base})")
    print()
    print(f"Changed files ({len(changed_rel)}):")
    for f in changed_rel:
        print(f"  • {f}")
    print()

    if not at_risk:
        if mind.synapses is None:
            print("No synapse graph yet — build and use the project first to learn associations.")
        else:
            print("No strongly associated files found outside the diff. Looks complete.")
        return

    print(f"Co-break candidates — files NOT in diff but strongly associated ({len(at_risk)}):")
    for item in at_risk:
        weight = item["synapse_weight"]
        bars = "█" * min(int(weight * 10), 8)
        print(f"  {weight:.3f} {bars:<8}  {item['file']}")
    print()
    print(
        "These files have historically been edited together with the ones above.\n"
        "Consider whether your change also needs to touch them."
    )


def cmd_benchmark(args):
    # Literal True check — a bare MagicMock() args (used by the benchmark unit
    # tests) makes `args.quality` a truthy attribute but not `is True`, so the
    # default token-reduction path still runs. Mirrors the --contribute guard.
    if getattr(args, "quality", False) is True:
        _run_quality_eval(args)
        return

    if getattr(args, "public", False) is True:
        _run_public_benchmark(args)
        return

    if getattr(args, "content", False):
        _run_content_benchmark(args)
        return

    print(f"Running benchmark for: {args.project_path}")
    mind = create_mind(args.project_path, auto_build=True)
    result = mind.benchmark()

    # Literal True check — MagicMock-auto-attribute would be truthy but not
    # `is True`, so existing tests that use `MagicMock()` without spec
    # don't accidentally trigger the community-submission path.
    if getattr(args, "contribute", False) is True:
        _emit_community_submission(args, result, mind)
        return

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Project: {result['project']}")
        print(f"Wake-up tokens: {result['wakeup_tokens']}")
        print(f"Avg query tokens: {result['avg_query_tokens']}")
        print(f"Avg reduction: {result['avg_reduction_ratio']}x")
        print(f"Summary: {result['summary']}")


def cmd_probe(args):
    """`neuralmind probe` — retrieval self-probe on your own codebase.

    Unlike `benchmark` (which measures token reduction) and `benchmark
    --quality` (which scores ranking against committed golden fixtures), this
    runs label-free on the current project: it samples indexed symbols, queries
    each by its docstring/intent, and reports recall@k / MRR / answerability
    plus the symbols it couldn't find.
    """
    import contextlib

    # Validate early — before the (potentially slow) build — so a bad depth or
    # an accidental full-repo probe fails fast with a clear message.
    if args.k < 1:
        print(f"probe: --k must be >= 1 (got {args.k})", file=sys.stderr)
        sys.exit(2)
    if args.sample_size < 0:
        print(
            f"probe: --sample-size must be >= 0 (got {args.sample_size}; 0 means 'all')",
            file=sys.stderr,
        )
        sys.exit(2)

    # The embedder prints graph-load / embedding progress to stdout, which would
    # corrupt --json and clutter the human report. Redirect that to stderr (the
    # same trick the quality harness uses) so stdout carries only the report.
    try:
        with contextlib.redirect_stdout(sys.stderr):
            mind = create_mind(args.project_path, auto_build=True)
            report = mind.retrieval_probe(
                sample_size=args.sample_size,
                k=args.k,
                seed=args.seed,
            )
    except ValueError as exc:
        # Bad --k / --sample-size: report cleanly and exit non-zero rather than
        # emitting a valid-looking zero-recall report (which would corrupt
        # baseline data).
        print(f"probe: {exc}", file=sys.stderr)
        sys.exit(2)
    data = report.to_dict()

    baseline = None
    if getattr(args, "baseline", None):
        try:
            raw = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
            baseline = raw.get("mean_recall") and raw or None
        except (OSError, ValueError) as exc:
            print(f"probe: could not read baseline {args.baseline}: {exc}", file=sys.stderr)
            sys.exit(1)

    if args.json:
        if baseline is not None:
            from neuralmind import quality

            data["baseline_deltas"] = [
                d.to_dict() for d in quality.compare_to_baseline(report.suite, baseline)
            ]
        print(json.dumps(data, indent=2))
        return

    if data["n_queries"] == 0:
        print(f"probe: no probeable symbols in {Path(args.project_path).resolve().name}.")
        print("Build the index first: neuralmind build .")
        sys.exit(1)

    print(f"Retrieval self-probe — {Path(args.project_path).resolve().name}")
    print(
        f"Sampled {data['sample_size']} of {data['index_size']} indexed symbols, "
        f"retrieval depth k={data['k']}"
    )
    sources = data.get("query_sources") or {}
    if sources:
        # Disclose query provenance: rationale = real NL→code test; label/file =
        # weaker, more circular fallback. A mostly-label run is a sanity check.
        src_str = ", ".join(f"{n} {s}" for s, n in sorted(sources.items(), key=lambda x: -x[1]))
        print(f"Query source: {src_str}")
    print("=" * 60)
    print(f"  answerability  : {data['answerability']:.0%}  (file found in top-{data['k']})")
    print(f"  MRR            : {data['mrr']:.3f}")
    recall = data["mean_recall"]
    print(
        "  recall@1/3/5   : "
        f"{recall.get('1', 0):.3f} / {recall.get('3', 0):.3f} / {recall.get('5', 0):.3f}"
    )
    print(f"  blind spots    : {data['blind_spot_total']}")
    if baseline is not None:
        from neuralmind import quality

        print("-" * 60)
        print("vs baseline:")
        for d in quality.compare_to_baseline(report.suite, baseline):
            arrow = "▲" if d.delta > 5e-4 else ("▼" if d.delta < -5e-4 else "=")
            print(f"  {d.metric}: {d.current:.3f} ({arrow} {d.delta:+.3f})")
    if data["blind_spots"]:
        print("-" * 60)
        shown = data["blind_spots"]
        print(
            f"Symbols the index couldn't retrieve from their own description ({data['blind_spot_total']} total):"
        )
        for spot in shown:
            print(f'  - {spot["label"]}  ({spot["source_file"]})   query: "{spot["query"]}"')
        if data["blind_spot_total"] > len(shown):
            print(f"  … and {data['blind_spot_total'] - len(shown)} more (see --json)")


def _run_public_benchmark(args) -> None:
    """`neuralmind benchmark --public` — the reproducible vs-alternatives benchmark.

    Runs against the pinned real-repo corpus + baseline matrix that ships with
    the *source* repo (the `evals/public` package), not the installed wheel.
    Clones the pinned repos on demand; reports gold-file recall (objective,
    no LLM judge) against context-token cost. See docs/benchmarks/public.md.
    """
    try:
        from evals.public import run as public_run
    except ImportError:
        print(
            "neuralmind benchmark --public runs against the pinned real-repo corpus "
            "that ships with the source repository (the `evals/public` package), not "
            "the installed wheel. Clone the repo and run "
            "`python -m evals.public.run` from its root.",
            file=sys.stderr,
        )
        sys.exit(2)

    judge_client = None
    if getattr(args, "judge", False):
        from evals.public import judge as public_judge

        judge_client = public_judge.make_client()
        if judge_client is None:
            print(
                "--judge needs ANTHROPIC_API_KEY and the `anthropic` package; "
                "skipping the answerability arm (the recall table still runs).",
                file=sys.stderr,
            )

    manifest = public_run.load_manifest()
    report = public_run.run_all(
        manifest,
        only=getattr(args, "repo", None),
        seeds=getattr(args, "seeds", 1) or 1,
        judge_client=judge_client,
    )
    if judge_client is not None:
        public_run._write_judge_transcripts(
            report, Path(getattr(args, "judge_out", None) or "bench/public/judge")
        )
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        print(public_run.render_markdown(report))


def _run_quality_eval(args) -> None:
    """`neuralmind benchmark --quality` — the retrieval-quality self-test.

    Like `neuralmind eval`, this runs against the golden suites that ship with
    the *source* repo (the `evals/` package), not the installed wheel. Exits
    non-zero when a suite regresses past its threshold so CI can gate on it.
    """
    try:
        from evals.quality import harness, runner
    except ImportError:
        print(
            "neuralmind benchmark --quality runs against the golden query suites "
            "that ship with the source repository (the `evals/` package), not the "
            "installed wheel. Clone the repo and run "
            "`python -m evals.quality.runner --run` from its root.",
            file=sys.stderr,
        )
        sys.exit(2)

    names = [args.suite] if getattr(args, "suite", None) else runner.all_suites()
    baseline = None
    if getattr(args, "baseline", None):
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))

    try:
        reports = [harness.run_suite(name) for name in names]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    except RuntimeError as exc:
        print(f"quality eval unavailable: {exc}", file=sys.stderr)
        print(
            "It needs the retrieval stack + built fixtures. Run "
            "`python -m evals.quality.runner --selfcheck` to validate the golden "
            "suites + metric math only.",
            file=sys.stderr,
        )
        sys.exit(2)

    exit_code = harness.emit(reports, baseline=baseline, as_json=args.json)
    sys.exit(exit_code)


def _run_content_benchmark(args) -> None:
    """`neuralmind benchmark --content` — the N-16 content retrieval benchmark.

    Ingests a book corpus (default: Underground) and runs the N-16 eval.
    Reports IR metrics + RAGAS faithfulness + CI regression status.
    """
    from pathlib import Path

    from evals.book_retrieval.run import run_eval

    content_path = args.content  # Already set by nargs="?" const
    manifest_path = None
    if content_path != "evals/book_retrieval/underground/chapters":
        # Custom path — look for manifest_v2.json in parent dir
        candidate = Path(content_path).parent / "manifest_v2.json"
        if candidate.exists():
            manifest_path = candidate

    print(f"N-16 Content Benchmark")
    print(f"  Content: {content_path}")
    print(f"  Manifest: {manifest_path or 'default'}")
    print()

    report = run_eval(manifest_path=manifest_path, verbose=True)

    if "error" in report:
        print(f"Error: {report['error']}", file=sys.stderr)
        sys.exit(1)

    # Check CI floors (matching tests/test_content_benchmark.py)
    agg = report["aggregates"]
    floors = {
        "recall@5": (agg["recall_at_5"], 0.20),
        "MRR": (agg["mrr"], 0.30),
        "nDCG@5": (agg["ndcg_at_5"], 0.20),
        "hit_rate": (agg["hit_rate"], 0.50),
        "faithfulness": (agg["mean_faithfulness"], 0.0),
    }

    print()
    print("CI REGRESSION GATE:")
    all_pass = True
    for metric, (actual, floor) in floors.items():
        passed = actual >= floor
        status = "PASS" if passed else "FAIL"
        print(f"  {metric}: {actual:.4f} >= {floor:.2f} [{status}]")
        if not passed:
            all_pass = False

    if args.json:
        report["ci_pass"] = all_pass
        print(json.dumps(report, indent=2))
    else:
        print()
        print(f"Overall: {'PASS' if all_pass else 'FAIL'}")

    if not all_pass:
        sys.exit(1)


def _emit_community_submission(args, benchmark_result: dict, mind) -> None:
    """Transform benchmark output into a community-benchmarks.json entry.

    Outputs a JSON blob users can paste directly into the community
    benchmarks file or attach to an issue/PR. Missing metadata is
    prompted interactively (TTY) or left as `null` with a comment
    explaining the omission (non-TTY / scripted use).
    """
    from datetime import date

    project_name = getattr(args, "project_name", None) or _prompt(
        "Project name (short, under 40 chars)",
        default=Path(args.project_path).resolve().name,
    )
    language = getattr(args, "language", None) or _prompt(
        "Primary language (Python / JavaScript / TypeScript / Go / Rust / Java / Mixed / Other)",
        default="",
    )
    model = getattr(args, "model", None) or _prompt(
        "Which model you run this against (e.g. 'Claude 3.5 Sonnet')",
        default="",
    )
    repo_url = getattr(args, "repo_url", None) or _maybe_detect_repo_url(args.project_path)
    notes = getattr(args, "notes", None)

    submitted_by = getattr(args, "submitter", None) or _prompt(
        "Your GitHub username (no leading @)",
        default="",
    )

    # Try to pull node count from stats; fall back to None so the reviewer
    # can spot it rather than silently reporting 0.
    try:
        stats = mind.get_stats() if hasattr(mind, "get_stats") else {}
    except Exception:
        stats = {}
    nodes = stats.get("total_nodes") or benchmark_result.get("nodes")

    entry = {
        "project_name": project_name,
        "language": language or "Other",
        "nodes": nodes,
        "avg_wakeup_tokens": benchmark_result.get("wakeup_tokens"),
        "avg_query_tokens": benchmark_result.get("avg_query_tokens"),
        "avg_reduction_ratio": round(float(benchmark_result.get("avg_reduction_ratio", 0)), 1),
        "model": model or None,
        "date_submitted": date.today().isoformat(),
        "submitted_by": submitted_by or None,
        "verification_command": f"neuralmind benchmark {args.project_path} --json",
    }
    if repo_url:
        entry["repo_url"] = repo_url
    if notes:
        entry["notes"] = notes

    # Drop null fields — schema treats them as missing, not null.
    entry = {k: v for k, v in entry.items() if v is not None and v != ""}

    # Lead with the value, not the JSON.
    ratio = float(benchmark_result.get("avg_reduction_ratio", 0))
    avg_query_tokens = benchmark_result.get("avg_query_tokens") or 0
    naive_tokens_estimate = int(avg_query_tokens * ratio) if avg_query_tokens else 0

    # Rough per-query dollar cost at Claude 3.5 Sonnet input pricing.
    # The user can adjust if they run against a different model.
    sonnet_per_mtok = 3.0
    monthly_naive = naive_tokens_estimate / 1_000_000 * sonnet_per_mtok * 100 * 30
    monthly_nm = avg_query_tokens / 1_000_000 * sonnet_per_mtok * 100 * 30
    monthly_saved = monthly_naive - monthly_nm

    print()
    print("=" * 68)
    print("What you just proved on your code:")
    print("=" * 68)
    print(f"  Reduction ratio  :  {ratio:.1f}×  (on YOUR codebase, not a demo fixture)")
    print(f"  Tokens per query :  {avg_query_tokens:,}  (vs ~{naive_tokens_estimate:,} raw)")
    print(
        f"  Est. $ saved/mo  :  ~${monthly_saved:,.2f}  (Claude 3.5 Sonnet input, 100 queries/day)"
    )
    print("")
    print("  Different model or volume? Scale linearly: GPT-4o ≈ 5× Sonnet cost;")
    print("  Haiku ≈ 1/4. Ratio stays the same.")
    print("=" * 68)
    print()
    print("Shareable JSON (paste into Slack, docs, PRs, or the community leaderboard):")
    print("-" * 68)
    print(json.dumps(entry, indent=2))
    print("-" * 68)
    print()
    print("If you want to contribute this to the public community leaderboard")
    print("(entirely optional — NeuralMind never uploads anything automatically):")
    print(
        "  • Issue form  : https://github.com/dfrostar/neuralmind/issues/new?template=community-benchmark.yml"
    )
    print("  • Direct PR   : add to docs/community-benchmarks.json, then")
    print("                  python scripts/render_community_table.py --inject README.md")


def _prompt(label: str, default: str = "") -> str:
    """Interactive prompt. Returns default if stdin isn't a TTY."""
    if not sys.stdin.isatty():
        return default
    suffix = f" [{default}]" if default else ""
    try:
        response = input(f"{label}{suffix}: ").strip()
    except EOFError:
        return default
    return response or default


def _maybe_detect_repo_url(project_path: str) -> str | None:
    """Best-effort: read the origin URL from .git/config if present."""
    import subprocess

    try:
        out = subprocess.check_output(
            ["git", "-C", project_path, "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        url = out.decode().strip()
        # Normalize SSH → HTTPS for public display
        if url.startswith("git@github.com:"):
            url = "https://github.com/" + url[len("git@github.com:") :].removesuffix(".git")
        return url or None
    except Exception:
        return None


def cmd_search(args):
    mind = create_mind(args.project_path, auto_build=True)
    results = mind.search(args.query, n=args.n)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"Search: {args.query}")
        for i, r in enumerate(results, 1):
            meta = r.get("metadata", {})
            print(f"{i}. {meta.get('label', 'unknown')} (score: {r.get('score', 0):.2f})")
            print(f"   File: {meta.get('source_file', 'unknown')}")


def cmd_stats(args):
    client = _try_daemon()
    if client is not None:
        try:
            stats = client.stats(str(Path(args.project_path).resolve()))
            if not stats.get("error"):
                stats.setdefault("via", "daemon")
                if args.json:
                    print(json.dumps(stats, indent=2))
                else:
                    print(f"Project: {stats.get('project')}  (via daemon)")
                    print(f"Built: {stats.get('built')}")
                    if stats.get("built"):
                        print(f"Nodes: {stats.get('nodes', stats.get('total_nodes', 0))}")
                return
        except Exception:
            pass

    mind = NeuralMind(args.project_path)
    try:
        stats = mind.embedder.get_stats()
        stats["project"] = Path(args.project_path).name
        stats["built"] = stats.get("total_nodes", 0) > 0
    except Exception as e:
        stats = {
            "project": Path(args.project_path).name,
            "built": False,
            "error": str(e),
        }
    # Learned-memory contribution by namespace (PRD 4). Read straight from
    # the synapse store so it shows without a built index — but only when a
    # store already exists (stats must not create one as a side effect).
    try:
        from neuralmind.synapses import default_db_path

        if default_db_path(args.project_path).exists() and mind.synapses is not None:
            stats["synapses"] = mind.synapses.stats()
    except Exception:
        pass
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"Project: {stats.get('project')}")
        print(f"Built: {stats.get('built')}")
        if stats.get("built"):
            print(f"Nodes: {stats.get('total_nodes', 0)}")
        synapse_stats = stats.get("synapses") or {}
        by_namespace = synapse_stats.get("namespaces") or {}
        if by_namespace:
            print(f"Memory namespaces (active: {synapse_stats.get('namespace')}):")
            for ns in sorted(by_namespace):
                entry = by_namespace[ns]
                print(
                    f"  {ns}: {entry['edges']} edges (weight {entry['weight']:.2f}), "
                    f"{entry['transitions']} transitions"
                )


def cmd_metrics(args):
    """Show aggregated metrics summary from .neuralmind/metrics/ JSONL files.

    Wraps MetricsCollector.summarize() with CLI-friendly ASCII table output
    and optional JSON export.
    """
    project_path = Path(getattr(args, "project_path", ".")).resolve()
    days = getattr(args, "days", 7)
    collector = MetricsCollector(project_path)
    summary = collector.summarize(days=days, event_type="query")

    if getattr(args, "json", False):
        print(json.dumps(summary, indent=2))
        return

    if not summary or summary.get("n_events", 0) == 0:
        print(f"No metrics data for {project_path.name} (last {days} days)")
        print(f"Metrics dir: {collector.project_path}/.neuralmind/metrics/")
        print("Run some queries to populate metrics.")
        return

    print(f"NeuralMind metrics — {project_path.name} (last {days} days)")
    print()

    queries = summary.get("queries", {})
    builds = summary.get("builds", {})
    print(f"{'Metric':<30} {'Value':>12}")
    print("-" * 43)

    if queries:
        print(f"{'Queries':.<30} {queries.get('n_queries', 0):>12,}")
        print(f"{'Mean latency (ms)':.<30} {queries.get('mean_latency_ms', 0):>12,.2f}")
        print(f"{'Mean tokens/query':.<30} {queries.get('mean_tokens_used', 0):>12,.0f}")
        print(f"{'Mean retrieval reuse':.<30} {queries.get('mean_retrieval_reuse_rate', 0):>12.4f}")
        print(f"{'Mean synapses fired':.<30} {queries.get('mean_synapses_activated', 0):>12.1f}")
        calls = queries.get("sum_tool_calls", 0)
        successes = queries.get("sum_tool_successes", 0)
        success_pct = (successes / calls * 100) if calls > 0 else 0.0
        print(f"{'Tool success rate':.<30} {success_pct:>11.1f}%")
        print(f"{'Total tool calls':.<30} {calls:>12,}")

    if builds:
        print(f"{'Builds':.<30} {builds.get('n_builds', 0):>12,}")
        print(f"{'Mean build time (s)':.<30} {builds.get('mean_duration_s', 0):>12,.2f}")


def cmd_validate(args):
    """Validate the project's canonical IR and report any schema problems.

    Adapts ``graph.json`` into the versioned IR (or reads a persisted one),
    runs structural validation, and prints the contract version, adapter
    metadata, coverage, and any errors/warnings. ``--write`` (re)materializes
    the IR to ``.neuralmind/`` — the in-place migration path for a legacy
    project that predates the IR.
    """
    from neuralmind.core import validate_project

    result = validate_project(args.project_path, write=args.write)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("error"):
            print(f"validate: {result['error']}")
            sys.exit(1)
        val = result.get("validation", {})
        print(f"IR version:      {result.get('ir_version')}")
        print(f"Source backend:  {result.get('source_backend')}")
        schema = result.get("source_schema_version")
        if schema is not None:
            print(f"Source schema:   v{schema}")
        print(f"Coverage:        {result.get('coverage')}")
        print(
            f"Entities:        {result.get('nodes', 0)} nodes, "
            f"{result.get('edges', 0)} edges, {result.get('clusters', 0)} clusters"
        )
        kinds = result.get("node_kinds", {})
        if kinds:
            kind_str = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
            print(f"Node kinds:      {kind_str}")
        langs = result.get("languages", {})
        if langs:
            lang_str = ", ".join(f"{k}={v}" for k, v in sorted(langs.items()))
            print(f"Languages:       {lang_str}")
        print("-" * 60)
        if val.get("ok"):
            print(f"VALID — 0 errors, {val.get('warnings', 0)} warning(s).")
        else:
            print(
                f"INVALID — {val.get('errors', 0)} error(s), {val.get('warnings', 0)} warning(s)."
            )
        for issue in val.get("issues", []):
            marker = "[ERROR]" if issue["severity"] == "error" else "[warn ]"
            print(f"  {marker} {issue['code']}: {issue['message']}")
        if result.get("written_to"):
            print("-" * 60)
            print(f"IR written to {result['written_to']}")

    # Exit non-zero on a top-level error (e.g. no graph, unsupported IR version)
    # as well as a failed validation — otherwise `validate --json` would exit 0
    # in CI on a hard error, since those carry no "validation" block.
    if result.get("error") or not result.get("validation", {}).get("ok", True):
        sys.exit(1)


def cmd_doctor(args):
    """Diagnose a project's NeuralMind setup and print actionable fixes."""
    from neuralmind import doctor

    base_checks = doctor.run_diagnostics(args.project_path)
    # Tier 2 additional checks (license, self-hosted) — additive, never breaking.
    extra = []
    try:
        extra = _tier2_doctor_checks(args)
    except Exception:
        pass  # fail-open — don't break doctor if tier2 import fails
    checks = base_checks + extra
    status = doctor.overall_status(checks)

    if args.json:
        print(
            json.dumps(
                {"status": status, "checks": [c.to_dict() for c in checks]},
                indent=2,
            )
        )
    else:
        markers = {doctor.OK: "[ ok ]", doctor.WARN: "[warn]", doctor.FAIL: "[FAIL]"}
        print(f"NeuralMind doctor — {Path(args.project_path).resolve()}")
        print("=" * 60)
        for c in checks:
            print(f"  {markers.get(c.status, '[ ?? ]')} {c.name}: {c.detail}")
            if c.fix and c.status != doctor.OK:
                print(f"         -> {c.fix}")
        print("=" * 60)
        summary = {
            doctor.OK: "All checks passed.",
            doctor.WARN: "Up and running; optional pieces are missing (see above).",
            doctor.FAIL: "Setup incomplete — run the fixes above, then re-check.",
        }
        print(summary.get(status, ""))


def _tier2_doctor_checks(args) -> list:
    """Return extra Tier 2 doctor checks (license, governance, audit)."""
    from neuralmind import doctor

    checks: list = []
    try:
        from neuralmind.tier2 import cli as _tc  # noqa: F401
    except ImportError:
        return checks  # tier2 not installed

    from neuralmind.tier2.config import load_config
    from neuralmind.tier2.license import _ISSUER_PUBLIC_KEY_HEX, load_license

    config = load_config(getattr(args, "config_path", None))
    lic_path = Path(config.license_file)
    if not lic_path.exists():
        checks.append(
            doctor.Check(
                "Tier 2 license",
                doctor.WARN,
                f"no license at {lic_path}",
                fix="Run: neuralmind team license activate <key>",
            )
        )
    else:
        status = load_license(lic_path, _ISSUER_PUBLIC_KEY_HEX)
        if status == "VALID":
            checks.append(
                doctor.Check(
                    "Tier 2 license",
                    doctor.OK,
                    f"valid, {config.seats} seats",
                )
            )
        else:
            checks.append(
                doctor.Check(
                    "Tier 2 license",
                    doctor.WARN,
                    f"status: {status}",
                    fix="Run: neuralmind team license status",
                )
            )

    if config.self_hosted.enabled:
        from neuralmind.tier2.self_hosted import check_data_dir_health

        sh = check_data_dir_health(Path(config.self_hosted.data_dir))
        if sh["writable"]:
            checks.append(
                doctor.Check(
                    "Self-hosted data dir",
                    doctor.OK,
                    f"{sh['path']} (mode {sh['mode']})",
                )
            )
        else:
            checks.append(
                doctor.Check(
                    "Self-hosted data dir",
                    doctor.FAIL,
                    sh.get("error", "unwritable"),
                    fix="Run: neuralmind team self-hosted init",
                )
            )

    return checks


def cmd_eval(args):
    """Run the faithfulness eval: does NeuralMind's selected context contain
    more gold facts than a matched-budget naive baseline?

    Self-evaluates against the committed reference fixture + gold-fact set,
    which ship with the *source* repository (the ``evals/`` package), so this
    is a quality self-test like ``neuralmind benchmark`` — not a per-repo
    command. The A/B needs the retrieval stack + a built index; ``--selfcheck``
    validates the gold set and offline scorer with no heavy deps.
    """
    # --onboarding swaps in the E1.5 onboarding-lift eval (committed team memory
    # vs a cold agent); both ship in the source `evals/` package, not the wheel.
    pkg = "onboarding" if getattr(args, "onboarding", False) else "faithfulness"
    label = "onboarding-lift" if pkg == "onboarding" else "faithfulness"
    try:
        if pkg == "onboarding":
            from evals.onboarding import harness, runner
        else:
            from evals.faithfulness import harness, runner
    except ImportError:
        print(
            f"neuralmind eval runs against the {label} gold set that ships with "
            "the source repository (the `evals/` package), not the installed "
            f"wheel. Clone the repo and run `python -m evals.{pkg}.runner --run` "
            "from its root.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.selfcheck:
        sys.exit(runner.main(["--selfcheck"]))

    try:
        report = harness.run_and_report(args.project_path)
    except RuntimeError as exc:
        print(f"{label} A/B unavailable: {exc}", file=sys.stderr)
        print(
            "The A/B needs the retrieval stack + a built index. Use `--selfcheck` "
            "to validate the gold set + offline scorer only.",
            file=sys.stderr,
        )
        sys.exit(2)

    print(harness.render_json(report) if args.json else harness.render_markdown(report))


def cmd_next(args):
    """Show what typically follows a node (file path or node id) in the
    learned directional-transition graph."""
    mind = NeuralMind(args.project_path)
    store = mind.synapses
    # Default: the merged namespace view (active branch + personal + shared);
    # --namespace pins the read to one namespace at raw weights (PRD 4).
    namespaces = [args.namespace] if getattr(args, "namespace", None) else None
    ranked = store.next_likely(args.from_node, top_k=args.n, namespaces=namespaces) if store else []
    if args.json:
        print(
            json.dumps(
                {
                    "from_node": args.from_node,
                    "namespace": args.namespace or "merged",
                    "next": [{"to_node": to_node, "probability": prob} for to_node, prob in ranked],
                },
                indent=2,
            )
        )
        return
    if not ranked:
        print(f"No learned transitions from {args.from_node!r} yet.")
        return
    print(f"After {args.from_node}:")
    for to_node, prob in ranked:
        print(f"  {prob * 100:5.1f}%  {to_node}")


def cmd_impact(args):
    """Reverse-dependency ("blast radius") lookup: what depends on a symbol.

    Friendlier-named, richer-output sibling of `structural --blast-radius`
    (see :func:`cmd_structural`) — same underlying structural index, but each
    dependent row carries its hop and relation, not just its id.
    """
    from .core import create_mind

    mind = create_mind(args.project_path, auto_build=True)
    result = mind.impact(args.symbol, depth=args.depth)
    if args.json:
        print(json.dumps(result, indent=2))
        return

    if result["resolution"] == "none":
        print(f"No graph node matched '{args.symbol}'. Try `neuralmind build .` first.")
        sys.exit(1)

    tag = " (semantic match)" if result["resolution"] == "semantic" else ""
    print(f"Impact of {result['resolved_node']}{tag} — depth {args.depth}:")
    dependents = result["dependents"]
    if not dependents:
        print("  Nothing depends on it.")
        return
    labels = _structural_label(mind, [d["id"] for d in dependents])
    for dep in dependents:
        print(f"  h{dep['hop']}  {dep['relation']:14} {labels.get(dep['id'], dep['id'])}")
    print(f"\n{result['count']} dependent(s).")


def _emit_local_audit(
    mind: NeuralMind,
    category: str,
    action: str = "cmd",
    *,
    actor: str | None = None,
    status: str = "success",
    target: str,
) -> None:
    """Emit an audit event with per-user actor resolution."""
    mind._emit_audit(
        category, action, status=status, target=target or mind.project_path.name, actor=actor
    )


def cmd_audit_export(args):
    """Export audit events in JSONL or CEF for SIEM (B-Audit card)."""
    trail = AuditTrail(args.project_path)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            for line in trail.export(
                format=args.format,
                category=args.category,
                action=args.action,
                actor=args.actor,
                since=args.since,
                until=args.until,
            ):
                f.write(line + "\n")
        print(f"Exported {len(trail.read_events())} events → {args.output}")
    else:
        for line in trail.export(
            format=args.format,
            category=args.category,
            action=args.action,
            actor=args.actor,
            since=args.since,
            until=args.until,
        ):
            sys.stdout.write(line + "\n")


def cmd_audit_verify(args):
    """Verify audit log integrity — walk the hash chain."""
    trail = AuditTrail(args.project_path)
    result = trail.verify()
    if args.json:
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["ok"] else 1)
    if result["ok"]:
        print(f"✓ Audit trail integrity OK ({result['total']} events)")
    else:
        print(
            f"✗ Audit trail tampered at line {result['first_bad_line']} "
            f"({result['total']} events total)",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_memory(args):
    """Namespace-level controls over the learned synapse memory (PRD 4).

    ``inspect`` shows contribution by namespace, ``reset`` clears exactly one
    namespace (the project index and every other namespace are untouched),
    ``export``/``import`` move a namespace as a portable, versioned JSON
    bundle (the PRD 8 team-memory on-ramp). All four work without a built
    index — the synapse store is stdlib SQLite.
    """
    from neuralmind.ir import IRError, export_synapse_bundle, import_synapse_bundle
    from neuralmind.namespaces import resolve_namespace
    from neuralmind.synapses import SynapseStore, default_db_path

    db = default_db_path(args.project_path)
    if args.memory_cmd != "import" and not db.exists():
        print(f"No learned synapse memory at {db} yet.")
        if args.memory_cmd != "inspect":
            sys.exit(1)
        return
    active = resolve_namespace(args.project_path)
    store = SynapseStore(db, namespace=active)

    if args.memory_cmd == "inspect":
        stats = store.stats()
        namespaces = stats.get("namespaces", {})
        if args.namespace:
            namespaces = {k: v for k, v in namespaces.items() if k == args.namespace}
        result = {
            "db_path": stats["db_path"],
            "active_namespace": stats["namespace"],
            "schema_version": stats["schema_version"],
            "namespaces": namespaces,
        }
        if args.json:
            print(json.dumps(result, indent=2))
            return
        print(f"Synapse memory — {stats['db_path']}")
        print(f"Active namespace: {stats['namespace']}  (schema v{stats['schema_version']})")
        if not namespaces:
            target = f"namespace {args.namespace!r}" if args.namespace else "any namespace"
            print(f"No learned memory in {target} yet.")
            return
        print(f"{'Namespace':<24} {'Edges':>7} {'Weight':>9} {'Transitions':>12} {'Nodes':>7}")
        for ns in sorted(namespaces):
            entry = namespaces[ns]
            print(
                f"{ns:<24} {entry['edges']:>7} {entry['weight']:>9.2f} "
                f"{entry['transitions']:>12} {entry['nodes']:>7}"
            )
        return

    if args.memory_cmd == "reset":
        try:
            counts = store.clear_namespace(args.namespace)
        except ValueError as exc:
            print(f"Invalid namespace: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(counts, indent=2))
            return
        print(
            f"Cleared namespace {counts['namespace']!r}: {counts['edges']} edges, "
            f"{counts['transitions']} transitions, {counts['activations']} activations."
        )
        print("All other namespaces and the project index are untouched.")
        return

    if args.memory_cmd == "export":
        namespace = args.namespace or active
        bundle = export_synapse_bundle(store, namespace)
        payload = json.dumps(bundle, indent=2)
        if args.output:
            Path(args.output).write_text(payload + "\n", encoding="utf-8")
            print(
                f"Exported namespace {namespace!r} → {args.output} "
                f"({bundle['counts']['synapses']} synapses, "
                f"{bundle['counts']['transitions']} transitions)"
            )
        else:
            print(payload)
        return

    if args.memory_cmd == "import":
        try:
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"Could not read bundle {args.file}: {exc}", file=sys.stderr)
            sys.exit(1)
        try:
            result = import_synapse_bundle(store, data, namespace=args.namespace)
        except IRError as exc:
            print(f"Import rejected: {exc}", file=sys.stderr)
            sys.exit(1)
        except ValueError as exc:
            print(f"Invalid namespace: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(result, indent=2))
            return
        print(
            f"Imported {result['synapses']} synapses and {result['transitions']} "
            f"transitions into namespace {result['namespace']!r}."
        )
        print("Re-importing the same bundle is idempotent (weights merge by MAX).")
        return

    if args.memory_cmd == "publish":
        from neuralmind.team_memory import publish_team_memory

        summary = publish_team_memory(args.project_path, store)
        if args.json:
            print(json.dumps(summary, indent=2))
            return
        c = summary["counts"]
        print(
            f"Published team memory → {summary['path']} "
            f"({c['synapses']} synapses, {c['transitions']} transitions)."
        )
        print(
            "Commit it so teammates inherit it automatically:\n"
            f"  git add {summary['path']} && git commit -m 'chore: publish neuralmind team memory'"
        )
        print(
            "A teammate's agent imports it once into the `shared` namespace on its "
            "next session/build. Measure the onboarding lift with "
            "`neuralmind eval --onboarding`."
        )
        return

    if args.memory_cmd == "review-list":
        from neuralmind.team_memory import _load_pending_review

        pending = _load_pending_review(store)
        if args.json:
            print(json.dumps({"pending": pending, "count": len(pending)}, indent=2))
            return
        if not pending:
            print("No edges pending review.")
            return
        print(f"Pending review ({len(pending)} edges):")
        for entry in pending:
            print(
                f"  [{entry['score']:.3f}] {entry['source']} → {entry['target']} "
                f"({entry['reviewer_hint']})"
            )
        return

    if args.memory_cmd == "review-approve":
        from neuralmind.team_memory import (
            _load_pending_review,
            _save_pending_review,
        )

        pending = _load_pending_review(store)
        before = len(pending)
        remaining = [
            e for e in pending if not (e["source"] == args.source and e["target"] == args.target)
        ]
        if len(remaining) == before:
            print(f"Edge {args.source} → {args.target} not found in pending review queue.")
            sys.exit(1)
        _save_pending_review(store, remaining)

        # Promote to shared namespace
        promoted = store.import_edges([(args.source, args.target, 1.0, 1)], namespace="shared")
        if args.json:
            print(json.dumps({"approved": True, "promoted": promoted}, indent=2))
            return
        print(f"Approved {args.source} → {args.target}, promoted to shared namespace.")
        return

    if args.memory_cmd == "review-reject":
        from neuralmind.team_memory import _load_pending_review, _save_pending_review

        pending = _load_pending_review(store)
        before = len(pending)
        remaining = [
            e for e in pending if not (e["source"] == args.source and e["target"] == args.target)
        ]
        if len(remaining) == before:
            print(f"Edge {args.source} → {args.target} not found in pending review queue.")
            sys.exit(1)
        _save_pending_review(store, remaining)
        if args.json:
            print(json.dumps({"rejected": True}, indent=2))
            return
        print(f"Rejected {args.source} → {args.target}, removed from review queue.")
        return

    if args.memory_cmd == "staleness-scan":
        from neuralmind.team_staleness import TeamStalenessDetector

        detector = TeamStalenessDetector()
        stale = detector.detect_stale_in_store(store, namespace=args.namespace or "shared")
        if args.json:
            print(
                json.dumps({"stale": [e.to_dict() for e in stale], "count": len(stale)}, indent=2)
            )
            return
        if not stale:
            print("No stale edges detected.")
            return
        print(f"Stale edges ({len(stale)}):")
        for edge in stale:
            print(
                f"  [{edge.score:.3f}] {edge.source} → {edge.target} "
                f"({edge.days_since_last:.0f}d / {edge.age_days:.0f}d)"
            )
        return

    if args.memory_cmd == "staleness-run":
        from neuralmind.team_staleness import TeamStalenessDetector

        detector = TeamStalenessDetector()
        updated, stale = detector.run_staleness_pass(store, namespace=args.namespace or "shared")
        if args.json:
            print(json.dumps({"updated": updated, "stale_count": len(stale)}, indent=2))
            return
        print(f"Staleness pass complete: {updated} edges decayed out of {len(stale)} stale.")
        return


def _resolve_project_path(file_path: Path, args) -> Path | None:
    """Resolve the project root from args or by walking up from file_path.

    Returns None if no project marker (.neuralmind/, .git) is found.
    """
    explicit_project = getattr(args, "project_path", None)
    if explicit_project:
        return Path(explicit_project).resolve()

    cwd = Path.cwd()
    if (
        (cwd / ".neuralmind" / "index_ir.json").exists()
        or (cwd / ".neuralmind" / "synapses.db").exists()
        or (cwd / ".git").exists()
    ):
        return cwd

    # Walk up from file to find project markers
    project_path = file_path.parent if file_path.is_file() else file_path
    while project_path.parent != project_path:
        if (
            (project_path / ".neuralmind" / "index_ir.json").exists()
            or (project_path / ".neuralmind" / "synapses.db").exists()
            or (project_path / ".git").exists()
        ):
            return project_path
        project_path = project_path.parent

    return None


def _scan_files_for_ingest(dir_path: Path) -> list[Path]:
    """Scan a directory for supported files, returning a sorted list.

    Supported: .pdf, .md, .markdown, .mkd, .txt, .text, .rst, .org
    Skips symlinks. Max depth: 10.
    """
    supported_exts = {".pdf", ".md", ".markdown", ".mkd", ".txt", ".text", ".rst", ".org"}
    files: list[Path] = []

    def _walk(path: Path, depth: int = 0):
        if depth > 10:
            return
        for item in sorted(path.iterdir()):
            if item.is_symlink():
                continue
            if item.is_dir():
                _walk(item, depth + 1)
            elif item.is_file() and item.suffix.lower() in supported_exts:
                files.append(item)

    _walk(dir_path)
    return files


def cmd_ingest_content(args):
    """Ingest a directory of Markdown chapters into a pure content index.

    Optimized for book/content benchmarking: ingests only .md/.txt files,
    chunks them with configurable size/overlap, and builds a pure content
    index (no code nodes). Reports files ingested, total chunks, node count.
    """
    import time

    from neuralmind.core import create_mind
    from neuralmind.document_ingestion import parse_document

    content_path = Path(args.content_path).resolve()
    if not content_path.exists():
        print(f"Error: path not found: {content_path}", file=sys.stderr)
        sys.exit(1)

    quiet = getattr(args, "quiet", False)
    chunk_size = args.chunk_size
    overlap = args.overlap

    # Collect files
    if content_path.is_file():
        files_to_ingest = [content_path]
    else:
        # Only .md and .txt for content indexing
        files_to_ingest = _scan_files_for_ingest(content_path)
        files_to_ingest = [
            f for f in files_to_ingest if f.suffix.lower() in (".md", ".markdown", ".mkd", ".txt", ".text")
        ]

    if not files_to_ingest:
        if not quiet:
            print("No supported content files found (.md, .txt).")
        sys.exit(0)

    # Resolve project root
    project_path = _resolve_project_path(content_path, args)
    if project_path is None:
        # Use content_path's parent as project if it's a directory
        project_path = content_path.parent if content_path.is_dir() else content_path.parent

    if not quiet:
        print(f"Content indexer: {len(files_to_ingest)} file(s) from {content_path}")
        print(f"Chunk size: {chunk_size}, overlap: {overlap}")
        print(f"Project: {project_path}")
        print()

    # Create a seed Python file if the project has no code files (required for build)
    seed_file = project_path / "_content_seed.py"
    if not any(project_path.rglob("*.py")):
        seed_file.write_text("# Auto-generated seed for content indexing\ndef _content_seed():\n    pass\n")

    mind = create_mind(str(project_path), auto_build=True)
    if not mind._built:
        print("Error: failed to build NeuralMind index.", file=sys.stderr)
        sys.exit(1)

    total_nodes = 0
    total_chunks = 0
    total_embed_time = 0.0
    errors: list[tuple[str, str]] = []
    wall_start = time.time()

    for idx, fpath in enumerate(files_to_ingest, 1):
        if not quiet and len(files_to_ingest) > 1:
            rel = fpath.relative_to(content_path) if content_path.is_dir() else fpath.name
            print(f"  [{idx}/{len(files_to_ingest)}] {rel}...", end="", flush=True)

        try:
            content_nodes = [
                n.to_graph_node()
                for n in parse_document(
                    fpath,
                    root=project_path,
                    content_type="auto",
                    chunk_size=chunk_size,
                    overlap=overlap,
                )
            ]
            if not content_nodes:
                errors.append((str(fpath), "No content extracted"))
                if not quiet and len(files_to_ingest) > 1:
                    print(" no content")
                continue

            # Sync to embedder nodes list (avoid duplicates)
            existing_ids = {n.get("id", "") for n in mind.embedder.nodes}
            new_nodes = [cn for cn in content_nodes if cn.get("id", "") not in existing_ids]
            mind.embedder.nodes.extend(new_nodes)

            # Embed
            embed_start = time.time()
            stats = mind.embedder.embed_content(new_nodes)
            embed_elapsed = time.time() - embed_start

            n = len(new_nodes) if new_nodes else len(content_nodes)
            total_nodes += n
            total_chunks += len(content_nodes)
            total_embed_time += embed_elapsed

            if not quiet and len(files_to_ingest) > 1:
                print(f" {n} node(s)")

        except (ValueError, RuntimeError) as e:
            errors.append((str(fpath), str(e)))
            if not quiet:
                if len(files_to_ingest) > 1:
                    print(" ERROR")
                    print(f"    {e}")
                else:
                    print(f"Error: {e}", file=sys.stderr)
        except Exception as e:
            errors.append((str(fpath), f"{type(e).__name__}: {e}"))
            if not quiet:
                if len(files_to_ingest) > 1:
                    print(" ERROR")
                    print(f"    {type(e).__name__}: {e}")
                else:
                    print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)

    wall_time = time.time() - wall_start

    if args.json:
        output = {
            "success": len(errors) == 0,
            "files_processed": len(files_to_ingest),
            "total_chunks": total_chunks,
            "total_nodes": total_nodes,
            "wall_time_seconds": round(wall_time, 2),
            "embed_time_seconds": round(total_embed_time, 2),
            "errors": [{"file": str(f), "error": e} for f, e in errors],
        }
        print(json.dumps(output, indent=2))
        if errors:
            sys.exit(1)
        return

    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for f, err in errors[:10]:
            print(f"  - {Path(f).name}: {err}", file=sys.stderr)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more", file=sys.stderr)
        sys.exit(1)

    if not quiet:
        print()
        print(f"Ingested {len(files_to_ingest)} file(s) → {total_chunks} chunks → {total_nodes} nodes")
        print(f"Wall time: {wall_time:.1f}s | Embed time: {total_embed_time:.2f}s")


def cmd_ingest(args):
    """Ingest documents (PDF/Markdown/text) into the knowledge graph.

    `learn` is an alias for this command. Supports single files and
    directories. Directories are scanned recursively for .pdf, .md,
    .txt, .rst, and .org files.

    Progress is reported per-file for directories. Errors on individual
    files are collected and reported at the end without stopping the
    batch.
    """
    import time

    from neuralmind.content_node import ContentNode
    from neuralmind.core import create_mind
    from neuralmind.document_ingestion import parse_document

    # Parse business context from JSON input
    business_types = {"decision", "meeting", "sop", "policy"}
    is_business_type = args.type in business_types

    file_path = Path(args.file_path).resolve() if args.file_path != "." else Path.cwd()
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    dry_run = getattr(args, "dry_run", False)
    quiet = getattr(args, "quiet", False)
    no_recursive = getattr(args, "no_recursive", False)

    # Collect files to ingest
    if file_path.is_file():
        files_to_ingest = [file_path]
    else:
        files_to_ingest = _scan_files_for_ingest(file_path)
        if no_recursive:
            files_to_ingest = [f for f in files_to_ingest if f.parent == file_path]

    if not files_to_ingest:
        if not quiet:
            print("No supported files found to ingest.")
        sys.exit(0)

    # Business context: JSON file input via --type decision|meeting|sop|policy
    if is_business_type:
        total_nodes = 0
        total_embed_time = 0.0
        errors: list[tuple[str, str]] = []
        wall_start = time.time()

        # Resolve project root
        project_path = _resolve_project_path(file_path, args)
        if project_path is None:
            print(
                "Error: no NeuralMind project found. Run 'neuralmind ingest' from your "
                "project directory (where 'neuralmind build .' was run).",
                file=sys.stderr,
            )
            sys.exit(1)

        mind = create_mind(str(project_path), auto_build=True)
        if not mind._built:
            print(
                "Error: failed to build NeuralMind index. Run 'neuralmind build .' first.",
                file=sys.stderr,
            )
            sys.exit(1)

        for idx, fpath in enumerate(files_to_ingest, 1):
            if not quiet and len(files_to_ingest) > 1:
                rel = fpath.relative_to(file_path)
                print(f"  [{idx}/{len(files_to_ingest)}] {rel}...", end="", flush=True)

            try:
                with open(fpath, encoding="utf-8") as fh:
                    data = json.load(fh)

                # Support both single object and array of objects
                items = data if isinstance(data, list) else [data]
                content_nodes: list[dict] = []

                for item in items:
                    if args.type == "decision":
                        content_nodes.append(ContentNode.from_decision(item).to_graph_node())
                    elif args.type == "meeting":
                        content_nodes.append(ContentNode.from_meeting_note(item).to_graph_node())
                    elif args.type == "sop":
                        content_nodes.append(ContentNode.from_sop(item).to_graph_node())
                    elif args.type == "policy":
                        content_nodes.append(ContentNode.from_policy(item).to_graph_node())

                if not content_nodes:
                    errors.append((str(fpath), "No content extracted"))
                    if not quiet and len(files_to_ingest) > 1:
                        print(" no content")
                    continue

                # Sync to embedder nodes list
                existing_ids = {n.get("id", "") for n in mind.embedder.nodes}
                new_nodes = [cn for cn in content_nodes if cn.get("id", "") not in existing_ids]
                mind.embedder.nodes.extend(new_nodes)

                embed_start = time.time()
                stats = mind.embedder.embed_content(new_nodes)
                embed_elapsed = time.time() - embed_start

                n = len(new_nodes) if new_nodes else len(content_nodes)
                total_nodes += n
                total_embed_time += embed_elapsed

                if not quiet and len(files_to_ingest) > 1:
                    added = stats.get("added", 0)
                    skipped = stats.get("skipped", 0)
                    print(f" {n} node(s) (+{added}, ~{skipped})")

            except (ValueError, RuntimeError, json.JSONDecodeError) as e:
                errors.append((str(fpath), str(e)))
                if not quiet:
                    if len(files_to_ingest) > 1:
                        print(" ERROR")
                        print(f"    {e}")
                    else:
                        print(f"Error: {e}", file=sys.stderr)
            except Exception as e:
                errors.append((str(fpath), f"{type(e).__name__}: {e}"))
                if not quiet:
                    if len(files_to_ingest) > 1:
                        print(" ERROR")
                        print(f"    {type(e).__name__}: {e}")
                    else:
                        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)

        wall_time = time.time() - wall_start

        if args.json:
            output = {
                "success": len(errors) == 0,
                "files_processed": len(files_to_ingest),
                "total_nodes": total_nodes,
                "wall_time_seconds": round(wall_time, 2),
                "errors": [{"file": str(f), "error": e} for f, e in errors],
            }
            print(json.dumps(output, indent=2))
            if errors:
                sys.exit(1)
            return

        if errors:
            print(f"\n{len(errors)} error(s):", file=sys.stderr)
            for f, err in errors[:10]:
                print(f"  - {Path(f).name}: {err}", file=sys.stderr)
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more", file=sys.stderr)
            sys.exit(1)

        if not quiet:
            print(
                f"Ingested {total_nodes} content node(s) from {len(files_to_ingest)} file(s) in {wall_time:.1f}s"
            )
            print(f"  Embed time: {total_embed_time:.2f}s")
        return

    # Resolve project root
    project_path = _resolve_project_path(file_path, args)
    if project_path is None:
        print(
            "Error: no NeuralMind project found. Run 'neuralmind ingest' from your "
            "project directory (where 'neuralmind build .' was run).",
            file=sys.stderr,
        )
        sys.exit(1)

    if dry_run:
        print(f"Would ingest {len(files_to_ingest)} file(s):")
        for f in files_to_ingest:
            rel = f.relative_to(file_path) if file_path.is_dir() else f.name
            print(f"  {rel}")
        return

    if not quiet:
        print(f"Ingesting {len(files_to_ingest)} file(s) from {file_path}")

    mind = create_mind(str(project_path), auto_build=True)
    if not mind._built:
        print(
            "Error: failed to build NeuralMind index. Run 'neuralmind build .' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    total_nodes = 0
    total_embed_time = 0.0
    errors: list[tuple[str, str]] = []
    wall_start = time.time()

    for idx, fpath in enumerate(files_to_ingest, 1):
        if not quiet and len(files_to_ingest) > 1:
            rel = fpath.relative_to(file_path)
            print(f"  [{idx}/{len(files_to_ingest)}] {rel}...", end="", flush=True)

        try:
            content_nodes = [
                n.to_graph_node()
                for n in parse_document(fpath, root=project_path, content_type=args.type)
            ]
            if not content_nodes:
                errors.append((str(fpath), "No content extracted"))
                if not quiet and len(files_to_ingest) > 1:
                    print(" no content")
                continue

            # Sync to embedder nodes list (avoid duplicates)
            existing_ids = {n.get("id", "") for n in mind.embedder.nodes}
            new_nodes = [cn for cn in content_nodes if cn.get("id", "") not in existing_ids]
            mind.embedder.nodes.extend(new_nodes)

            # Embed
            embed_start = time.time()
            stats = mind.embedder.embed_content(new_nodes)
            embed_elapsed = time.time() - embed_start

            # Count actually-added nodes from embed stats (M1 fix: was overstating)
            added = stats.get("added", 0)
            n = added if added > 0 else len(new_nodes) if new_nodes else len(content_nodes)
            total_nodes += n
            total_chunks += len(content_nodes)
            total_embed_time += embed_elapsed

            if not quiet and len(files_to_ingest) > 1:
                skipped = stats.get("skipped", 0)
                print(f" {n} node(s) (+{added}, ~{skipped})")
        except (ValueError, RuntimeError) as e:
            errors.append((str(fpath), str(e)))
            if not quiet:
                if len(files_to_ingest) > 1:
                    print(" ERROR")
                    print(f"    {e}")
                else:
                    print(f"Error: {e}", file=sys.stderr)
        except Exception as e:
            errors.append((str(fpath), f"{type(e).__name__}: {e}"))
            if not quiet:
                if len(files_to_ingest) > 1:
                    print(" ERROR")
                    print(f"    {type(e).__name__}: {e}")
                else:
                    print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)

    # Seed synapse edges from documentation (one-time, gated on env vars)
    synapse_doc_edges = 0
    if mind.enable_synapses:
        try:
            store = mind.synapses
            if store is not None:
                synapse_doc_edges = store.seed_from_documentation(project_path)
        except Exception:
            pass

    wall_time = time.time() - wall_start

    if args.json:
        output = {
            "success": len(errors) == 0,
            "files_processed": len(files_to_ingest),
            "total_nodes": total_nodes,
            "wall_time_seconds": round(wall_time, 2),
            "synapse_doc_edges": synapse_doc_edges,
            "errors": [{"file": str(f), "error": e} for f, e in errors],
        }
        print(json.dumps(output, indent=2))
        if errors:
            sys.exit(1)
        return

    if errors:
        # Always report errors and exit non-zero, even with --quiet
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for f, err in errors[:10]:
            print(f"  - {Path(f).name}: {err}", file=sys.stderr)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more", file=sys.stderr)
        sys.exit(1)

    if not quiet:
        if total_nodes > 0:
            print(
                f"Ingested {total_nodes} content node(s) from "
                f"{len(files_to_ingest)} file(s) in {wall_time:.1f}s"
            )
        if synapse_doc_edges > 0:
            print(f"  Synapse doc edges: {synapse_doc_edges}")


def cmd_learn(args):
    """Alias for `neuralmind ingest`."""
    return cmd_ingest(args)


def cmd_self_improve_status(args):
    """Show the self-improvement engine's current selector tuning state."""
    from .self_improve import selector_report

    project_path = Path(args.project_path).resolve()
    report = selector_report(project_path)
    autotune_on = os.environ.get("NEURALMIND_SELECTOR_AUTOTUNE") == "1"

    if args.json:
        report["autotune_enabled"] = autotune_on
        print(json.dumps(report, indent=2))
        return

    print(f"Project: {project_path.name}")
    print(f"Autotune enabled: {autotune_on} (NEURALMIND_SELECTOR_AUTOTUNE)")
    print(f"l2_recall_k: {report['l2_recall_k']}")
    print(f"Last tuned at: {report['l2_recall_k_tuned_at'] or 'never'}")
    print(f"Query events logged: {report['total_events']} (warmed up: {report['warmed_up']})")
    print(f"Query events in tuning window: {report['windowed_events']}")
    print(f"re_query_rate: {report['re_query_rate']:.3f}")


def cmd_skeleton(args):
    """Return a graph-backed compact view of a file."""
    from .core import create_mind

    mind = create_mind(args.project_path, auto_build=True)
    skeleton = mind.skeleton(args.file_path)
    if not skeleton:
        if args.json:
            print(json.dumps({"error": "file not indexed", "file": args.file_path}))
        else:
            print(f"No graph nodes found for {args.file_path}")
            print("Build the graph first: neuralmind build .")
        sys.exit(1)
    if args.json:
        print(
            json.dumps(
                {"file": args.file_path, "skeleton": skeleton, "chars": len(skeleton)}, indent=2
            )
        )
    else:
        print(skeleton)


def _structural_label(mind, node_ids):
    """Map node ids → 'label — source_file:Lnn' strings for display.

    Best-effort: falls back to the raw node id when the embedder can't
    resolve metadata (e.g. an id present in the graph but not embedded).
    """
    labels: dict[str, str] = {}
    get_nodes_by_ids = getattr(mind.embedder, "get_nodes_by_ids", None)
    if callable(get_nodes_by_ids):
        try:
            for node in get_nodes_by_ids(list(node_ids)):
                meta = node.get("metadata", {})
                label = meta.get("label", node.get("id"))
                src = meta.get("source_file", "")
                if src:
                    src = src.replace("\\", "/").split("/")[-1]
                labels[node.get("id")] = f"{label} — {src}" if src else str(label)
        except Exception:
            pass
    return {nid: labels.get(nid, nid) for nid in node_ids}


def cmd_structural(args):
    """Show how a symbol is wired into the codebase from the static code graph.

    Answers "what calls / inherits / imports this?" — the precise structural
    relationships graphify extracts, distinct from the learned synapse graph.
    """
    from .core import create_mind

    mind = create_mind(args.project_path, auto_build=True)

    if getattr(args, "blast_radius", False):
        result = mind.blast_radius(args.symbol, depth=args.depth)
        ids = result.get("blast_radius", [])
        if args.json:
            print(json.dumps(result, indent=2))
            return
        node_id = result.get("node_id")
        if not node_id:
            print(f"No graph node matched '{args.symbol}'. Try `neuralmind build .` first.")
            sys.exit(1)
        print(f"## Blast radius of {node_id} (depth {args.depth}) — {len(ids)} symbols\n")
        if not ids:
            print("Nothing depends on this symbol in the static graph.")
            return
        for text in _structural_label(mind, ids).values():
            print(f"- {text}")
        return

    relations = None
    if getattr(args, "relation", None) and args.relation != "all":
        relations = [args.relation]
    elif getattr(args, "relation", None) == "all":
        relations = ["all"]

    result = mind.structural_neighbors(args.symbol, relations=relations)
    if args.json:
        print(json.dumps(result, indent=2))
        return

    node_id = result.get("node_id")
    neighbors = result.get("neighbors", {})
    if not node_id:
        print(f"No graph node matched '{args.symbol}'. Try `neuralmind build .` first.")
        sys.exit(1)
    print(f"## Structural neighbors of {node_id}\n")
    if not neighbors:
        print("No structural edges for this symbol (leaf node, or thin extractor).")
        return
    all_ids = [nid for ids in neighbors.values() for nid in ids]
    labels = _structural_label(mind, all_ids)
    view_titles = {
        "callers": "Callers",
        "callees": "Callees",
        "bases": "Base classes",
        "subclasses": "Subclasses",
        "importers": "Importers",
        "imports": "Imports",
        "members": "Members",
        "container": "Container",
        "implementers": "Implementers",
        "interfaces": "Interfaces",
        "uses": "Uses",
        "used_by": "Used by",
    }
    for view, ids in neighbors.items():
        print(f"### {view_titles.get(view, view.title())} ({len(ids)})")
        for nid in ids:
            print(f"- {labels.get(nid, nid)}")
        print()


def cmd_watch(args):
    """Run the file watcher → synapse co-activation daemon in the foreground.

    Edits to project files are debounced into batches and fed to the
    synapse store, so the brain keeps learning even when no query runs.
    Periodic decay ticks age unused weights without manual intervention.
    Stops cleanly on Ctrl-C.
    """
    import signal
    import time

    from neuralmind.watcher import FileActivityWatcher

    project_path = args.project_path or "."
    path = Path(project_path).resolve()
    if not path.is_dir():
        print(f"watch failed: not a directory: {project_path}")
        sys.exit(1)

    quiet = bool(getattr(args, "quiet", False))
    decay_interval = float(getattr(args, "decay_interval", 600))
    debounce = float(getattr(args, "debounce", 0.75))
    reindex = bool(getattr(args, "reindex", False))

    if not quiet:
        print(f"NeuralMind watcher starting for: {path}")
        print(f"  debounce: {debounce}s   decay every: {decay_interval}s")
        if reindex:
            print("  incremental re-index: on (edited files re-parsed into the graph)")
        print("  Ctrl-C to stop.\n")

    mind = NeuralMind(str(path))
    if mind.synapses is None:
        print("watch failed: synapses are disabled for this NeuralMind instance.")
        sys.exit(1)

    try:
        mind.build()
    except Exception as exc:
        if not quiet:
            print(f"  warning: build skipped ({exc}); watcher will still record edits.")

    # Bridge synapse + file events into the project's JSONL log so that
    # a separate `neuralmind serve` process picks them up and renders
    # pulse rings on the canvas in real time. Best-effort: a missing
    # `.neuralmind/` dir or NEURALMIND_EVENT_LOG=0 just leaves the
    # daemon silent on the cross-process channel.
    try:
        from neuralmind.event_bus import configure_event_log
        from neuralmind.event_log import (
            EventLogWriter,
            default_log_path,
            event_log_enabled,
        )

        if event_log_enabled():
            log_path = default_log_path(path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            configure_event_log(EventLogWriter(log_path))
    except Exception:
        pass

    activations_total = 0

    def on_batch(paths: list[str]) -> None:
        nonlocal activations_total
        # Surface the raw file edits to the cross-process bridge first
        # so the server can echo them even if no synapse pair fires.
        try:
            from neuralmind.event_bus import publish as _publish

            _publish("file", {"paths": list(paths), "count": len(paths)})
        except Exception:
            pass
        try:
            pairs = mind.activate_files(paths)
        except Exception:
            pairs = 0
        activations_total += pairs
        if not quiet and pairs:
            print(f"  + {len(paths)} file(s) → {pairs} synapse pair(s) reinforced")
        # Incremental re-index: re-parse just the edited files into the built-in
        # graph + re-embed only their nodes. Opt-in (--reindex) since it needs
        # the retrieval stack in the watch process.
        if reindex:
            try:
                stats = mind.update_files(paths)
            except Exception as exc:  # pragma: no cover - defensive
                stats = {"success": False, "error": str(exc)}
            if not quiet and stats.get("success") and stats.get("files_reparsed"):
                print(
                    f"  ↻ re-indexed {stats['files_reparsed']} file(s): "
                    f"{stats.get('embedded', 0)} node(s) re-embedded, "
                    f"{stats.get('skipped', 0)} unchanged, {stats.get('pruned', 0)} pruned"
                )

    def on_deleted(paths: list[str]) -> None:
        targeted = 0
        try:
            targeted = mind.deactivate_files(paths)
        except Exception:
            pass
        if not quiet and targeted:
            print(f"  - {len(paths)} file(s) deleted → {targeted} node(s) fast-decayed")

    watcher = FileActivityWatcher(path, on_batch, debounce=debounce, deletion_callback=on_deleted)
    watcher.start()

    stop = {"flag": False}

    def _shutdown(signum, _frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    last_decay = time.time()
    try:
        while not stop["flag"]:
            time.sleep(0.5)
            if decay_interval > 0 and time.time() - last_decay >= decay_interval:
                try:
                    mind.synapses.decay()
                except Exception:
                    pass
                last_decay = time.time()
                if not quiet:
                    stats = mind.synapses.stats()
                    print(
                        f"  ~ decay tick — edges={stats['edges']}, "
                        f"ltp={stats['ltp_edges']}, total_weight={stats['total_weight']:.2f}"
                    )
    finally:
        watcher.stop()
        if not quiet:
            print(f"\nWatcher stopped. Reinforced {activations_total} synapse pair(s) total.")


def cmd_daemon(args):
    """Manage the local NeuralMind daemon (PRD 5, experimental).

    The daemon holds project state warm so repeated queries skip cold backend
    init. CLI read commands prefer it automatically when it's running; set
    NEURALMIND_NO_DAEMON=1 to force direct mode.
    """
    import subprocess
    import time

    from neuralmind import daemon as daemon_mod
    from neuralmind.daemon_client import connect

    action = args.action

    if action == "status":
        client = connect()
        if client is None:
            print("daemon: not running")
            sys.exit(3)
        health = client.health()
        if args.json:
            print(json.dumps(health, indent=2))
        else:
            print(f"daemon: running (pid {health.get('pid')}, v{health.get('version')})")
            print(f"  uptime: {health.get('uptime_seconds')}s")
            print(f"  projects warm: {len(health.get('projects', []))}")
            print(f"  jobs active: {health.get('jobs_active', 0)}")
        return

    if action == "stop":
        client = connect()
        if client is None:
            print("daemon: not running")
            return
        try:
            client.shutdown()
        except Exception:
            pass
        # Confirm it actually went away; clear stale discovery otherwise.
        for _ in range(20):
            if connect(ping=True) is None:
                break
            time.sleep(0.1)
        daemon_mod.clear_discovery()
        print("daemon: stopped")
        return

    if action in ("start", "restart"):
        if action == "restart":
            existing = connect()
            if existing is not None:
                try:
                    existing.shutdown()
                except Exception:
                    pass
                time.sleep(0.3)
                daemon_mod.clear_discovery()
        if connect() is not None:
            print("daemon: already running")
            return
        if args.foreground:
            daemon_mod.serve(host=args.host, port=args.port)
            return
        # Detached background process; it writes discovery once bound.
        daemon_mod.clear_discovery()
        log_dir = Path.home() / ".neuralmind"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = open(log_dir / "daemon.log", "ab")  # noqa: SIM115 - lifetime is the child's
        cmd = [
            sys.executable,
            "-m",
            "neuralmind.daemon",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]
        subprocess.Popen(cmd, stdout=log, stderr=log, start_new_session=True)
        for _ in range(50):  # up to ~5s for it to come up
            client = connect()
            if client is not None:
                health = client.health()
                print(
                    f"daemon: started (pid {health.get('pid')}) on port "
                    f"{daemon_mod.read_discovery().get('port')}"
                )
                return
            time.sleep(0.1)
        print("daemon: failed to start (see ~/.neuralmind/daemon.log)")
        sys.exit(1)


def cmd_serve(args):
    """Start the local graph-view UI server.

    Builds the index (writes/updates ``graphify-out/neuralmind_db/`` the
    same way ``neuralmind build`` does), then serves an Obsidian-style
    force-directed graph of the codebase (structural edges + learned
    synapse overlay) with backlinks, local-graph focus, a community
    browser, and semantic quick-switch search. The HTTP handlers
    themselves are read-only.
    """
    from neuralmind.server import serve

    project_path = args.project_path or "."
    path = Path(project_path)
    if not path.is_dir():
        print(f"serve failed: not a directory: {project_path}")
        sys.exit(1)
    try:
        serve(
            str(path),
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
            auth=not args.no_auth,
            editor=args.editor,
        )
    except RuntimeError as exc:
        print(f"serve failed: {exc}")
        sys.exit(1)
    except OSError as exc:
        print(f"serve failed: could not bind {args.host}:{args.port} ({exc})")
        sys.exit(1)


def cmd_demo(args):
    """Run the bundled 30-second demo.

    Copies the bundled sample project (with pre-built graph.json) to a
    temp directory, builds the vector index, and runs three pre-canned
    questions against it. Designed to work right after
    ``pip install neuralmind`` — no git checkout, no graphify install,
    no manual setup needed.
    """
    import shutil
    import tempfile
    from importlib import resources

    from neuralmind import _demo_report
    from neuralmind.core import NeuralMind

    # Locate the bundled fixture inside the wheel via importlib.resources.
    # ``files()`` returns a Traversable; we materialize it to a real
    # directory on disk because ChromaDB and the embedder both expect a
    # writable filesystem path (zipped wheels would break otherwise).
    try:
        bundle_root = resources.files("neuralmind") / "demo_data" / "sample_project"
    except (ModuleNotFoundError, AttributeError) as exc:
        print(f"demo failed: bundled demo data not found ({exc}).", file=sys.stderr)
        sys.exit(1)

    if not (bundle_root / "graphify-out" / "graph.json").is_file():
        print(
            "demo failed: bundled demo data is missing graphify-out/graph.json. "
            "Reinstall neuralmind to restore it.",
            file=sys.stderr,
        )
        sys.exit(1)

    keep = bool(getattr(args, "keep", False))
    workdir = tempfile.mkdtemp(prefix="neuralmind-demo-")
    fixture_dir = Path(workdir) / "sample_project"

    try:
        # importlib.resources.as_file gives us a real path even if the
        # package was installed from a zip. shutil.copytree then makes a
        # writable working copy so the build doesn't pollute site-packages.
        with resources.as_file(bundle_root) as src:
            shutil.copytree(src, fixture_dir)

        if not args.quiet:
            print(f"[demo] working copy: {fixture_dir}")
            print("[demo] building vector index (one-time, ~5s)…")

        mind = NeuralMind(str(fixture_dir))
        result = mind.build(force=True)
        if not result.get("success"):
            print(
                f"demo failed during build: {result.get('error', 'unknown error')}", file=sys.stderr
            )
            sys.exit(1)

        _demo_report.run_demo_report(
            fixture_dir,
            header_label="bundled sample_project",
        )
    finally:
        if keep:
            print(f"[demo] keeping working copy at {workdir} (--keep)")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def cmd_init(args):
    """One-command NeuralMind setup: scan → build graph → create embeddings → start watcher."""

    project_path = args.project_path or "."
    path = Path(project_path).resolve()

    if not path.is_dir():
        print(f"init failed: not a directory: {project_path}")
        sys.exit(1)

    # 1. Auto-detect languages (same scan as _dry_run_scan)
    scan = _dry_run_scan(project_path)
    lang_counts = scan.get("languages", {})
    total_files = scan.get("total_files", 0)

    if total_files == 0:
        print(f"No supported code files found in {project_path}.")
        sys.exit(1)

    print(f"NeuralMind setting up: {path.name}")
    print(f"  Files found  : {total_files}")
    if lang_counts:
        langs = ", ".join(f"{v} {k}" for k, v in sorted(lang_counts.items(), key=lambda kv: -kv[1]))
        print(f"  Languages    : {langs}")
    print()

    # 2. Build graph + create embeddings
    print("Building graph and creating embeddings...")
    mind = NeuralMind(str(path))
    result = mind.build(force=bool(getattr(args, "force", False)))
    if not result.get("success"):
        print(f"init failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    nodes_total = result.get("nodes_total", 0)
    duration = result.get("duration_seconds", 0)

    # 3. Derive function/class count from embedder if available
    func_class_summary = ""
    try:
        if mind.embedder and hasattr(mind.embedder, "nodes") and mind.embedder.nodes:
            func_count = sum(
                1
                for n in mind.embedder.nodes
                if n.get("type") in ("function", "method", "class", "constructor")
            )
            class_count = sum(1 for n in mind.embedder.nodes if n.get("type") == "class")
            file_count = sum(1 for n in mind.embedder.nodes if n.get("file_type") == "code")
            lang_count = len(lang_counts)
            func_class_summary = (
                f"  Functions : {func_count}\n"
                f"  Classes   : {class_count}\n"
                f"  Files     : {file_count}\n"
                f"  Languages : {lang_count}"
            )
            summary_line = (
                f"NeuralMind active — {nodes_total} nodes"
                f" ({func_count} functions, {class_count} classes)"
                f" across {lang_count} languages"
            )
        else:
            lang_count = len(lang_counts)
            summary_line = f"NeuralMind active — {nodes_total} nodes across {lang_count} languages"
            func_class_summary = f"  Languages : {lang_count}"
    except Exception:
        lang_count = len(lang_counts)
        summary_line = f"NeuralMind active — {nodes_total} nodes across {lang_count} languages"
        func_class_summary = f"  Languages : {lang_count}"

    print()
    print(summary_line)
    if func_class_summary:
        print(func_class_summary)
    print(f"  Duration  : {duration}s")
    print()

    # 4. Optional watcher start
    watch = getattr(args, "watch", True) and not getattr(args, "no_watch", False)
    if watch:
        print("Starting file watcher (edits trigger synapse co-activation)...")
        try:
            from neuralmind.watcher import FileActivityWatcher

            if mind.synapses is None:
                print("  watcher skipped: synapses disabled for this instance")
            else:
                import signal
                import threading

                def on_batch(paths: list[str]) -> None:
                    try:
                        mind.activate_files(paths)
                    except Exception:
                        pass

                watcher = FileActivityWatcher(
                    str(path),
                    on_batch,
                    debounce=0.75,
                )
                watcher.start()
                print(f"  File watcher running on {path} (synapses enabled)")
                print("  Press Ctrl-C to stop the watcher (graph + embeddings persist).")

                def _wait() -> None:
                    try:
                        signal.pause()
                    except KeyboardInterrupt:
                        pass

                wait_thread = threading.Thread(target=_wait, daemon=True)
                wait_thread.start()
        except ImportError:
            print("  file watcher unavailable (watcher module not installed)")
        except Exception as exc:
            print(f"  file watcher failed to start: {exc}")
    else:
        print("File watcher not started (--no-watch).")
        print("Run `neuralmind watch` later to enable live synapse learning.")

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))

    return  # 0 implied


def cmd_compliance(args):
    """Scan files for compliance annotations and report findings."""
    project_path = args.project_path or "."
    path = Path(project_path).resolve()

    use_watch = getattr(args, "watch", False)

    # Scan files for compliance annotations
    from neuralmind.compliance_matcher import find_compliance_annotations_in_file

    if use_watch:
        # Watch mode: run a watcher that checks every file change
        print(f"Watching {path} for compliance annotations...")
        print("Edit a file with CMMC/NIST/SOX/HIPAA annotations and watch them appear.")
        print("Press Ctrl-C to stop.")
        print()

        mind = create_mind(str(path), auto_build=True)
        from neuralmind.watcher import FileActivityWatcher

        if mind.synapses is not None:

            def on_change(paths: list[str]) -> None:
                detections = mind.detect_compliance(paths)
                for d in detections:
                    print(
                        f"  [compliance] {d['framework']} {d['control_id']} "
                        f"— {d['label']}  ({d['file']})"
                    )
                if detections:
                    print(f"  -> {len(detections)} compliance synapses reinforced")

            watcher = FileActivityWatcher(
                str(path),
                on_change,
                debounce=0.75,
            )
            watcher.start()
            try:
                import signal

                signal.pause()
            except KeyboardInterrupt:
                watcher.stop()
        else:
            print("Synapses disabled — compliance detection requires synapses.")
            sys.exit(1)
        return

    # One-shot scan mode
    matches_total = 0
    results: list[dict] = []

    for f in path.rglob("*"):
        if f.is_file() and f.suffix in {
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".go",
            ".rs",
            ".java",
            ".cs",
            ".rb",
            ".php",
            ".c",
            ".cpp",
            ".h",
        }:
            matches = find_compliance_annotations_in_file(f)
            if matches:
                matches_total += len(matches)
                for m in matches:
                    rel = f.relative_to(path)
                    results.append({"file": str(rel), **m})

    if getattr(args, "json", False):
        print(json.dumps(results, indent=2))
        return

    if not results:
        print(f"No compliance annotations found in {path}.")
        print(
            "Tip: add annotations like:\n"
            "  // CMMC AC.L2-3.1.1: Authorized Access Control\n"
            "  # SOX ITGC-CM-001: Change approved via CAB\n"
        )
        return

    print(f"Found {matches_total} compliance annotations across {path.name}:\n")
    for r in results:
        print(f"  [{r['framework']:>10}] {r['control_id']}")
        print(f"             {r['label']}")
        print(f"             {r['file']}")
        print()


def cmd_ingest_cmmc(args):
    """Ingest CMMC practice registry as first-class content nodes."""
    project_path = args.project_path or "."
    registry_path = args.registry

    if not registry_path:
        # Default: check NEURALMIND_CMMC_REGISTRY env var, then error
        env_path = os.environ.get("NEURALMIND_CMMC_REGISTRY")
        if env_path and Path(env_path).exists():
            registry_path = env_path
        else:
            print("Error: --registry path is required.")
            print("Usage: neuralmind ingest-cmmc --registry /path/to/registry.json")
            print("Or set NEURALMIND_CMMC_REGISTRY env var.")
            sys.exit(1)
    if not registry_path or not Path(registry_path).exists():
        print(f"Error: registry file not found: {registry_path}")
        sys.exit(1)
    try:
        with open(registry_path, encoding="utf-8") as f:
            json.load(f)
    except Exception as e:
        print(f"Error: failed to read registry: {e}")
        sys.exit(1)

    print(f"Ingesting CMMC practices from {Path(registry_path).name}...")
    mind = create_mind(str(project_path), auto_build=True)
    result = mind.ingest_cmmc(str(registry_path))

    if not result.get("success"):
        print(f"Ingestion failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    node_count = result.get("node_count", 0)
    stats = result.get("embed_stats", {})

    print(f"✅ Ingested {node_count} CMMC practices into the code graph")
    if stats:
        print(
            f"   Added: {stats.get('added', 0)}, Updated: {stats.get('updated', 0)}, "
            f"Skipped: {stats.get('skipped', 0)}"
        )

    print()
    print("Try: neuralmind query 'What is AC.L2-3.1.1?'")


def cmd_export(args):
    """Export NeuralMind state for audit (CSV or PDF)."""
    from neuralmind.export import run_export

    result = run_export(args)
    if result.get("error"):
        print(f"Export failed: {result['error']}")
        sys.exit(1)

    if getattr(args, "json", False):
        import json as _json

        print(_json.dumps(result, indent=2))


def cmd_ci_check(args):
    """Run CI compliance check on the project."""
    from neuralmind.ci_check import format_ci_output, run_ci_check

    project_path = getattr(args, "project_path", ".")
    base = getattr(args, "diff", "HEAD")
    framework = getattr(args, "framework", "all")

    result = run_ci_check(
        project_path,
        framework=framework,
        base=base,
        json_output=bool(getattr(args, "json", False)),
    )

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
    else:
        print(format_ci_output(result))

    # Non-zero exit when warnings exist (optionally fail the build)
    if getattr(args, "fail_on_warning", False) and result.get("warnings"):
        sys.exit(1)


def cmd_last(args):
    """Print the most recent cached bash output (recovery without re-running).

    Whenever NeuralMind's PostToolUse hook compresses a Bash output, it
    stashes the raw stdout/stderr to ``.neuralmind/last_output.json``.
    This command surfaces that cache so an agent can fetch the dropped
    middle on demand instead of re-running an expensive command with
    NEURALMIND_BYPASS=1.
    """
    import datetime

    from .output_cache import cache_path, read_last_output

    project_path = args.project_path or "."
    data = read_last_output(project_path)
    if data is None:
        print(
            "No cached output found at "
            f"{cache_path(project_path)}.\n"
            "Run a Bash tool call through Claude Code first — the "
            "PostToolUse hook will populate the cache."
        )
        sys.exit(1)

    if args.json:
        print(json.dumps(data, indent=2))
        return

    ts = data.get("ts", 0)
    when = datetime.datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts else "unknown"
    print(f"# cached: {when}   exit={data.get('exit_code', 0)}")
    if data.get("command"):
        print(f"# command: {data['command']}")
    print()
    stdout = data.get("stdout") or ""
    stderr = data.get("stderr") or ""
    if stdout:
        print(stdout.rstrip())
    if stderr:
        if stdout:
            print()
        print("[stderr]")
        print(stderr.rstrip())


def cmd_install_hooks(args):
    """Install or remove Claude Code PostToolUse hooks."""
    from .hooks import install_hooks

    scope = "global" if args.global_ else "project"
    project_path = args.project_path if scope == "project" else None
    try:
        result = install_hooks(
            scope=scope,
            project_path=project_path,
            uninstall=args.uninstall,
        )
        action = result["action"]
        path = result["path"]
        print(f"✓ NeuralMind hooks {action} at {path}")
        if action == "installed":
            print(
                "  PostToolUse hooks active: compress-read, compress-bash, "
                "cap-search, edit-activity (reuse feedback)"
            )
            print("  Run `neuralmind install-hooks --uninstall` to remove.")
            print("  Set NEURALMIND_BYPASS=1 env var to disable compression temporarily.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_install_mcp(args):
    """Register the NeuralMind MCP server with one or more AI coding agents."""
    from . import mcp_install

    project_dir = Path(args.project_path or ".").resolve()

    if getattr(args, "print_only", False):
        print(mcp_install.snippet())
        print(
            "\nPaste the above into your client's MCP config "
            "(Claude Code: .mcp.json · Cursor: .cursor/mcp.json · "
            "Claude Desktop / Cline: the app's settings file)."
        )
        return

    if getattr(args, "all", False):
        clients = mcp_install.detect_clients(project_dir)
        if not clients:
            print("No MCP clients detected. Use --client <name> or --print.")
            print(f"  Known clients: {', '.join(mcp_install.CLIENTS)}")
            return
    else:
        clients = [args.client]

    any_change = False
    for client in clients:
        try:
            result = mcp_install.install(client, project_dir)
        except ValueError as exc:
            print(f"Error: {exc}")
            sys.exit(1)
        symbol = "✓" if result.action != "already-present" else "•"
        print(f"{symbol} {client}: {result.action} → {result.path}")
        any_change = any_change or result.action != "already-present"

    if any_change:
        print(
            "\nThe agent exposes NeuralMind's tools (wakeup, query, search, "
            "skeleton, …). Restart the client to pick up the new server."
        )


def cmd_hook(args):
    """Internal: runtime entrypoint invoked by Claude Code hooks."""
    from .hooks import run_hook

    sys.exit(run_hook(args.action))


def cmd_risks(args):
    """Show type-risk signals from static type verification.

    Runs the type verifier over the project graph and reports any
    Optional/None-return risks for compliance review.
    """
    project_path = Path(args.project_path or ".").resolve()
    if not project_path.exists():
        print(f"Error: project path does not exist: {project_path}", file=sys.stderr)
        sys.exit(1)

    min_severity = getattr(args, "min_severity", "info")
    severity_order = {"info": 0, "warn": 1, "high": 2}

    try:
        from neuralmind import type_verifier

        # Load graph from embedder or generate
        mind = create_mind(str(project_path), auto_build=False)
        if not mind._built:
            mind.build()

        graph = getattr(mind.embedder, "graph", None)
        if not graph:
            if args.json:
                print(json.dumps({"risks": [], "message": "no graph"}))
            else:
                print("No graph available. Run `neuralmind build` first.")
            return

        tv = type_verifier.TypeVerifier(project_path)
        tv.augment_graph(graph)
        risks = tv.detect_type_risks(graph)

        # Filter by severity
        min_level = severity_order.get(min_severity, 0)
        filtered = [r for r in risks if severity_order.get(r.severity, 0) >= min_level]

        if args.json:
            output = {
                "risks": [
                    {
                        "caller_id": r.caller_id,
                        "callee_id": r.callee_id,
                        "risk_type": r.risk_type,
                        "severity": r.severity,
                        "detail": r.detail,
                        "callee_returns": r.callee_returns,
                    }
                    for r in filtered
                ],
                "total": len(filtered),
            }
            print(json.dumps(output, indent=2))
        else:
            report = type_verifier.format_type_risks(filtered)
            print(report)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error running type verification: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_license_issue(args):
    """Issue a new Team license."""
    from neuralmind.tier2.operations import LicenseOperations

    storage_path = Path.home() / ".neuralmind"
    private_key = os.environ.get("NEURALMIND_ISSUER_PRIVATE_KEY_HEX", "")
    if not private_key:
        print("Error: NEURALMIND_ISSUER_PRIVATE_KEY_HEX not set", file=sys.stderr)
        sys.exit(1)
    ops = LicenseOperations(private_key, storage_path)
    output_path = Path(args.output) if args.output else None
    lic = ops.issue_team_license(
        customer_name=args.customer,
        seats=args.seats,
        term_months=args.term,
        partner_id=args.partner,
        output_path=output_path,
    )
    print(f"License issued: {lic.raw.get('license_id')}")
    print(f"Customer: {lic.issued_to}")
    print(f"Seats: {lic.seats}")
    print(f"Expires: {lic.expires_at}")


def cmd_license_renew(args):
    """Renew an existing license."""
    from neuralmind.tier2.operations import LicenseOperations

    storage_path = Path.home() / ".neuralmind"
    private_key = os.environ.get("NEURALMIND_ISSUER_PRIVATE_KEY_HEX", "")
    if not private_key:
        print("Error: NEURALMIND_ISSUER_PRIVATE_KEY_HEX not set", file=sys.stderr)
        sys.exit(1)
    ops = LicenseOperations(private_key, storage_path)
    lic = ops.renew_license(args.customer, args.term)
    print(f"License renewed: {lic.raw.get('license_id')}")
    print(f"New expiry: {lic.expires_at}")


def cmd_license_revoke(args):
    """Revoke a license."""
    from neuralmind.tier2.operations import LicenseOperations

    storage_path = Path.home() / ".neuralmind"
    private_key = os.environ.get("NEURALMIND_ISSUER_PRIVATE_KEY_HEX", "")
    if not private_key:
        print("Error: NEURALMIND_ISSUER_PRIVATE_KEY_HEX not set", file=sys.stderr)
        sys.exit(1)
    ops = LicenseOperations(private_key, storage_path)
    lic = ops.revoke_license(args.customer, args.reason)
    print(f"License revoked: {lic.raw.get('license_id')}")
    print(f"Reason: {args.reason}")


def cmd_license_status(args):
    """Show license status."""
    from neuralmind.tier2.operations import LicenseOperations

    storage_path = Path.home() / ".neuralmind"
    private_key = os.environ.get("NEURALMIND_ISSUER_PRIVATE_KEY_HEX", "")
    ops = LicenseOperations(private_key, storage_path)
    status = ops.get_license_status(args.customer)
    for k, v in status.items():
        print(f"{k}: {v}")


def cmd_license_list(args):
    """List all licenses."""
    from neuralmind.tier2.operations import LicenseOperations

    storage_path = Path.home() / ".neuralmind"
    private_key = os.environ.get("NEURALMIND_ISSUER_PRIVATE_KEY_HEX", "")
    ops = LicenseOperations(private_key, storage_path)
    licenses = ops.list_customer_licenses(args.partner)
    for lic in licenses:
        print(
            f"{lic['customer']}: {lic['status']} ({lic['seats']} seats, expires {lic['expires_at']})"
        )


def cmd_partner_add(args):
    """Add a new partner."""
    from neuralmind.tier2.operations import PartnerOperations

    storage_path = Path.home() / ".neuralmind"
    ops = PartnerOperations(storage_path, storage_path / "audit_log.jsonl")
    partner = ops.add_partner(args.name, args.commission, args.email)
    print(f"Partner added: {partner['partner_id']}")


def cmd_partner_list(args):
    """List all partners."""
    from neuralmind.tier2.operations import PartnerOperations

    storage_path = Path.home() / ".neuralmind"
    ops = PartnerOperations(storage_path, storage_path / "audit_log.jsonl")
    for p in ops.list_partners():
        print(f"{p['partner_id']}: {p['name']} ({p['commission_percent']}%)")


def cmd_partner_licenses(args):
    """List partner's licenses."""
    from neuralmind.tier2.operations import LicenseOperations

    storage_path = Path.home() / ".neuralmind"
    private_key = os.environ.get("NEURALMIND_ISSUER_PRIVATE_KEY_HEX", "")
    ops = LicenseOperations(private_key, storage_path)
    for lic in ops.list_customer_licenses(args.partner):
        print(f"{lic['customer']}: {lic['status']}")


def cmd_optimize_docs(args):
    """`neuralmind optimize-docs` — evolve JSDoc for undocumented methods.

    Runs an AST audit to find undocumented public methods (or accepts a
    pre-computed blind spot list), then uses DocEvolver to generate and
    evolve JSDoc variants that maximize retrieval fitness. The winning
    variant is patched back into the source files.

    Scoring: Recall@1 — the reciprocal of the rank of the correct source
    file when querying with a natural-language description of the method.
    A method with JSDoc that ranks #1 scores 1.0, #2 scores 0.5, #3 scores
    0.33, etc.
    """
    project_path = Path(args.project_path or ".").resolve()

    if not project_path.exists():
        print(f"Path does not exist: {project_path}", file=sys.stderr)
        sys.exit(1)

    # Load or audit blind spots
    if args.blind_spots:
        try:
            raw = json.loads(Path(args.blind_spots).read_text(encoding="utf-8"))
            blind_spots = [
                BlindSpot(
                    name=s.get("name", ""),
                    file_path=s.get("file_path", s.get("file", s.get("source_file", ""))),
                    line=s.get("line", 1),
                    method_type=s.get("method_type", "function"),
                    params=s.get("params", []),
                )
                for s in raw
            ]
        except (OSError, ValueError) as exc:
            print(f"Could not read blind spots file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        from neuralmind.doc_evolver import audit_blind_spots

        blind_spots = audit_blind_spots(project_path)

    if not blind_spots:
        if args.json:
            print(json.dumps({"status": "no_blind_spots", "project": str(project_path)}))
        else:
            print(f"No undocumented methods found in {project_path.name}.")
            print("Run `neuralmind build .` first to ensure the index is up to date.")
        return

    if args.json:
        print(json.dumps({"status": "starting", "blind_spots": len(blind_spots)}))
    else:
        print(f"DocEvolver — {len(blind_spots)} undocumented method(s) in {project_path.name}")
        print(
            f"  Pop={args.population or 5}, Gen={args.generations or 5}, Hyst={args.hysteresis or 0.05}"
        )
        print("=" * 60)

    # Build evolver
    evolver = DocEvolver(
        project_path=project_path,
        blind_spots=blind_spots,
        population_size=args.population,
        generations=args.generations,
        hysteresis=args.hysteresis,
    )

    # Run evolution
    results = evolver.evolve()

    # Report results
    total_fitness = sum(r.best_fitness for r in results)
    avg_fitness = total_fitness / len(results) if results else 0.0
    promoted_count = sum(1 for r in results if r.promoted)

    if args.json:
        output = {
            "results": [
                {
                    "name": r.name,
                    "file": r.file_path,
                    "line": r.line,
                    "fitness": round(r.best_fitness, 4),
                    "promoted": r.promoted,
                    "variant": r.best_variant.text if r.best_variant else None,
                }
                for r in results
            ],
            "summary": {
                "total": len(results),
                "promoted": promoted_count,
                "avg_fitness": round(avg_fitness, 4),
            },
        }
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            status = "PROMOTED" if r.promoted else "no improvement"
            print(f"  {r.name:30s} {r.file_path:30s} fit={r.best_fitness:.3f} [{status}]")
            if r.best_variant and not args.dry_run:
                print(f"    JSDoc: {r.best_variant.text.splitlines()[0]} ...")
        print("=" * 60)
        print(f"  Average fitness: {avg_fitness:.3f}  ({promoted_count}/{len(results)} promoted)")

    # Patch winners (unless dry-run)
    if not args.dry_run:
        modified = evolver.patch_winners(results)
        if args.json:
            print(json.dumps({"patched_files": modified}))
        else:
            if modified:
                print(f"\nPatched JSDoc into {len(modified)} file(s):")
                for f in modified:
                    print(f"  ✓ {f}")
            else:
                print("\nNo files were patched (no winning variants found).")


def _cmd_gaps_structural(args):
    """Run structural gap detection (G5) and output results."""
    import json
    import os

    from .structural_gaps import detect_gaps, format_structural_gaps

    project_path = getattr(args, "project_path", ".")
    threshold = getattr(args, "threshold", 0.1)
    top_k = getattr(args, "top_k", 10)
    as_json = getattr(args, "json", False)

    graph_path = os.path.join(project_path, "graphify-out", "graph.json")
    if not os.path.exists(graph_path):
        print("No graph found. Run `neuralmind build` first.")
        return

    with open(graph_path, encoding="utf-8") as f:
        graph = json.load(f)

    gaps = detect_gaps(graph, top_k=top_k, threshold=threshold)

    if as_json:
        output = {
            "gaps": [
                {
                    "node_id": g.node_id,
                    "node_name": g.node_name,
                    "communities": list(g.communities),
                    "betweenness": g.betweenness,
                    "degree": g.degree,
                    "gap_score": g.gap_score,
                    "suggested_connections": list(g.suggested_connections),
                }
                for g in gaps
            ],
            "total_nodes": len(graph.get("nodes", [])),
            "total_edges": len(graph.get("links", [])),
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_structural_gaps(gaps))


def cmd_gaps(args):
    """Find endpoints tested only in mock mode — the coverage that lies.

    Scans a project's JS/TS source for Express route registrations and its
    test files for the routes they exercise, then classifies each endpoint
    as live-covered / mock-only / untested. Phase 1 heuristics (Express +
    Jest); an endpoint "green" only under a mocked store is the P2003 shape.

    With ``--structural``, uses graph-topological gap detection (G5) to
    identify cross-community bridge nodes and structural blind spots.
    """
    structural = getattr(args, "structural", False)
    if structural:
        _cmd_gaps_structural(args)
        return

    import os

    from .gaps import classify, extract_routes, extract_test_refs, format_gaps

    project_path = getattr(args, "project_path", ".")
    routes: list = []
    refs: list = []
    skip_dirs = {"node_modules", ".git", "dist", "build", ".next", "coverage"}
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if not fname.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")):
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    src = fh.read()
            except Exception:
                continue
            is_test = ".test." in fname or ".spec." in fname or "__tests__" in root
            if is_test:
                refs.extend(extract_test_refs(src))
            else:
                routes.extend(extract_routes(src))

    if not routes:
        print(
            "No Express route registrations found (Phase 1 covers JS/TS app.get/router.post styles)."
        )
        return
    gaps = classify(routes, refs)
    print(format_gaps(gaps))


def cmd_why(args):
    """Answer "why is <X> the way it is?" from recorded decision provenance.

    Harvests ``Decision:`` trailers from git history and surfaces the ones
    whose subjects the query mentions — the rationale that would otherwise
    live only in a human's head.
    """
    from .provenance import format_decisions, harvest, recall

    project_path = getattr(args, "project_path", ".")
    records = harvest(project_path)
    hits = recall(records, args.query)
    if not hits:
        if not records:
            print("No decisions recorded yet.")
            print("Capture one by adding a 'Decision:' trailer to a commit message, e.g.:")
            print("  Decision: resolveOrgId is per-handler — avoids Prisma on /health.")
        else:
            print(f"No recorded decisions match {args.query!r}.")
        return
    print(format_decisions(hits))


def cmd_init_hook(args):
    """Initialize Git post-commit hook for automatic updates.

    Safe: appends to an existing post-commit hook rather than overwriting
    it, and is idempotent — re-running only updates the neuralmind block.
    """
    import os
    import stat
    import sys

    project_path = getattr(args, "project_path", ".")
    project_path = os.path.abspath(project_path)
    git_hooks_dir = os.path.join(project_path, ".git", "hooks")

    if not os.path.exists(git_hooks_dir):
        print(
            f"Error: .git/hooks directory not found in {project_path}. Are you in a Git repository?"
        )
        sys.exit(1)

    hook_path = os.path.join(git_hooks_dir, "post-commit")

    # The neuralmind block is delimited by sentinels so re-runs replace
    # the block in place and coexist with other tools' hook contributions
    # (e.g. `graphify hook install`).
    #
    # Note: `neuralmind build` has no --quiet flag; we redirect output to
    # /dev/null instead. Using --force keeps it fast (skips nothing) but
    # still reuses existing embeddings for unchanged nodes via hash checks.
    nm_block = """# neuralmind-hook-start
# Auto-rebuild NeuralMind index after each commit. Managed by `neuralmind init-hook`.
if command -v neuralmind >/dev/null 2>&1; then
    echo "[neuralmind] Rebuilding neural index..."
    neuralmind build . >/dev/null 2>&1 && \\
        echo "[neuralmind] OK" || \\
        echo "[neuralmind] Rebuild failed (non-critical)"
fi
# neuralmind-hook-end
"""

    existing = ""
    if os.path.exists(hook_path):
        with open(hook_path) as f:
            existing = f.read()

    if "# neuralmind-hook-start" in existing and "# neuralmind-hook-end" in existing:
        # Idempotent replacement of just our block
        pre, _, rest = existing.partition("# neuralmind-hook-start")
        _, _, post = rest.partition("# neuralmind-hook-end")
        # post starts right after the sentinel; strip the trailing newline
        # from our pre-slice if it produced one, then splice
        new_content = pre.rstrip("\n") + "\n\n" + nm_block + post.lstrip("\n")
        action = "updated"
    elif existing.strip():
        # Append to existing hook without clobbering
        if not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + "\n" + nm_block
        action = "appended to"
    else:
        # Fresh hook
        new_content = "#!/bin/sh\n" + nm_block
        action = "created"

    try:
        with open(hook_path, "w") as f:
            f.write(new_content)
        # Make executable (no-op on Windows but harmless)
        current_mode = os.stat(hook_path).st_mode
        os.chmod(hook_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"✓ NeuralMind post-commit hook {action} at {hook_path}")
        print("  The index will rebuild automatically after every commit.")
    except Exception as e:
        print(f"Error installing hook: {e}")
        sys.exit(1)


def _version_string() -> str:
    """Build `neuralmind --version` string with tier info."""
    from . import __version__

    base = f"neuralmind {__version__}"
    try:
        from neuralmind.tier2.config import load_config
        from neuralmind.tier2.license import _ISSUER_PUBLIC_KEY_HEX, LicenseValidator

        cfg = load_config()
        lic_path = Path(cfg.license_file)
        if lic_path.exists():
            validator = LicenseValidator(_ISSUER_PUBLIC_KEY_HEX, lic_path)
            lic_info = validator._load_raw()
            if lic_info and cfg.is_team_active():
                return f"{base} ({lic_info.tier.title()}, {cfg.seats} seats)"
    except Exception:
        pass
    return base


def main():
    # Windows consoles default to cp1252 and crash (UnicodeEncodeError) on the
    # Unicode glyphs we print — and on the em-dash argparse prints in --help.
    # Force UTF-8 before any output. No-op on Linux/macOS and under pytest capture.
    _force_utf8_io()

    parser = argparse.ArgumentParser(
        description=(
            "NeuralMind — reduce Claude/GPT/Gemini token costs 12-50x on code questions. "
            "Local semantic codebase index + MCP server + PostToolUse compression hooks "
            "for Claude Code, Cursor, Cline, and Continue."
        ),
        epilog=(
            "Quick start: `neuralmind wakeup .` · docs: https://github.com/dfrostar/neuralmind"
        ),
    )

    parser.add_argument("--version", action="version", version=_version_string())
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    build_p = subparsers.add_parser("build", help="Build neural knowledge base")
    build_p.add_argument("project_path", nargs="?", default=".")
    build_p.add_argument("--force", "-f", action="store_true")
    build_p.add_argument(
        "--bootstrap",
        default=None,
        help="Path to a synapse bundle JSON for cold-start seeding",
    )
    build_p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Scan the project and estimate token savings without building the index.",
    )
    build_p.add_argument("--json", "-j", action="store_true")
    build_p.set_defaults(func=cmd_build)

    query_p = subparsers.add_parser("query", help="Query the knowledge base")
    query_p.add_argument("project_path")
    query_p.add_argument("question")
    query_p.add_argument("--json", "-j", action="store_true")
    query_p.add_argument(
        "--trace",
        action="store_true",
        help="Attach a per-layer retrieval trace (candidates, cluster scores, "
        "synapse boosts, final hits, token budget) for explainability/debugging.",
    )
    query_p.add_argument(
        "--trace-verbose",
        action="store_true",
        help="With --trace, keep full candidate/hit lists in the trace.",
    )
    query_p.add_argument(
        "--relevance",
        action="store_true",
        help="With --json, attach a structured relevance sidecar (per-file, "
        "per-node score/synapse-boost/recall + line spans) so a downstream "
        "compressor can protect the load-bearing spans.",
    )
    query_p.add_argument(
        "--explain",
        action="store_true",
        help="Show a human-friendly breakdown of why this context was selected: "
        "token savings, layers used, communities loaded, top search hits, "
        "and which synapses fired.",
    )
    query_p.set_defaults(func=cmd_query)

    wakeup_p = subparsers.add_parser("wakeup", help="Get wake-up context")
    wakeup_p.add_argument("project_path")
    wakeup_p.add_argument("--json", "-j", action="store_true")
    wakeup_p.set_defaults(func=cmd_wakeup)

    savings_p = subparsers.add_parser(
        "savings",
        help="Show cumulative token savings from the local query event log — "
        "verifies the 12-50x claim against your own real usage.",
    )
    savings_p.add_argument("project_path", nargs="?", default=".")
    savings_p.add_argument(
        "--global",
        dest="global_",
        action="store_true",
        help="Show savings across ALL projects (reads the global event log).",
    )
    savings_p.add_argument("--json", "-j", action="store_true")
    savings_p.add_argument(
        "--cost",
        action="store_true",
        help="Also show estimated dollar savings, priced on input tokens "
        f"(default model: {memory.DEFAULT_PRICING_MODEL}).",
    )
    savings_p.add_argument(
        "--model",
        choices=sorted(memory.MODEL_PRICING_PER_MTOK),
        default=None,
        help="Pricing model for --cost.",
    )
    savings_p.add_argument(
        "--queries-per-day",
        type=int,
        default=100,
        help="Assumed queries per day for the --cost monthly projection (default: 100).",
    )
    savings_p.set_defaults(func=cmd_savings)

    review_p = subparsers.add_parser(
        "review",
        help="Warn about likely co-breakage: files NOT in your git diff but strongly "
        "associated via the synapse graph — catch forgotten test files, coupled modules.",
    )
    review_p.add_argument("project_path", nargs="?", default=".")
    review_p.add_argument(
        "--base",
        default="HEAD",
        help="Git ref to diff against (default: HEAD = uncommitted changes). "
        "Use 'HEAD~1' to review the last commit, or a branch name.",
    )
    review_p.add_argument(
        "--top-k",
        type=int,
        default=10,
        dest="top_k",
        help="Maximum number of at-risk files to report (default: 10).",
    )
    review_p.add_argument("--json", "-j", action="store_true")
    review_p.set_defaults(func=cmd_review)

    bench_p = subparsers.add_parser(
        "benchmark",
        help="Run benchmark on your project (supports --contribute for community submissions)",
    )
    bench_p.add_argument("project_path", nargs="?", default=".")
    bench_p.add_argument("--json", "-j", action="store_true")
    bench_p.add_argument(
        "--quality",
        action="store_true",
        help="Quality-eval mode: precision@k / recall@k / MRR / answerability over the "
        "golden polyglot suites (a contributor/CI self-test, not a per-project run).",
    )
    bench_p.add_argument(
        "--suite",
        help="With --quality, run a single suite (python / typescript / go) instead of all.",
    )
    bench_p.add_argument(
        "--baseline",
        help="With --quality, a saved suite JSON to compare against (reports metric deltas).",
    )
    bench_p.add_argument(
        "--public",
        action="store_true",
        help="Public benchmark: NeuralMind vs. full-file / ripgrep / embedding-RAG on "
        "pinned real repos, reporting gold-file recall (objective, no LLM judge) against "
        "context-token cost. Reproduces docs/benchmarks/public.md (clones pinned repos). "
        "Requires a source checkout — the evals/public harness ships in the repo, not the "
        "PyPI wheel; run it from a clone.",
    )
    bench_p.add_argument(
        "--repo",
        help="With --public, run a single repo from the corpus by name (e.g. requests).",
    )
    bench_p.add_argument(
        "--seeds",
        type=int,
        default=1,
        help="With --public, seed count (the pipeline is deterministic; recorded honestly).",
    )
    bench_p.add_argument(
        "--judge",
        action="store_true",
        help="With --public, also run the opt-in LLM-judged answerability arm (a secondary "
        "signal — each backend answered from its real window by a pinned model, graded vs. the "
        "def-site gold anchor). Needs ANTHROPIC_API_KEY; never runs in CI; the recall table is "
        "byte-identical with or without it. Transcripts committed under --judge-out.",
    )
    bench_p.add_argument(
        "--judge-out",
        default="bench/public/judge",
        help="With --public --judge, where to write answerability transcripts.",
    )
    bench_p.add_argument(
        "--contribute",
        action="store_true",
        help="Emit a schema-ready JSON blob you can submit to the community benchmarks. "
        "No data is uploaded — you copy-paste the output into an issue or PR.",
    )
    bench_p.add_argument(
        "--content",
        nargs="?",
        const="evals/book_retrieval/underground/chapters",
        help="Content benchmark: ingest + evaluate a book corpus. Optionally takes a path (default: Underground book).",
    )
    bench_p.add_argument(
        "--project-name", help="Project name for contribution (optional; prompts on TTY)"
    )
    bench_p.add_argument("--language", help="Primary language for contribution (optional)")
    bench_p.add_argument("--model", help="LLM you run against (optional)")
    bench_p.add_argument("--repo-url", help="Public repo URL (optional)")
    bench_p.add_argument("--submitter", help="Your GitHub username (optional)")
    bench_p.add_argument("--notes", help="Optional notes for the submission")
    bench_p.set_defaults(func=cmd_benchmark)

    probe_p = subparsers.add_parser(
        "probe",
        help="Retrieval self-probe: does the index find YOUR symbols? "
        "(recall@k / MRR / answerability + a blind-spot list, no labeling needed)",
    )
    probe_p.add_argument("project_path", nargs="?", default=".")
    probe_p.add_argument(
        "--sample-size",
        type=int,
        default=50,
        help="How many indexed symbols to probe (default: 50; 0 = all)",
    )
    probe_p.add_argument(
        "--k",
        type=int,
        default=10,
        help="Retrieval depth — a symbol's file must surface in the top-k (default: 10)",
    )
    probe_p.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Sampling seed; same seed = same sample, for stable/comparable runs (default: 0)",
    )
    probe_p.add_argument(
        "--baseline",
        help="A saved probe JSON to compare against (reports recall/MRR deltas)",
    )
    probe_p.add_argument("--json", "-j", action="store_true")
    probe_p.set_defaults(func=cmd_probe)

    search_p = subparsers.add_parser("search", help="Direct semantic search")
    search_p.add_argument("project_path")
    search_p.add_argument("query")
    search_p.add_argument("--n", type=int, default=10)
    search_p.add_argument("--json", "-j", action="store_true")
    search_p.set_defaults(func=cmd_search)

    doctor_p = subparsers.add_parser(
        "doctor",
        help="Diagnose install health (graph, index, hooks, MCP, synapses)",
    )
    doctor_p.add_argument("project_path", nargs="?", default=".")
    doctor_p.add_argument("--json", "-j", action="store_true")
    doctor_p.set_defaults(func=cmd_doctor)

    stats_p = subparsers.add_parser("stats", help="Show index statistics")
    stats_p.add_argument("project_path")
    stats_p.add_argument("--json", "-j", action="store_true")
    stats_p.set_defaults(func=cmd_stats)

    metrics_p = subparsers.add_parser(
        "metrics",
        help="Show aggregated metrics summary from .neuralmind/metrics/ JSONL files",
    )
    metrics_p.add_argument("project_path", nargs="?", default=".")
    metrics_p.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="Window in days for metrics aggregation (default: 7)",
    )
    metrics_p.add_argument("--json", "-j", action="store_true")
    metrics_p.set_defaults(func=cmd_metrics)

    validate_p = subparsers.add_parser(
        "validate",
        help="Validate the project's canonical IR (schema, versions, orphans)",
    )
    validate_p.add_argument("project_path", nargs="?", default=".")
    validate_p.add_argument(
        "--write",
        action="store_true",
        help="(Re)materialize the IR to .neuralmind/ — migrates a legacy project in place",
    )
    validate_p.add_argument("--json", "-j", action="store_true")
    validate_p.set_defaults(func=cmd_validate)

    eval_p = subparsers.add_parser(
        "eval",
        help="Run the faithfulness eval (NeuralMind vs naive baseline) on the reference fixture",
    )
    eval_p.add_argument(
        "project_path",
        nargs="?",
        default=None,
        help="Project to evaluate (default: the committed gold-set fixture)",
    )
    eval_p.add_argument("--json", "-j", action="store_true")
    eval_p.add_argument(
        "--selfcheck",
        action="store_true",
        help="Validate the gold set + offline scorer only (no retrieval deps)",
    )
    eval_p.add_argument(
        "--onboarding",
        action="store_true",
        help="Run the onboarding-lift eval (committed team memory vs a cold agent) instead",
    )
    eval_p.set_defaults(func=cmd_eval)

    ingest_p = subparsers.add_parser(
        "ingest",
        help="Ingest documents (PDF/Markdown/text) into the knowledge graph",
    )
    ingest_p.add_argument("file_path", nargs="?", default=".", help="File or directory to ingest")
    ingest_p.add_argument(
        "--type",
        default="auto",
        choices=["auto", "pdf", "markdown", "text", "cmmc", "decision", "meeting", "sop", "policy"],
        help="Content type hint (default: auto-detect). Business types: decision, meeting, sop, policy (JSON input)",
    )
    ingest_p.add_argument("--json", "-j", action="store_true", help="Output JSON")
    ingest_p.add_argument(
        "--dry-run", action="store_true", help="List files that would be ingested without ingesting"
    )
    ingest_p.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    ingest_p.add_argument(
        "--no-recursive", action="store_true", help="Do not recurse into subdirectories"
    )
    ingest_p.set_defaults(func=cmd_ingest)

    # ingest-content: dedicated content indexer for books/markdown corpora
    ingest_content_p = subparsers.add_parser(
        "ingest-content",
        help="Ingest a directory of Markdown chapters into a pure content index (for book/content benchmarking)",
    )
    ingest_content_p.add_argument(
        "content_path",
        help="Path to a directory of .md files (chapters) or a single file",
    )
    ingest_content_p.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Max characters per chunk (default: 500)",
    )
    ingest_content_p.add_argument(
        "--overlap",
        type=int,
        default=50,
        help="Character overlap between chunks (default: 50)",
    )
    ingest_content_p.add_argument("--json", "-j", action="store_true", help="Output JSON")
    ingest_content_p.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    ingest_content_p.set_defaults(func=cmd_ingest_content)

    learn_p = subparsers.add_parser(
        "learn", help="Alias for 'ingest' — ingest documents into the knowledge graph"
    )
    learn_p.add_argument("file_path", nargs="?", default=".", help="File or directory to ingest")
    learn_p.add_argument(
        "--type",
        default="auto",
        choices=["auto", "pdf", "markdown", "text", "cmmc", "decision", "meeting", "sop", "policy"],
        help="Content type hint (default: auto-detect). Business types: decision, meeting, sop, policy (JSON input)",
    )
    learn_p.add_argument("--json", "-j", action="store_true", help="Output JSON")
    learn_p.add_argument(
        "--dry-run", action="store_true", help="List files that would be ingested without ingesting"
    )
    learn_p.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    learn_p.add_argument(
        "--no-recursive", action="store_true", help="Do not recurse into subdirectories"
    )
    learn_p.set_defaults(func=cmd_ingest)

    # onboarding command — interactive setup wizard for team tier
    onboarding_p = subparsers.add_parser(
        "onboarding",
        help="Interactive setup wizard: license, governance, admin, verification",
    )
    onboarding_p.add_argument(
        "--quick",
        action="store_true",
        help="Skip all prompts, use defaults",
    )
    onboarding_p.set_defaults(func=cmd_onboarding)

    # Self-improvement engine — nested so future subsystems can attach here.
    self_improve_p = subparsers.add_parser(
        "self-improve", help="Inspect the self-improvement engine"
    )
    self_improve_sub = self_improve_p.add_subparsers(dest="self_improve_command")
    self_improve_p.set_defaults(func=lambda _a: self_improve_p.print_help())
    si_status_p = self_improve_sub.add_parser("status", help="Show selector auto-tuning state")
    si_status_p.add_argument("project_path", nargs="?", default=".")
    si_status_p.add_argument("--json", "-j", action="store_true")
    si_status_p.set_defaults(func=cmd_self_improve_status)

    # Next-likely — directional transition recall (v0.11.0+)
    next_p = subparsers.add_parser(
        "next",
        help="Show what typically follows a node in the learned transition graph",
    )
    next_p.add_argument("project_path")
    next_p.add_argument(
        "from_node",
        help="Source node (file path or node id) to predict successors for",
    )
    next_p.add_argument("--n", type=int, default=5, help="Top-N successors to return")
    next_p.add_argument(
        "--namespace",
        help="Read one memory namespace at raw weights (default: merged view)",
    )
    next_p.add_argument("--json", "-j", action="store_true")
    next_p.set_defaults(func=cmd_next)

    # Impact — friendlier-named, richer-output blast-radius lookup (v0.47.0+)
    impact_p = subparsers.add_parser(
        "impact",
        help="Reverse-dependency (blast-radius) lookup: what depends on a symbol",
    )
    impact_p.add_argument("project_path")
    impact_p.add_argument(
        "symbol",
        help="Symbol (function/class/module label) or exact node id to trace dependents of",
    )
    impact_p.add_argument(
        "--depth",
        type=int,
        default=1,
        help="How many hops of transitive dependents to include (default: 1)",
    )
    impact_p.add_argument("--json", "-j", action="store_true")
    impact_p.set_defaults(func=cmd_impact)

    # audit command group — SIEM export + integrity verify (B-Audit card)
    audit_p = subparsers.add_parser(
        "audit",
        help="Export audit trail and verify integrity",
    )
    audit_sub = audit_p.add_subparsers(dest="audit_cmd", required=True)

    audit_export = audit_sub.add_parser(
        "export",
        help="Export audit events in JSONL or CEF for SIEM ingest",
    )
    audit_export.add_argument("project_path", nargs="?", default=".")
    audit_export.add_argument("--format", choices=["jsonl", "cef"], default="jsonl")
    audit_export.add_argument("--category", help="Filter by category (substring)")
    audit_export.add_argument("--action", help="Filter by action (substring)")
    audit_export.add_argument("--actor", help="Filter by actor (substring)")
    audit_export.add_argument("--since", help="ISO-8601 lower bound on timestamp")
    audit_export.add_argument("--until", help="ISO-8601 upper bound on timestamp")
    audit_export.add_argument(
        "-o",
        "--output",
        help="Write to a file instead of stdout",
    )
    audit_export.set_defaults(func=cmd_audit_export)

    audit_verify = audit_sub.add_parser(
        "verify",
        help="Verify audit log hash chain integrity",
    )
    audit_verify.add_argument("project_path", nargs="?", default=".")
    audit_verify.add_argument("--json", "-j", action="store_true")
    audit_verify.set_defaults(func=cmd_audit_verify)

    # memory command group — namespace controls over learned memory (PRD 4)
    memory_p = subparsers.add_parser(
        "memory",
        help="Inspect, reset, export, or import learned synapse memory by namespace",
    )
    memory_sub = memory_p.add_subparsers(dest="memory_cmd", required=True)

    mem_inspect = memory_sub.add_parser(
        "inspect", help="Show learned memory contribution by namespace"
    )
    mem_inspect.add_argument("project_path", nargs="?", default=".")
    mem_inspect.add_argument("--namespace", help="Limit output to one namespace")
    mem_inspect.add_argument("--json", "-j", action="store_true")
    mem_inspect.set_defaults(func=cmd_memory)

    mem_reset = memory_sub.add_parser(
        "reset", help="Clear ONE namespace without touching the index or other namespaces"
    )
    mem_reset.add_argument("project_path", nargs="?", default=".")
    mem_reset.add_argument(
        "--namespace",
        required=True,
        help="Namespace to clear (personal, shared, ephemeral, branch:<name>)",
    )
    mem_reset.add_argument("--json", "-j", action="store_true")
    mem_reset.set_defaults(func=cmd_memory)

    mem_export = memory_sub.add_parser(
        "export", help="Export a namespace as a portable, versioned JSON bundle"
    )
    mem_export.add_argument("project_path", nargs="?", default=".")
    mem_export.add_argument(
        "--namespace", help="Namespace to export (default: the active namespace)"
    )
    mem_export.add_argument("-o", "--output", help="Write the bundle to a file (default: stdout)")
    mem_export.set_defaults(func=cmd_memory)

    mem_import = memory_sub.add_parser(
        "import", help="Validate a bundle and merge it into a namespace"
    )
    mem_import.add_argument("file", help="Bundle JSON produced by `neuralmind memory export`")
    mem_import.add_argument(
        "--project-path", dest="project_path", default=".", help="Project root (default: .)"
    )
    mem_import.add_argument(
        "--namespace",
        help="Target namespace (default: the bundle's own namespace, e.g. 'shared')",
    )
    mem_import.add_argument("--json", "-j", action="store_true")
    mem_import.set_defaults(func=cmd_memory)

    mem_publish = memory_sub.add_parser(
        "publish",
        help="Write the project's learned memory to the committed team bundle "
        "(.neuralmind-team-memory.json) so teammates' agents inherit it",
    )
    mem_publish.add_argument("project_path", nargs="?", default=".")
    mem_publish.add_argument("--json", "-j", action="store_true")
    mem_publish.set_defaults(func=cmd_memory)

    mem_review_list = memory_sub.add_parser(
        "review-list",
        help="Show edges pending operator review before entering the shared namespace",
    )
    mem_review_list.add_argument("project_path", nargs="?", default=".")
    mem_review_list.add_argument("--json", "-j", action="store_true")
    mem_review_list.set_defaults(func=cmd_memory)

    mem_review_approve = memory_sub.add_parser(
        "review-approve",
        help="Approve an edge from the pending review queue, promoting it to shared",
    )
    mem_review_approve.add_argument("source", help="Edge source node")
    mem_review_approve.add_argument("target", help="Edge target node")
    mem_review_approve.add_argument("project_path", nargs="?", default=".")
    mem_review_approve.add_argument("--json", "-j", action="store_true")
    mem_review_approve.set_defaults(func=cmd_memory)

    mem_review_reject = memory_sub.add_parser(
        "review-reject",
        help="Reject an edge from the pending review queue, dropping it",
    )
    mem_review_reject.add_argument("source", help="Edge source node")
    mem_review_reject.add_argument("target", help="Edge target node")
    mem_review_reject.add_argument("project_path", nargs="?", default=".")
    mem_review_reject.add_argument("--json", "-j", action="store_true")
    mem_review_reject.set_defaults(func=cmd_memory)

    mem_staleness_scan = memory_sub.add_parser(
        "staleness-scan",
        help="Detect stale team edges past the reinforcement threshold",
    )
    mem_staleness_scan.add_argument("project_path", nargs="?", default=".")
    mem_staleness_scan.add_argument(
        "--namespace", default="shared", help="Namespace to scan (default: shared)"
    )
    mem_staleness_scan.add_argument("--json", "-j", action="store_true")
    mem_staleness_scan.set_defaults(func=cmd_memory)

    mem_staleness_run = memory_sub.add_parser(
        "staleness-run",
        help="Run a staleness pass: flag and decay stale team edges",
    )
    mem_staleness_run.add_argument("project_path", nargs="?", default=".")
    mem_staleness_run.add_argument(
        "--namespace", default="shared", help="Namespace to target (default: shared)"
    )
    mem_staleness_run.add_argument("--json", "-j", action="store_true")
    mem_staleness_run.set_defaults(func=cmd_memory)

    # Ingest CMMC command — load compliance practices into the graph
    ingest_cmmc_p = subparsers.add_parser(
        "ingest-cmmc",
        help="Ingest CMMC practice registry as first-class content nodes in the code graph",
    )
    ingest_cmmc_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    ingest_cmmc_p.add_argument(
        "--registry",
        default=None,
        help="Path to CMMC practices registry JSON file",
    )
    ingest_cmmc_p.set_defaults(func=cmd_ingest_cmmc)

    # Init-hook command
    init_parser = subparsers.add_parser(
        "init-hook", help="Initialize Git post-commit hook for auto-updates"
    )
    init_parser.add_argument(
        "project_path",
        type=str,
        nargs="?",
        default=".",
        help="Path to the project (defaults to current directory)",
    )
    init_parser.set_defaults(func=cmd_init_hook)

    # init command — one-command setup: scan → build graph → embed → watch
    init_p = subparsers.add_parser(
        "init",
        help="One-command NeuralMind setup: scan languages, build graph, "
        "create embeddings, and optionally start the file watcher",
    )
    init_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    init_p.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force rebuild, regenerating all embeddings",
    )
    init_p.add_argument(
        "--no-watch",
        action="store_true",
        help="Skip launching the file watcher after setup",
    )
    init_p.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output build stats as JSON",
    )
    init_p.set_defaults(func=cmd_init)

    # Export command — auditor-ready CSV or PDF reports
    export_p = subparsers.add_parser(
        "export",
        help="Export NeuralMind state as auditor-ready CSV or PDF",
    )
    export_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    export_p.add_argument(
        "--format",
        choices=["csv", "pdf"],
        default="csv",
        help="Export format (default: csv)",
    )
    export_p.add_argument(
        "--output",
        default=None,
        help="Output file path (default: neuralmind_export.csv or neuralmind_export.pdf)",
    )
    export_p.add_argument(
        "--controls",
        action="store_true",
        help="Export compliance-control-to-code mappings (CSV only)",
    )
    export_p.add_argument(
        "--nodes",
        action="store_true",
        help="Export all nodes with metadata (CSV only)",
    )
    export_p.add_argument(
        "--report",
        choices=["ssp"],
        default="ssp",
        help="Report type for PDF export (default: ssp)",
    )
    export_p.add_argument("--json", "-j", action="store_true")
    export_p.set_defaults(func=cmd_export)

    # CI check command — compliance-aware diff analysis for pipelines
    ci_p = subparsers.add_parser(
        "ci-check",
        help="Run compliance-aware CI check against a git diff",
    )
    ci_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    ci_p.add_argument(
        "--framework",
        default="all",
        help="Compliance framework to check (cmmc, nist, sox, hipaa, or all)",
    )
    ci_p.add_argument(
        "--diff",
        default="HEAD",
        help="Git ref to diff against (default: HEAD for uncommitted changes)",
    )
    ci_p.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with non-zero status when compliance warnings exist",
    )
    ci_p.add_argument("--json", "-j", action="store_true")
    ci_p.set_defaults(func=cmd_ci_check)

    # Skeleton command — graph-backed compact view of a file
    skel_p = subparsers.add_parser(
        "skeleton",
        help="Show compact graph-backed skeleton of a file (functions, rationales, call graph)",
    )
    skel_p.add_argument("file_path", help="File to show skeleton for")
    skel_p.add_argument(
        "--project-path",
        default=".",
        help="Project root (default: current directory)",
    )
    skel_p.add_argument("--json", "-j", action="store_true")
    skel_p.set_defaults(func=cmd_skeleton)

    # Why command — recall decision provenance for a symbol / question
    why_p = subparsers.add_parser(
        "why",
        help="Recall the recorded rationale (Decision: trailers) behind code",
    )
    why_p.add_argument("query", help="Symbol or question, e.g. 'why is resolveOrgId per-handler'")
    why_p.add_argument(
        "--project-path",
        default=".",
        help="Project root (default: current directory)",
    )
    why_p.set_defaults(func=cmd_why)

    # Gaps command — endpoints tested only in mock mode (no live-DB coverage)
    gaps_p = subparsers.add_parser(
        "gaps",
        help="Find endpoints tested only in mock mode (live-DB coverage gaps)",
    )
    gaps_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root to scan (default: current directory)",
    )
    gaps_p.add_argument(
        "--structural",
        action="store_true",
        help="Use structural gap detection (betweenness centrality + bridge analysis)",
    )
    gaps_p.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        help="Betweenness threshold for structural gaps (default: 0.1)",
    )
    gaps_p.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Max results for structural gaps (default: 10)",
    )
    gaps_p.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output in JSON format",
    )
    gaps_p.set_defaults(func=cmd_gaps)

    # Compliance command — detect annotations and reinforce synapses
    comp_p = subparsers.add_parser(
        "compliance",
        help="Scan for compliance annotations (CMMC, NIST, SOX, HIPAA) in code comments",
    )
    comp_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    comp_p.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode: live-detect annotations as files change and reinforce synapses",
    )
    comp_p.add_argument("--json", "-j", action="store_true")
    comp_p.set_defaults(func=cmd_compliance)

    # Structural command — typed structural neighbors (calls/inherits/imports)
    struct_p = subparsers.add_parser(
        "structural",
        help="Show how a symbol is wired: callers, callees, base/sub classes, importers",
    )
    struct_p.add_argument("symbol", help="Symbol name or NL description; resolved to a graph node")
    struct_p.add_argument(
        "--relation",
        choices=["calls", "inherits", "imports", "contains", "all"],
        default=None,
        help="Limit to one relation (default: callers/callees/bases/subclasses/importers)",
    )
    struct_p.add_argument(
        "--blast-radius",
        dest="blast_radius",
        action="store_true",
        help="Show the transitive reverse-dependency set (what a change would affect)",
    )
    struct_p.add_argument(
        "--depth", type=int, default=2, help="Blast-radius hop depth (default: 2)"
    )
    struct_p.add_argument(
        "--project-path",
        default=".",
        help="Project root (default: current directory)",
    )
    struct_p.add_argument("--json", "-j", action="store_true")
    struct_p.set_defaults(func=cmd_structural)

    # watch command — run the file activity → synapse co-activation daemon
    watch_p = subparsers.add_parser(
        "watch",
        help="Watch the project for edits and feed co-activations into the synapse store",
    )
    watch_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    watch_p.add_argument(
        "--debounce",
        type=float,
        default=0.75,
        help="Seconds to wait before grouping edits into one batch (default: 0.75)",
    )
    watch_p.add_argument(
        "--decay-interval",
        type=float,
        default=600.0,
        help="Seconds between decay ticks; 0 disables periodic decay (default: 600)",
    )
    watch_p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-batch logging",
    )
    watch_p.add_argument(
        "--reindex",
        action="store_true",
        help="Incrementally re-index edited files into the built-in graph as they "
        "change (re-parses just those files, re-embeds only their nodes)",
    )
    watch_p.set_defaults(func=cmd_watch)

    # team command — Tier 2 Team administration (governance, seats, license, audit)
    # Wired via tier2.cli.build_team_subparsers to keep tier2 code isolated.
    try:
        from neuralmind.tier2.cli import build_team_subparsers

        build_team_subparsers(subparsers)
    except ImportError:
        # tier2 package not available — team commands silently absent
        pass

    # serve command — local graph-view UI (Obsidian-style)
    serve_p = subparsers.add_parser(
        "serve",
        help="Start the local graph-view UI (Obsidian-style graph of your code + synapses)",
    )
    serve_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    serve_p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind (default: 127.0.0.1)",
    )
    serve_p.add_argument(
        "--port",
        type=int,
        default=8787,
        help="Port to bind (default: 8787)",
    )
    serve_p.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open a browser window",
    )
    serve_p.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable the per-session access token. Use only on trusted hosts.",
    )
    serve_p.add_argument(
        "--editor",
        default=None,
        help="Editor command for 'open in editor' clicks (defaults to $EDITOR/$VISUAL). "
        "Examples: 'code', 'cursor', 'vim', 'subl', 'code -n'.",
    )
    serve_p.set_defaults(func=cmd_serve)

    daemon_p = subparsers.add_parser(
        "daemon",
        help="Manage the local NeuralMind daemon (warm state for fast repeat queries)",
    )
    daemon_p.add_argument(
        "action",
        choices=["start", "stop", "restart", "status"],
        help="start (background), stop, restart, or status",
    )
    daemon_p.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    daemon_p.add_argument("--port", type=int, default=8787, help="Port to bind (default: 8787)")
    daemon_p.add_argument(
        "--foreground",
        action="store_true",
        help="Run in the foreground instead of detaching (start/restart only)",
    )
    daemon_p.add_argument("--json", "-j", action="store_true")
    daemon_p.set_defaults(func=cmd_daemon)

    # demo command — runs against bundled sample_project, no git checkout needed
    demo_p = subparsers.add_parser(
        "demo",
        help="Run the 30-second NeuralMind demo against the bundled sample project",
    )
    demo_p.add_argument(
        "--keep",
        action="store_true",
        help="Keep the working copy directory after the demo finishes (for inspection)",
    )
    demo_p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress preamble logging (still prints the report)",
    )
    demo_p.set_defaults(func=cmd_demo)

    # last command — recovery cache for the most recent compressed bash output
    last_p = subparsers.add_parser(
        "last",
        help="Print the last bash output the PostToolUse hook cached "
        "(recover dropped content without re-running)",
    )
    last_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root containing .neuralmind/last_output.json (default: current dir)",
    )
    last_p.add_argument("--json", "-j", action="store_true")
    last_p.set_defaults(func=cmd_last)

    # install-hooks command — Claude Code PostToolUse integration
    hooks_p = subparsers.add_parser(
        "install-hooks",
        help="Install/uninstall Claude Code PostToolUse compression hooks",
    )
    hooks_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (used when --global not set). Default: current dir",
    )
    hooks_p.add_argument(
        "--global",
        dest="global_",
        action="store_true",
        help="Install hooks in ~/.claude/settings.json (affects all projects)",
    )
    hooks_p.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove neuralmind hooks, preserve other hooks",
    )
    hooks_p.set_defaults(func=cmd_install_hooks)

    # install-mcp command — register the MCP server with AI coding agents
    mcp_p = subparsers.add_parser(
        "install-mcp",
        help="Register the NeuralMind MCP server with Claude Code / Cursor / Cline / Claude Desktop",
    )
    mcp_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root for project-scoped clients (default: current dir)",
    )
    mcp_p.add_argument(
        "--client",
        choices=("claude-code", "cursor", "cline", "claude-desktop", "vscode"),
        default="claude-code",
        help="Which client to register with (default: claude-code)",
    )
    mcp_p.add_argument(
        "--all",
        action="store_true",
        help="Register with every detected client (auto-detect installed agents)",
    )
    mcp_p.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="Print the config snippet to paste manually instead of writing files",
    )
    mcp_p.set_defaults(func=cmd_install_mcp)

    # Internal hook runtime (invoked by Claude Code, not user-facing)
    hook_p = subparsers.add_parser(
        "_hook",
        help=argparse.SUPPRESS,  # hidden from --help
    )
    hook_p.add_argument(
        "action",
        choices=[
            "compress-read",
            "compress-bash",
            "cap-search",
            "offload",
            "edit-activity",
            "session-start",
            "prompt-submit",
            "pre-compact",
        ],
    )
    hook_p.set_defaults(func=cmd_hook)

    # optimize-docs command — evolve JSDoc for undocumented methods
    opt_docs_p = subparsers.add_parser(
        "optimize-docs",
        help="Evolve JSDoc for undocumented methods to maximize retrieval fitness",
    )
    opt_docs_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    opt_docs_p.add_argument(
        "--blind-spots",
        default=None,
        help="Path to pre-computed blind spot list (JSON format)",
    )
    opt_docs_p.add_argument(
        "--generations",
        type=int,
        default=None,
        help="Max generations per blind spot (default: 5)",
    )
    opt_docs_p.add_argument(
        "--population",
        type=int,
        default=None,
        help="Population size per generation (default: 5)",
    )
    opt_docs_p.add_argument(
        "--hysteresis",
        type=float,
        default=None,
        help="Promotion hysteresis margin (default: 0.05)",
    )
    opt_docs_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be evolved without patching source files",
    )
    opt_docs_p.add_argument("--json", "-j", action="store_true")
    opt_docs_p.set_defaults(func=cmd_optimize_docs)

    # risks command — type-risk compliance report
    risks_p = subparsers.add_parser(
        "risks",
        help="Show type-risk signals from static type verification (compliance)",
    )
    risks_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    risks_p.add_argument(
        "--type",
        action="store_true",
        default=True,
        help="Show type-related risks (default)",
    )
    risks_p.add_argument(
        "--min-severity",
        choices=["info", "warn", "high"],
        default="info",
        help="Minimum severity to report (default: info)",
    )
    risks_p.add_argument("--json", "-j", action="store_true")
    risks_p.set_defaults(func=cmd_risks)

    # license command — issue, renew, revoke, status
    license_p = subparsers.add_parser(
        "license",
        help="Manage Team licenses (issue, renew, revoke, status)",
    )
    license_sub = license_p.add_subparsers(dest="license_command")

    issue_lp = license_sub.add_parser("issue", help="Issue a new Team license")
    issue_lp.add_argument("--customer", required=True, help="Customer name")
    issue_lp.add_argument("--seats", type=int, required=True, help="Number of seats")
    issue_lp.add_argument(
        "--term", type=int, required=True, choices=[1, 3, 6, 12, 24, 36], help="Term in months"
    )
    issue_lp.add_argument("--partner", default=None, help="Partner ID")
    issue_lp.add_argument("--output", default=None, help="Output path for license file")
    issue_lp.set_defaults(func=cmd_license_issue)

    renew_lp = license_sub.add_parser("renew", help="Renew an existing license")
    renew_lp.add_argument("--customer", required=True, help="Customer name")
    renew_lp.add_argument(
        "--term", type=int, required=True, choices=[1, 3, 6, 12, 24, 36], help="Term in months"
    )
    renew_lp.set_defaults(func=cmd_license_renew)

    revoke_lp = license_sub.add_parser("revoke", help="Revoke a license")
    revoke_lp.add_argument("--customer", required=True, help="Customer name")
    revoke_lp.add_argument("--reason", required=True, help="Revocation reason")
    revoke_lp.set_defaults(func=cmd_license_revoke)

    status_lp = license_sub.add_parser("status", help="Show license status")
    status_lp.add_argument("--customer", required=True, help="Customer name")
    status_lp.set_defaults(func=cmd_license_status)

    list_lp = license_sub.add_parser("list", help="List all licenses")
    list_lp.add_argument("--partner", default=None, help="Filter by partner ID")
    list_lp.set_defaults(func=cmd_license_list)

    # partner command — add, list, licenses
    partner_p = subparsers.add_parser(
        "partner",
        help="Manage partners (resellers)",
    )
    partner_sub = partner_p.add_subparsers(dest="partner_command")

    add_pp = partner_sub.add_parser("add", help="Add a new partner")
    add_pp.add_argument("--name", required=True, help="Partner name")
    add_pp.add_argument("--commission", type=float, required=True, help="Commission percent (0-50)")
    add_pp.add_argument("--email", required=True, help="Contact email")
    add_pp.set_defaults(func=cmd_partner_add)

    list_pp = partner_sub.add_parser("list", help="List all partners")
    list_pp.set_defaults(func=cmd_partner_list)

    plic_pp = partner_sub.add_parser("licenses", help="List partner's licenses")
    plic_pp.add_argument("--partner", required=True, help="Partner ID")
    plic_pp.set_defaults(func=cmd_partner_licenses)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    try:
        args.func(args)
    except GraphNotBuiltError as e:
        # Turn the "no graph yet" failure into a readable setup hint instead
        # of a stack trace. `neuralmind doctor` gives the full picture.
        print(f"\n{e}\n", file=sys.stderr)
        print("Run `neuralmind doctor` to check your setup.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
