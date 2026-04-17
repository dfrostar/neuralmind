#!/usr/bin/env python3
"""
cli.py - NeuralMind Command Line Interface
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neuralmind.core import NeuralMind, create_mind


def cmd_build(args):
    project_path = args.project_path or "."
    force = args.force
    print(f"Building NeuralMind index for: {project_path}")
    print(f"Force rebuild: {force}")
    print()
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
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Project: {result['project']}")
        print(f"Wake-up tokens: {result['wakeup_tokens']}")
        print(f"Avg query tokens: {result['avg_query_tokens']}")
        print(f"Avg reduction: {result['avg_reduction_ratio']}x")
        print(f"Summary: {result['summary']}")


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
    parser = argparse.ArgumentParser(description="NeuralMind - Adaptive Neural Knowledge System")
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

    bench_p = subparsers.add_parser("benchmark", help="Run benchmark")
    bench_p.add_argument("project_path")
    bench_p.add_argument("--json", "-j", action="store_true")
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

    
    # Init-hook command
    init_parser = subparsers.add_parser("init-hook", help="Initialize Git post-commit hook for auto-updates")
    init_parser.add_argument(
        "project_path",
        type=str,
        nargs="?",
        default=".",
        help="Path to the project (defaults to current directory)",
    )
    init_parser.set_defaults(func=cmd_init_hook)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
