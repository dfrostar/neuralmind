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
    # Dependency-vulnerability dispositions, read by the same CISOs as the two
    # above — and the surface most likely to grow a reassuring absolute while
    # explaining why an alert was dismissed.
    "docs/VULNERABILITY-MANAGEMENT-POLICY.md",
    "docs/DEPLOYMENT-GUIDE.md",
    "docs/ENTERPRISE.md",
    "docs/BUSINESS-CASE.md",
    # Written for models to read, and the one surface nothing scanned: it was
    # still carrying two superseded magnitudes and "no code leaves the machine"
    # long after every gated surface had been corrected.
    "docs/llms.txt",
    # The Hermes plugin catalog renders this as the plugin's page, and it
    # carries the plugin's privacy disclosures.
    "neuralmind/hermes_plugin/README.md",
    # The 2026-10-19 audit found both quoting the 12-50x range against the
    # wrong baseline while no guard read them.
    "docs/HONEST-ASSESSMENT.md",
    # Its `description` is the PyPI summary line, the first claim most
    # installers read.
    "pyproject.toml",
    # The user guide linked from the README. It carried the "~800 vs ~50,000
    # tokens" pairing UNSOURCED_FIGURES rejects, unread by any guard.
    "USAGE.md",
    # Registry manifests: their `description` is the listing other people's
    # agent runtimes show (Agent Zero's a0-plugins index). Both quoted a bare
    # 12-50× while no prose guard read them; test_site_claims only checked
    # their ratios.
    "plugin.yaml",
    "integrations/a0-plugins/neuralmind/index.yaml",
)
PUBLISHED_GLOBS = (
    "docs/comparisons/*.md",
    "docs/use-cases/*.md",
    "docs/wiki/*.md",
    # docs/benchmarks/ is where the numbers themselves live, and it was
    # likewise unscanned.
    "docs/benchmarks/*.md",
    "docs/benchmarks/*.html",
    # Social copy (LinkedIn posts + their image prompts) is the surface class
    # where the worst historical overclaims shipped: one infographic carried an
    # unsourced latency figure and a "never leaves your machine" absolute at
    # once. Posts are drafted in-repo precisely so this guard vets them BEFORE
    # they're pasted somewhere no CI can reach.
    "docs/social/*.md",
    # Shipped to Hermes-Agent taps, OpenClaw's ClawHub and the Agent Zero
    # index — read by models in other people's runtimes, where no CI of ours
    # can reach it. Same argument as docs/llms.txt above.
    "skills/*/SKILL.md",
    # The docs-site layout renders its footer on every docs.neuralmind.uk page,
    # and it carried "100% local · 12-50× token reduction" long after the pages
    # themselves were corrected, because no guard read the template.
    "docs/_layouts/*.html",
    # GitHub issue forms are public copy too: the community-benchmark form told
    # contributors their "code never leaves your machine".
    ".github/ISSUE_TEMPLATE/*.yml",
    # The policies COMPLIANCE-SUMMARY.md links auditors to. They described a
    # compliance platform as running when it had only been planned, and no
    # guard read them.
    "docs/compliance/*.md",
)

# A post may legitimately *quote* a forbidden phrase in order to correct it —
# the correction post renders the old claim as "Before:" beside its fix. Same
# mechanism as tests/test_site_claims.py: mark the line (or the line above it)
# with the marker and the guards skip that line only. The marker is an audit
# trail, not an off switch — an unmarked reappearance still fails the build.
ALLOW_MARKER = "claims-guard:allow"


def _allowed(lines: list[str], index: int) -> bool:
    """True when ``lines[index]`` (0-based) carries or follows the allow marker."""
    if ALLOW_MARKER in lines[index]:
        return True
    return index > 0 and ALLOW_MARKER in lines[index - 1]


# Each entry: (compiled pattern, why it's forbidden / what to say instead).
# Patterns target whole misleading phrases, case-insensitive.
FORBIDDEN = [
    (
        re.compile(r"\b(code|logic|data)\s+never\s+leaves?\b", re.IGNORECASE),
        (
            "Absolute privacy claim — the agent still egresses its chosen slice. "
            "Say what NeuralMind itself does, scoped to leaving the machine: "
            "'sends no telemetry and transmits no repository content off your "
            "machine'. Unscoped, 'transmits no repository content' contradicts "
            "the adjacent copy, because handing a slice to a local agent is "
            "transmitting repository content."
        ),
    ),
    (
        re.compile(
            r"\bnever\s+leaves?\s+(your|the)\s+(machine|infrastructure|environment|network|organi[sz]ation)\b",
            re.IGNORECASE,
        ),
        (
            "Absolute privacy claim about the whole workflow — inaccurate. "
            "Scope the claim to NeuralMind's own behavior."
        ),
    ),
    (
        # "no data leaves your machine" and "no code leaves the machine" make
        # the identical absolute; only the noun and article differ, and the
        # narrower pattern let the second ship on docs/llms.txt.
        re.compile(r"\bno\s+(code|logic|data)\s+leaves?\s+(your|the)\b", re.IGNORECASE),
        "Absolute claim — reword to NeuralMind's own local processing.",
    ),
    (
        # "the" as well as "your": "Nothing leaves the machine" shipped in a
        # comparison table while this pattern only knew the second person.
        re.compile(r"\bnothing\s+leaves?\s+(your|the)\b", re.IGNORECASE),
        (
            "Absolute privacy claim about the whole workflow — inaccurate. "
            "Scope the claim to NeuralMind's own behavior."
        ),
    ),
    (
        re.compile(r"\b(zero|no)\s+(data\s+)?exfiltration\b", re.IGNORECASE),
        (
            "Absolute exfiltration claim. Say what NeuralMind itself does: 'by "
            "default, sends no telemetry and transmits no repository content off "
            "your machine'."
        ),
    ),
    (
        # This one was the guard's OWN prescribed replacement until 2026-08-28,
        # which is how it spread to the README, the site, llms.txt, SECURITY.md
        # and two registry manifests. It is false: on a cold first build
        # neuralmind/onnx_embedder.py itself calls urllib.request.urlretrieve
        # for the MiniLM ONNX archive. The fetch is NeuralMind's own code, not
        # a dependency's, which is precisely what "of its own" denies.
        re.compile(
            # "(network|external)" is optional: "makes no calls of its own" made
            # the same false claim in a comparison table and a FAQ snippet.
            r"\b(no|zero)\s+((network|external)\s+)?calls?\s+of\s+its\s+own\b",
            re.IGNORECASE,
        ),
        (
            "False on a cold install — neuralmind/onnx_embedder.py downloads the "
            "embedding model over HTTPS itself. Say the true and stronger thing, "
            "scoped to leaving the machine: 'sends no telemetry and transmits no "
            "repository content off your machine'."
        ),
    ),
    (
        re.compile(r"\bexfiltration\s+risk\b", re.IGNORECASE),
        (
            "Implies the workflow can't exfiltrate — it can (the agent egresses). "
            "Describe NeuralMind's own zero network surface instead."
        ),
    ),
    (
        # Any qualifier — "zero data egress", "zero code egress", "no egress" —
        # makes the same inaccurate absolute about the whole agent workflow.
        re.compile(r"\b(zero|no)\s+(\w+\s+)?egress\b", re.IGNORECASE),
        "Absolute egress claim. NeuralMind minimizes egress, doesn't eliminate it.",
    ),
    (
        re.compile(r"\bfully\s+air[-\s]?gapped\b", re.IGNORECASE),
        "Overclaim. 'air-gap installable' is the accurate phrasing.",
    ),
    (
        re.compile(
            r"\b(soc[-\s]?2(\s+type\s+(ii|i|2|1))?|cmmc(\s+2\.0)?(\s+level\s+[123])?)"
            r"[-\s]*(compliant|certified)\b",
            re.IGNORECASE,
        ),
        (
            "NeuralMind is not certified, and CMMC assesses a contractor's environment, "
            "not a tool. Use 'SOC 2-ready posture / evidence for your review'."
        ),
    ),
    (
        # "NeuralMind satisfies SOC 2 Type II criteria" sat in SECURITY-GUIDE.md
        # for months beside a summary that said nothing was certified, because
        # the pattern above only knew "compliant" and "certified".
        re.compile(
            r"\b(satisf(y|ies|ied)|meets?|compl(y|ies)\s+with)\s+(all\s+)?(the\s+)?"
            r"(soc[-\s]?2|cmmc)\b",
            re.IGNORECASE,
        ),
        "Only an audit can say criteria are satisfied. Say what evidence NeuralMind provides.",
    ),
    (
        # A checkmark beside a report type reads as "we hold this report".
        # SECURITY.md's framework list carried "✅ SOC 2 Type II".
        re.compile(r"✅\s*soc[-\s]?2\s+type\b", re.IGNORECASE),
        "NeuralMind holds no SOC 2 report of either type. Drop the type or the checkmark.",
    ),
    (
        re.compile(r"\bzero\s+compliance\s+risk\b", re.IGNORECASE),
        "Overclaim. Say the architecture supports certification of the deployment.",
    ),
]


# Point estimates that must never come back as bare claims.
#
# The synapse-recall and faithfulness A/Bs run against a ~500-line fixture
# behind a ChromaDB HNSW index, so their deltas jitter between runs — CI
# averages the onboarding lift over three runs for exactly that reason, and
# gates both A/Bs on *direction* (on >= off, delta >= 0), never on a magnitude.
# Published as fixed figures, they go stale within days: the synapse lift was
# written as +12 pts (2026-08-06), +6.1 pts (2026-08-11, in a commit whose own
# message reported +14 from its fresh run), and measured +3.5 pts in CI on
# 2026-08-18. The onboarding lift simultaneously read +11.6, +6.5, and +0.9 pts
# on three different surfaces, two of them in the same README.
#
# So these patterns match the *bare point-estimate* form only. Quoting the
# observed band ("+0.013 to +0.143 across runs") is the correct phrasing and
# deliberately still passes.
SUPERSEDED_FIGURES = [
    (
        re.compile(r"\+?6\.1\s*(pts|points|pt)\b", re.IGNORECASE),
        (
            "The synapse-recall lift is run-dependent (+3.5 to +14 pts observed). "
            "Quote the CI gate — recall-on >= recall-off — and the observed band."
        ),
    ),
    (
        re.compile(r"77\.2\s*%\s*(→|->|to)\s*83\.3\s*%"),
        (
            "These hit-rate levels are one run's output, not a stable result. "
            "Quote the gate and the band instead."
        ),
    ),
    (
        re.compile(r"faithfulness\s*\+0\.143", re.IGNORECASE),
        (
            "The faithfulness delta is run-dependent (+0.013 to +0.143 observed) "
            "and CI gates it at >= 0, not at a magnitude."
        ),
    ),
    (
        # +0.25 / +0.251 / +0.26 were roundings of v4.12.0's +0.265 that drifted
        # onto the site and llms.txt. "+0.265" itself must keep passing.
        re.compile(
            r"(faithfulness|grounding|delta)[^\n]{0,80}?\+0\.(25|251|26)(?![\d])", re.IGNORECASE
        ),
        (
            "The faithfulness delta measured +0.265 at v4.12.0 (0.839 vs 0.574, one "
            "machine), and CI gates it at a mean delta >= -0.10, not at a magnitude."
        ),
    ),
    (
        re.compile(r"\+?11\.6\s*(pts|points)\b|\+?6\.5\s*points\b", re.IGNORECASE),
        (
            "The onboarding lift is run-dependent (+0.9 to +11.6 pts observed) and "
            "was simultaneously published as three different values."
        ),
    ),
]

# Public-benchmark ratios that a regenerated run replaced (site/claims.json,
# `unsourced_do_not_use`). Each was the measurement of its day and stays in the
# dated release notes and CHANGELOG.md, which this guard doesn't read; a
# published page that records the history marks the line with the allow
# marker. The v4.3.4 run's 45.0× for `requests` was still on two pages a week
# after v4.6.0 replaced it. Unlike the point estimates above, most of these are
# ranges, so they're matched on the raw line: _without_ranges would blank them.
_TIMES = r"(?:\s*(?:×|&times;|&#215;)|x(?![a-z]))"
_TO = r"\s*(?:×|&times;|&#215;|x)?\s*(?:–|—|-|&ndash;|&mdash;|&#8211;|to)\s*"


def _ratio_range(low: str, high: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\d.])(?:{low}){_TO}(?:{high}){_TIMES}")


def _ratios(*values: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\d.])(?:{'|'.join(values)}){_TIMES}")


# The current run (v4.12.0) measures 51–242×: requests 51.2×, click 117.1×,
# flask 68.5×, rich 242.0×. Until 2026-10-19 these messages quoted a pre-merge
# draft of that run instead (54–260×), which is how /measure-your-own came to
# carry its 54.9×; the draft is now on the list itself.
_CURRENT_RUN = "requests 51.2×, click 117.1×, flask 68.5×, rich 242.0×"

SUPERSEDED_BENCHMARK_FIGURES = [
    (
        _ratio_range(r"54(?:\.9)?", r"2(?:60|59\.3)"),
        f"A draft of the v4.12.0 run that never became canon. The committed run: 51–242× ({_CURRENT_RUN}).",
    ),
    (
        _ratios(r"54\.9", r"124\.2", r"73\.1", r"259\.3"),
        f"A per-repo ratio from a draft of the v4.12.0 run. The committed run: {_CURRENT_RUN}.",
    ),
    (
        _ratio_range(r"45(?:\.3)?", r"24[56](?:\.2)?"),
        "The v4.10.0 run's range, replaced 2026-10-08 at v4.12.0: 51–242×.",
    ),
    (
        _ratios(r"45\.3", r"115\.2", r"76\.3", r"245\.2"),
        f"A v4.10.0 per-repo ratio, replaced 2026-10-08 at v4.12.0: {_CURRENT_RUN}.",
    ),
    (
        _ratio_range(r"46(?:\.6)?", r"26[23](?:\.1)?"),
        "The v4.6.0 run's range, replaced 2026-10-07 at v4.10.0 (since: 51–242×).",
    ),
    (
        # click's 121.7× is left out: the embedding-rag baseline measures
        # exactly that on click in the current run, in the tables that list it.
        _ratios(r"46\.6", r"78(?:\.0)?", r"262\.1", r"263"),
        f"A v4.6.0 per-repo ratio, replaced 2026-10-07 at v4.10.0 (since: {_CURRENT_RUN}).",
    ),
    (
        _ratio_range(r"45(?:\.0)?", r"26(?:0\.7|1)"),
        "The v4.3.4 run's range, replaced at v4.6.0, v4.10.0 and v4.12.0 (51–242×).",
    ),
    (
        _ratios(r"45\.0", r"110\.4", r"81\.6", r"260\.7", r"261"),
        f"A v4.3.4 per-repo ratio. The current run measures {_CURRENT_RUN}.",
    ),
    (
        _ratio_range(r"46", r"259"),
        "Published 2026-09-16 from a run whose raw output was never committed.",
    ),
]

# Every public-benchmark run before v4.12.0 had a miss, and 40 of 40 at v4.12.0
# is too small a sample to carry a perfect-recall claim. A bare
# "100% gold-file recall" shipped in the README for weeks while the same file's
# later section correctly reported the range.
PERFECT_RECALL_RE = re.compile(
    r"100\s*%[^.\n]{0,40}?gold-file\s+recall|gold-file\s+recall[^.\n]{0,40}?100\s*%",
    re.IGNORECASE,
)

# A figure quoted as one end of a band ("+0.9 to +11.6 pts", "79-100%") is the
# correct phrasing, not the defect. Blank those spans before matching so the
# guards catch bare point estimates only.
_RANGE_RES = (
    re.compile(
        r"\+?\d+(?:\.\d+)?\s*(?:to|–|—|-|&ndash;|&mdash;)\s*\+?\d+(?:\.\d+)?\s*(?:pts|points|%)?",
        re.IGNORECASE,
    ),
)


# "100% gold-file recall" is accurate for the disclosed, off-by-default
# competitor eval, which runs on `requests`/`click` only. The defect is
# attaching it to the 4-repo public benchmark, whose mean is 95%. Lines that
# name the competitor comparison within a short window are making the narrower,
# true claim.
COMPETITOR_SCOPE_RE = re.compile(r"codebase-memory-mcp|competitor", re.IGNORECASE)
_SCOPE_WINDOW = 3


def _scoped_to_competitor_eval(lines: list[str], index: int) -> bool:
    window = lines[max(0, index - _SCOPE_WINDOW) : index + _SCOPE_WINDOW + 1]
    return any(COMPETITOR_SCOPE_RE.search(line) for line in window)


def _without_ranges(line: str) -> str:
    for pattern in _RANGE_RES:
        line = pattern.sub(" ", line)
    return line


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
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if _allowed(lines, index):
                continue
            for pattern, reason in FORBIDDEN:
                m = pattern.search(line)
                if m:
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(
                        f"{rel}:{index + 1}: forbidden claim {m.group(0)!r} — {reason}"
                    )
    assert not violations, (
        "Forbidden absolute claim(s) found on published surfaces "
        "(NeuralMind minimizes egress, it does not eliminate it):\n  " + "\n  ".join(violations)
    )


def test_guard_actually_matches_a_known_bad_phrase() -> None:
    # Sanity: the guard must trip on the canonical bad phrase, so a future
    # refactor can't neuter it into a silent no-op.
    bad = "100% local — your code never leaves your machine."
    assert any(p.search(bad) for p, _ in FORBIDDEN)
    # The variant that shipped on llms.txt while the narrower pattern watched.
    assert any(p.search("100% local: no code leaves the machine") for p, _ in FORBIDDEN)
    # The comparison-table variant, in the third person.
    assert any(p.search("| Nothing leaves the machine |") for p, _ in FORBIDDEN)
    # The phrase this guard itself used to prescribe, false since the embedder
    # started fetching its own model. Both spellings that shipped.
    assert any(p.search("NeuralMind makes no network calls of its own") for p, _ in FORBIDDEN)
    assert any(p.search("makes zero network calls of its own") for p, _ in FORBIDDEN)
    assert any(p.search("and makes no external calls of its own") for p, _ in FORBIDDEN)
    assert any(p.search("NeuralMind makes no calls of its own") for p, _ in FORBIDDEN)
    # The compliance overclaims that shipped, and the CMMC forms of the same.
    assert any(p.search("NeuralMind satisfies SOC 2 Type II criteria:") for p, _ in FORBIDDEN)
    assert any(p.search("### ✅ SOC 2 Type II") for p, _ in FORBIDDEN)
    assert any(p.search("CMMC 2.0 Level 2 certified") for p, _ in FORBIDDEN)
    assert any(p.search("NeuralMind is SOC 2 Type II certified") for p, _ in FORBIDDEN)
    assert any(p.search("a SOC 2 Type I compliant deployment") for p, _ in FORBIDDEN)
    assert any(p.search("a CMMC-compliant code index") for p, _ in FORBIDDEN)
    assert any(p.search("meets CMMC requirements") for p, _ in FORBIDDEN)
    assert any(p.search("NeuralMind complies with CMMC 2.0") for p, _ in FORBIDDEN)
    assert any(p.search("it complies with the SOC 2 criteria") for p, _ in FORBIDDEN)
    # Accurate scoped wording must still pass, or the guard blocks correct copy.
    ok = "No telemetry, and nothing on the wire at query time."
    assert not any(p.search(ok) for p, _ in FORBIDDEN)
    for ok in (
        "**SOC 2-ready posture, certification on the roadmap.**",
        "### ✅ SOC 2 (Trust Services Criteria)",
        "## CMMC 2.0 — practice evidence",
        "Next audit target: a SOC 2 Type I report — Q3 2027",
    ):
        assert not any(p.search(ok) for p, _ in FORBIDDEN), ok


def test_social_copy_is_scanned() -> None:
    # docs/social/ went unscanned while it held finished LinkedIn copy — the
    # exact surface class the 0.81s infographic shipped from. Pin the coverage
    # so a glob refactor can't silently drop it.
    assert any(
        p.parts[-2:] == ("docs", "social") or "social" in p.parts for p in _published_paths()
    )


def test_allow_marker_exempts_quoted_disavowals_only() -> None:
    # A correction post quotes the old claim beside its fix; the marker skips
    # that line — and only that line. Unmarked reappearances still fail.
    quoted = [
        "<!-- claims-guard:allow — quoting the retracted claim to correct it -->",
        'Before: "your IP never leaves your machine."',
        "After: NeuralMind transmits no repository content off your machine.",
    ]
    assert _allowed(quoted, 1), "marker on the previous line must exempt the quote"
    assert not _allowed(quoted, 2), "the line after the quote is not exempt"
    unmarked = ['Before: "your IP never leaves your machine."']
    assert not _allowed(unmarked, 0)
    assert any(p.search(unmarked[0]) for p, _ in FORBIDDEN)


def test_published_surfaces_do_not_quote_superseded_point_estimates() -> None:
    violations: list[str] = []
    for path in _published_paths():
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for index, raw in enumerate(lines):
            if _allowed(lines, index):
                continue
            line = _without_ranges(raw)
            for pattern, reason in SUPERSEDED_FIGURES:
                m = pattern.search(line)
                if m:
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{index + 1}: {m.group(0)!r} — {reason}")
    assert not violations, (
        "A run-dependent A/B magnitude is published as a fixed figure. CI gates "
        "these on direction, not size — quote the gate and the observed band:\n  "
        + "\n  ".join(violations)
    )


def test_published_surfaces_do_not_quote_superseded_benchmark_figures() -> None:
    violations: list[str] = []
    for path in _published_paths():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            if _allowed(lines, index):
                continue
            for pattern, reason in SUPERSEDED_BENCHMARK_FIGURES:
                m = pattern.search(line)
                if m:
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{index + 1}: {m.group(0)!r} — {reason}")
                    break  # a range's high end would otherwise report the line twice
    assert not violations, (
        "A published surface quotes a public-benchmark ratio that a regenerated "
        "run replaced. Quote the committed run (site/claims.json), or, on a dated "
        "line that records the history, add the claims-guard:allow marker:\n  "
        + "\n  ".join(violations)
    )


def test_superseded_benchmark_guard_trips_on_the_copy_that_shipped() -> None:
    shipped = [
        "**46–263× fewer tokens than pasting every source file, at 95% mean",
        '<div class="num">46&#8211;263&#215;</div>',
        "<li>3 of 40 queries missed, 46&ndash;263&times; fewer tokens</li>",
        "That is 46.6–262.1× fewer input tokens per query, not 46.6–262.1× less spend.",
        "found-rate (37 of 40), 46.6×–262.1× fewer tokens than pasting whole files.",
        '<td class="num"><span class="win">78.0×</span></td>',
        "The public benchmark's 45.0× on `requests` is a different measurement",
        "**93.75% mean gold-file recall (85–100% per repo) at 45–261× fewer tokens**",
        "45 to 261x fewer tokens",
        "**45–246× fewer tokens than pasting every source file, at 95% mean",
        '<div class="num">45&#8211;246&#215;</div>',
        "That is 45.3–245.2× fewer input tokens per query",
        "requests 45.3×, click 115.2×, flask 76.3×, rich 245.2×",
        # The draft that reached /measure-your-own.
        "(The public benchmark’s 54.9× on the same repo is a different measurement",
        "**54–260× fewer tokens than pasting every source file, at 97.5% mean",
    ]
    for line in shipped:
        assert any(p.search(line) for p, _ in SUPERSEDED_BENCHMARK_FIGURES), line

    current = [
        "**51–242× fewer tokens than pasting every source file, with the gold file",
        '<div class="num">51&#8211;242&#215;</div>',
        "That is 51.2–242.0× fewer input tokens per query",
        _CURRENT_RUN,
        "| `embedding-rag` | 1.00 | 100% | 645 | 0.69 | 121.7× |",
        "78.6× on psf/requests v2.32.3 at v4.5.0",
        "the community submissions so far (46× to 65.6×)",
        "5.1× on the CI fixture at v4.3.4; the build fails below 4.0×",
    ]
    for line in current:
        assert not any(p.search(line) for p, _ in SUPERSEDED_BENCHMARK_FIGURES), line


def test_published_surfaces_do_not_claim_perfect_gold_file_recall() -> None:
    violations: list[str] = []
    for path in _published_paths():
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for index, raw in enumerate(lines):
            if not PERFECT_RECALL_RE.search(_without_ranges(raw)):
                continue
            if _allowed(lines, index):
                continue
            if _scoped_to_competitor_eval(lines, index):
                continue
            rel = path.relative_to(REPO_ROOT)
            violations.append(f"{rel}:{index + 1}: {raw.strip()[:110]}")
    assert not violations, (
        "A published surface claims 100% gold-file recall. The public benchmark "
        "reports 95% mean across 40 queries (0.96 / 0.86 / 0.95 / 1.00) and "
        "publishes every miss:\n  " + "\n  ".join(violations)
    )


def test_superseded_figure_guards_trip_on_the_copy_that_shipped() -> None:
    # Each pattern must fire on the exact text that was live, and must NOT fire
    # on the band phrasing that replaced it — otherwise the guard either rots
    # into a no-op or blocks the correct wording.
    bad = [
        "hit-rate **+6.1 points (77.2%→83.3%), budget-neutral**",
        "faithfulness +0.143, grounding 1.00",
        "| **Onboarding lift** | — | — | **+11.6 pts** |",
        "- **Onboarding lift:** +6.5 points top-k module hit-rate",
    ]
    for line in bad:
        assert any(p.search(line) for p, _ in SUPERSEDED_FIGURES), line

    good = [
        "recall-on >= recall-off, at a neutral token budget | **+3.5 to +14 pts**",
        "delta **>= 0** | **+0.013 to +0.143**",
        "lift **>= 0**, averaged over 3 runs | **+0.9 to +11.6 pts** across runs",
    ]
    for line in good:
        stripped = _without_ranges(line)
        assert not any(p.search(stripped) for p, _ in SUPERSEDED_FIGURES), line

    assert PERFECT_RECALL_RE.search("**100% gold-file recall, MRR 0.96** on the public benchmark")
    assert not PERFECT_RECALL_RE.search(
        _without_ranges("**79-100% gold-file recall (93.75% mean)**")
    )
    assert not PERFECT_RECALL_RE.search(_without_ranges("79–100% gold-file recall"))
    assert not PERFECT_RECALL_RE.search(_without_ranges("79&ndash;100% gold-file recall"))
    # The narrower competitor-eval claim is true and stays allowed; the same
    # sentence without that scope is the defect.
    scoped = ["100% gold-file recall, MRR 0.96", "beats codebase-memory-mcp 0.96 vs 0.23"]
    assert _scoped_to_competitor_eval(scoped, 0)
    assert not _scoped_to_competitor_eval(["100% gold-file recall on the public benchmark"], 0)


# ---------------------------------------------------------------------------
# Overclaims the 2026-10-19 audit of every public surface found.
#
# site/claims.json was honest; the copy around it was not. Hand-copied numbers
# and phrases drifted on every surface the guards above didn't read for them:
# "smarter the more you use it" beside a synapse gate that only asserts
# direction (and measured +0 at v4.12.0), "zero telemetry, no calls home" on a
# tool whose first build downloads a model, "HIPAA friendly" and "NIST AI RMF
# compliant" for a tool that holds no certification, "fewer wrong turns, faster
# teams" when no benchmark measures task outcomes, and the 12–50× field-report
# range quoted against whatever baseline the sentence happened to need. These
# rules read every published surface and, through tests/test_site_claims.py,
# every page under site/src.
# ---------------------------------------------------------------------------

# A negation earlier in the same sentence turns a banned phrase into the
# disclosure it should be: "nothing here measures whether an agent makes fewer
# mistakes", "using NeuralMind does not make you compliant".
_NEGATION_RE = re.compile(
    r"\b(not|never|nothing|no|none|isn't|aren't|doesn't|don't|can't|cannot|won't|without)\b",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.!?;](?:\s|$)|<p>|</p>|<li>|</li>|\|")


def _sentence_before(line: str, start: int) -> str:
    """The part of *line*'s current sentence that precedes *start*."""
    head = line[:start]
    ends = list(_SENTENCE_END_RE.finditer(head))
    return head[ends[-1].end() :] if ends else head


def _negated(text: str, start: int) -> bool:
    """True if the sentence that reaches *start* in *text* carries a negation."""
    return bool(_NEGATION_RE.search(_sentence_before(text, start)))


def _paragraph_before(lines: list[str], index: int, limit: int = 2) -> str:
    """Up to *limit* lines before ``lines[index]``, stopping at a blank line."""
    out: list[str] = []
    for line in reversed(lines[max(0, index - limit) : index]):
        if not line.strip():
            break
        out.insert(0, line.strip())
    return " ".join(out)


# (pattern, reason, negatable). A negatable phrase is fine in a sentence that
# denies it; the rest are wrong however they're framed.
OVERCLAIMS: list[tuple[re.Pattern[str], str, bool]] = [
    (
        re.compile(
            r"\b(smarter|sharper|better)\b[^.\n]{0,30}?\b(over\s+time|the\s+(more|longer)\s+"
            r"(you|it|the\s+system)\b|with\s+(use|every\s+(session|query)))"
            r"|\bthe\s+(more|longer)\s+you\s+(use|run|work\s+with)\s+(it|neuralmind)\b[^.\n]{0,40}?"
            r"\b(smarter|sharper|better)\b"
            # Bare "smarter" too: "the smarter your Claude Code session gets, the
            # smarter your Hermes session gets" never said "over time" and slipped
            # past the first version of this pattern.
            r"|\bsmarter\b"
            r"|\b(memory|learning|knowledge|layer|retrieval)\s+compounds\b"
            r"|\bimproves?\s+(retrieval\s+)?continuously\b",
            re.IGNORECASE,
        ),
        (
            "Nothing published shows the synapse layer improving a real repo over "
            "time: its CI gate asserts only that recall never lowers hit rate, on a "
            "~500-line fixture (+0 at v4.12.0). Say what it does, and point at "
            "`neuralmind eval . --synapse-ab` to measure it (site/claims.json disclosure)."
        ),
        True,
    ),
    (
        re.compile(r"\bSOTA\b|\bstate[-\s]of[-\s]the[-\s]art\b", re.IGNORECASE),
        (
            "An unmeasured superiority claim: no benchmark here compares NeuralMind "
            "with the state of the art. Name the technique and cite its source."
        ),
        False,
    ),
    (
        re.compile(
            r"\bzero\s+(cloud\s+|network\s+|external\s+|outbound\s+)?(calls|telemetry|requests)\b"
            r"|\b(no|never|zero|doesn't|does\s+not)\s+(make\s+)?(calls?|phones?|phoning|calling)\s+home\b",
            re.IGNORECASE,
        ),
        (
            "Absolute: the first build downloads the embedding model, and "
            "NEURALMIND_LLM_SEED=1 sends doc prose to Anthropic. Say 'by default, "
            "no telemetry' and name both (docs/wiki/FAQ.md, 'Does NeuralMind send "
            "data to external servers?')."
        ),
        False,
    ),
    (
        re.compile(
            r"(?<!ACID-)(?<!ACID )\bcompliant\b"
            r"|\b(GDPR|HIPAA|NIST(\s+AI\s+RMF)?|FedRAMP|PCI(\s+DSS)?|ISO\s*\d{4,5}|CCPA)"
            r"[-\s]+(friendly|ready)\b"
            r"|\b(SOC\s*2|CMMC(\s+2\.0)?)[-\s]+friendly\b"
            r"|\bcompliance[-\s]ready\b|\bbuilt\s+for\s+compliance\b"
            r"|\bsupports?\s+(major\s+|all\s+)?compliance\s+frameworks\b",
            re.IGNORECASE,
        ),
        (
            "NeuralMind holds no certification, and a tool can't be compliant on a "
            "deployment's behalf. Say what evidence it provides for your review "
            "(audit trail, framework mappings) and that assessment is of the deployment."
        ),
        True,
    ),
    (
        re.compile(
            r"\bfaster\s+teams\b|\bfewer\s+(wrong\s+turns|hallucinations?|mistakes|errors|bugs)\b"
            r"|\breduc\w*\s+hallucinations?\b|\bbetter\s+answers\b|\bship(s|ping)?\s+faster\b",
            re.IGNORECASE,
        ),
        (
            "Task outcomes are not measured (site/claims.json disclosure): every "
            "published figure is retrieval — what reaches the window and whether the "
            "right file is in it. Say that, not an outcome."
        ),
        True,
    ),
    (
        re.compile(
            r"\b(local[-\s]only|local[-\s]first|privacy|on[-\s]device)\b[^.\n]{0,40}?\bguarantee"
            r"|\bguarantee[sd]?\b[^.\n]{0,30}?\b(privacy|your\s+code)\b",
            re.IGNORECASE,
        ),
        (
            "A privacy guarantee is an absolute: the model download, the opt-in "
            "seeding and the agent's own egress all exist. Describe the default."
        ),
        False,
    ),
]


def overclaims_in(line: str, before: str = "") -> list[tuple[str, str]]:
    """(matched text, reason) for every overclaim on *line*.

    *before* is the wrapped text preceding the line in the same paragraph, so a
    negation a line break away still counts.
    """
    hits: list[tuple[str, str]] = []
    prefix = f"{before} " if before else ""
    for pattern, reason, negatable in OVERCLAIMS:
        for m in pattern.finditer(line):
            if negatable and _negated(prefix + line, len(prefix) + m.start()):
                continue
            hits.append((m.group(0), reason))
            break
    return hits


# The 12–50× range is real, but only against its baseline: `neuralmind
# benchmark` before v4.5.0 divided a fixed 50K-token estimate, and v4.5.0+
# divides the measured code, so a new run is not on this scale. Quoted bare it
# read as "vs pasting raw source files" (the public benchmark's baseline, where
# the figure is 51–242×) on one page and "vs a ~30K dump-all baseline" on
# another. The baseline must be named on the line or the one beside it.
RANGE_12_50_RE = re.compile(
    r"(?<![\d.])12\s*(?:×|x|&times;)?\s*(?:–|—|-|&ndash;|&mdash;|&#8211;|to)\s*50\s*"
    r"(?:×|x(?![a-z%])|&times;|&#215;)",
    re.IGNORECASE,
)
FIXED_BASELINE_RE = re.compile(
    r"50\s*K\b|50,000|fixed[-\s]+(?:50|estimate|baseline)|naive-50k|(?:before|pre-?)\s*v?4\.5",
    re.IGNORECASE,
)
_BASELINE_WINDOW = 2


def unscoped_12_50(lines: list[str], index: int) -> bool:
    """True when ``lines[index]`` quotes 12–50× with no fixed-50K baseline nearby."""
    if not RANGE_12_50_RE.search(lines[index]):
        return False
    window = lines[max(0, index - _BASELINE_WINDOW) : index + _BASELINE_WINDOW + 1]
    return not any(FIXED_BASELINE_RE.search(line) for line in window)


# Figures no run in the repo produces (site/claims.json, `unsourced_do_not_use`).
UNSOURCED_FIGURES = [
    (
        # The pairing is the defect: ~800 on its own is close to the measured
        # 670–961 (and ~830 on the 150-question eval); set against "~50,000" it
        # becomes a ratio nobody measured.
        re.compile(
            r"\b800\s+tokens?[^.\n]{0,60}?50,?000|50,?000\+?\s+tokens?[^.\n]{0,80}?\b800\b"
            r"|\b800\b[^.\n]{0,30}?(?:instead\s+of|not|vs\.?)\s*~?\s*50\s*K",
            re.IGNORECASE,
        ),
        (
            "'~800 tokens instead of ~50,000' pairs a rough figure with the CLI's old "
            "fixed estimate. Measured: 670–961 mean tokens per question vs 41,729–232,483 "
            "for every source file (public benchmark, v4.12.0)."
        ),
    ),
    (
        re.compile(r"\$0\.15\s*(?:–|-|to)\s*\$?3\.75|\$0\.002\s*(?:–|-|to)\s*\$?0\.06"),
        "No pricing run produces these. `neuralmind savings --cost` prices your own usage.",
    ),
    (
        re.compile(
            r"\b12\s*(?:–|-|&ndash;|to)\s*50\s*%\s*(?:bill|cost|spend|lower)", re.IGNORECASE
        ),
        "No measurement produces a 12–50% bill drop.",
    ),
    (
        re.compile(r"~\s*60\s*(?:×|x(?![a-z])|&times;)|~\s*88\s*%\s*cheaper", re.IGNORECASE),
        "No measurement in the repo produces this figure.",
    ),
]

# The codebase-memory-mcp head-to-head ran once, in June 2026, on two repos. It
# may be quoted in body text with that date beside it — not as a current
# headline. tests above already require the competitor's name in the window;
# this requires the date or version too.
COMPETITOR_DATE_RE = re.compile(
    r"June\s+2026|2026-06|v0\.3[0-3]\b|not\s+(?:been\s+)?re-?(?:run|verified)", re.IGNORECASE
)


def _dated_competitor_scope(lines: list[str], index: int) -> bool:
    window = lines[max(0, index - _SCOPE_WINDOW) : index + _SCOPE_WINDOW + 1]
    return any(COMPETITOR_SCOPE_RE.search(line) for line in window) and any(
        COMPETITOR_DATE_RE.search(line) for line in window
    )


# The about page's "Current Release: v0.19.0" stood for months while the
# package shipped v4.x. A hand-written "current release" goes stale on the next
# tag; link the release notes instead.
HARDCODED_CURRENT_RELEASE_RE = re.compile(
    r"(current|latest)\s+release\s*[:—–-]+\s*(<[^>]+>\s*)*v?\d+\.\d+", re.IGNORECASE
)


def _claim_lines() -> list[tuple[Path, list[str], int]]:
    """(path, lines, index) for every line of every published surface, minus
    lines the allow marker exempts."""
    out: list[tuple[Path, list[str], int]] = []
    for path in _published_paths():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        out.extend((path, lines, i) for i in range(len(lines)) if not _allowed(lines, i))
    return out


def test_published_surfaces_have_no_overclaims() -> None:
    violations = [
        f"{path.relative_to(REPO_ROOT)}:{i + 1}: {text!r} — {reason}"
        for path, lines, i in _claim_lines()
        for text, reason in overclaims_in(lines[i], _paragraph_before(lines, i))
    ]
    assert not violations, (
        "Overclaim(s) on a published surface. Say what is measured, scoped to "
        "what NeuralMind itself does:\n  " + "\n  ".join(violations)
    )


def test_published_12_50_range_names_its_baseline() -> None:
    violations = [
        f"{path.relative_to(REPO_ROOT)}:{i + 1}: {lines[i].strip()[:110]}"
        for path, lines, i in _claim_lines()
        if unscoped_12_50(lines, i)
    ]
    assert not violations, (
        "12–50× quoted without its baseline. It was measured before v4.5.0 against "
        "`neuralmind benchmark`'s fixed 50K-token estimate — name that on the line, "
        "or quote the public benchmark's 51–242× (vs every source file):\n  "
        + "\n  ".join(violations)
    )


def test_published_surfaces_quote_no_unsourced_figures() -> None:
    violations = [
        f"{path.relative_to(REPO_ROOT)}:{i + 1}: {m.group(0)!r} — {reason}"
        for path, lines, i in _claim_lines()
        for pattern, reason in UNSOURCED_FIGURES
        if (m := pattern.search(lines[i]))
    ]
    assert not violations, (
        "A figure no measurement in the repo produces (site/claims.json, "
        "unsourced_do_not_use):\n  " + "\n  ".join(violations)
    )


def test_competitor_recall_is_dated_where_quoted() -> None:
    violations = [
        f"{path.relative_to(REPO_ROOT)}:{i + 1}: {lines[i].strip()[:110]}"
        for path, lines, i in _claim_lines()
        if PERFECT_RECALL_RE.search(_without_ranges(lines[i]))
        and _scoped_to_competitor_eval(lines, i)
        and not _dated_competitor_scope(lines, i)
    ]
    assert not violations, (
        "The codebase-memory-mcp head-to-head (100% recall, MRR 0.96 vs 0.23) is "
        "quoted without its date. It ran in June 2026 (v0.33.0) on requests and "
        "click only, and has not been re-run — say so beside it:\n  " + "\n  ".join(violations)
    )


def test_published_surfaces_do_not_hardcode_the_current_release() -> None:
    violations = [
        f"{path.relative_to(REPO_ROOT)}:{i + 1}: {m.group(0)!r}"
        for path, lines, i in _claim_lines()
        if path.suffix in {".html", ".md", ".txt"}
        and (m := HARDCODED_CURRENT_RELEASE_RE.search(lines[i]))
    ]
    assert not violations, (
        "A page names a 'current release' by hand; it goes stale on the next tag. "
        "Link the release notes or the latest-release page instead:\n  " + "\n  ".join(violations)
    )


def test_overclaim_guards_trip_on_the_copy_that_shipped() -> None:
    shipped = [
        "The more you use it, the smarter the retrieval gets",
        "your agent's context gets *better* the more you work.",
        "Retrieval that gets sharper the longer the system runs on a codebase.",
        "It's the memory layer that makes every agent smarter.",
        "reinforce the same brain, so the smarter your Claude Code session",
        "> - Thinks with your brain, not just your code: 6 SOTA synaptic learning techniques",
        "### N-15 — SOTA Retrieval Quality Benchmarks (August 2026)",
        "- **The memory compounds per codebase.**",
        "NeuralMind runs entirely local. Zero cloud calls, zero telemetry, no calls home.",
        "'NeuralMind is local-first with zero telemetry — engagements follow the same rule.'",
        "- ✅ GDPR-compliant (local processing)",
        "- ✅ HIPAA-friendly (local processing, no calls home)",
        "<li><strong>vs Cursor @codebase:</strong> Works with any LLM, local-first, NIST AI RMF compliant</li>",
        "<p>Built for regulated industries. NIST AI RMF, SOC 2, GDPR, HIPAA friendly.</p>",
        "<strong>Compliance Ready</strong>",
        "- **Architecture supports major compliance frameworks** (GDPR, SOC 2, CMMC 2.0, HIPAA)",
        "title: 'Fewer wrong turns, faster teams',",
        "| **Faster, more grounded** agent responses | wakeup | Fewer hallucinations; less re-exploration |",
        "its local-only design is a guarantee to you, not a license to bypass security controls",
    ]
    for line in shipped:
        assert overclaims_in(line), line
    honest = [
        "Nothing here measures whether an agent fixes a bug faster or makes fewer mistakes",
        "- **Task outcomes aren't measured.** not whether agents finish with fewer errors.",
        "Using NeuralMind does not by itself make you compliant with any regulation.",
        'rationale="Single-file, no server, ACID-compliant",',
        "**SOC 2-ready posture, certification on the roadmap.**",
        "By default, NeuralMind sends no telemetry and transmits no repository content.",
        "Do not write that the layer gets smarter over time until a history is published.",
    ]
    for line in honest:
        assert not overclaims_in(line), line
    # A negation on the wrapped line above still counts.
    wrapped = [
        "- **Task outcomes.** Nothing here, or anywhere in this repository, measures",
        "  whether an agent fixes a bug faster or makes fewer mistakes with NeuralMind.",
    ]
    assert not overclaims_in(wrapped[1], _paragraph_before(wrapped, 1))
    assert overclaims_in(wrapped[1])


def test_scope_guards_trip_on_the_copy_that_shipped() -> None:
    bare = [
        "The result: 12-50× fewer tokens per code question compared to pasting raw source files.",
        "<p>Ready to reduce your per-query token costs by 12-50&times;?</p>",
        "| Token reduction on code questions | **5.1×** (v4.3.4) | **12-50×** (more files to prune) |",
    ]
    for line in bare:
        assert unscoped_12_50([line], 0), line
    scoped = [
        "**12–50×** in field reports measured before v4.5.0 against the fixed 50K-token estimate",
        "12-50x on real repos against a fixed 50K-token estimate",
    ]
    for line in scoped:
        assert not unscoped_12_50([line], 0), line
    # The baseline may sit on the wrapped line beside it.
    assert not unscoped_12_50(
        ["reported **12–50×** on", "real repos against a fixed 50K-token estimate"], 0
    )
    # 12–50% is a different (and also unsourced) claim, caught below.
    assert not RANGE_12_50_RE.search("12–50% bill drops")

    unsourced = [
        "> - Queries your codebase in ~800 tokens instead of ~50,000",
        "❌ Naive:  Load entire codebase → 50,000 tokens → $0.15-$3.75/query",
        "(50K+ tokens of raw source compressed into ~800 tokens of structured context) and 12–50% bill drops",
        "| NeuralMind | ~60× fewer tokens |",
    ]
    for line in unsourced:
        assert any(p.search(line) for p, _ in UNSOURCED_FIGURES), line
    assert not any(
        p.search("670–961 mean tokens per question vs 41,729–232,483") for p, _ in UNSOURCED_FIGURES
    )

    undated = ["**100% gold-file recall, MRR 0.96** — beats `codebase-memory-mcp` (0.96 vs 0.23)"]
    assert _scoped_to_competitor_eval(undated, 0) and not _dated_competitor_scope(undated, 0)
    dated = [
        "In a June 2026 head-to-head (v0.33.0, requests and click only, not re-run since),",
        "NeuralMind reached 100% gold-file recall, MRR 0.96 vs codebase-memory-mcp's 0.23.",
    ]
    assert _dated_competitor_scope(dated, 1)

    assert HARDCODED_CURRENT_RELEASE_RE.search(
        "<h3>Current Release: v0.19.0 — One-command MCP setup</h3>"
    )
    assert not HARDCODED_CURRENT_RELEASE_RE.search(
        "Read the latest release notes in docs/releases/"
    )
