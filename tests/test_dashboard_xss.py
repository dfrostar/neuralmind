"""The dashboard escapes every server-provided value it puts into HTML.

``escapeHtml`` (textContent → innerHTML) left quotes alone, and its output
went into ``title="..."``, so a file or symbol name from an untrusted repo
(``x" onmouseover="..."``) became a live attribute. Community ids and sizes,
synapse weights and counts, and ingestion node counts were interpolated with
no escaping at all.

Renders ``neuralmind/web/dashboard.js`` with Node against a stub DOM
(tests/js/dashboard_xss_harness.js); skipped where Node isn't installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / "js" / "dashboard_xss_harness.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    out = subprocess.run(
        ["node", str(HARNESS)], capture_output=True, text=True, timeout=60, check=True
    ).stdout
    return json.loads(out)


@pytest.mark.parametrize("view", ["communities-list", "top-edges-list", "ingestion-list"])
def test_hostile_values_render_inert(rendered, view):
    html = rendered[view]
    assert html, f"{view} rendered nothing"
    assert 'onmouseover="alert' not in html
    assert "<img" not in html
    assert "&quot;" in html or "&lt;img" in html
