#!/usr/bin/env python3
"""ONNX embedding subprocess — one embed chunk per process.

onnxruntime 1.29 on Python 3.14 deadlocks after 2-3 session.run() calls in
the same process (CPU provider, independent of thread count). Isolating
each chunk in its own process is the only reliable workaround.

The parent (turbovec_backend._embed_matrix) may send up to 256 texts per
invocation; this script re-chunks to the proven-safe size (32) and creates
a FRESH embedder — hence a fresh ONNX session — per chunk, so no session
ever sees more than one run.

stdin:  JSON {"texts": [...]}
stdout: JSON {"shape": [n, 384], "data": "<base64 float32>"}
"""

import base64
import json
import sys

_CHUNK = 32  # proven-safe size; matches onnx_embedder._BATCH


def main() -> None:
    payload = json.load(sys.stdin)
    texts = payload.get("texts", [])
    if not texts:
        print(json.dumps({"shape": [0, 384], "data": ""}))
        return

    import numpy as np

    from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

    matrices = []
    for i in range(0, len(texts), _CHUNK):
        chunk = texts[i : i + _CHUNK]
        # Fresh embedder per chunk == fresh ONNX session per chunk.
        matrices.append(OnnxMiniLMEmbedder().embed(chunk))
    if matrices:
        matrix = np.concatenate(matrices) if len(matrices) > 1 else matrices[0]
    else:
        matrix = np.zeros((0, 384), dtype=np.float32)
    print(
        json.dumps(
            {
                "shape": list(matrix.shape),
                "data": base64.b64encode(matrix.astype(np.float32).tobytes()).decode("ascii"),
            }
        )
    )


if __name__ == "__main__":
    main()
