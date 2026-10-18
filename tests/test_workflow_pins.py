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
# GitHub accepts both spellings for workflows and action metadata.
FILES = sorted(
    [
        *(ROOT / ".github" / "workflows").glob("*.yml"),
        *(ROOT / ".github" / "workflows").glob("*.yaml"),
        *(ROOT / ".github" / "actions").rglob("action.yml"),
        *(ROOT / ".github" / "actions").rglob("action.yaml"),
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


# A job holding the deploy key that pushes to main past any ruleset runs no
# package installed from an index: those jobs only download the file another
# job built and commit it. Text-matched, since YAML isn't in the stdlib.
DEPLOY_KEY = "MAIN_PUSH_DEPLOY_KEY"
JOB = re.compile(r"^  ([\w-]+):\s*$")
INSTALLS = re.compile(r"pip install|setup-python|\buv\b|pipx|npm (?:ci|install)|\bpython\b")


def _jobs(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("jobs:") + 1
    except ValueError:
        return
    name, body = None, []
    for line in lines[start:]:
        m = JOB.match(line)
        if m:
            if name:
                yield name, body
            name, body = m.group(1), []
        elif name:
            body.append(line)
    if name:
        yield name, body


def test_deploy_key_jobs_were_found():
    holders = [
        name for path in FILES for name, body in _jobs(path) if any(DEPLOY_KEY in b for b in body)
    ]
    assert len(holders) >= 3, f"expected the three deploy-key jobs, found {holders}"


def test_a_job_holding_the_deploy_key_installs_nothing():
    bad = []
    for path in FILES:
        for name, body in _jobs(path):
            if not any(DEPLOY_KEY in line for line in body):
                continue
            code = [line.split("#", 1)[0] for line in body]
            bad += [
                f"{path.relative_to(ROOT)} job {name}: {c.strip()}"
                for c in code
                if INSTALLS.search(c)
            ]
    assert not bad, (
        "build in a job without the deploy key and hand the result over as an artifact:\n"
        + "\n".join(bad)
    )
