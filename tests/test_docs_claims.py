"""Guard the published surfaces against forbidden absolute claims.

NeuralMind is a *local context layer that feeds an AI coding agent*. The
agent still sends its selected slice to its model, so NeuralMind minimizes
egress — it does not eliminate it. Absolute privacy/compliance claims
("your code never leaves your machine", "zero exfiltration", "SOC 2
certified") are therefore inaccurate and repeatedly leaked back into the
docs during release passes (they get copied from one surface to the next).

This test is the backstop: it scans the *published* claim surfaces (the
live docs site + README + security/compliance guides) and fails if any
forbidden absolute reappears. It is intentionally stdlib-only and keyed to
whole phrases, not bare words, so accurate copy — "no telemetry", "no
network calls of its own", "air-gap installable", "SOC 2-ready posture" —
keeps passing.

If you are adding a legitimate use of one of these words, phrase it as what
NeuralMind *itself* does (no calls of its own / no telemetry) rather than as
an absolute about the whole agent workflow.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Explicit list of files + globs that are actually published to users: the
# live docs site, the README, and the security/compliance guides CISOs read.
# Internal planning notes and unpublished drafts (docs/launch, docs/plans,
# docs/prd, docs/market-research, docs/notebooklm, PROJECT_LINKEDIN…) are
# deliberately excluded — they are working material, not live claims.
PUBLISHED_FILES = (
    "README.md",
    "SECURITY.md",
    "docs/index.html",
    "docs/about.html",
    "docs/COMPLIANCE-SUMMARY.md",
    "docs/SECURITY-GUIDE.md",
    "docs/DEPLOYMENT-GUIDE.md",
    "docs/ENTERPRISE.md",
    "docs/BUSINESS-CASE.md",
)
PUBLISHED_GLOBS = (
    "docs/comparisons/*.md",
    "docs/use-cases/*.md",
    "docs/wiki/*.md",
)

# Each entry: (compiled pattern, why it's forbidden / what to say instead).
# Patterns target whole misleading phrases, case-insensitive.
FORBIDDEN = [
    (
        re.compile(r"\b(code|logic|data)\s+never\s+leaves?\b", re.IGNORECASE),
        "Absolute privacy claim — the agent still egresses its chosen slice. "
        "Say what NeuralMind itself does: 'makes no network calls of its own'.",
    ),
    (
        re.compile(
            r"\bnever\s+leaves?\s+(your|the)\s+(machine|infrastructure|environment|network|organi[sz]ation)\b",
            re.IGNORECASE,
        ),
        "Absolute privacy claim about the whole workflow — inaccurate. "
        "Scope the claim to NeuralMind's own behavior.",
    ),
    (
        re.compile(r"\bno\s+data\s+leaves?\s+your\b", re.IGNORECASE),
        "Absolute claim — reword to NeuralMind's own local processing.",
    ),
    (
        re.compile(r"\b(zero|no)\s+(data\s+)?exfiltration\b", re.IGNORECASE),
        "Absolute exfiltration claim. Use 'no telemetry / no calls home'.",
    ),
    (
        re.compile(r"\bexfiltration\s+risk\b", re.IGNORECASE),
        "Implies the workflow can't exfiltrate — it can (the agent egresses). "
        "Describe NeuralMind's own zero network surface instead.",
    ),
    (
        re.compile(r"\b(zero|no)\s+(data\s+)?egress\b", re.IGNORECASE),
        "Absolute egress claim. NeuralMind minimizes egress, doesn't eliminate it.",
    ),
    (
        re.compile(r"\bfully\s+air[-\s]?gapped\b", re.IGNORECASE),
        "Overclaim. 'air-gap installable' is the accurate phrasing.",
    ),
    (
        re.compile(r"\bsoc[-\s]?2[-\s]*(compliant|certified)\b", re.IGNORECASE),
        "NeuralMind is not certified. Use 'SOC 2-ready posture / evidence for your review'.",
    ),
    (
        re.compile(r"\bzero\s+compliance\s+risk\b", re.IGNORECASE),
        "Overclaim. Say the architecture supports certification of the deployment.",
    ),
]


def _published_paths() -> list[Path]:
    paths: list[Path] = []
    for rel in PUBLISHED_FILES:
        p = REPO_ROOT / rel
        if p.exists():
            paths.append(p)
    for pattern in PUBLISHED_GLOBS:
        paths.extend(sorted(REPO_ROOT.glob(pattern)))
    return paths


def test_published_surfaces_have_no_forbidden_absolute_claims() -> None:
    violations: list[str] = []
    for path in _published_paths():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, reason in FORBIDDEN:
                m = pattern.search(line)
                if m:
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{lineno}: forbidden claim {m.group(0)!r} — {reason}")
    assert not violations, (
        "Forbidden absolute claim(s) found on published surfaces "
        "(NeuralMind minimizes egress, it does not eliminate it):\n  " + "\n  ".join(violations)
    )


def test_guard_actually_matches_a_known_bad_phrase() -> None:
    # Sanity: the guard must trip on the canonical bad phrase, so a future
    # refactor can't neuter it into a silent no-op.
    bad = "100% local — your code never leaves your machine."
    assert any(p.search(bad) for p, _ in FORBIDDEN)
