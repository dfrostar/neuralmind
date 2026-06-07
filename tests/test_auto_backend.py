"""Tests for v0.22 backend auto-selection + ChromaDB-free import.

Stdlib-only (no pytest fixtures, no heavy deps), so it runs everywhere.

    python tests/test_auto_backend.py
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from neuralmind.backend_manager import (  # noqa: E402
    DEFAULT_BACKEND_CONFIG,
    _turbovec_available,
    resolve_backend_name,
)


class ResolveBackendNameTests(unittest.TestCase):
    def test_default_is_auto(self) -> None:
        self.assertEqual(DEFAULT_BACKEND_CONFIG["backend"], "auto")

    def test_explicit_names_pass_through(self) -> None:
        for name in ("graph", "chroma", "chromadb", "turbovec", "in_memory"):
            self.assertEqual(resolve_backend_name(name), name)
            self.assertEqual(resolve_backend_name(name.upper()), name)

    def test_auto_matches_availability(self) -> None:
        # auto resolves to turbovec iff its deps are importable, else graph.
        expected = "turbovec" if _turbovec_available() else "graph"
        self.assertEqual(resolve_backend_name("auto"), expected)
        self.assertIn(resolve_backend_name("auto"), {"turbovec", "graph"})


class ChromaFreeImportTest(unittest.TestCase):
    def test_import_neuralmind_does_not_import_chromadb(self) -> None:
        # `import neuralmind` must not pull ChromaDB (a heavy tree). Run in a
        # fresh interpreter so this process's already-imported modules don't
        # mask a regression.
        code = "import sys, neuralmind; sys.exit(1 if 'chromadb' in sys.modules else 0)"
        result = subprocess.run([sys.executable, "-c", code], cwd=str(_REPO_ROOT))
        self.assertEqual(result.returncode, 0, "import neuralmind eagerly imported chromadb")

    def test_graphembedder_still_accessible(self) -> None:
        import neuralmind

        self.assertEqual(neuralmind.GraphEmbedder.__name__, "GraphEmbedder")


if __name__ == "__main__":
    unittest.main(verbosity=2)
