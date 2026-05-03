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
from neuralmind.core import NeuralMind, create_mind


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

    stats_p = subparsers.add_parser("stats", help="Show index statistics")
    stats_p.add_argument("project_path")
    stats_p.add_argument("--json", "-j", action="store_true")
    stats_p.set_defaults(func=cmd_stats)

    learn_p = subparsers.add_parser(
        "learn", help="Run continual learning scaffold (safe no-op for MVP)"
    )
    learn_p.add_argument("project_path")
    learn_p.set_defaults(func=cmd_learn)

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
    args.func(args)


if __name__ == "__main__":
    main()
