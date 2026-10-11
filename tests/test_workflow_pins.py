"""Every third-party GitHub Action is pinned to a full commit SHA.

The release workflows sign images, attest builds and publish to PyPI, so the
actions they run are part of what a signature vouches for. A tag such as
`@v7` can be moved to different code after the fact (the tj-actions/changed-
files compromise did exactly that); a 40-character commit SHA can't. The
trailing `# vX.Y.Z` comment is what Dependabot reads to keep the pin current,
so it is required too (see .github/dependabot.yml).

Local actions (`./...`) and `docker://` images are out of scope: the first
are this repository's own code, and none of the second are used.

Stdlib-only.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted(
    [
        *(ROOT / ".github" / "workflows").glob("*.yml"),
        *(ROOT / ".github" / "actions").rglob("action.yml"),
    ]
)
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(.*)$")
PINNED = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}")
VERSION_COMMENT = re.compile(r"^\s+# v\d+\.\d+\.\d+\s*$")


def _third_party_uses():
    for path in FILES:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = USES.match(line)
            if m and not m.group(1).startswith("./"):
                yield f"{path.relative_to(ROOT)}:{lineno}", m.group(1), m.group(2)


def test_workflows_were_found():
    assert any(_third_party_uses()), "no third-party `uses:` found; did the workflows move?"


def test_every_action_is_pinned_to_a_commit_sha():
    bad = [f"{where}: {ref}" for where, ref, _ in _third_party_uses() if not PINNED.fullmatch(ref)]
    assert not bad, "pin these to a full commit SHA:\n" + "\n".join(bad)


def test_every_pin_names_its_version_for_dependabot():
    bad = [
        f"{where}: {ref}{rest}"
        for where, ref, rest in _third_party_uses()
        if PINNED.fullmatch(ref) and not VERSION_COMMENT.match(rest)
    ]
    assert not bad, "add a `# vX.Y.Z` comment after the SHA:\n" + "\n".join(bad)
