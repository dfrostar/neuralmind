"""Only commits that change what ships may start a release.

release-please's `python` strategy, unlike its defaults for other languages,
lists `docs` as a visible changelog section, and every visible type counts as
releasable. So a docs-only merge (a Show HN draft, `update-chart.yml`'s
"docs: refresh benchmark chart") opened a release PR and cut a patch: 4.22.1
shipped nothing but a docs change. `release-please-config.json` now lists the
sections itself with `docs` hidden. This test keeps it that way.

Stdlib-only by repo convention.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "release-please-config.json"

RELEASING = {"feat", "fix", "perf", "deps", "revert"}
NOT_RELEASING = {"docs", "style", "chore", "refactor", "test", "build", "ci"}


def _sections() -> dict[str, dict]:
    package = json.loads(CONFIG.read_text(encoding="utf-8"))["packages"]["."]
    return {s["type"]: s for s in package["changelog-sections"]}


def test_only_shipping_changes_are_releasable():
    sections = _sections()
    visible = {t for t, s in sections.items() if not s.get("hidden")}
    assert visible == RELEASING


def test_every_other_conventional_type_is_listed_hidden():
    # An unlisted type is dropped either way, but listing them keeps the
    # breaking-change rule working: a hidden type with `!` still releases.
    sections = _sections()
    assert NOT_RELEASING <= set(sections)
    assert all(sections[t].get("hidden") is True for t in NOT_RELEASING)
