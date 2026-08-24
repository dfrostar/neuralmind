"""secret_scan.py — secret detection and redaction

NeuralMind persists text that a developer's tools produced: the most
recent Bash stdout/stderr (``.neuralmind/last_output.json``), ingested
document chunks, and node descriptions bound for the vector index. Any
of those can incidentally carry a live credential — ``printenv`` output,
a ``curl -H "Authorization: Bearer ..."`` command line, a runbook with
an inline token.

This module is the single detection engine behind both defenses:

- ``redact_text`` — scrub before persisting (output cache, and the
  build path when ``--redact-secrets`` / ``NEURALMIND_REDACT_SECRETS=1``
  is on).
- ``scan_file`` / ``scan_project`` — the ``neuralmind scan-for-secrets``
  command, for finding credentials *before* they reach the index.

Design:
- **Stdlib only.** Mirrors the synapse layer's convention so the tests
  run without the full dep set, and so the output-cache hook can import
  it on a bare install.
- **Two confidence tiers.** ``high`` patterns match a vendor-specific
  shape (``sk-ant-``, ``AKIA``, a PEM block) and effectively never fire
  on prose. ``heuristic`` patterns match a generic ``SECRET=value``
  assignment and are gated on Shannon entropy plus a placeholder
  denylist, because ``password = "changeme"`` is not a finding.
- **Previews never carry the tail.** A report shows a short prefix and
  nothing else, so scan output is safe to paste into an issue or a CI
  log.
- **Fail-open on read errors.** A file we cannot decode is skipped, not
  fatal — scanning must never break a build.

Known limitation — token boundaries. Vendor patterns are anchored with
``\\b`` so ``AKIA``+16 chars does not match inside a longer hex or base64
blob. Build logs are full of hashes, and this runs on every Bash output,
so the false-positive cost of dropping the anchor is real. The price is
that two credentials concatenated with *no* delimiter at all
(``AKIA…EXAMPLEghp_…``) match neither, since neither has a word boundary.
Every realistic separator works — whitespace, newline, ``=``, ``:``,
``,``, quotes, brackets, URL parameters — and a token abutting another
alphanumeric is not well-formed at that boundary anyway. Treat a clean
scan as evidence, not proof.
"""

from __future__ import annotations

import bisect
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

# Redaction marker. Keeps the *kind* so a developer reading a scrubbed
# cache knows what was removed and can go re-run the command themselves.
REDACTION_TEMPLATE = "[REDACTED:{kind}]"

# Directories we never descend when scanning a project. Mirrors
# graphgen._DEFAULT_IGNORES, duplicated rather than imported to keep this
# module dependency-free (graphgen pulls in tree-sitter).
_SCAN_IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".neuralmind",
        "graphify-out",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "target",
        "CMakeFiles",
        "cmake-build-debug",
        "cmake-build-release",
    }
)

# Skip files larger than this when scanning — a credential lives in a
# config file, not a 50 MB fixture, and scanning those is pure latency.
MAX_SCAN_BYTES = 5 * 1024 * 1024

# The state directory is excluded from the walk, but this one file inside it
# can hold a plaintext credential written by a pre-redaction version, so it
# is scanned explicitly. Kept in sync with output_cache.CACHE_FILENAME.
STATE_DIR_NAME = ".neuralmind"
LEGACY_CACHE_FILENAME = "last_output.json"

# Values that match a secret-shaped assignment but are obviously inert.
_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "changeme",
        "change_me",
        "dummy",
        "example",
        "fake",
        "none",
        "null",
        "pass",
        "passwd",
        "password",
        "placeholder",
        "pwd",
        "redacted",
        "sample",
        "secret",
        "test",
        "todo",
        "true",
        "false",
        "undefined",
        "xxx",
        "xxxx",
        "yourkeyhere",
        "your_api_key",
        "your_key_here",
    }
)

# Whole tokens that mark a separator-joined value as descriptive rather than
# secret: "secure_password", "my-api-key". Matched per token, so a real
# high-entropy password ("sup3rS3cretPw") is untouched.
_PLACEHOLDER_TOKENS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pass",
        "pwd",
        "secret",
        "key",
        "token",
        "changeme",
        "example",
        "placeholder",
        "dummy",
        "sample",
        "here",
        "value",
    }
)

# Minimum Shannon entropy (bits/char) for a heuristic assignment match.
# Tuned so base64/hex credentials pass and English words do not.
_MIN_ENTROPY = 3.0


@dataclass(frozen=True)
class SecretMatch:
    """One detected credential span within a piece of text."""

    kind: str
    confidence: str  # "high" | "heuristic"
    start: int
    end: int
    preview: str

    @property
    def marker(self) -> str:
        return REDACTION_TEMPLATE.format(kind=self.kind)


@dataclass(frozen=True)
class SecretFinding:
    """A ``SecretMatch`` located in a file, for scanner reporting."""

    path: str
    line: int
    kind: str
    confidence: str
    preview: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "kind": self.kind,
            "confidence": self.confidence,
            "preview": self.preview,
        }


@dataclass(frozen=True)
class _Pattern:
    kind: str
    regex: re.Pattern
    confidence: str
    # Which capture group holds the secret. A tuple means "the first of
    # these that matched" — needed where one pattern has alternatives for
    # double-quoted, single-quoted and bare values.
    group: int | tuple[int, ...] = 0
    # Run the placeholder denylist even on a high-confidence pattern. Needed
    # where the "secret" is an arbitrary string rather than a vendor-issued
    # token: documentation is full of postgres://user:password@host and
    # postgres://user:****@host, and flagging those as HIGH — the tier that
    # exits non-zero — turns the CI gate into noise.
    check_placeholder: bool = False


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Every vendor pattern is \b-anchored. This is load-bearing, not cosmetic:
# without it ``sk-`` matches inside ta**sk-**, di**sk-**, ri**sk-**,
# ma**sk-**, de**sk-**, fla**sk-**, da**sk-**, so an ordinary branch name
# ("feature/task-management-refactor-v2") or k8s pod name
# ("my-task-runner-7d8f9c5b4-xk2mp") gets shredded in the default-on output
# cache. See TestNoFalsePositivesOnBuildOutput for the regression suite.
_HIGH_CONFIDENCE: tuple[_Pattern, ...] = (
    _Pattern(
        "anthropic-api-key",
        re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}"),
        "high",
    ),
    # Negative lookahead keeps this from double-matching an Anthropic key.
    _Pattern(
        "openai-api-key",
        re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{20,}"),
        "high",
    ),
    _Pattern(
        "aws-access-key-id",
        re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[0-9A-Z]{16}\b"),
        "high",
    ),
    _Pattern(
        "aws-secret-access-key",
        re.compile(
            r"(?i)aws_secret_access_key[ \t]*[:=][ \t]*[\"']?([A-Za-z0-9/+=]{40})",
        ),
        "high",
        group=1,
    ),
    _Pattern(
        "github-token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        "high",
    ),
    _Pattern(
        "github-fine-grained-pat",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
        "high",
    ),
    _Pattern(
        "slack-token",
        re.compile(r"\bxox[baprse]-[A-Za-z0-9-]{10,}\b"),
        "high",
    ),
    _Pattern(
        "google-api-key",
        re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
        "high",
    ),
    _Pattern(
        "stripe-secret-key",
        re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b"),
        "high",
    ),
    _Pattern(
        "pypi-token",
        re.compile(r"\bpypi-[A-Za-z0-9_\-]{16,}"),
        "high",
    ),
    _Pattern(
        "npm-token",
        re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
        "high",
    ),
    _Pattern(
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
        "high",
    ),
    # Only the credential itself is redacted, not the whole header line —
    # keeping "Authorization: Bearer" visible preserves the debugging signal.
    _Pattern(
        "bearer-token",
        re.compile(r"(?i)authorization[ \t]*:[ \t]*bearer[ \t]+([A-Za-z0-9._\-+/=]{12,})"),
        "high",
        group=1,
    ),
    _Pattern(
        "basic-auth-header",
        re.compile(r"(?i)authorization[ \t]*:[ \t]*basic[ \t]+([A-Za-z0-9+/=]{12,})"),
        "high",
        group=1,
    ),
    _Pattern(
        "connection-string-password",
        re.compile(
            r"(?i)\b(?:postgres|postgresql|mysql|mongodb\+srv|mongodb|rediss|redis|amqp)"
            r"://[^:/\s]+:([^@\s/]{3,})@"
        ),
        "high",
        group=1,
        check_placeholder=True,
    ),
)

_HEURISTIC: tuple[_Pattern, ...] = (
    _Pattern(
        "generic-secret-assignment",
        re.compile(
            # (?<![A-Za-z0-9]) rather than \b: `_` is a word character, so \b
            # never fires after one and db_password / DB_PASSWORD /
            # PROD_API_KEY / my_access_token were all invisible — the most
            # common shape a real credential takes. This still rejects
            # mypassword, where a letter precedes the keyword.
            r"(?i)(?<![A-Za-z0-9])(?:api[_-]?key|apikey|secret|secret[_-]?key|"
            r"access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|"
            r"credentials?|private[_-]?key)\b[ \t]*[:=][ \t]*"
            # Quoted values run to their closing quote. A bare value stops at
            # whitespace or a delimiter. Parsing them with one character class
            # truncated quoted secrets at an interior comma or semicolon, so
            # password="Ab9xQ2mZ;SUPERSECRETTAIL" persisted its tail in the
            # output cache — a partial credential left on disk, under a marker
            # claiming it had been redacted.
            r"(?:\"([^\"\n]{8,})\"|'([^'\n]{8,})'|([^\s\"',;]{8,}))"
        ),
        "heuristic",
        group=(1, 2, 3),
    ),
)


# PEM private-key blocks are matched by pairing BEGIN/END markers rather than
# with a single regex. The obvious pattern —
# ``-----BEGIN ... -----[\s\S]*?-----END ... -----`` — is quadratic: every
# unmatched BEGIN marker scans the rest of the buffer looking for an END that
# is not there. Measured on the output-cache hot path, 2 MB of text carrying
# repeated BEGIN markers with no END took **100 seconds**, which would hang the
# PostToolUse hook on something as ordinary as cat-ing a malformed cert bundle.
#
# Pairing instead costs two linear passes plus a binary search per BEGIN.
# ``BLOCK`` covers PGP, whose armor reads "PRIVATE KEY BLOCK-----".
_PEM_BEGIN_RE = re.compile(r"-----BEGIN [A-Z ]{0,40}PRIVATE KEY(?: BLOCK)?-----")
_PEM_END_RE = re.compile(r"-----END [A-Z ]{0,40}PRIVATE KEY(?: BLOCK)?-----")

# An RSA-4096 PEM is roughly 3.2 KB, so this leaves ~2.5x headroom while
# stopping a stray BEGIN marker from pairing with an unrelated END far away
# (which is how a source file discussing PEM formats false-positives).
MAX_PEM_BLOCK_CHARS = 8192


def _find_pem_blocks(text: str) -> list[tuple[int, int]]:
    """Locate ``BEGIN…END`` private-key blocks as (start, end) offsets.

    Linear in the size of the text. An unterminated BEGIN marker yields
    nothing rather than scanning to the end of the buffer.
    """
    begins = list(_PEM_BEGIN_RE.finditer(text))
    if not begins:
        return []
    ends = list(_PEM_END_RE.finditer(text))
    if not ends:
        return []

    end_starts = [m.start() for m in ends]
    blocks: list[tuple[int, int]] = []
    consumed_to = -1

    for begin in begins:
        if begin.start() < consumed_to:
            continue  # already inside a block we emitted
        idx = bisect.bisect_left(end_starts, begin.end())
        if idx >= len(ends):
            continue  # no END after this BEGIN
        end_match = ends[idx]
        if end_match.start() - begin.end() > MAX_PEM_BLOCK_CHARS:
            continue  # too far apart to be one block
        blocks.append((begin.start(), end_match.end()))
        consumed_to = end_match.end()

    return blocks


def _shannon_entropy(value: str) -> float:
    """Bits of entropy per character. Empty string scores 0."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


# Prefix of a marker this module already wrote. Recognised so redaction is
# idempotent: `[REDACTED:anthropic-api-key]` is itself a keyword-shaped,
# high-entropy assignment value, so scrubbing already-scrubbed text used to
# replace the marker with `[REDACTED:generic-secret-assignment]` and lose
# which kind had been removed.
_REDACTION_PREFIX = REDACTION_TEMPLATE.split("{", 1)[0]


def _is_placeholder(value: str) -> bool:
    """True when a secret-shaped value is obviously inert."""
    stripped = value.strip().strip("\"'")
    if stripped.startswith(_REDACTION_PREFIX):
        return True  # already redacted — never re-redact a marker
    low = stripped.lower()
    if low in _PLACEHOLDERS:
        return True
    # Env-var indirection is a reference, not a secret.
    if stripped.startswith(("$", "<", "{", "%")) or "${" in stripped:
        return True
    if low.startswith(("your_", "your-", "my_", "insert_", "replace_", "example")):
        return True
    if "os.environ" in stripped or "process.env" in stripped or "getenv" in low:
        return True
    # All-same-character masks: xxxxxxxx, ********, --------.
    if len(set(stripped)) <= 2:
        return True
    # Separator-joined values naming the thing rather than being it:
    # secure_password, my-api-key, db_secret. Documentation is full of these.
    # A real credential containing "password" as a whole token is a bad
    # credential, so the trade favours a quiet high-confidence tier.
    if any(token in _PLACEHOLDER_TOKENS for token in re.split(r"[-_.]+", low) if token):
        return True
    return False


def _mask(value: str) -> str:
    """A locator-only preview. Never includes the tail of the secret."""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:4]}…({len(value)} chars)"


def _accept(pattern: _Pattern, value: str) -> bool:
    """Confidence gate for a candidate span."""
    if pattern.confidence == "high":
        # Vendor-shaped tokens are self-evidencing; patterns whose captured
        # value is free-form still have to clear the placeholder denylist.
        return not (pattern.check_placeholder and _is_placeholder(value))
    if _is_placeholder(value):
        return False
    return _shannon_entropy(value) >= _MIN_ENTROPY


# Cheap superset prefilter. Every pattern above can only match text that
# contains one of these literals, so when none is present we skip the full
# pattern sweep entirely. This matters because the output cache redacts
# *every* Bash payload up to 2 MB: without it an ordinary build log pays
# ~18 full regex passes for nothing (~370 ms). Substring search is used
# rather than a combined alternation because Python's `re` has no
# multi-literal fast path — the equivalent regex measured ~15x slower
# than these `in` checks.
#
# Over-triggering is harmless (it just costs a sweep); under-triggering
# would be a missed secret, so **any new pattern must add its literal
# here**, lowercased.
_PREFILTER_LITERALS: tuple[str, ...] = (
    "sk-",  # anthropic, openai
    "sk_",
    "rk_",  # stripe
    "akia",
    "asia",
    "agpa",
    "aida",
    "aroa",
    "aipa",
    "anpa",
    "anva",  # aws key id prefixes
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "github_pat_",  # github
    "xox",  # slack
    "aiza",  # google
    "pypi-",
    "npm_",
    "-----begin",  # pem blocks
    "eyj",  # jwt
    "authorization",  # bearer / basic headers
    # Connection strings: match the scheme words, not "://". Every URL in
    # every build log contains "://", so that literal short-circuited
    # almost nothing — an npm log paid the full sweep (460 ms/2 MB) for it.
    # The pattern cannot match without one of these schemes, so this stays
    # a superset while letting ordinary URL-bearing output skip the sweep.
    "postgres",  # also covers postgresql
    "mysql",
    "mongodb",  # also covers mongodb+srv
    "redis",  # also covers rediss
    "amqp",
    # generic assignment keywords (also covers aws_secret_access_key,
    # access_token, auth_token, client_secret)
    "apikey",
    "api_key",
    "api-key",
    "secret",
    "token",
    "password",
    "passwd",
    "credential",
    "privatekey",
    "private_key",
    "private-key",
)


def _may_contain_secret(text: str) -> bool:
    """Fast negative check — True means "run the full sweep"."""
    lowered = text.lower()
    return any(literal in lowered for literal in _PREFILTER_LITERALS)


def scan_text(text: str, include_heuristic: bool = True) -> list[SecretMatch]:
    """Find credential spans in ``text``, sorted by position.

    Overlapping matches collapse to the first (high-confidence patterns
    are evaluated first), so a value never gets redacted twice.
    """
    if not text or not _may_contain_secret(text):
        return []

    patterns = _HIGH_CONFIDENCE + (_HEURISTIC if include_heuristic else ())
    candidates: list[SecretMatch] = []

    # PEM blocks are paired separately — see _find_pem_blocks for why.
    for start, end in _find_pem_blocks(text):
        candidates.append(
            SecretMatch(
                kind="private-key-block",
                confidence="high",
                start=start,
                end=end,
                preview=_mask(text[start:end]),
            )
        )

    for pattern in patterns:
        groups = pattern.group if isinstance(pattern.group, tuple) else (pattern.group,)
        for m in pattern.regex.finditer(text):
            # With alternatives, exactly one branch participates in the match;
            # take the first that did.
            index = next((g for g in groups if m.group(g) is not None), None)
            if index is None:
                continue
            value = m.group(index)
            if not value or not _accept(pattern, value):
                continue
            candidates.append(
                SecretMatch(
                    kind=pattern.kind,
                    confidence=pattern.confidence,
                    start=m.start(index),
                    end=m.end(index),
                    preview=_mask(value),
                )
            )

    # Overlaps are MERGED, never dropped. Dropping the loser used to leave
    # the tail of a longer credential in the clear: the generic-assignment
    # value stops at ";", so
    #     password=redis://default:{pw-containing-a-semicolon}@cache:6379
    # produced a short heuristic span starting first, which discarded the
    # longer connection-string-password span behind it and emitted the
    # marker followed by the rest of that password, still in the clear.
    # (The example uses a braced placeholder deliberately: a literal DSN
    # here would be a finding in this project's own self-scan.)
    # Taking the union of any overlapping run guarantees full coverage
    # regardless of which pattern happened to start earliest.
    candidates.sort(key=lambda s: (s.start, -(s.end - s.start)))

    accepted: list[SecretMatch] = []
    for match in candidates:
        if accepted and match.start < accepted[-1].end:
            prev = accepted[-1]
            if match.end <= prev.end:
                # Coverage is already guaranteed by the enclosing span, but
                # a contained *high-confidence* match must still promote the
                # label. Otherwise API_KEY=AKIA...-extra is reported as
                # heuristic only, and `scan-for-secrets` — which exits
                # non-zero only on high — silently passes the CI gate.
                if match.confidence == "high" and prev.confidence != "high":
                    accepted[-1] = SecretMatch(
                        kind=match.kind,
                        confidence="high",
                        start=prev.start,
                        end=prev.end,
                        preview=prev.preview,
                    )
                continue
            # Extend to the union, keeping the more informative label.
            kind = prev.kind if prev.confidence == "high" else match.kind
            confidence = (
                "high" if "high" in (prev.confidence, match.confidence) else prev.confidence
            )
            accepted[-1] = SecretMatch(
                kind=kind,
                confidence=confidence,
                start=prev.start,
                end=match.end,
                preview=_mask(text[prev.start : match.end]),
            )
        else:
            accepted.append(match)
    return accepted


def redact_text(text: str, include_heuristic: bool = True) -> tuple[str, list[SecretMatch]]:
    """Replace every detected credential with a ``[REDACTED:kind]`` marker.

    Returns the scrubbed text and the matches that were removed. When
    nothing matches, the original string is returned unchanged (identity,
    not a copy) so callers can cheaply detect a no-op.
    """
    matches = scan_text(text, include_heuristic=include_heuristic)
    if not matches:
        return text, []

    out: list[str] = []
    cursor = 0
    for match in matches:
        out.append(text[cursor : match.start])
        out.append(match.marker)
        cursor = match.end
    out.append(text[cursor:])
    return "".join(out), matches


def redaction_enabled() -> bool:
    """True when build-time index redaction is requested.

    Off by default (redacting the index costs recall on legitimately
    secret-shaped identifiers); ``--redact-secrets`` and
    ``NEURALMIND_REDACT_SECRETS=1`` both turn it on.
    """
    return os.environ.get("NEURALMIND_REDACT_SECRETS") == "1"


def redact_if_enabled(text: str) -> str:
    """Scrub ``text`` only when build-time redaction is switched on."""
    if not text or not redaction_enabled():
        return text
    scrubbed, _ = redact_text(text)
    return scrubbed


def _looks_binary(raw: bytes) -> bool:
    """Heuristic binary sniff — a NUL byte in the first 8 KB."""
    return b"\x00" in raw[:8192]


def scan_file(path: str | Path, include_heuristic: bool = True) -> list[SecretFinding]:
    """Scan one file, returning findings with 1-based line numbers.

    Unreadable, oversized, and binary files yield no findings rather than
    raising — a scanner that dies on a stray ``.so`` is useless in CI.
    """
    p = Path(path)
    try:
        if p.stat().st_size > MAX_SCAN_BYTES:
            return []
        raw = p.read_bytes()
    except (OSError, ValueError):
        return []
    if _looks_binary(raw):
        return []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except (UnicodeDecodeError, ValueError):  # pragma: no cover
            return []

    matches = scan_text(text, include_heuristic=include_heuristic)
    if not matches:
        return []

    # Map offsets to line numbers in one pass over the newline positions.
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def line_of(offset: int) -> int:
        lo, hi = 0, len(newlines)
        while lo < hi:
            mid = (lo + hi) // 2
            if newlines[mid] < offset:
                lo = mid + 1
            else:
                hi = mid
        return lo + 1

    return [
        SecretFinding(
            path=str(p),
            line=line_of(m.start),
            kind=m.kind,
            confidence=m.confidence,
            preview=m.preview,
        )
        for m in matches
    ]


def _load_neuralmindignore(root: Path) -> list[str]:
    """Read ``.neuralmindignore`` globs, if present.

    **Opt-in only.** ``.neuralmindignore`` is tuned for retrieval quality,
    not for security — this very repository excludes ``docs/``, ``*.md``
    and ``tests/`` from it because markdown dilutes code retrieval. Letting
    a secret scanner inherit that list would silently skip the places
    credentials most often sit and report a false all-clear. The scanner
    therefore reads everything by default; a caller must ask for these
    globs explicitly.
    """
    path = root / ".neuralmindignore"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _matches_ignore(rel_path: str, patterns: list[str]) -> bool:
    """``.gitignore``-style glob match against a project-relative path."""
    if not patterns:
        return False
    from fnmatch import fnmatch

    parts = rel_path.split("/")
    for pattern in patterns:
        cleaned = pattern.rstrip("/")
        if fnmatch(rel_path, pattern) or fnmatch(parts[-1], pattern):
            return True
        # A directory pattern matches everything beneath it.
        if any(fnmatch(part, cleaned) for part in parts[:-1]):
            return True
        if rel_path.startswith(cleaned + "/"):
            return True
    return False


def scan_project(
    root: str | Path,
    include_heuristic: bool = True,
    ignore_dirs: frozenset[str] | None = None,
    respect_ignore_file: bool = False,
) -> list[SecretFinding]:
    """Walk ``root`` and scan every non-binary file.

    Reads everything except vendored/build directories. ``.neuralmindignore``
    is honoured **only** when ``respect_ignore_file`` is True — see
    :func:`_load_neuralmindignore` for why that is not the default. Paths in
    the result are project-relative so output is stable across machines (and
    safe to paste into an issue).
    """
    root_path = Path(root).resolve()
    ignores = ignore_dirs if ignore_dirs is not None else _SCAN_IGNORE_DIRS
    globs = _load_neuralmindignore(root_path) if respect_ignore_file else []
    findings: list[SecretFinding] = []

    # The state directory is pruned below, but a cache written by a version
    # before redaction existed is plaintext and untracked — so neither
    # `scan-for-secrets` nor `git ls-files` would surface it, and the
    # documented upgrade path would report all-clear while `neuralmind last`
    # still handed the credential back. Scan that one file explicitly.
    legacy_cache = root_path / STATE_DIR_NAME / LEGACY_CACHE_FILENAME
    if legacy_cache.is_file():
        for finding in scan_file(legacy_cache, include_heuristic=include_heuristic):
            findings.append(
                SecretFinding(
                    path=f"{STATE_DIR_NAME}/{LEGACY_CACHE_FILENAME}",
                    line=finding.line,
                    kind=finding.kind,
                    confidence=finding.confidence,
                    preview=finding.preview,
                )
            )

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(d for d in dirnames if d not in ignores)
        if globs:
            dirnames[:] = [
                d
                for d in dirnames
                if not _matches_ignore((Path(dirpath) / d).relative_to(root_path).as_posix(), globs)
            ]
        for name in sorted(filenames):
            fpath = Path(dirpath) / name
            if fpath.is_symlink():
                continue
            if globs and _matches_ignore(fpath.relative_to(root_path).as_posix(), globs):
                continue
            for finding in scan_file(fpath, include_heuristic=include_heuristic):
                try:
                    rel = str(Path(finding.path).resolve().relative_to(root_path))
                except ValueError:  # pragma: no cover - outside root
                    rel = finding.path
                findings.append(
                    SecretFinding(
                        path=rel,
                        line=finding.line,
                        kind=finding.kind,
                        confidence=finding.confidence,
                        preview=finding.preview,
                    )
                )
    return findings
