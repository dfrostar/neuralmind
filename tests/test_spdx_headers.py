"""Every Python file in the package names its license in an SPDX tag (#638).

The repository holds two licenses: MIT for the core and the Commercial Modules
License for `neuralmind/tier2/` (LICENSING.md). Dependency scanners and legal
review read a file's SPDX-License-Identifier, so each file states which side of
that line it is on, and a file moved across the line has to change its tag.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "neuralmind"
TIER2 = PACKAGE / "tier2"
# The demo's sample project stands in for a user's code, and its bundled
# graph.json pins each symbol's line number; a tag line would shift them all.
DEMO_PROJECT = PACKAGE / "demo_data" / "sample_project"


def _tag(path: Path) -> str | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[1:3] if lines and lines[0].startswith("#!") else lines[:2]
    for line in head:
        if line.startswith("# SPDX-License-Identifier: "):
            return line.split(": ", 1)[1].strip()
    return None


def test_every_package_file_names_its_license():
    wrong = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts or DEMO_PROJECT in path.parents:
            continue
        expected = "LicenseRef-NeuralMind-Commercial" if TIER2 in path.parents else "MIT"
        if _tag(path) != expected:
            wrong.append(f"{path.relative_to(PACKAGE.parent)}: {_tag(path)!r}, not {expected!r}")
    assert not wrong, "Add or fix the first-line SPDX tag:\n" + "\n".join(wrong)


def test_the_package_metadata_names_both_licenses():
    pyproject = (PACKAGE.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = "MIT AND LicenseRef-NeuralMind-Commercial"' in pyproject
