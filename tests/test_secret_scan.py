"""Tests for neuralmind.secret_scan — credential detection and redaction.

Stdlib-only (no chromadb/tree-sitter), matching the synapse layer's
convention so these run on a bare install.
"""

from __future__ import annotations

import pytest

from neuralmind.secret_scan import (
    _HEURISTIC,
    _HIGH_CONFIDENCE,
    REDACTION_TEMPLATE,
    _may_contain_secret,
    redact_if_enabled,
    redact_text,
    scan_file,
    scan_project,
    scan_text,
)
from tests.secret_fixtures import (
    ANTHROPIC_KEY,
    AWS_KEY_ID,
    AWS_SECRET,
    GENERIC_SECRET,
    GITHUB_TOKEN,
    GOOGLE_KEY,
    JWT,
    OPENAI_KEY,
    PEM_BLOCK,
    PG_PASSWORD,
    SLACK_TOKEN,
    STRIPE_KEY,
)

# (label, text, expected kind) — one per vendor shape we claim to catch.
HIGH_CONFIDENCE_CASES = [
    ("anthropic", f"ANTHROPIC_API_KEY={ANTHROPIC_KEY}", "anthropic-api-key"),
    ("openai", f'OPENAI_API_KEY="{OPENAI_KEY}"', "openai-api-key"),
    ("aws-id", f"AWS_ACCESS_KEY_ID={AWS_KEY_ID}", "aws-access-key-id"),
    ("aws-secret", f"aws_secret_access_key = {AWS_SECRET}", "aws-secret-access-key"),
    ("github", GITHUB_TOKEN, "github-token"),
    ("slack", SLACK_TOKEN, "slack-token"),
    ("google", GOOGLE_KEY, "google-api-key"),
    ("stripe", STRIPE_KEY, "stripe-secret-key"),
    ("jwt", JWT, "jwt"),
    (
        "pg-url",
        f"DATABASE_URL=postgres://admin:{PG_PASSWORD}@db.internal:5432/app",
        "connection-string-password",
    ),
    ("pem", PEM_BLOCK, "private-key-block"),
]

# Values that look secret-shaped but carry nothing sensitive.
BENIGN_CASES = [
    ("placeholder", "API_KEY=changeme"),
    ("your-key", 'api_key = "your_api_key_here"'),
    ("env-ref", "API_KEY=${OPENAI_API_KEY}"),
    ("os-environ", 'api_key = os.environ["FOO"]'),
    ("getenv", 'secret = os.getenv("APP_SECRET")'),
    ("prose", "The password reset flow sends an email to the user."),
    ("mask", 'password = "********"'),
    ("docstring", "Validates user credentials and returns a session."),
    ("too-short", 'token = "abc"'),
]


class TestScanText:
    @pytest.mark.parametrize("label,text,kind", HIGH_CONFIDENCE_CASES)
    def test_detects_vendor_shapes(self, label, text, kind):
        kinds = [m.kind for m in scan_text(text)]
        assert kind in kinds, f"{label}: expected {kind}, got {kinds}"

    @pytest.mark.parametrize("label,text", BENIGN_CASES)
    def test_no_false_positive(self, label, text):
        assert scan_text(text) == [], f"{label}: unexpected hit"

    def test_empty_text(self):
        assert scan_text("") == []

    def test_generic_assignment_is_heuristic(self):
        matches = scan_text(f'client_secret: "{GENERIC_SECRET}"')
        assert matches
        assert matches[0].confidence == "heuristic"

    def test_heuristics_can_be_disabled(self):
        text = f'client_secret: "{GENERIC_SECRET}"'
        assert scan_text(text, include_heuristic=False) == []

    def test_matches_do_not_overlap(self):
        text = f"key={ANTHROPIC_KEY} and more"
        matches = scan_text(text)
        for a, b in zip(matches, matches[1:], strict=False):
            assert a.end <= b.start

    def test_bearer_header_matches_the_token_only(self):
        """The header name stays readable; only the credential is a match."""
        text = f"Authorization: Bearer {GITHUB_TOKEN}"
        match = scan_text(text)[0]
        assert text[match.start : match.end].startswith("ghp_")

    def test_preview_never_leaks_the_tail(self):
        secret = ANTHROPIC_KEY
        match = scan_text(f"KEY={secret}")[0]
        assert secret[-6:] not in match.preview
        assert match.preview.startswith("sk-a")


class TestRedactText:
    def test_replaces_secret_with_marker(self):
        out, matches = redact_text(f"KEY={ANTHROPIC_KEY}")
        assert ANTHROPIC_KEY not in out
        assert REDACTION_TEMPLATE.format(kind="anthropic-api-key") in out
        assert len(matches) == 1

    def test_clean_text_returned_unchanged(self):
        text = "def hello():\n    return 1\n"
        out, matches = redact_text(text)
        assert out is text  # identity, so callers can detect a no-op
        assert matches == []

    def test_redacts_multiple_distinct_kinds(self):
        text = (
            f"export ANTHROPIC_API_KEY={ANTHROPIC_KEY}\n"
            f'curl -H "Authorization: Bearer {GITHUB_TOKEN}"\n'
        )
        out, matches = redact_text(text)
        assert {m.kind for m in matches} == {"anthropic-api-key", "github-token"}
        assert ANTHROPIC_KEY not in out
        assert GITHUB_TOKEN not in out

    def test_surrounding_text_is_preserved(self):
        out, _ = redact_text(f"before KEY={AWS_KEY_ID} after")
        assert out.startswith("before ")
        assert out.endswith(" after")


class TestRedactIfEnabled:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("NEURALMIND_REDACT_SECRETS", raising=False)
        text = f"KEY={ANTHROPIC_KEY}"
        assert redact_if_enabled(text) == text

    def test_on_when_flag_set(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_REDACT_SECRETS", "1")
        assert ANTHROPIC_KEY not in redact_if_enabled(f"KEY={ANTHROPIC_KEY}")


class TestScanFile:
    def test_reports_line_numbers(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text(f"import os\n\nAPI_KEY = '{ANTHROPIC_KEY}'\n")
        findings = scan_file(f)
        assert len(findings) == 1
        assert findings[0].line == 3

    def test_binary_file_skipped(self, tmp_path):
        f = tmp_path / "blob.bin"
        f.write_bytes(b"\x00\x01" + ANTHROPIC_KEY.encode())
        assert scan_file(f) == []

    def test_missing_file_is_not_fatal(self, tmp_path):
        assert scan_file(tmp_path / "nope.txt") == []

    def test_oversized_file_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr("neuralmind.secret_scan.MAX_SCAN_BYTES", 10)
        f = tmp_path / "big.env"
        f.write_text(AWS_KEY_ID * 10)
        assert scan_file(f) == []


class TestScanProject:
    def test_finds_secret_and_reports_relative_path(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "conf.py").write_text(f"KEY='{AWS_KEY_ID}'\n")
        findings = scan_project(tmp_path)
        assert len(findings) == 1
        assert findings[0].path.replace("\\", "/") == "src/conf.py"

    def test_scans_dotenv_files(self, tmp_path):
        """.env is skipped by the *indexer*, but the scanner must still see it."""
        (tmp_path / ".env").write_text(f"ANTHROPIC_API_KEY={ANTHROPIC_KEY}\n")
        assert [f.kind for f in scan_project(tmp_path)] == ["anthropic-api-key"]

    def test_skips_ignored_directories(self, tmp_path):
        state = tmp_path / ".neuralmind"
        state.mkdir()
        (state / "last_output.json").write_text(AWS_KEY_ID)
        vendored = tmp_path / "node_modules"
        vendored.mkdir()
        (vendored / "x.js").write_text(AWS_KEY_ID)
        assert scan_project(tmp_path) == []

    def test_clean_project_yields_nothing(self, tmp_path):
        (tmp_path / "main.py").write_text("def main():\n    return 0\n")
        assert scan_project(tmp_path) == []


class TestPrefilter:
    """The prefilter is a performance shortcut that must never lose a match.

    scan_text() returns early when no literal is present, so a pattern
    whose literal is missing from _PREFILTER_LITERALS would silently stop
    detecting. These tests are the guard on that contract.
    """

    @pytest.mark.parametrize("label,text,kind", HIGH_CONFIDENCE_CASES)
    def test_every_positive_passes_the_prefilter(self, label, text, kind):
        assert _may_contain_secret(text), f"{label}: prefilter would skip a real secret"

    def test_every_registered_pattern_is_covered(self):
        """Each pattern must have a literal, proven via a string it matches."""
        uncovered = []
        for pattern in _HIGH_CONFIDENCE + _HEURISTIC:
            # Build a probe from the shared corpus that this pattern matches,
            # then assert the prefilter admits it.
            probes = [t for _, t, _ in HIGH_CONFIDENCE_CASES] + [
                f'client_secret: "{GENERIC_SECRET}"'
            ]
            matched = [p for p in probes if pattern.regex.search(p)]
            if matched and not all(_may_contain_secret(p) for p in matched):
                uncovered.append(pattern.kind)
        assert uncovered == [], f"patterns not covered by the prefilter: {uncovered}"

    def test_ordinary_output_is_skipped(self):
        """The common case — no literal, no sweep."""
        assert not _may_contain_secret("PASSED tests/test_foo.py::test_bar\n" * 100)
        assert not _may_contain_secret("[INFO] compiling module foo/bar/baz.py ok\n" * 100)

    def test_prefilter_is_case_insensitive(self):
        assert _may_contain_secret("AUTHORIZATION: BEARER abc")
        assert _may_contain_secret("authorization: bearer abc")
