#!/usr/bin/env python3
"""
cli.py - NeuralMind Command Line Interface
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neuralmind import memory
from neuralmind.core import GraphNotBuiltError, NeuralMind, create_mind


def cmd_build(args):
    project_path = args.project_path or "."
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

    mind = NeuralMind(project_path)
    result = mind.build(force=force)
    if result.get("success"):
        print("Build successful!")
        print(f"   Project: {result.get('project')}")
        print(f"   Nodes: {result.get('nodes_total')}")
        print(f"   Communities: {result.get('communities')}")
        print(f"   Duration: {result.get('duration_seconds')}s")
    else:
        print(f"Build failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


def cmd_query(args):
    _maybe_prompt_for_memory_opt_in()
    mind = create_mind(args.project_path, auto_build=True)
    result = mind.query(args.question)
    if args.json:
        output = {
            "query": args.question,
            "tokens": result.budget.total,
            "reduction_ratio": round(result.reduction_ratio, 1),
            "layers": result.layers_used,
            "context": result.context,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Query: {args.question}")
        print(f"Tokens: {result.budget.total} ({result.reduction_ratio:.1f}x reduction)")
        print("=" * 60)
        print(result.context)
        print("=" * 60)


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
    if args.json:
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


def cmd_benchmark(args):
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
        f"  Est. $ saved/mo  :  ~${monthly_saved:,.2f}"
        f"  (Claude 3.5 Sonnet input, 100 queries/day)"
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
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"Project: {stats.get('project')}")
        print(f"Built: {stats.get('built')}")
        if stats.get("built"):
            print(f"Nodes: {stats.get('total_nodes', 0)}")


def cmd_doctor(args):
    """Diagnose a project's NeuralMind setup and print actionable fixes."""
    from neuralmind import doctor

    checks = doctor.run_diagnostics(args.project_path)
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

    if status == doctor.FAIL:
        sys.exit(1)


def cmd_eval(args):
    """Run the faithfulness eval: does NeuralMind's selected context contain
    more gold facts than a matched-budget naive baseline?

    Self-evaluates against the committed reference fixture + gold-fact set,
    which ship with the *source* repository (the ``evals/`` package), so this
    is a quality self-test like ``neuralmind benchmark`` — not a per-repo
    command. The A/B needs the retrieval stack + a built index; ``--selfcheck``
    validates the gold set and offline scorer with no heavy deps.
    """
    try:
        from evals.faithfulness import harness, runner
    except ImportError:
        print(
            "neuralmind eval runs against the faithfulness gold set that ships "
            "with the source repository (the `evals/` package), not the installed "
            "wheel. Clone the repo and run "
            "`python -m evals.faithfulness.runner --run` from its root.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.selfcheck:
        sys.exit(runner.main(["--selfcheck"]))

    try:
        report = harness.run_and_report(args.project_path)
    except RuntimeError as exc:
        print(f"faithfulness A/B unavailable: {exc}", file=sys.stderr)
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
    ranked = store.next_likely(args.from_node, top_k=args.n) if store else []
    if args.json:
        print(
            json.dumps(
                {
                    "from_node": args.from_node,
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


def cmd_learn(args):
    project_path = Path(args.project_path).resolve()
    if memory.is_learning_disabled():
        print("Learning is disabled (NEURALMIND_LEARNING=0). No-op.")
        return

    # Count events
    events_file = memory.project_query_events_file(project_path)
    project_event_count = memory.count_events(events_file)

    if project_event_count == 0:
        print(f"No query events found for {project_path}")
        print("Events are logged automatically when you query the codebase.")
        return

    # Read and analyze events
    events = memory.read_query_events(events_file)
    if not events:
        print("No queryable events found in memory.")
        return

    # Build patterns
    print(f"Analyzing {len(events)} query events...")
    index = memory.build_cooccurrence_index(events)

    # Write patterns
    patterns_file = memory.write_learned_patterns(project_path, index)

    # Report results
    print(f"✓ Learned {index['metadata']['patterns_learned']} cooccurrence patterns")
    print(f"✓ Patterns saved to {patterns_file}")
    print("✓ Next query will apply learned patterns for improved retrieval")

    # Show top patterns
    cooccurrence = index["cooccurrence"]
    if cooccurrence:
        print("\nTop cooccurrence patterns:")
        sorted_pairs = sorted(cooccurrence.items(), key=lambda x: x[1], reverse=True)
        for pair, count in sorted_pairs[:5]:
            print(f"  {pair}: {count} times")


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

    watcher = FileActivityWatcher(path, on_batch, debounce=debounce)
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
            print("  PostToolUse hooks active: compress-read, compress-bash, cap-search")
            print("  Run `neuralmind install-hooks --uninstall` to remove.")
            print("  Set NEURALMIND_BYPASS=1 env var to disable compression temporarily.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_hook(args):
    """Internal: runtime entrypoint invoked by Claude Code hooks."""
    from .hooks import run_hook

    sys.exit(run_hook(args.action))


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
            f"Error: .git/hooks directory not found in {project_path}. "
            "Are you in a Git repository?"
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


def main():
    parser = argparse.ArgumentParser(
        description=(
            "NeuralMind — reduce Claude/GPT/Gemini token costs 40-70x on code questions. "
            "Local semantic codebase index + MCP server + PostToolUse compression hooks "
            "for Claude Code, Cursor, Cline, and Continue."
        ),
        epilog=(
            "Quick start: `neuralmind wakeup .` · docs: https://github.com/dfrostar/neuralmind"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    build_p = subparsers.add_parser("build", help="Build neural knowledge base")
    build_p.add_argument("project_path", nargs="?", default=".")
    build_p.add_argument("--force", "-f", action="store_true")
    build_p.set_defaults(func=cmd_build)

    query_p = subparsers.add_parser("query", help="Query the knowledge base")
    query_p.add_argument("project_path")
    query_p.add_argument("question")
    query_p.add_argument("--json", "-j", action="store_true")
    query_p.set_defaults(func=cmd_query)

    wakeup_p = subparsers.add_parser("wakeup", help="Get wake-up context")
    wakeup_p.add_argument("project_path")
    wakeup_p.add_argument("--json", "-j", action="store_true")
    wakeup_p.set_defaults(func=cmd_wakeup)

    bench_p = subparsers.add_parser(
        "benchmark",
        help="Run benchmark on your project (supports --contribute for community submissions)",
    )
    bench_p.add_argument("project_path")
    bench_p.add_argument("--json", "-j", action="store_true")
    bench_p.add_argument(
        "--contribute",
        action="store_true",
        help="Emit a schema-ready JSON blob you can submit to the community benchmarks. "
        "No data is uploaded — you copy-paste the output into an issue or PR.",
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
    eval_p.set_defaults(func=cmd_eval)

    learn_p = subparsers.add_parser(
        "learn", help="Run continual learning scaffold (safe no-op for MVP)"
    )
    learn_p.add_argument("project_path")
    learn_p.set_defaults(func=cmd_learn)

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
    next_p.add_argument("--json", "-j", action="store_true")
    next_p.set_defaults(func=cmd_next)

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
        default=8765,
        help="Port to bind (default: 8765)",
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
            "session-start",
            "prompt-submit",
            "pre-compact",
        ],
    )
    hook_p.set_defaults(func=cmd_hook)

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
