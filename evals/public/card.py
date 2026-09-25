"""Generate a shareable SVG result card from benchmark JSON output.

Usage:
    python -m evals.public.card --json --repo requests --out card.svg
    python -m evals.public.card --json --repo requests --out card.svg --share-text "My repo scored 45.7×"

The card is a self-contained SVG with embedded styling — no external dependencies.
It is designed to be posted on X, LinkedIn, Reddit, or embedded in a README.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def fmt_tokens(n: float) -> str:
    """Format token count: 41,729 → '41.7K', 913 → '913'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"


def fmt_pct(n: float) -> str:
    """Format ratio as percentage: 0.893 → '89.3%'."""
    return f"{n * 100:.1f}%"


def fmt_mrr(n: float) -> str:
    """Format MRR: 0.92 → '0.92'."""
    return f"{n:.2f}"


def fmt_ratio(n: float) -> str:
    """Format reduction ratio: 45.7 → '45.7×'."""
    return f"{n:.1f}×"


def generate_card(
    repo_name: str,
    commit: str,
    language: str,
    n_queries: int,
    nm_tokens: float,
    naive_tokens: float,
    nm_recall: float,
    nm_mrr: float,
    nm_found_rate: float,
    share_text: str | None = None,
) -> str:
    """Generate a self-contained SVG result card.

    Args:
        repo_name: Repository name (e.g., "requests")
        commit: Short commit SHA
        language: Programming language
        n_queries: Number of benchmark queries
        nm_tokens: NeuralMind mean tokens/query
        naive_tokens: Naive full-file mean tokens/query
        nm_recall: NeuralMind gold-file recall (0-1)
        nm_mrr: NeuralMind MRR (0-1)
        nm_found_rate: NeuralMind found rate (0-1)
        share_text: Optional custom share text

    Returns:
        Complete SVG string.
    """
    reduction = naive_tokens / nm_tokens if nm_tokens > 0 else 0

    # Card dimensions
    w, h = 1200, 630  # OG image ratio

    # Colors (matching neuralmind.uk theme)
    bg = "#0a0b0d"
    card_bg = "#111318"
    border = "#1e2126"
    text_white = "#ffffff"
    text_slate = "#94a3b8"
    text_faint = "#64748b"
    accent = "#00d4ff"  # electric blue
    accent_dim = "#0099bb"
    proton = "#00ff88"  # green for good metrics
    warn = "#fbbf24"  # yellow for medium
    bad = "#f87171"  # red for poor

    # Determine color based on recall
    if nm_recall >= 0.95:
        recall_color = proton
    elif nm_recall >= 0.85:
        recall_color = warn
    else:
        recall_color = bad

    # Determine color based on reduction
    if reduction >= 40:
        reduction_color = proton
    elif reduction >= 15:
        reduction_color = warn
    else:
        reduction_color = bad

    # Token bar widths (proportional, max 100%)
    max_tokens = max(naive_tokens, nm_tokens)
    naive_bar_w = 100.0
    nm_bar_w = (nm_tokens / max_tokens) * 100.0 if max_tokens > 0 else 0

    # Share text
    if share_text is None:
        share_text = (
            f"My {repo_name} codebase scored {fmt_ratio(reduction)} fewer tokens with NeuralMind"
        )

    # Build SVG
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="grad-accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{accent};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{proton};stop-opacity:1" />
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="{w}" height="{h}" fill="{bg}"/>

  <!-- Card background -->
  <rect x="40" y="40" width="{w - 80}" height="{h - 80}" rx="16" fill="{card_bg}" stroke="{border}" stroke-width="1"/>

  <!-- Header: NeuralMind branding -->
  <text x="80" y="110" font-family="system-ui, -apple-system, sans-serif" font-size="28" font-weight="700" fill="{text_white}">NeuralMind</text>
  <text x="80" y="140" font-family="system-ui, -apple-system, sans-serif" font-size="14" fill="{text_faint}">AI Coding Agent Memory</text>

  <!-- Repo info badge -->
  <rect x="80" y="165" width="280" height="32" rx="6" fill="{bg}" stroke="{border}" stroke-width="1"/>
  <text x="96" y="186" font-family="ui-monospace, monospace" font-size="13" fill="{text_slate}">{repo_name} · {language} · {n_queries} queries</text>

  <!-- Big number: Token reduction -->
  <text x="80" y="280" font-family="system-ui, -apple-system, sans-serif" font-size="72" font-weight="800" fill="url(#grad-accent)" filter="url(#glow)">{fmt_ratio(reduction)}</text>
  <text x="80" y="310" font-family="system-ui, -apple-system, sans-serif" font-size="16" fill="{text_slate}">fewer tokens vs pasting files</text>

  <!-- Token comparison bars -->
  <text x="80" y="360" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="{text_faint}">Naive: {fmt_tokens(naive_tokens)} tokens/query</text>
  <rect x="80" y="370" width="400" height="8" rx="4" fill="{text_faint}" opacity="0.3"/>
  <rect x="80" y="370" width="400" height="8" rx="4" fill="{text_faint}" opacity="0.3"/>

  <text x="80" y="410" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="{accent}">NeuralMind: {fmt_tokens(nm_tokens)} tokens/query</text>
  <rect x="80" y="420" width="{int(400 * nm_bar_w / 100)}" height="8" rx="4" fill="url(#grad-accent)"/>

  <!-- Metrics row -->
  <rect x="560" y="240" width="280" height="120" rx="12" fill="{bg}" stroke="{border}" stroke-width="1"/>
  <text x="580" y="280" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="{text_faint}">Gold-file recall</text>
  <text x="580" y="320" font-family="system-ui, -apple-system, sans-serif" font-size="36" font-weight="700" fill="{recall_color}">{fmt_pct(nm_recall)}</text>
  <text x="580" y="345" font-family="system-ui, -apple-system, sans-serif" font-size="12" fill="{text_faint}">found rate: {fmt_pct(nm_found_rate)}</text>

  <rect x="860" y="240" width="280" height="120" rx="12" fill="{bg}" stroke="{border}" stroke-width="1"/>
  <text x="880" y="280" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="{text_faint}">MRR (rank quality)</text>
  <text x="880" y="320" font-family="system-ui, -apple-system, sans-serif" font-size="36" font-weight="700" fill="{text_white}">{fmt_mrr(nm_mrr)}</text>
  <text x="880" y="345" font-family="system-ui, -apple-system, sans-serif" font-size="12" fill="{text_faint}">mean reciprocal rank</text>

  <!-- Share text -->
  <text x="80" y="500" font-family="system-ui, -apple-system, sans-serif" font-size="14" fill="{text_slate}" font-style="italic">"{share_text}"</text>

  <!-- CTA -->
  <rect x="80" y="530" width="320" height="40" rx="8" fill="url(#grad-accent)"/>
  <text x="240" y="556" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="600" fill="{bg}" text-anchor="middle">Run it yourself →</text>

  <!-- Footer -->
  <text x="80" y="600" font-family="system-ui, -apple-system, sans-serif" font-size="11" fill="{text_faint}">neuralmind.uk/benchmark · reproducible · no cherry-picking · every miss published</text>
</svg>"""

    return svg  # noqa: RET504


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a shareable SVG result card")
    parser.add_argument("--json", action="store_true", help="Read JSON from stdin")
    parser.add_argument("--repo", type=str, help="Run benchmark for a single repo")
    parser.add_argument("--out", type=str, default="card.svg", help="Output SVG path")
    parser.add_argument("--share-text", type=str, help="Custom share text")
    parser.add_argument("--seeds", type=int, default=1, help="Seed count")
    args = parser.parse_args()

    if args.json:
        # Read JSON from stdin
        data = json.load(sys.stdin)
    elif args.repo:
        # Run benchmark and capture JSON
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "evals.public.run",
                "--json",
                "--repo",
                args.repo,
                "--seeds",
                str(args.seeds),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        if result.returncode != 0:
            print(f"Benchmark failed: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(result.stdout)
    else:
        parser.error("Either --json or --repo is required")

    # Extract data from JSON
    repos = data.get("repos", [])
    if not repos:
        print("No repos in benchmark output", file=sys.stderr)
        sys.exit(1)

    # Use first repo (or aggregate if multiple)
    repo = repos[0]
    summary = repo.get("summary", {})
    nm = summary.get("neuralmind", {})
    naive = summary.get("full-file", {})

    svg = generate_card(
        repo_name=repo.get("name", "unknown"),
        commit=repo.get("commit", "unknown")[:8],
        language=repo.get("language", "unknown"),
        n_queries=repo.get("n_queries", 0),
        nm_tokens=nm.get("mean_tokens", 0),
        naive_tokens=naive.get("mean_tokens", 0),
        nm_recall=nm.get("mean_recall", 0),
        nm_mrr=nm.get("mean_mrr", 0),
        nm_found_rate=nm.get("found_rate", 0),
        share_text=args.share_text,
    )

    out_path = Path(args.out)
    out_path.write_text(svg, encoding="utf-8")
    print(f"Card written to {out_path}")

    # Also print share text for convenience
    share_text = (
        args.share_text
        or f"My {repo.get('name', 'unknown')} codebase scored {fmt_ratio(naive.get('mean_tokens', 0) / nm.get('mean_tokens', 1))} fewer tokens with NeuralMind"
    )
    print(f"\nShare text:\n{share_text}")
    print("\nX/Twitter share URL:")
    print(
        f"https://twitter.com/intent/tweet?text={share_text.replace(' ', '%20').replace('×', 'x')}"
    )


if __name__ == "__main__":
    main()
