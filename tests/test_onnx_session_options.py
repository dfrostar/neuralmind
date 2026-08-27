"""Tests for NEURALMIND_ORT_THREADS plumbing in the ONNX embedder.

Separate from test_onnx_embedder.py deliberately: that module skips entirely
when the MiniLM model isn't cached on disk, but ``_session_options`` is pure
option-building — no model, no session — so its behavior stays tested on
runners that never embed anything. Requires only ``onnxruntime``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("onnxruntime")

from neuralmind.onnx_embedder import OnnxMiniLMEmbedder  # noqa: E402


def _opts(monkeypatch, value: str | None):
    if value is None:
        monkeypatch.delenv("NEURALMIND_ORT_THREADS", raising=False)
    else:
        monkeypatch.setenv("NEURALMIND_ORT_THREADS", value)
    return OnnxMiniLMEmbedder._session_options()


def test_unset_keeps_ort_defaults(monkeypatch):
    """No env var → ORT sizes its own pool (0 is ORT's 'auto' sentinel)."""
    so = _opts(monkeypatch, None)
    assert so.intra_op_num_threads == 0
    assert so.inter_op_num_threads == 0


def test_pin_to_one_thread(monkeypatch):
    """The benchmark harness's setting: fully serialized, machine-independent."""
    so = _opts(monkeypatch, "1")
    assert so.intra_op_num_threads == 1
    assert so.inter_op_num_threads == 1


def test_pin_to_n_threads_serializes_inter_op(monkeypatch):
    so = _opts(monkeypatch, "4")
    assert so.intra_op_num_threads == 4
    assert so.inter_op_num_threads == 1


@pytest.mark.parametrize("bad", ["bogus", "0", "-2", "  "])
def test_invalid_or_nonpositive_values_keep_defaults(monkeypatch, bad):
    """Misconfiguration degrades to ORT defaults rather than crashing a build."""
    so = _opts(monkeypatch, bad)
    assert so.intra_op_num_threads == 0
    assert so.inter_op_num_threads == 0


def test_optimization_settings_unchanged(monkeypatch):
    """The pin must not disturb the existing session tuning."""
    import onnxruntime as ort

    so = _opts(monkeypatch, "1")
    assert so.graph_optimization_level == ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    assert so.log_severity_level == 3
