"""Tests for the TTY-aware progress reporter.

Stdlib-only. The point of these is the *guards*: a progress bar must
never be the reason a long ingest dies, and it must still say something
useful when there's no terminal to draw on (CI logs, agent shells).
"""

import io

import pytest

from neuralmind.progress import ProgressReporter, format_duration, stream_is_tty


class _FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class _ExplodingStream(io.StringIO):
    """Every terminal operation fails — a closed pipe, a detached fd."""

    def isatty(self) -> bool:
        raise OSError("Inappropriate ioctl for device")

    def write(self, _text):
        raise OSError("Broken pipe")


class TestStreamIsTty:
    def test_pipe_is_not_a_tty(self):
        assert stream_is_tty(io.StringIO()) is False

    def test_terminal_is_a_tty(self):
        assert stream_is_tty(_FakeTTY()) is True

    def test_none_is_not_a_tty(self):
        assert stream_is_tty(None) is False

    def test_raising_isatty_is_not_a_tty(self):
        """The tcsetattr/ioctl failure mode: treat it as 'no terminal'."""
        assert stream_is_tty(_ExplodingStream()) is False

    def test_stream_without_isatty_is_not_a_tty(self):
        class _Bare:
            pass

        assert stream_is_tty(_Bare()) is False


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [(0, "0.0s"), (2.58, "2.6s"), (42, "42s"), (95, "1m35s"), (4000, "1h06m")],
    )
    def test_formats(self, seconds, expected):
        assert format_duration(seconds) == expected

    def test_negative_clamps_to_zero(self):
        assert format_duration(-5) == "0.0s"

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), "not a number", None])
    def test_unusable_values_render_as_unknown(self, value):
        assert format_duration(value) == "--"


class TestNonTtyOutput:
    def test_emits_milestone_lines(self):
        """A redirected stream still shows movement, so a long embed doesn't
        look hung."""
        stream = io.StringIO()
        bar = ProgressReporter(10, label="Embedding", stream=stream, milestone_pct=50)
        for _ in range(10):
            bar.advance()
        lines = [line for line in stream.getvalue().splitlines() if line]
        assert lines, "expected milestone lines on a non-TTY stream"
        assert all("Embedding" in line for line in lines)
        assert any("10/10" in line for line in lines)

    def test_no_carriage_returns_on_a_pipe(self):
        """In-place redraws would corrupt a log file."""
        stream = io.StringIO()
        bar = ProgressReporter(4, stream=stream)
        for _ in range(4):
            bar.advance()
        assert "\r" not in stream.getvalue()

    def test_final_unit_is_always_announced(self):
        stream = io.StringIO()
        bar = ProgressReporter(3, stream=stream, milestone_pct=50)
        for _ in range(3):
            bar.advance()
        assert "3/3" in stream.getvalue()


class TestTtyOutput:
    def test_draws_in_place(self):
        stream = _FakeTTY()
        bar = ProgressReporter(4, label="Ingesting", stream=stream, min_redraw_interval=0)
        for _ in range(4):
            bar.advance()
        out = stream.getvalue()
        assert "\r" in out
        assert "Ingesting" in out
        assert "4/4" in out

    def test_clear_erases_the_bar(self):
        stream = _FakeTTY()
        bar = ProgressReporter(2, stream=stream, min_redraw_interval=0)
        bar.advance()
        bar.clear()
        assert stream.getvalue().endswith("\r")

    def test_write_line_does_not_smear_the_bar(self):
        stream = _FakeTTY()
        bar = ProgressReporter(2, stream=stream, min_redraw_interval=0)
        bar.advance()
        bar.write_line("a diagnostic")
        assert "a diagnostic\n" in stream.getvalue()


class TestGuards:
    def test_disabled_when_there_is_no_work(self):
        stream = io.StringIO()
        bar = ProgressReporter(0, stream=stream)
        bar.advance()
        assert stream.getvalue() == ""

    def test_env_kill_switch(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_NO_PROGRESS", "1")
        stream = io.StringIO()
        bar = ProgressReporter(5, stream=stream)
        bar.advance()
        assert stream.getvalue() == ""

    def test_write_failures_do_not_propagate(self):
        """A broken pipe must not kill the work the bar only describes."""
        bar = ProgressReporter(3, stream=_ExplodingStream(), enabled=True)
        for _ in range(3):
            bar.advance()
        bar.finish("done")
        assert bar.enabled is False

    def test_context_manager_clears_on_exception(self):
        stream = _FakeTTY()
        with pytest.raises(RuntimeError):
            with ProgressReporter(2, stream=stream, min_redraw_interval=0) as bar:
                bar.advance()
                raise RuntimeError("boom")
        assert stream.getvalue().endswith("\r")

    def test_advance_never_exceeds_total(self):
        bar = ProgressReporter(2, stream=io.StringIO())
        bar.advance(10)
        assert bar.done == 2

    def test_eta_appears_once_there_is_a_sample(self):
        stream = io.StringIO()
        bar = ProgressReporter(4, stream=stream, milestone_pct=25)
        bar.advance()
        assert "left" in stream.getvalue()
