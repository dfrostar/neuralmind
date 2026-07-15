"""Tests for neuralmind query --cost and neuralmind batch-estimate."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _rate_for_model helper
# ---------------------------------------------------------------------------


class TestRateForModel:
    """Unit tests for the _rate_for_model helper."""

    def test_explicit_rate_wins(self):
        from neuralmind.cli import _rate_for_model

        rate, label = _rate_for_model("haiku", 1.23)
        assert rate == 1.23
        assert "1.23" in label

    def test_sonnet_default(self):
        from neuralmind.cli import _rate_for_model

        rate, label = _rate_for_model(None, None)
        assert rate == 3.00
        assert "sonnet" in label

    def test_known_slugs(self):
        from neuralmind.cli import _MODEL_PRICES, _rate_for_model

        for slug, expected in _MODEL_PRICES.items():
            rate, label = _rate_for_model(slug, None)
            assert rate == expected
            assert slug in label

    def test_unknown_slug_falls_back_to_sonnet(self):
        from neuralmind.cli import _rate_for_model

        rate, label = _rate_for_model("totally-unknown-model-xyz", None)
        assert rate == 3.00  # sonnet fallback

    def test_slug_is_case_insensitive(self):
        from neuralmind.cli import _rate_for_model

        rate_lower, _ = _rate_for_model("haiku", None)
        rate_upper, _ = _rate_for_model("HAIKU", None)
        assert rate_lower == rate_upper == 0.25


# ---------------------------------------------------------------------------
# neuralmind query --cost  (text output)
# ---------------------------------------------------------------------------


class TestCmdQueryCost:
    """Tests for cmd_query with --cost flag."""

    def _make_result(self, tokens=1200, ratio=40.0):
        result = MagicMock()
        result.budget.total = tokens
        result.reduction_ratio = ratio
        result.layers_used = ["L0", "L1"]
        result.context = "some context"
        result.trace = None
        result.top_search_hits = []
        return result

    def test_cost_receipt_printed_in_text_mode(self, capsys):
        from neuralmind.cli import cmd_query

        args = MagicMock()
        args.project_path = "/tmp/proj"
        args.question = "auth flow"
        args.json = False
        args.cost = True
        args.model = "sonnet"
        args.rate = None
        args.trace = False
        args.trace_verbose = False
        args.relevance = False
        args.explain = False

        mock_result = self._make_result(tokens=1200, ratio=40.0)

        with patch("neuralmind.cli.memory.should_prompt_for_consent", return_value=False):
            with patch("neuralmind.cli._try_daemon", return_value=None):
                with patch("neuralmind.cli.create_mind") as mock_create:
                    mock_create.return_value.query.return_value = mock_result
                    cmd_query(args)

        out = capsys.readouterr().out
        assert "Cost:" in out
        assert "used" in out
        assert "saved" in out
        assert "sonnet" in out

    def test_no_cost_receipt_without_flag(self, capsys):
        from neuralmind.cli import cmd_query

        args = MagicMock()
        args.project_path = "/tmp/proj"
        args.question = "auth flow"
        args.json = False
        args.cost = False
        args.model = "sonnet"
        args.rate = None
        args.trace = False
        args.trace_verbose = False
        args.relevance = False
        args.explain = False

        mock_result = self._make_result()

        with patch("neuralmind.cli.memory.should_prompt_for_consent", return_value=False):
            with patch("neuralmind.cli._try_daemon", return_value=None):
                with patch("neuralmind.cli.create_mind") as mock_create:
                    mock_create.return_value.query.return_value = mock_result
                    cmd_query(args)

        out = capsys.readouterr().out
        assert "Cost:" not in out

    def test_cost_json_keys_present(self, capsys):
        from neuralmind.cli import cmd_query

        args = MagicMock()
        args.project_path = "/tmp/proj"
        args.question = "auth flow"
        args.json = True
        args.cost = True
        args.model = "haiku"
        args.rate = None
        args.trace = False
        args.trace_verbose = False
        args.relevance = False
        args.explain = False

        mock_result = self._make_result(tokens=800, ratio=20.0)

        with patch("neuralmind.cli.memory.should_prompt_for_consent", return_value=False):
            with patch("neuralmind.cli._try_daemon", return_value=None):
                with patch("neuralmind.cli.create_mind") as mock_create:
                    mock_create.return_value.query.return_value = mock_result
                    cmd_query(args)

        data = json.loads(capsys.readouterr().out)
        assert "cost_used_usd" in data
        assert "cost_saved_usd" in data
        assert "rate_per_mtok" in data
        assert data["rate_per_mtok"] == 0.25  # haiku
        # cost_used = 800 / 1e6 * 0.25 = 0.0002
        assert abs(data["cost_used_usd"] - 800 / 1_000_000 * 0.25) < 1e-8
        # tokens_saved = 800 * (20 - 1) = 15200; cost_saved = 15200 / 1e6 * 0.25
        assert abs(data["cost_saved_usd"] - 15200 / 1_000_000 * 0.25) < 1e-8

    def test_cost_json_absent_without_flag(self, capsys):
        from neuralmind.cli import cmd_query

        args = MagicMock()
        args.project_path = "/tmp/proj"
        args.question = "q"
        args.json = True
        args.cost = False
        args.model = "sonnet"
        args.rate = None
        args.trace = False
        args.trace_verbose = False
        args.relevance = False
        args.explain = False

        mock_result = self._make_result()

        with patch("neuralmind.cli.memory.should_prompt_for_consent", return_value=False):
            with patch("neuralmind.cli._try_daemon", return_value=None):
                with patch("neuralmind.cli.create_mind") as mock_create:
                    mock_create.return_value.query.return_value = mock_result
                    cmd_query(args)

        data = json.loads(capsys.readouterr().out)
        assert "cost_used_usd" not in data
        assert "cost_saved_usd" not in data

    def test_explicit_rate_overrides_model(self, capsys):
        from neuralmind.cli import cmd_query

        args = MagicMock()
        args.project_path = "/tmp/proj"
        args.question = "q"
        args.json = True
        args.cost = True
        args.model = "opus"   # would be 15.00 $/MTok
        args.rate = 2.50       # explicit rate wins
        args.trace = False
        args.trace_verbose = False
        args.relevance = False
        args.explain = False

        mock_result = self._make_result(tokens=1000, ratio=10.0)

        with patch("neuralmind.cli.memory.should_prompt_for_consent", return_value=False):
            with patch("neuralmind.cli._try_daemon", return_value=None):
                with patch("neuralmind.cli.create_mind") as mock_create:
                    mock_create.return_value.query.return_value = mock_result
                    cmd_query(args)

        data = json.loads(capsys.readouterr().out)
        assert data["rate_per_mtok"] == 2.50
        # cost_used = 1000 / 1e6 * 2.50
        assert abs(data["cost_used_usd"] - 1000 / 1_000_000 * 2.50) < 1e-8


# ---------------------------------------------------------------------------
# neuralmind batch-estimate
# ---------------------------------------------------------------------------

def _write_events(log_file, events):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


_SAMPLE_EVENTS = [
    {
        "event_type": "query",
        "timestamp": "2026-07-01T10:00:00+00:00",
        "query": "auth flow",
        "retrieval_summary": {"tokens": 1200, "reduction_ratio": 40.0},
    },
    {
        "event_type": "query",
        "timestamp": "2026-07-02T11:00:00+00:00",
        "query": "database schema",
        "retrieval_summary": {"tokens": 1800, "reduction_ratio": 28.0},
    },
    {
        "event_type": "wakeup",  # should be excluded from query aggregation
        "timestamp": "2026-07-02T11:01:00+00:00",
        "retrieval_summary": {"tokens": 600, "reduction_ratio": 10.0},
    },
]


class TestCmdBatchEstimate:
    """Tests for cmd_batch_estimate."""

    def test_no_log_prints_message(self, tmp_path, capsys):
        from neuralmind.cli import cmd_batch_estimate

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = None
        args.json = False

        cmd_batch_estimate(args)

        out = capsys.readouterr().out
        assert "no" in out.lower() or "not" in out.lower()

    def test_no_log_json_error(self, tmp_path, capsys):
        from neuralmind.cli import cmd_batch_estimate

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = None
        args.json = True

        cmd_batch_estimate(args)

        data = json.loads(capsys.readouterr().out)
        assert "error" in data

    def test_reads_event_log_text_output(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, _SAMPLE_EVENTS)

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = None
        args.json = False

        cmd_batch_estimate(args)

        out = capsys.readouterr().out
        assert "Queries logged" in out
        assert "2" in out        # two query events (wakeup excluded)
        assert "Avg tokens" in out
        assert "Cost:" in out or "cost" in out.lower()

    def test_wakeup_events_excluded(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, _SAMPLE_EVENTS)

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = None
        args.json = True

        cmd_batch_estimate(args)

        data = json.loads(capsys.readouterr().out)
        # _SAMPLE_EVENTS has 3 records but 1 is a wakeup → only 2 queries
        assert data["total_queries"] == 2

    def test_json_output_keys(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, _SAMPLE_EVENTS)

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = None
        args.json = True

        cmd_batch_estimate(args)

        data = json.loads(capsys.readouterr().out)
        for key in (
            "total_queries",
            "total_tokens_used",
            "total_tokens_saved",
            "total_cost_used_usd",
            "total_cost_saved_usd",
            "avg_tokens_per_query",
            "avg_cost_per_query_usd",
            "rate_per_mtok",
        ):
            assert key in data, f"missing key: {key}"

    def test_math_correctness(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        # Single clean event for easy manual verification
        event = {
            "event_type": "query",
            "query": "test",
            "retrieval_summary": {"tokens": 1000, "reduction_ratio": 10.0},
        }
        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, [event])

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"  # 3.00 $/MTok
        args.rate = None
        args.queries_per_day = None
        args.json = True

        cmd_batch_estimate(args)

        data = json.loads(capsys.readouterr().out)
        # cost_used = 1000 / 1e6 * 3.00 = 0.003
        assert abs(data["total_cost_used_usd"] - 0.003) < 1e-6
        # tokens_saved = 1000 * (10 - 1) = 9000; cost_saved = 9000 / 1e6 * 3 = 0.027
        assert abs(data["total_cost_saved_usd"] - 0.027) < 1e-6

    def test_projection_with_qpd(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        event = {
            "event_type": "query",
            "query": "test",
            "retrieval_summary": {"tokens": 1000, "reduction_ratio": 10.0},
        }
        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, [event])

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = 100
        args.json = True

        cmd_batch_estimate(args)

        data = json.loads(capsys.readouterr().out)
        assert "projection" in data
        proj = data["projection"]
        assert proj["queries_per_day"] == 100
        # avg_cost_used = 0.003; monthly_used = 0.003 * 100 * 30 = 9.0
        assert abs(proj["projected_monthly_cost_with_nm_usd"] - 9.0) < 0.01
        # avg_cost_without = 0.003 + 0.027 = 0.030; monthly_without = 0.030 * 100 * 30 = 90.0
        assert abs(proj["projected_monthly_cost_without_nm_usd"] - 90.0) < 0.01
        assert abs(proj["projected_monthly_savings_usd"] - 81.0) < 0.01

    def test_projection_absent_without_qpd(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        event = {
            "event_type": "query",
            "query": "test",
            "retrieval_summary": {"tokens": 500, "reduction_ratio": 5.0},
        }
        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, [event])

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = None
        args.json = True

        cmd_batch_estimate(args)

        data = json.loads(capsys.readouterr().out)
        assert "projection" not in data

    def test_text_output_shows_projection_section(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        events = [
            {
                "event_type": "query",
                "query": "test",
                "retrieval_summary": {"tokens": 1000, "reduction_ratio": 10.0},
            }
        ]
        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, events)

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = 50
        args.json = False

        cmd_batch_estimate(args)

        out = capsys.readouterr().out
        assert "Monthly projection" in out
        assert "With NeuralMind" in out
        assert "Without" in out
        assert "Savings" in out

    def test_explicit_rate_used_in_calculation(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        event = {
            "event_type": "query",
            "query": "test",
            "retrieval_summary": {"tokens": 1000, "reduction_ratio": 2.0},
        }
        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, [event])

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"  # ignored — rate wins
        args.rate = 10.0
        args.queries_per_day = None
        args.json = True

        cmd_batch_estimate(args)

        data = json.loads(capsys.readouterr().out)
        assert data["rate_per_mtok"] == 10.0
        # cost_used = 1000 / 1e6 * 10 = 0.01
        assert abs(data["total_cost_used_usd"] - 0.01) < 1e-6

    def test_empty_log_no_crash(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, [])  # zero events

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = None
        args.json = False

        cmd_batch_estimate(args)  # must not raise

        out = capsys.readouterr().out
        assert "No query events" in out or "no" in out.lower()

    def test_text_output_includes_per_query_breakdown(self, tmp_path, capsys):
        from neuralmind import memory
        from neuralmind.cli import cmd_batch_estimate

        events = [
            {
                "event_type": "query",
                "timestamp": "2026-07-01T00:00:00+00:00",
                "query": "what does auth() do?",
                "retrieval_summary": {"tokens": 1187, "reduction_ratio": 38.2},
            }
        ]
        log_file = memory.project_query_events_file(tmp_path)
        _write_events(log_file, events)

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.model = "sonnet"
        args.rate = None
        args.queries_per_day = None
        args.json = False

        cmd_batch_estimate(args)

        out = capsys.readouterr().out
        assert "Per-query breakdown" in out
        assert "auth()" in out
