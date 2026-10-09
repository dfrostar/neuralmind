"""ONNX session reuse and dynamic padding in the MiniLM embedder.

No model needed: the tokenizer and session are stand-ins, so this runs on the
firewalled unit-test job. Requires only numpy.
"""

from __future__ import annotations

import sys

import pytest

np = pytest.importorskip("numpy")

from neuralmind import onnx_embedder  # noqa: E402
from neuralmind.onnx_embedder import OnnxMiniLMEmbedder, _session_reuse_safe  # noqa: E402


class _Enc:
    def __init__(self, n):
        self.ids = [1] * n
        self.attention_mask = [1] * n


class _Tokenizer:
    """Pads each batch to its longest text, as enable_padding() without a length does."""

    def encode_batch(self, texts):
        width = max(len(t.split()) for t in texts)
        return [_Enc(width) for _ in texts]


class _Session:
    def __init__(self, created):
        created.append(self)
        self.runs = 0

    def run(self, _outputs, feed):
        self.runs += 1
        b, n = feed["input_ids"].shape
        return [np.ones((b, n, 384), dtype=np.float32)]


@pytest.fixture
def embedder(monkeypatch, tmp_path):
    created: list[_Session] = []
    # Files present so model resolution never looks further (or downloads).
    (tmp_path / "model.onnx").write_bytes(b"")
    (tmp_path / "tokenizer.json").write_text("{}")
    e = OnnxMiniLMEmbedder(model_dir=tmp_path)
    e.__dict__["_tokenizer"] = _Tokenizer()
    monkeypatch.setattr(e, "_session_factory", lambda: _Session(created))
    monkeypatch.setattr(onnx_embedder, "_SESSIONS", {})
    e.created = created
    return e


def test_reuse_is_on_except_on_python_314(monkeypatch):
    monkeypatch.delenv("NEURALMIND_ORT_SESSION_CACHE", raising=False)
    assert _session_reuse_safe() is (sys.version_info < (3, 14))


@pytest.mark.parametrize("value,expected", [("0", False), ("1", True)])
def test_env_forces_either_way(monkeypatch, value, expected):
    monkeypatch.setenv("NEURALMIND_ORT_SESSION_CACHE", value)
    assert _session_reuse_safe() is expected


def test_one_session_serves_every_batch_and_call_when_reuse_is_safe(monkeypatch, embedder):
    monkeypatch.setenv("NEURALMIND_ORT_SESSION_CACHE", "1")
    texts = [f"text number {i}" for i in range(70)]  # three batches of <= 32
    assert embedder.embed(texts).shape == (70, 384)
    embedder.embed(["a query"])
    assert len(embedder.created) == 1
    assert embedder.created[0].runs == 4


def test_a_fresh_session_per_batch_when_reuse_is_not_safe(monkeypatch, embedder):
    # Python 3.14 + onnxruntime 1.29 deadlocks after 2-3 runs on one session.
    monkeypatch.setenv("NEURALMIND_ORT_SESSION_CACHE", "0")
    embedder.embed([f"text {i}" for i in range(70)])
    assert [s.runs for s in embedder.created] == [1, 1, 1]


class _LengthTokenizer:
    """Right-pads each batch to its longest text; a text's ids are its word lengths."""

    def encode_batch(self, texts):
        width = max(len(t.split()) for t in texts)
        out = []
        for t in texts:
            ids = [len(w) for w in t.split()]
            enc = _Enc(width)
            enc.ids = ids + [0] * (width - len(ids))
            enc.attention_mask = [1] * len(ids) + [0] * (width - len(ids))
            out.append(enc)
        return out


class _IdSession:
    """Each token's hidden state is its id, so a row's mean is a function of its own text."""

    def __init__(self, widths):
        self.widths = widths

    def run(self, _outputs, feed):
        ids = feed["input_ids"].astype(np.float32)
        b, n = ids.shape
        self.widths.append(n)
        hidden = np.zeros((b, n, 384), dtype=np.float32)
        hidden[:, :, 0] = ids
        hidden[:, :, 1] = 1.0
        return [hidden]


def test_length_sorted_batches_keep_input_order(embedder, monkeypatch):
    widths: list[int] = []
    session = _IdSession(widths)
    embedder.__dict__["_tokenizer"] = _LengthTokenizer()
    monkeypatch.setattr(embedder, "_session_factory", lambda: session)
    monkeypatch.setattr(onnx_embedder, "_SORT_WINDOW", 50)
    # Long and short texts interleaved, across three sort windows.
    texts = [("word " * (60 if i % 7 == 0 else 1 + i % 5)) + "x" * (1 + i % 9) for i in range(120)]

    batched = embedder.embed(texts)
    one_by_one = np.vstack([embedder.embed([t]) for t in texts])

    assert np.array_equal(batched, one_by_one)
    # Sorting kept the long texts together: most batches never pad to 61.
    first = widths[: len(widths) - len(texts)]
    assert sum(w == 61 for w in first) <= 3
