"""``neuralmind.__version__`` must equal the packaging metadata.

Between v3.11.0 and v3.11.3 the literal in ``neuralmind/__init__.py`` lagged
``pyproject.toml`` by a release because the version was bumped by hand in one
place; ``neuralmind --version`` and the daemon health payload reported the
stale value. release-please now owns both files; this test makes any future
drift a red build instead of a support ticket.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+
    except ImportError:  # pragma: no cover - Python 3.10
        import toml as tomllib  # type: ignore[no-redef]

        return tomllib.loads(text)["project"]["version"]
    return tomllib.loads(text)["project"]["version"]


def test_dunder_version_matches_pyproject():
    import neuralmind

    assert neuralmind.__version__ == _pyproject_version()


def test_dunder_version_matches_release_please_manifest():
    import neuralmind

    manifest = json.loads((REPO_ROOT / ".release-please-manifest.json").read_text(encoding="utf-8"))
    assert manifest["."] == neuralmind.__version__


def test_version_info_is_derived_from_version():
    import neuralmind

    assert neuralmind.__version_info__ == tuple(int(p) for p in neuralmind.__version__.split("."))
