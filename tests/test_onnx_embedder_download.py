from urllib.error import URLError
from unittest.mock import patch

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
