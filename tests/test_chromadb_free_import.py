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

    def test_star_import_does_not_import_chromadb(self) -> None:
        # `from neuralmind import *` must not resolve the lazy GraphEmbedder
        # export (which imports chromadb) — so it stays usable on the default
        # ChromaDB-free install. GraphEmbedder is therefore excluded from
        # __all__; explicit `from neuralmind import GraphEmbedder` still works.
        code = (
            "import sys; ns = {}; exec('from neuralmind import *', ns); "
            "sys.exit(1 if 'chromadb' in sys.modules else 0)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, "`from neuralmind import *` pulled in chromadb")

    def test_graphembedder_still_importable_on_demand(self) -> None:
        # The lazy export must still resolve when actually accessed — but only
        # when the optional [chromadb] extra is installed (v0.29.0+). On a
        # ChromaDB-free install, accessing it raises (the chroma backend is gone).
        import importlib.util

        if importlib.util.find_spec("chromadb") is None:
            self.skipTest("needs the optional [chromadb] extra")
        import neuralmind

        self.assertEqual(neuralmind.GraphEmbedder.__name__, "GraphEmbedder")


if __name__ == "__main__":
    unittest.main(verbosity=2)
