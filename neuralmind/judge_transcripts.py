# neuralmind/judge_transcripts.py — judge transcript loader + generator (PRD 2 D3).
#
# D3 closes the "empty bench/public/judge/ directory" gap. This module:
# 1. Loads + validates existing judge transcripts
# 2. Generates new offline transcripts from the benchmark_queries fixtures
#    (no API cost — derives reference answers from expected_facts)
# 3. Provides a CLI: python -m neuralmind.judge_transcripts --generate
#
# The offline transcripts complement the opt-in LLM-judged arm
# (neuralmind benchmark --public --judge, requires ANTHROPIC_API_KEY).

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
JUDGE_DIR = REPO_ROOT / "bench" / "public" / "judge"
BENCHMARK_DIR = REPO_ROOT / "tests" / "fixtures"

# --------------------------------------------------------------------------- #
# Loading + validation
# --------------------------------------------------------------------------- #


def load_transcript(path: Path) -> dict:
    """Load one judge transcript JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("query", "reference_answer"):
        if key not in data:
            raise ValueError(f"{path.name}: missing required field {key!r}")
    return data


def load_all_transcripts() -> list[dict]:
    """Load every transcript in bench/public/judge/."""
    transcripts = []
    for path in sorted(JUDGE_DIR.glob("*.json")):
        if path.name == "manifest.json":
            continue
        try:
            transcripts.append(load_transcript(path))
        except ValueError as exc:
            log.warning("Skipping %s: %s", path.name, exc)
    return transcripts


def validate_transcript(t: dict) -> list[str]:
    """Return a list of issues (empty = valid)."""
    issues = []
    if not t.get("query", "").strip():
        issues.append("empty query")
    if not t.get("reference_answer", "").strip():
        issues.append("empty reference_answer")
    if "expected_facts" in t:
        for i, f in enumerate(t["expected_facts"]):
            if not f.get("fact", "").strip():
                issues.append(f"expected_facts[{i}]: empty fact")
    return issues


# --------------------------------------------------------------------------- #
# Offline generation from benchmark fixtures
# --------------------------------------------------------------------------- #


def generate_transcript_from_benchmark(benchmark_path: Path) -> list[dict]:
    """Generate offline judge transcripts from a benchmark_queries fixture.

    Uses expected_facts as the gold standard (no LLM cost). Each query becomes
    one transcript. Reference answer is synthesized from the expected_facts.
    """
    try:
        data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Failed to read %s: %s", benchmark_path.name, exc)
        return []

    language = data.get("language", benchmark_path.stem.replace("benchmark_queries_", ""))
    queries = data.get("queries", [])
    transcripts = []

    for q in queries:
        facts = q.get("expected_facts", [])
        if not facts:
            # No gold facts — skip this query for offline generation
            continue

        # Synthesize a reference answer from the expected facts
        fact_texts = [f["fact"] for f in facts if f.get("fact")]
        if fact_texts:
            reference_answer = " ".join(fact_texts)
        else:
            continue

        transcript = {
            "query": q["question"],
            "reference_answer": reference_answer,
            "source_files": [
                f"{data.get('fixture', '')}/{mod}"
                for mod in q.get("expected_modules", [])
            ],
            "category": q.get("category", "architecture"),
            "language": language,
            "query_id": q.get("id", ""),
        }
        transcripts.append(transcript)

    return transcripts


def generate_all_transcripts() -> dict[str, list[dict]]:
    """Generate transcripts from all benchmark fixtures. Returns {language: [transcripts]}."""
    results = {}
    for path in sorted(BENCHMARK_DIR.glob("benchmark_queries_*.json")):
        language = path.stem.replace("benchmark_queries_", "")
        transcripts = generate_transcript_from_benchmark(path)
        if transcripts:
            results[language] = transcripts
    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    """Commands: --generate, --list, --validate"""
    parser = argparse.ArgumentParser(description="NeuralMind judge transcripts (D3)")
    parser.add_argument("--list", action="store_true", help="List existing transcripts")
    parser.add_argument("--validate", action="store_true", help="Validate all transcripts")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate offline transcripts from benchmark fixtures",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write generated transcripts to bench/public/judge/",
    )
    args = parser.parse_args(argv)

    if args.list:
        transcripts = load_all_transcripts()
        print(f"{len(transcripts)} transcripts in {JUDGE_DIR}")
        for t in transcripts:
            lang = t.get("language", "?")
            print(f"  [{lang}] {t['query'][:60]}...")
        return 0

    if args.validate:
        transcripts = load_all_transcripts()
        issues = 0
        for t in transcripts:
            t_issues = validate_transcript(t)
            if t_issues:
                issues += len(t_issues)
                print(f"  [WARN] {t['query'][:40]}...: {t_issues}")
        if issues == 0:
            print(f"All {len(transcripts)} transcripts valid.")
            return 0
        print(f"{issues} issues found.")
        return 1

    if args.write:
        results = generate_all_transcripts()
        written = 0
        for language, transcripts in sorted(results.items()):
            for t in transcripts:
                qid = t.get("query_id") or f"q{written:03d}"
                out = JUDGE_DIR / f"{language}_{qid}.json"
                out.write_text(json.dumps(t, indent=2) + "\n", encoding="utf-8")
                written += 1
        print(f"Wrote {written} transcripts.")
        return 0

    if args.generate:
        results = generate_all_transcripts()
        for language, transcripts in sorted(results.items()):
            print(f"  {language}: {len(transcripts)} transcripts")
        total = sum(len(v) for v in results.values())
        print(f"  TOTAL: {total} transcripts (dry run — use --write to save)")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
