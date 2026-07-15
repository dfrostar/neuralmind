"""Tests for test-coverage gap detection (prototype).

Stdlib-only. The pure core (normalize_path, classify) is tested on data
structures; the Express/Jest extractors are tested against the committed
fixture in ``tests/fixtures/express_gaps``.
"""

from __future__ import annotations

import os

from neuralmind.gaps import (
    Endpoint,
    TestRef,
    classify,
    extract_routes,
    extract_test_refs,
    format_gaps,
    normalize_path,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "express_gaps")


# --- pure core -------------------------------------------------------------- #


def test_normalize_collapses_every_param_style():
    assert normalize_path("/api/users/:id") == "/api/users/:param"
    assert normalize_path("/api/users/{id}") == "/api/users/:param"
    assert normalize_path("/api/users/${userId}") == "/api/users/:param"
    assert normalize_path("/api/users/*") == "/api/users/:param"


def test_normalize_matches_registration_to_template_literal():
    assert normalize_path("/api/sessions/:id") == normalize_path("/api/sessions/${id}")


def test_normalize_drops_trailing_slash_and_quotes():
    assert normalize_path("`/api/sessions/`") == "/api/sessions"


def test_classify_untested():
    eps = [Endpoint("post", "/api/auth/jwk/rotate")]
    gaps = classify(eps, [])
    assert gaps[0].status == "untested"
    assert gaps[0].test_count == 0


def test_classify_mock_only_when_all_skipped():
    eps = [Endpoint("post", "/api/sessions")]
    refs = [TestRef("/api/sessions", skipped=True, hits_real_db=False) for _ in range(3)]
    gaps = classify(eps, refs)
    assert gaps[0].status == "mock-only"
    assert gaps[0].test_count == 3
    assert gaps[0].all_skipped


def test_classify_live_covered_when_unskipped_real_db():
    eps = [Endpoint("get", "/health")]
    refs = [TestRef("/health", skipped=False, hits_real_db=True)]
    assert classify(eps, refs)[0].status == "live-covered"


def test_classify_matches_param_route_via_template_literal():
    eps = [Endpoint("get", "/api/sessions/:id")]
    refs = [TestRef("/api/sessions/${id}", skipped=True, hits_real_db=False)]
    assert classify(eps, refs)[0].status == "mock-only"


# --- extractors against the committed fixture ------------------------------- #


def _read(name):
    with open(os.path.join(FIXTURE, name), encoding="utf-8") as fh:
        return fh.read()


def test_extract_routes_finds_app_and_router_registrations():
    routes = {e.key for e in extract_routes(_read("server.js"))}
    assert "POST /api/sessions" in routes
    assert "GET /api/sessions/:param" in routes
    assert "GET /.well-known/jwks.json" in routes
    assert "POST /api/auth/jwk/rotate" in routes  # router.post, not app.post
    assert "GET /api/costs/avoidance" in routes


def test_end_to_end_flags_the_mock_only_trap():
    routes = extract_routes(_read("server.js"))
    refs = extract_test_refs(_read("server.test.js"))
    gaps = {g.endpoint.key: g for g in classify(routes, refs)}

    # The P2003 hiding spot: tested but mock-only.
    assert gaps["POST /api/sessions"].status == "mock-only"
    assert gaps["POST /api/sessions"].test_count == 3
    # Live control: /health hits the real DB fixture, unskipped.
    assert gaps["GET /health"].status == "live-covered"
    # Genuinely untested endpoints.
    assert gaps["POST /api/auth/jwk/rotate"].status == "untested"
    assert gaps["GET /api/costs/avoidance"].status == "untested"


def test_format_groups_by_status():
    routes = extract_routes(_read("server.js"))
    refs = extract_test_refs(_read("server.test.js"))
    text = format_gaps(classify(routes, refs))
    assert "POST /api/sessions" in text
    assert "no tests" in text
    assert "SKIP_PG" in text


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
