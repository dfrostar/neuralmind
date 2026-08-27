"""Guard the marketing site's numeric claims against drift.

``tests/test_docs_claims.py`` scans the README, the docs site, and the
security guides — but **not** ``site/``, which is the surface most people
actually read. That gap let four different classes of drift ship at once:

- the same token-reduction figure attributed to three different repo sizes
  (241 nodes in one component, "1,486-node" in two others, neither of which
  is where the number came from),
- a transcription error of that figure (``63.6×`` for ``65.6×``) sitting one
  card away from the original,
- a query-latency number with no measurement behind it anywhere in the repo,
- a ``100%`` gold-file recall claim the current public benchmark contradicts
  (93.75% mean; ``click`` is 0.79), and the real name of a private client
  whose field report every doc deliberately anonymizes.

So this module enforces three rules:

1. **Ratio provenance** — every ``N×`` performance ratio on the high-traffic
   surfaces must be listed in ``site/claims.json`` with a source and a
   reproduction command. Small multipliers (< 2×) are exempt: those are decay
   coefficients and worked examples in the publications, not claims.
2. **No private names** — names on the manifest's ``private_names_never_publish``
   list must not appear anywhere under ``site/``.
3. **No absolute privacy claims** — the same ``FORBIDDEN`` patterns the docs
   guard uses, applied to the site too.

Stdlib-only, like the docs guard, so it runs without the full dep set.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tests.test_docs_claims import FORBIDDEN

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "site" / "src"
CLAIMS_FILE = REPO_ROOT / "site" / "claims.json"

# Surfaces where a bare ratio reads as a headline product claim. The
# publications and field-report pages carry their own inline provenance
# (and worked arithmetic), so they are checked for names and absolutes but
# not for ratio provenance.
RATIO_GATED = (
    "components/sections/*.tsx",
    "app/page.tsx",
    "app/layout.tsx",
)

# Registry manifests shipped to external indexes (Agent Zero's a0-plugins,
# and any future ClawHub/Hermes listing files at the repo root). They are read
# in other people's runtimes where none of our CI runs, which is exactly how
# plugin.yaml carried an unsourced "12-70×" — a blend of two drafts matching
# no measurement — until 2026-08-27. Gated for ratio provenance and absolutes
# alongside the site surfaces.
REGISTRY_MANIFESTS = ("plugin.yaml",)

# Ratios below this are never performance claims — they're decay weights,
# merge coefficients, and other worked math in the publications.
MIN_CLAIM_RATIO = 2.0

# className="..." holds Tailwind tokens, not prose. Strip it before scanning
# so `w-[100%]` and friends can't masquerade as claims.
CLASSNAME_RE = re.compile(r"className=(?:\"[^\"]*\"|'[^']*'|\{[^}]*\})", re.DOTALL)

# A page may legitimately *quote* a forbidden phrase in order to disown it —
# the effectiveness page lists "Zero code egress" under what NeuralMind does
# not claim. Mark those lines (or the line above) so the guard stays useful
# instead of being switched off wholesale.
ALLOW_MARKER = "claims-guard:allow"

# Any number immediately preceding a multiplication sign, including both
# endpoints of a range ("45–257×" yields 45 and 257).
RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[–—-]\s*(\d+(?:\.\d+)?)\s*×")
SINGLE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*×")

# "100% recall" in any word order within a short window. The public
# benchmark's mean is 93.75% and its per-repo floor is 0.79.
PERFECT_RECALL_RE = re.compile(
    r"100\s*%[^.<>{}]{0,40}?recall|recall[^.<>{}]{0,40}?100\s*%", re.IGNORECASE
)


# A ratio is only right in company with the repo it was measured on and the
# evidence level it carries. The shipped defect was not a wrong number — 65.6 is
# a real community submission — it was that number bolted to a "1,486-node
# production codebase" that appears in no dataset. Checking membership in a set
# of floats would have passed it, so these two patterns bind each occurrence to
# its context.
NODE_ATTR_RE = re.compile(r"([\d,]+)\s*-\s*node", re.IGNORECASE)
CI_GATED_RE = re.compile(
    r"CI[-\s]gated|gated in CI|recomputed by CI|produced by CI|asserted on every",
    re.IGNORECASE,
)
# "method reproducible, not CI-gated" is the copy doing its job — disclosing the
# evidence level rather than inflating it. A guard that fires on correct copy is
# worse than no guard, so a negated mention doesn't count as a claim.
NEGATION_RE = re.compile(r"\b(not|never|isn't|is not|rather than)\s*$", re.IGNORECASE)
# The site rounds ("~9,300-node" for a 9,293-node repo); a mis-attribution is
# off by orders of magnitude, never by a rounding step.
NODE_TOLERANCE = 0.02


def _claims() -> dict:
    return json.loads(CLAIMS_FILE.read_text(encoding="utf-8"))


def _allowed_ratios() -> set[float]:
    return {float(entry["value"]) for entry in _claims()["ratios"]}


def _claims_ci_gating(line: str) -> bool:
    """True if the line asserts CI gating, rather than disclaiming it."""
    return any(
        not NEGATION_RE.search(line[max(0, m.start() - 12) : m.start()])
        for m in CI_GATED_RE.finditer(line)
    )


def _entries_for(value: float) -> list[dict]:
    return [e for e in _claims()["ratios"] if float(e["value"]) == value]


def _nodes_in(line: str) -> list[int]:
    """Node counts the copy attributes on this line ("1,486-node" -> 1486)."""
    return [int(m.group(1).replace(",", "")) for m in NODE_ATTR_RE.finditer(line)]


def _site_files(patterns: tuple[str, ...] | None = None) -> list[Path]:
    if patterns is None:
        return sorted(SITE_ROOT.rglob("*.tsx")) + sorted(SITE_ROOT.rglob("*.ts"))
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(SITE_ROOT.glob(pattern)))
    return files


def _prose(path: Path) -> str:
    """File text with className attributes blanked, line numbering preserved."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return CLASSNAME_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _exempt(lines: list[str], index: int) -> bool:
    """True if this line, or the one above it, carries the opt-out marker."""
    window = lines[max(0, index - 1) : index + 1]
    return any(ALLOW_MARKER in line for line in window)


def _ratios_in(text: str) -> list[tuple[int, float]]:
    """Return (lineno, ratio) for every ratio claim in *text*."""
    found: list[tuple[int, float]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        consumed = line
        for m in RANGE_RE.finditer(line):
            found.append((lineno, float(m.group(1))))
            found.append((lineno, float(m.group(2))))
            consumed = consumed.replace(m.group(0), " ")
        for m in SINGLE_RE.finditer(consumed):
            found.append((lineno, float(m.group(1))))
    return found


def test_every_site_ratio_has_provenance() -> None:
    allowed = _allowed_ratios()
    violations: list[str] = []
    manifests = [REPO_ROOT / name for name in REGISTRY_MANIFESTS]
    for path in _site_files(RATIO_GATED) + manifests:
        for lineno, ratio in _ratios_in(_prose(path)):
            if ratio < MIN_CLAIM_RATIO or ratio in allowed:
                continue
            rel = path.relative_to(REPO_ROOT)
            violations.append(f"{rel}:{lineno}: {ratio:g}× is not in site/claims.json")
    assert not violations, (
        "Unsourced performance ratio(s) on the marketing site. Every ratio the "
        "site quotes needs an entry in site/claims.json naming where it was "
        "measured and how to reproduce it — add the measurement first, then the "
        "claim:\n  " + "\n  ".join(violations)
    )


def test_site_does_not_name_private_projects() -> None:
    names = _claims()["private_names_never_publish"]
    violations: list[str] = []
    for path in _site_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for name in names:
                if name.lower() in line.lower():
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{lineno}: names private project {name!r}")
    assert not violations, (
        "The marketing site names a private project. Field reports are "
        "anonymized in docs/ and in docs/community-benchmarks.json; the public "
        "site must match:\n  " + "\n  ".join(violations)
    )


def test_site_does_not_claim_perfect_gold_file_recall() -> None:
    violations: list[str] = []
    for path in _site_files():
        lines = _prose(path).splitlines()
        for index, line in enumerate(lines):
            lineno = index + 1
            if PERFECT_RECALL_RE.search(line) and not _exempt(lines, index):
                rel = path.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{lineno}: {line.strip()[:110]}")
    assert not violations, (
        "The site claims 100% gold-file recall. The public benchmark reports "
        "93.75% mean across 40 queries (0.96 requests / 0.79 click / 0.95 flask "
        "/ 1.00 rich) and publishes every miss — quote the mean and the range:\n  "
        + "\n  ".join(violations)
    )


def test_site_has_no_forbidden_absolute_claims() -> None:
    violations: list[str] = []
    manifests = [REPO_ROOT / name for name in REGISTRY_MANIFESTS]
    for path in _site_files() + manifests:
        lines = _prose(path).splitlines()
        for index, line in enumerate(lines):
            lineno = index + 1
            for pattern, reason in FORBIDDEN:
                m = pattern.search(line)
                if m and not _exempt(lines, index):
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{lineno}: {m.group(0)!r} — {reason}")
    assert not violations, (
        "Forbidden absolute claim(s) on the marketing site (NeuralMind "
        "minimizes egress, it does not eliminate it):\n  " + "\n  ".join(violations)
    )


def test_guards_actually_trip_on_known_bad_copy() -> None:
    # Sanity: each rule must fire on the copy that shipped, so a future
    # refactor can't quietly neuter it.
    assert _ratios_in("value: '63.6×',") == [(1, 63.6)]
    assert 63.6 not in _allowed_ratios()
    assert _ratios_in("'45–257× fewer tokens'") == [(1, 45.0), (1, 257.0)]
    assert PERFECT_RECALL_RE.search("{ metric: 'Gold-File Recall', value: '100%' }")
    assert PERFECT_RECALL_RE.search("100% gold-file recall on the public benchmark")
    assert any(p.search("100% local with zero code egress") for p, _ in FORBIDDEN)
    # ...and the opt-out must only cover the line it annotates and the next one.
    marked = [f"// {ALLOW_MARKER}", "title: 'Zero code egress',", "unmarked line"]
    assert _exempt(marked, 1)
    assert not _exempt(marked, 2)


def test_site_node_attributions_name_a_repo_that_exists() -> None:
    """Every repo size the copy cites must be one we actually measured.

    The first version of the attribution check only fired when a ratio shared
    the line, so `Sub-second on a 1,486-node repo` — the same invented repo,
    minus the ratio — survived the sweep it was written to catch. A node count
    is a factual claim about provenance whether or not a number rides along.
    """
    declared = [e["nodes"] for e in _claims()["ratios"] if "nodes" in e]
    violations: list[str] = []
    for path in _site_files(RATIO_GATED):
        for lineno, line in enumerate(_prose(path).splitlines(), start=1):
            for claimed in _nodes_in(line):
                if any(abs(claimed - d) <= NODE_TOLERANCE * d for d in declared):
                    continue
                rel = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{rel}:{lineno}: cites a {claimed:,}-node repo; "
                    f"measured repos are {sorted(declared)}"
                )
    assert not violations, (
        "The site cites a repo size that appears in no dataset. Cite a repo we "
        "measured, or add it to site/claims.json with its measurement:\n  "
        + "\n  ".join(violations)
    )


def test_site_ratios_are_attributed_to_the_repo_they_were_measured_on() -> None:
    """A ratio quoted next to the wrong repo size is the defect, not the value.

    `65.6× ... on a 1,486-node production codebase` shipped for weeks and would
    pass a value-only check, because 65.6 is a real number — measured on a
    241-node repo. Where the copy states both a ratio and a node count, the pair
    must exist in the manifest.
    """
    violations: list[str] = []
    for path in _site_files(RATIO_GATED):
        for lineno, line in enumerate(_prose(path).splitlines(), start=1):
            claimed_nodes = _nodes_in(line)
            if not claimed_nodes:
                continue
            for _, ratio in _ratios_in(line):
                if ratio < MIN_CLAIM_RATIO:
                    continue
                declared = [e["nodes"] for e in _entries_for(ratio) if "nodes" in e]
                if not declared:
                    continue
                if any(
                    abs(claimed - d) <= NODE_TOLERANCE * d
                    for claimed in claimed_nodes
                    for d in declared
                ):
                    continue
                rel = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{rel}:{lineno}: {ratio:g}× attributed to "
                    f"{claimed_nodes} nodes; measured on {declared}"
                )
    assert not violations, (
        "A ratio is quoted against a repo size it was not measured on. This is the "
        "original defect: the number is real, the attribution is invented:\n  "
        + "\n  ".join(violations)
    )


def test_site_does_not_upgrade_a_ratios_evidence_level() -> None:
    """Calling a field report or community submission 'CI-gated' is drift too.

    Evidence level is part of the claim: `48.8×` is one maintainer's field
    report, and presenting it as recomputed-by-CI overstates it exactly as
    surely as changing the digits would.
    """
    violations: list[str] = []
    for path in _site_files(RATIO_GATED):
        for lineno, line in enumerate(_prose(path).splitlines(), start=1):
            if not _claims_ci_gating(line):
                continue
            for _, ratio in _ratios_in(line):
                if ratio < MIN_CLAIM_RATIO:
                    continue
                entries = _entries_for(ratio)
                if not entries or any(e["evidence"] == "ci-gated" for e in entries):
                    continue
                rel = path.relative_to(REPO_ROOT)
                levels = sorted({e["evidence"] for e in entries})
                violations.append(
                    f"{rel}:{lineno}: {ratio:g}× presented as CI-gated; it is {levels}"
                )
    assert not violations, (
        "A ratio is presented as CI-gated when its manifest evidence level says "
        "otherwise. Say which kind of evidence it actually is:\n  " + "\n  ".join(violations)
    )


def test_attribution_guards_trip_on_the_copy_that_shipped() -> None:
    # The exact line that was live, which the value-only check passed.
    shipped = "desc: '65.6× compression measured on a 1,486-node production codebase.',"
    assert _nodes_in(shipped) == [1486]
    ratios = [r for _, r in _ratios_in(shipped)]
    assert ratios == [65.6]
    declared = [e["nodes"] for e in _entries_for(65.6) if "nodes" in e]
    assert declared and all(
        abs(1486 - d) > NODE_TOLERANCE * d for d in declared
    ), "the 1,486-node attribution must not match the repo 65.6× came from"

    # The bare node count — no ratio on the line — is the shape that slipped
    # through the first attempt and shipped to production.
    assert _nodes_in("Sub-second on a 1,486-node repo.") == [1486]

    # ...and the correct attribution, including the site's rounded form, passes.
    assert any(abs(241 - d) <= NODE_TOLERANCE * d for d in declared)
    field = [e["nodes"] for e in _entries_for(48.8) if "nodes" in e]
    assert any(abs(9300 - d) <= NODE_TOLERANCE * d for d in field), "~9,300 ≈ 9,293"

    # Evidence-level upgrade: 48.8× is a field report, not a CI gate.
    assert _claims_ci_gating("a CI-gated 48.8× on a ~9,300-node codebase")
    assert all(e["evidence"] != "ci-gated" for e in _entries_for(48.8))
    # ...but disclosing the level honestly must keep passing. This exact line is
    # live on the site and an earlier draft of this guard failed it.
    assert not _claims_ci_gating(
        "'48.8×', detail: '~9,300-node codebase — method reproducible, not CI-gated'"
    )
