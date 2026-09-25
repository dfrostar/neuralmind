#!/usr/bin/env python3
"""ONNX embedding subprocess — one batch per process.

onnxruntime 1.29 on Python 3.14 deadlocks after 2-3 session.run() calls in the
same process (CPU provider, independent of thread count). Isolating each batch
in its own process is the only reliable workaround.

stdin:  JSON {"texts": [...]}
stdout: JSON {"shape": [n, 384], "data": "<base64 float32>"}
"""
import base64
import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    texts = payload.get("texts", [])
    if not texts:
        print(json.dumps({"shape": [0, 384], "data": ""}))
        return

    import numpy as np

    from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

    matrix = OnnxMiniLMEmbedder().embed(texts)
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
