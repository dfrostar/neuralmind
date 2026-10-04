"""Guard docs/ against files that don't belong on the public docs site.

``scripts/check_docs_site_allowlist.py`` is the authoritative check, wired into
``docs-site-allowlist.yml``. This module runs the same check in the ordinary
Python test job, so a local ``pytest tests/`` catches a stray file before it is
pushed. It also pins the guard to the files that actually leaked, so a later
edit to the allowlist can't quietly let them back in.

Stdlib-only, so it runs without the full dep set.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "check_docs_site_allowlist", REPO_ROOT / "scripts" / "check_docs_site_allowlist.py"
)
assert _spec and _spec.loader
guard = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = guard
_spec.loader.exec_module(guard)

# Pushed straight to main in c8c6b8f; both were served from docs.neuralmind.uk.
LEAKED = ["docs/train_sft_70b_v3.py", "docs/logos-checkpoint-upload.py"]


def test_every_file_under_docs_is_a_docs_site_type() -> None:
    files = guard.tracked_docs_files()
    # An empty listing would pass vacuously, so require a file the site can't lack.
    assert "docs/CNAME" in files, "git ls-files found no docs/CNAME"
    bad = guard.disallowed(files)
    assert not bad, guard.failure_message(bad)


def test_guard_trips_on_the_files_that_leaked() -> None:
    # The quick way to turn the check green is to allowlist the offending type.
    # This makes that a visible edit to a test as well as to the script.
    assert guard.disallowed(LEAKED) == LEAKED
    for path in ["docs/.env", "docs/run.sh", "docs/model.safetensors", "docs/LICENSE"]:
        assert guard.disallowed([path]) == [path], path
    # ...without catching the extensionless files the site needs, or an
    # upper-case extension.
    site = ["docs/CNAME", "docs/images/.gitkeep", "docs/_config.yml", "docs/images/Shot.PNG"]
    assert guard.disallowed(site) == []


def test_failure_message_says_docs_is_public() -> None:
    cname = (REPO_ROOT / "docs" / "CNAME").read_text(encoding="utf-8").strip()
    assert guard.SITE_URL == f"https://{cname}/"
    message = guard.failure_message(LEAKED)
    assert f"docs/ is published at {guard.SITE_URL}" in message
    assert all(path in message for path in LEAKED)
