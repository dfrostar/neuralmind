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
    BASIC_AUTH_B64,
    GENERIC_SECRET,
    GITHUB_TOKEN,
    GOOGLE_KEY,
    JWT,
    OPENAI_KEY,
    PEM_BLOCK,
    PG_PASSWORD,
    SLACK_TOKEN,
    STRIPE_KEY,
    pem_begin,
    pem_end,
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


class TestPemBlocks:
    """PEM pairing is hand-rolled because the obvious regex is quadratic."""

    def test_detects_a_block(self):
        text = f"prefix\n{PEM_BLOCK}\nsuffix"
        matches = scan_text(text)
        assert [m.kind for m in matches] == ["private-key-block"]

    def test_detects_multiple_blocks(self):
        text = f"{PEM_BLOCK}\n\n{PEM_BLOCK}"
        assert [m.kind for m in scan_text(text)] == [
            "private-key-block",
            "private-key-block",
        ]

    def test_redaction_preserves_surrounding_text(self):
        out, _ = redact_text(f"before\n{PEM_BLOCK}\nafter")
        assert out == "before\n[REDACTED:private-key-block]\nafter"

    def test_unterminated_begin_marker_yields_nothing(self):
        assert scan_text(f"{pem_begin()}\nAAAA\n") == []

    def test_end_too_far_away_is_not_paired(self):
        from neuralmind.secret_scan import MAX_PEM_BLOCK_CHARS

        text = f"{pem_begin()}\n" + "A" * (MAX_PEM_BLOCK_CHARS + 10) + f"\n{pem_end()}"
        assert scan_text(text) == []

    def test_unterminated_markers_do_not_blow_up(self):
        """Regression: the quadratic pattern took 100s on this input.

        Many BEGIN markers with no END made every marker scan the rest of
        the buffer. On the output-cache hot path that hung the PostToolUse
        hook. The bound is deliberately loose — it only needs to catch a
        return to quadratic behaviour, not police normal variance.
        """
        import time

        unit = f"{pem_begin()}\n" + ("A" * 64 + "\n") * 4
        text = unit * (1_000_000 // len(unit))  # ~1 MB

        start = time.perf_counter()
        matches = scan_text(text)
        elapsed = time.perf_counter() - start

        assert matches == []
        assert elapsed < 5.0, f"scan took {elapsed:.1f}s — quadratic behaviour is back"


class TestHeaderTokens:
    def test_bearer_does_not_span_a_newline(self):
        """Regression: \\s+ let the token match the *next* line's text."""
        text = "Authorization: Bearer \nAuthorization: Bearer \n"
        assert scan_text(text) == []

    def test_bearer_still_matches_on_one_line(self):
        matches = scan_text(f"Authorization: Bearer {GITHUB_TOKEN}")
        assert matches
        assert matches[0].kind == "github-token"

    def test_basic_auth_header(self):
        matches = scan_text(f"Authorization: Basic {BASIC_AUTH_B64}")
        assert [m.kind for m in matches] == ["basic-auth-header"]

    def test_basic_does_not_span_a_newline(self):
        assert scan_text("Authorization: Basic \nQUJDREVGR0hJSktM\n") == []


class TestTokenBoundaries:
    """Vendor patterns are \\b-anchored to avoid firing inside hashes.

    These pin the separators that must keep working, and document the
    one case the anchoring gives up on.
    """

    @pytest.mark.parametrize(
        "label,template",
        [
            ("newline", "line\n{s}\nnext"),
            ("space", "key {s} end"),
            ("equals", "AWS_ACCESS_KEY_ID={s}"),
            ("json-quotes", '{{"key":"{s}"}}'),
            ("url-param", "https://h/?token={s}&x=1"),
            ("shell-export", "export K={s};"),
            ("comma", "a,{s},b"),
            ("tab", "a\t{s}\tb"),
            ("colon", "aws:{s}"),
            ("yaml", "  key: {s}"),
            ("bracket", "[{s}]"),
            ("end-of-string", "trailing {s}"),
        ],
    )
    def test_realistic_separators_still_match(self, label, template):
        text = template.format(s=AWS_KEY_ID)
        assert [m.kind for m in scan_text(text)] == ["aws-access-key-id"], label

    def test_two_secrets_on_one_line_both_match(self):
        text = f"{AWS_KEY_ID} {GITHUB_TOKEN}"
        assert {m.kind for m in scan_text(text)} == {
            "aws-access-key-id",
            "github-token",
        }

    def test_documented_limitation_zero_delimiter_concatenation(self):
        """Known gap: back-to-back credentials with no separator at all.

        Neither token has a word boundary, so neither matches. Dropping
        the \\b anchor would fix this at the cost of firing inside every
        hex/base64 hash in a build log — a bad trade on a path that runs
        on every Bash output. Documented in the module docstring and the
        security docs rather than silently patched.

        This test exists so the behaviour is a recorded decision rather
        than an unexamined surprise. If a future change makes these match
        without regressing the false-positive suite, delete it.
        """
        assert scan_text(f"{AWS_KEY_ID}{GITHUB_TOKEN}") == []


# Real-world command output that must survive redaction untouched. The
# output cache redacts every Bash payload by default, so a false positive
# here silently corrupts what `neuralmind last` gives back.
#
# The "sk-" family is deliberately over-represented: an unanchored
# `sk-` pattern matches inside task-, disk-, risk-, mask-, desk-, flask-,
# dask-, which shredded 4 of 10 ordinary lines before the \b was added.
BUILD_OUTPUT_LINES = [
    "git checkout feature/task-management-refactor-v2",
    "git branch -D bugfix/disk-usage-reporting-overhaul",
    "pod/my-task-runner-7d8f9c5b4-xk2mp   Running   0   4d",
    "  desk-booking-api-prod-deployment   3/3   Running   0   12d",
    "Downloading disk-utils-2.39.3-linux-amd64.tar.gz",
    "Installing flask-sqlalchemy-3.1.1-py3-none-any.whl",
    "npm ERR! dask-distributed-2024.1.0 requires python>=3.9",
    "WARN  risk-assessment-service-v1.2.0 has a deprecated peer dep",
    "src/mask-generator/index.ts:42:7 - error TS2322: Type mismatch",
    "ok  github.com/org/repo/internal/task-queue  0.312s",
    "PASSED tests/test_foo.py::test_bar",
    "[INFO] compiling module foo/bar/baz.py ok",
    "  1234567890abcdef1234567890abcdef12345678  refs/heads/main",
    "Successfully built 9f8e7d6c5b4a3210fedcba9876543210deadbeef",
    "  remote: Resolving deltas: 100% (1234/1234), done.",
    "-rw-r--r--  1 user staff  4096 Aug 24 14:00 database-migration-runner.sql",
    "docker.io/library/postgres@sha256:abcdef0123456789abcdef0123456789abcdef01",
    "Run `terraform apply -target=module.disk-encryption-baseline`",
]


class TestNoFalsePositivesOnBuildOutput:
    """The default-on output cache must not corrupt ordinary command output.

    Regression suite for the unanchored `sk-` pattern, which matched
    inside task-/disk-/risk-/mask-/desk- and mangled branch names, pod
    names and package filenames.
    """

    @pytest.mark.parametrize("line", BUILD_OUTPUT_LINES)
    def test_line_is_not_redacted(self, line):
        out, matches = redact_text(line)
        assert matches == [], f"false positive: {[m.kind for m in matches]}"
        assert out == line

    def test_whole_corpus_is_untouched(self):
        blob = "\n".join(BUILD_OUTPUT_LINES)
        out, matches = redact_text(blob)
        assert matches == []
        assert out is blob  # identity — proves the no-op path was taken

    @pytest.mark.parametrize(
        "word", ["task", "disk", "risk", "mask", "desk", "flask", "dask", "brisk"]
    )
    def test_sk_prefixed_words_do_not_match(self, word):
        """`sk-` inside an ordinary word is not the start of a key."""
        text = f"{word}-management-refactor-v2-prod-cluster"
        assert scan_text(text) == []

    def test_sk_prefixed_word_before_ant_does_not_match(self):
        """The anthropic pattern had the same hole: ta+sk-ant-..."""
        assert scan_text("task-ant-omation-service-v2-prod") == []

    @pytest.mark.parametrize(
        "context",
        ["{k}", "KEY={k}", '"{k}"', "export X={k};", "line\n{k}\nnext", "  key: {k}"],
    )
    def test_anchoring_does_not_break_real_anthropic_keys(self, context):
        assert scan_text(context.format(k=ANTHROPIC_KEY))

    @pytest.mark.parametrize(
        "context",
        ["{k}", "KEY={k}", '"{k}"', "export X={k};", "line\n{k}\nnext", "  key: {k}"],
    )
    def test_anchoring_does_not_break_real_openai_keys(self, context):
        assert scan_text(context.format(k=OPENAI_KEY))


# Vendor patterns where the credential itself is the whole match. The
# contextual ones (aws_secret_access_key=…, Authorization: …) are excluded:
# they are anchored by the surrounding keyword, not by a token boundary.
ANCHORED_FIXTURES = [
    ("anthropic-api-key", ANTHROPIC_KEY),
    ("openai-api-key", OPENAI_KEY),
    ("aws-access-key-id", AWS_KEY_ID),
    ("github-token", GITHUB_TOKEN),
    ("slack-token", SLACK_TOKEN),
    ("google-api-key", GOOGLE_KEY),
    ("stripe-secret-key", STRIPE_KEY),
    ("jwt", JWT),
]


class TestPatternAnchoringInvariant:
    """Every vendor pattern must require a token boundary.

    This is the invariant whose violation shredded ordinary build output:
    the `sk-` patterns were written without `\\b`, so they matched inside
    task-/disk-/risk-. Asserting it behaviourally — rather than claiming
    it in a docstring, which is what let the bug through — means a new
    pattern added without an anchor fails here.
    """

    @pytest.mark.parametrize("kind,secret", ANCHORED_FIXTURES)
    def test_not_matched_mid_identifier(self, kind, secret):
        """A credential shape inside a longer identifier is not a credential."""
        kinds = [m.kind for m in scan_text(f"deploybot{secret}")]
        assert kind not in kinds, f"{kind} matched without a leading boundary"

    @pytest.mark.parametrize("kind,secret", ANCHORED_FIXTURES)
    def test_still_matched_at_a_boundary(self, kind, secret):
        """The anchor must not cost a real detection."""
        kinds = [m.kind for m in scan_text(f"value = {secret}")]
        assert kind in kinds, f"{kind} lost at a legitimate boundary"


class TestIndexRedactionCoversEveryBackend:
    """`--redact-secrets` must apply on whichever backend is actually in use.

    turbovec is the shipped default (v0.46.0+); ChromaDB is the opt-in
    extra. Wiring redaction into only one of them would leave the flag a
    silent no-op for most users, which is worse than not offering it.
    """

    @staticmethod
    def _node():
        return {
            "label": f"KEY = {ANTHROPIC_KEY}",
            "file_type": "code",
            "source_file": "cfg.py",
        }

    def _node_to_text(self, cls):
        # _node_to_text touches no instance state, so an uninitialised
        # instance is enough and avoids requiring the backend's runtime.
        return cls._node_to_text(cls.__new__(cls), self._node())

    def _backends(self):
        from neuralmind.in_memory_backend import InMemoryEmbeddingBackend
        from neuralmind.turbovec_backend import TurboVecEmbedder

        backends = [
            ("turbovec", TurboVecEmbedder),  # shipped default
            ("in_memory", InMemoryEmbeddingBackend),  # selectable via config
        ]
        try:
            from neuralmind.embedder import GraphEmbedder

            backends.append(("chroma", GraphEmbedder))
        except ImportError:  # chromadb is an opt-in extra
            pass
        return backends

    def test_off_by_default_on_every_backend(self, monkeypatch):
        monkeypatch.delenv("NEURALMIND_REDACT_SECRETS", raising=False)
        for name, cls in self._backends():
            assert ANTHROPIC_KEY in self._node_to_text(cls), f"{name} redacted while disabled"

    def test_redacts_when_enabled_on_every_backend(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_REDACT_SECRETS", "1")
        for name, cls in self._backends():
            text = self._node_to_text(cls)
            assert ANTHROPIC_KEY not in text, f"{name} leaked the key with redaction on"
            assert "[REDACTED:anthropic-api-key]" in text, f"{name} did not mark the redaction"

    def test_turbovec_is_covered_not_just_chroma(self, monkeypatch):
        """Pins the specific gap: turbovec is the default, chroma is opt-in."""
        from neuralmind.turbovec_backend import TurboVecEmbedder

        monkeypatch.setenv("NEURALMIND_REDACT_SECRETS", "1")
        assert "[REDACTED" in self._node_to_text(TurboVecEmbedder)


class TestKeywordPrefixes:
    """`db_password` is the commonest shape a real credential takes.

    The heuristic keyword was `\\b`-anchored, but `_` is a word character,
    so `\\b` never fires after one — every PREFIX_SECRET name was invisible.
    A `.env` full of DB_PASSWORD=... scanned completely clean.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "db_password",
            "DB_PASSWORD",
            "MYSQL_PASSWORD",
            "app_secret",
            "PROD_API_KEY",
            "my_access_token",
            "client-secret",
            "SERVICE_AUTH_TOKEN",
            "password",
            "API_KEY",
        ],
    )
    def test_prefixed_keyword_is_detected(self, name):
        matches = scan_text(f'{name} = "{GENERIC_SECRET}"')
        assert matches, f"{name} not detected"
        assert matches[0].kind == "generic-secret-assignment"

    @pytest.mark.parametrize("name", ["mypassword", "thesecret", "notoken", "xapikey"])
    def test_letter_prefixed_keyword_is_not_a_finding(self, name):
        """The lookbehind still rejects a keyword glued to a letter."""
        assert scan_text(f'{name} = "{GENERIC_SECRET}"') == []

    @pytest.mark.parametrize(
        "line",
        [
            'password = os.environ["DB_PASSWORD"]',
            'db_password = os.getenv("DB_PASSWORD")',
            "DB_PASSWORD=${DB_PASSWORD}",
            "my_access_token = None",
            "PROD_API_KEY: <set-me>",
            "# db_password is read from vault",
            'client_secret = ""',
            "api_key: changeme",
            'AWS_SECRET_ACCESS_KEY="your_key_here"',
        ],
    )
    def test_named_but_valueless_config_is_not_a_finding(self, line):
        """Looser keyword matching must not cost the placeholder guard."""
        assert scan_text(line) == []


class TestPgpKeyBlocks:
    """PGP armor reads `PRIVATE KEY BLOCK-----`, not `PRIVATE KEY-----`."""

    def test_pgp_block_detected(self):
        block = f"{pem_begin('PGP')}\nlQOYBFxyz123\n{pem_end('PGP')}"
        assert [m.kind for m in scan_text(block)] == ["private-key-block"]

    @pytest.mark.parametrize("kind", ["RSA", "OPENSSH", "EC", "DSA", "ENCRYPTED"])
    def test_other_key_types_still_detected(self, kind):
        block = f"{pem_begin(kind)}\nAAAA\n{pem_end(kind)}"
        assert [m.kind for m in scan_text(block)] == ["private-key-block"]
