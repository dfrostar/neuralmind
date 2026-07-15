"""Test-coverage gap detection — "find what you think you tested" (PROTOTYPE).

NeuralMind indexes endpoints and test files, but never crosses them. So a route
that passes its whole suite *in mock mode* — an in-memory store that accepts any
string where Postgres would reject a non-UUID foreign key — reads as "green"
right up until it hits a live database and throws. That is the exact shape of
the P2003 incident: three passing tests, all ``SKIP_PG``-guarded, zero live
coverage, one production failure.

This module surfaces that gap. It classifies every registered route as:

    live-covered  — has a non-skipped test that touches the real DB
    mock-only     — has tests, but all are skipped / never touch the DB
    untested      — no test references it at all

Design mirrors the other prototypes: the classifier and path normalizer are
pure and framework-agnostic, tested exhaustively on data structures. The
Express/Jest *extractors* are the framework-coupled Phase-1 heuristics — regex
over JS/TS source, deliberately narrow (Express `app`/`router` route
registration; Jest `it`/`test` blocks). They are honest heuristics, not a
parser; a real build would back them with the tree-sitter index NeuralMind
already holds, or an LSP.

Status: prototype. Demonstrated against ``tests/fixtures/express_gaps``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")

# --------------------------------------------------------------------------- #
# Pure core — path normalization + classification (framework-agnostic)
# --------------------------------------------------------------------------- #

_TEMPLATE_EXPR = re.compile(r"\$\{[^}]*\}")  # `${id}` in a template literal
_EXPRESS_PARAM = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")  # /users/:id
_BRACE_PARAM = re.compile(r"\{[^}]*\}")  # /users/{id}
_WILDCARD = re.compile(r"\*+")


def normalize_path(path: str) -> str:
    """Collapse every parameter style to a single canonical ``:param`` token.

    So ``/api/users/:id``, ``/api/users/{id}``, ``/api/users/${userId}`` and
    ``/api/users/*`` all normalize to ``/api/users/:param`` and match each
    other across the route-registration side and the test-reference side.
    Trailing slashes are dropped; case is preserved (paths are case-sensitive).
    """
    p = path.strip().strip("\"'`")
    p = _TEMPLATE_EXPR.sub(":param", p)
    p = _EXPRESS_PARAM.sub(":param", p)
    p = _BRACE_PARAM.sub(":param", p)
    p = _WILDCARD.sub(":param", p)
    if len(p) > 1:
        p = p.rstrip("/")
    return p


@dataclass(frozen=True)
class Endpoint:
    """A registered route: HTTP method + normalized path."""

    method: str
    path: str

    @property
    def key(self) -> str:
        return f"{self.method.upper()} {normalize_path(self.path)}"


@dataclass(frozen=True)
class TestRef:
    """A test case that references a route path.

    ``skipped`` — guarded so it never runs the real path (``SKIP_PG``,
    ``it.skip``). ``hits_real_db`` — the enclosing file touches a real-DB
    fixture *and* this case is not skipped.
    """

    path: str
    skipped: bool
    hits_real_db: bool
    name: str = ""


@dataclass(frozen=True)
class Gap:
    """Classification of one endpoint against the tests that reference it."""

    endpoint: Endpoint
    status: str  # "live-covered" | "mock-only" | "untested"
    test_count: int
    all_skipped: bool


def classify(endpoints: list[Endpoint], refs: list[TestRef]) -> list[Gap]:
    """Classify each endpoint by the strongest coverage any test gives it.

    Matching is path-normalized (method-agnostic on the test side, since test
    references rarely restate the verb). ``live-covered`` if any referencing
    test hits the real DB unskipped; ``mock-only`` if referenced but never
    live; ``untested`` if no test references the path.
    """
    by_path: dict[str, list[TestRef]] = {}
    for r in refs:
        by_path.setdefault(normalize_path(r.path), []).append(r)

    gaps: list[Gap] = []
    for ep in endpoints:
        matched = by_path.get(normalize_path(ep.path), [])
        if not matched:
            gaps.append(Gap(ep, "untested", 0, True))
            continue
        live = any(r.hits_real_db and not r.skipped for r in matched)
        all_skipped = all(r.skipped for r in matched)
        status = "live-covered" if live else "mock-only"
        gaps.append(Gap(ep, status, len(matched), all_skipped))
    return gaps


# --------------------------------------------------------------------------- #
# Framework-coupled extractors — Express + Jest, Phase-1 heuristics
# --------------------------------------------------------------------------- #

_ROUTE_RE = re.compile(
    r"\b(?:app|router)\.(" + "|".join(HTTP_METHODS) + r")\(\s*([`'\"])(.*?)\2",
    re.IGNORECASE,
)
_REAL_DB_RE = re.compile(r"""from\s+['"](?:@/db|@/repositories)['"]|\btestDb\b""")
_PATH_LITERAL_RE = re.compile(r"[`'\"](/[^`'\"]*)[`'\"]")
_NAME_PATH_RE = re.compile(r"(/[\w./:${}*-]+)")
# The it()/test() opener, capturing an optional .skip/.only and the case name.
_TEST_OPEN_RE = re.compile(r"\b(?:it|test)(\.skip|\.only)?\s*\(\s*([`'\"])(.*?)\2")


def extract_routes(source: str) -> list[Endpoint]:
    """Extract Express route registrations from JS/TS source (heuristic)."""
    out: list[Endpoint] = []
    seen: set[str] = set()
    for method, _q, path in _ROUTE_RE.findall(source):
        ep = Endpoint(method.lower(), path)
        if ep.key not in seen:
            seen.add(ep.key)
            out.append(ep)
    return out


def _callback_body(source: str, from_index: int) -> str:
    """Return the brace-matched callback body starting at/after ``from_index``.

    Finds the first ``{`` after the test opener and matches to its closing
    ``}`` so a case's skip markers and path literals are read from *its own*
    body only — not bled in from the next case or a trailing comment.
    """
    open_idx = source.find("{", from_index)
    if open_idx == -1:
        return ""
    depth = 0
    for j in range(open_idx, len(source)):
        c = source[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return source[open_idx : j + 1]
    return source[open_idx:]


def extract_test_refs(source: str) -> list[TestRef]:
    """Extract Jest test cases and the route paths they reference (heuristic).

    A file that imports a real-DB fixture is *live-capable*. A case is
    ``skipped`` when it uses ``.skip`` or guards on ``SKIP_PG`` (in its name or
    body). Paths are read from both the case *name* (tests routinely name the
    route without restating it in the body) and body string literals; each
    distinct route a case references yields one ``TestRef``.
    """
    file_has_real_db = bool(_REAL_DB_RE.search(source))
    refs: list[TestRef] = []

    for m in _TEST_OPEN_RE.finditer(source):
        name = m.group(3)
        body = _callback_body(source, m.end())
        explicit_skip = m.group(1) == ".skip"
        skipped = explicit_skip or ("SKIP_PG" in body) or ("SKIP_PG" in name)

        paths = set(_NAME_PATH_RE.findall(name)) | set(_PATH_LITERAL_RE.findall(body))
        for path in paths:
            refs.append(
                TestRef(
                    path=normalize_path(path),
                    skipped=skipped,
                    hits_real_db=file_has_real_db and not skipped,
                    name=name,
                )
            )
    return refs


def format_gaps(gaps: list[Gap]) -> str:
    """Render the gap report in the shape the roadmap/spec specify."""
    mock = [g for g in gaps if g.status == "mock-only"]
    untested = [g for g in gaps if g.status == "untested"]
    live = [g for g in gaps if g.status == "live-covered"]

    lines: list[str] = ["## neuralmind gaps — live-Postgres coverage", ""]
    if mock:
        lines.append("Routes tested in-memory only (no live-DB coverage):")
        for g in sorted(mock, key=lambda g: g.endpoint.key):
            skip = " — all SKIP_PG" if g.all_skipped else ""
            n = g.test_count
            lines.append(f"  {g.endpoint.key:<32} — {n} test{'s' if n != 1 else ''}{skip}  ❌")
        lines.append("")
    if untested:
        lines.append("Endpoints with no tests:")
        for g in sorted(untested, key=lambda g: g.endpoint.key):
            lines.append(f"  {g.endpoint.key:<32} ⚠️")
        lines.append("")
    if live:
        lines.append("Live-covered:")
        for g in sorted(live, key=lambda g: g.endpoint.key):
            lines.append(f"  {g.endpoint.key:<32} ✅")
    return "\n".join(lines).rstrip()
