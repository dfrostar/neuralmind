from unittest.mock import patch
from urllib.error import URLError

import pytest

from neuralmind.onnx_embedder import _ARCHIVE_SHA256, _DOWNLOAD_RETRIES, OnnxMiniLMEmbedder


def test_download_into_retries_transient_network_errors(tmp_path):
    embedder = OnnxMiniLMEmbedder()
    dest = tmp_path / "onnx_models" / "all-MiniLM-L6-v2" / "onnx"

    with (
        patch(
            "neuralmind.onnx_embedder.urllib.request.urlretrieve",
            side_effect=[URLError("dns"), None],
        ) as mock_retrieve,
        patch("neuralmind.onnx_embedder._sha256", return_value=_ARCHIVE_SHA256),
        patch("neuralmind.onnx_embedder.tarfile.open") as mock_tar_open,
    ):
        embedder._download_into(dest)

    assert mock_retrieve.call_count == 2
    mock_tar_open.assert_called_once()


def test_download_into_raises_after_max_retries(tmp_path):
    embedder = OnnxMiniLMEmbedder()
    dest = tmp_path / "onnx_models" / "all-MiniLM-L6-v2" / "onnx"

    with patch(
        "neuralmind.onnx_embedder.urllib.request.urlretrieve",
        side_effect=URLError("dns"),
    ) as mock_retrieve:
        with pytest.raises(URLError):
            embedder._download_into(dest)

    assert mock_retrieve.call_count == _DOWNLOAD_RETRIES


def test_local_model_dir_finds_a_cached_model_and_never_downloads(tmp_path, monkeypatch):
    """Decision search asks this before loading the model; it must not fetch."""
    import neuralmind.onnx_embedder as mod

    monkeypatch.delenv("NEURALMIND_ONNX_MODEL_DIR", raising=False)
    monkeypatch.setattr(mod, "_NM_CACHE", tmp_path / "nm" / "onnx")
    monkeypatch.setattr(mod, "_CHROMA_CACHE", tmp_path / "chroma" / "onnx")
    embedder = OnnxMiniLMEmbedder()
    with patch.object(OnnxMiniLMEmbedder, "_download_into") as download:
        assert embedder.local_model_dir() is None
        chroma = tmp_path / "chroma" / "onnx"
        chroma.mkdir(parents=True)
        (chroma / "model.onnx").write_bytes(b"")
        (chroma / "tokenizer.json").write_text("{}")
        assert embedder.local_model_dir() == chroma
    download.assert_not_called()
