"""Tests for D3 — judge transcripts loader + generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuralmind.judge_transcripts import (
    generate_all_transcripts,
    generate_transcript_from_benchmark,
    load_all_transcripts,
    load_transcript,
    validate_transcript,
)


class TestLoadTranscript:
    """load_transcript() — load + validate one transcript."""

    def test_load_valid(self, tmp_path: Path):
        path = tmp_path / "test.json"
        path.write_text(
            json.dumps(
                {
                    "query": "How does auth work?",
                    "reference_answer": "Auth uses JWT tokens.",
                },
                indent=2,
            )
        )
        t = load_transcript(path)
        assert t["query"] == "How does auth work?"
        assert t["reference_answer"] == "Auth uses JWT tokens."

    def test_missing_query(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"reference_answer": "ok"}))
        with pytest.raises(ValueError, match="query"):
            load_transcript(path)

    def test_missing_answer(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"query": "ok"}))
        with pytest.raises(ValueError, match="reference_answer"):
            load_transcript(path)


class TestValidateTranscript:
    """validate_transcript() — return issues list."""

    def test_valid(self):
        t = {"query": "ok", "reference_answer": "ok"}
        assert validate_transcript(t) == []

    def test_empty_query(self):
        t = {"query": "", "reference_answer": "ok"}
        assert validate_transcript(t) == ["empty query"]

    def test_empty_answer(self):
        t = {"query": "ok", "reference_answer": ""}
        assert validate_transcript(t) == ["empty reference_answer"]

    def test_empty_fact(self):
        t = {
            "query": "ok",
            "reference_answer": "ok",
            "expected_facts": [{"id": "f1", "fact": ""}],
        }
        assert "expected_facts[0]: empty fact" in validate_transcript(t)


class TestGenerateFromBenchmark:
    """generate_transcript_from_benchmark() — offline transcript generation."""

    def test_generates_from_fixture(self):
        path = Path("tests/fixtures/benchmark_queries_go.json")
        if not path.exists():
            pytest.skip("fixture not found")
        transcripts = generate_transcript_from_benchmark(path)
        assert len(transcripts) > 0
        for t in transcripts:
            assert "query" in t
            assert "reference_answer" in t
            assert "language" in t
            assert t["language"] == "go"

    def test_skips_queries_without_facts(self):
        """Queries without expected_facts are skipped."""
        path = Path("tests/fixtures/benchmark_queries_c.json")
        if not path.exists():
            pytest.skip("fixture not found")
        transcripts = generate_transcript_from_benchmark(path)
        # C fixture has no expected_facts → should generate 0
        assert len(transcripts) == 0

    def test_generated_transcript_has_all_fields(self):
        path = Path("tests/fixtures/benchmark_queries_ts.json")
        if not path.exists():
            pytest.skip("fixture not found")
        transcripts = generate_transcript_from_benchmark(path)
        assert len(transcripts) > 0
        t = transcripts[0]
        assert "query" in t
        assert "reference_answer" in t
        assert "source_files" in t
        assert "category" in t
        assert "language" in t
        assert "query_id" in t


class TestGenerateAllTranscripts:
    """generate_all_transcripts() — generate from all fixtures."""

    def test_generates_multiple_languages(self):
        results = generate_all_transcripts()
        # go, java, rust, typescript have expected_facts → should generate
        assert "go" in results
        assert "java" in results
        assert "rust" in results
        assert "typescript" in results  # from data field, not filename

    def test_excludes_languages_without_facts(self):
        """Languages without expected_facts are excluded."""
        results = generate_all_transcripts()
        # c, cpp, csharp, php, ruby have no expected_facts → excluded
        assert "c" not in results
        assert "cpp" not in results
        assert "csharp" not in results
        assert "php" not in results
        assert "ruby" not in results

    def test_total_count(self):
        results = generate_all_transcripts()
        total = sum(len(v) for v in results.values())
        assert total >= 76  # 19 each for 4 languages


class TestLoadAllTranscripts:
    """load_all_transcripts() — load from bench/public/judge/."""

    def test_loads_existing(self):
        transcripts = load_all_transcripts()
        # Should load the 4 existing transcripts (py_auth_flow, etc.)
        assert len(transcripts) >= 4
