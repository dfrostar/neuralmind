"""Render docs/community-benchmarks.json as a Markdown table.

Two modes:

- Default (stdout): print the Markdown table. Useful locally to preview.
- ``--inject README.md``: splice the table into README.md between the
  markers ``<!-- COMMUNITY-BENCHMARKS:START -->`` and
  ``<!-- COMMUNITY-BENCHMARKS:END -->``, preserving everything outside.
  The CI workflow uses this mode to auto-refresh the README when the
  JSON changes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = REPO_ROOT / "docs" / "community-benchmarks.json"
START_MARKER = "<!-- COMMUNITY-BENCHMARKS:START -->"
END_MARKER = "<!-- COMMUNITY-BENCHMARKS:END -->"


def render_table(entries: list[dict]) -> str:
    """Produce the Markdown table + footer line."""
    if not entries:
        return "_No community benchmarks yet — be the first!_\n"

    # Sort by reduction ratio, highest first. Keeps the table interesting
    # while remaining deterministic.
    entries = sorted(entries, key=lambda e: e.get("avg_reduction_ratio", 0), reverse=True)

    lines = [
        "| Project | Lang | Nodes | Wakeup | Avg Query | Reduction | Model | Submitted |",
        "|---------|------|------:|-------:|----------:|----------:|-------|-----------|",
    ]
    for e in entries:
        project = e["project_name"]
        if e.get("repo_url"):
            project = f"[{project}]({e['repo_url']})"
        wakeup = f"{e['avg_wakeup_tokens']:,}" if e.get("avg_wakeup_tokens") else "—"
        query = f"{e['avg_query_tokens']:,}" if e.get("avg_query_tokens") else "—"
        model = e.get("model", "—")
        submitter = f"[@{e['submitted_by']}](https://github.com/{e['submitted_by']}) · {e['date_submitted']}"
        lines.append(
            f"| {project} | {e['language']} | {e['nodes']:,} | {wakeup} | "
            f"{query} | **{e['avg_reduction_ratio']:.1f}×** | {model} | {submitter} |"
        )
    lines.append("")
    lines.append(
        f"_{len(entries)} submission(s). See the [JSON data]"
        f"(docs/community-benchmarks.json) for notes and verification commands._"
    )
    return "\n".join(lines)


def inject_into_readme(readme_path: Path, rendered: str) -> bool:
    """Splice the rendered table between the markers. Returns True if changed."""
    text = readme_path.read_text()
    if START_MARKER not in text or END_MARKER not in text:
        raise RuntimeError(
            f"README.md missing markers {START_MARKER} / {END_MARKER}. "
            "Add both markers around the Community Benchmarks table placeholder."
        )

    before, rest = text.split(START_MARKER, 1)
    _stale, after = rest.split(END_MARKER, 1)

    new_block = f"{START_MARKER}\n{rendered}\n{END_MARKER}"
    new_text = before + new_block + after
    if new_text == text:
        return False
    readme_path.write_text(new_text)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inject",
        metavar="FILE",
        help="Splice the table into FILE between the COMMUNITY-BENCHMARKS markers.",
    )
    args = parser.parse_args()

    data = json.loads(DATA_PATH.read_text())
    rendered = render_table(data.get("entries", []))

    if args.inject:
        target = Path(args.inject)
        if not target.is_absolute():
            target = REPO_ROOT / target
        changed = inject_into_readme(target, rendered)
        if changed:
            print(f"Updated {target}")
        else:
            print(f"{target} already up to date")
        return 0

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
