"""Regression guard: `import neuralmind` must not import ChromaDB.

v0.22 made the package ChromaDB-optional — the `GraphEmbedder` export is lazy
(PEP 562 `__getattr__`) and the Posthog telemetry patch lives in the chroma
backend, so merely importing `neuralmind` no longer drags in ChromaDB (a heavy
tree). This locks that in: a future eager `import chromadb` on the package path
would fail here.

(Backend auto-selection / `resolve_backend` are covered in
``tests/test_backend_manager.py``; this file only guards the import surface.)

    python tests/test_chromadb_free_import.py
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class ChromaFreeImportTest(unittest.TestCase):
    def test_import_neuralmind_does_not_import_chromadb(self) -> None:
        # Fresh interpreter so this process's already-imported modules can't
        # mask a regression. Exit 1 if chromadb got pulled in transitively.
        code = "import sys, neuralmind; sys.exit(1 if 'chromadb' in sys.modules else 0)"
        result = subprocess.run([sys.executable, "-c", code], cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, "`import neuralmind` eagerly imported chromadb")

    def test_graphembedder_still_importable_on_demand(self) -> None:
        # The lazy export must still resolve when actually accessed.
        import neuralmind

        self.assertEqual(neuralmind.GraphEmbedder.__name__, "GraphEmbedder")


if __name__ == "__main__":
    unittest.main(verbosity=2)
