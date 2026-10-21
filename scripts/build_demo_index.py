#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regenerate (or check) the demo's bundled vector index.

`neuralmind demo` ships its sample project's vector index and the vectors of
its three questions in `neuralmind/demo_data/prebuilt/`, so it runs the real
ranking straight after `pip install`, with no 88 MB model download. Both come
from the MiniLM model; this script makes them from the sample project:

    python scripts/build_demo_index.py           # rewrite prebuilt/
    python scripts/build_demo_index.py --check   # fail if prebuilt/ is stale

`--check` runs in the self-benchmark workflow (ci-benchmark.yml), which has
the model. It rebuilds into a temporary directory and compares what the
ranking depends on: the indexed nodes and their content hashes, and the
question vectors. Run the script without `--check`, and commit the result,
whenever the sample project, its graph or the demo questions change.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "neuralmind" / "demo_data"
PREBUILT = DEMO / "prebuilt"
INDEX_DIR = "neuralmind_turbovec"
INDEX_FILES = ("index.tvim", "store.sqlite", "bm25_index.json")
QUERY_VECTORS = "query_vectors.json"


def _build(out: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from neuralmind import _demo_report
    from neuralmind.cli import _copy_demo_fixture
    from neuralmind.core import NeuralMind
    from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

    with tempfile.TemporaryDirectory(prefix="neuralmind-demo-index-") as tmp:
        project = Path(tmp) / "sample_project"
        _copy_demo_fixture(DEMO / "sample_project", project)
        result = NeuralMind(str(project)).build(force=True)
        if not result.get("success"):
            raise SystemExit(f"build failed: {result.get('error')}")
        (out / INDEX_DIR).mkdir(parents=True, exist_ok=True)
        for name in INDEX_FILES:
            shutil.copy2(project / ".neuralmind" / INDEX_DIR / name, out / INDEX_DIR / name)

    questions = [q for _, q in _demo_report.DEMO_QUERIES]
    vectors = OnnxMiniLMEmbedder()(questions)
    payload = {
        "model": "all-MiniLM-L6-v2",
        "vectors": {
            q: [round(float(x), 7) for x in v] for q, v in zip(questions, vectors, strict=True)
        },
    }
    (out / QUERY_VECTORS).write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


def _nodes(store: Path) -> dict[str, str]:
    conn = sqlite3.connect(store)
    try:
        return dict(conn.execute("SELECT node_id, content_hash FROM nodes"))
    finally:
        conn.close()


def _vectors(path: Path) -> dict[str, list[float]]:
    return json.loads(path.read_text(encoding="utf-8"))["vectors"]


def _check() -> int:
    with tempfile.TemporaryDirectory(prefix="neuralmind-demo-check-") as tmp:
        fresh = Path(tmp)
        _build(fresh)
        problems = []
        if _nodes(fresh / INDEX_DIR / "store.sqlite") != _nodes(
            PREBUILT / INDEX_DIR / "store.sqlite"
        ):
            problems.append("the indexed nodes or their content hashes changed")
        old, new = _vectors(PREBUILT / QUERY_VECTORS), _vectors(fresh / QUERY_VECTORS)
        if set(old) != set(new):
            problems.append("the demo questions changed")
        elif any(abs(a - b) > 1e-4 for q in new for a, b in zip(old[q], new[q], strict=True)):
            problems.append("the question vectors changed")
    if problems:
        print(f"demo_data/prebuilt is stale: {'; '.join(problems)}.", file=sys.stderr)
        print("Regenerate it: python scripts/build_demo_index.py, and commit.", file=sys.stderr)
        return 1
    print("demo_data/prebuilt matches the sample project and the demo questions.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if prebuilt/ is stale")
    args = parser.parse_args()
    if args.check:
        return _check()
    if PREBUILT.exists():
        shutil.rmtree(PREBUILT)
    _build(PREBUILT)
    print(f"wrote {PREBUILT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
