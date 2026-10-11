#!/usr/bin/env python3
"""Print pip-audit `--ignore-vuln` flags for the advisories VEX says don't apply.

security/neuralmind.openvex.json records, for each advisory in a dependency
that NeuralMind is not affected by, the status and the reason. CI's pip-audit
step ignores exactly those advisories and nothing else:

    pip-audit $(python scripts/vex_ignores.py)

so the published VEX and the CI gate can't disagree. An advisory gets ignored
only by adding a `not_affected` statement there (with its argument in
SECURITY.md), never by editing the workflow. Stdlib-only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

VEX = Path(__file__).resolve().parent.parent / "security" / "neuralmind.openvex.json"


def ignored_ids(path: Path = VEX) -> list[str]:
    """Every name and alias of the advisories VEX marks not_affected."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids: list[str] = []
    for statement in doc["statements"]:
        if statement["status"] != "not_affected":
            continue
        vuln = statement["vulnerability"]
        for vid in [vuln["name"], *vuln.get("aliases", [])]:
            if vid not in ids:
                ids.append(vid)
    return ids


def main() -> int:
    print(" ".join(f"--ignore-vuln {vid}" for vid in ignored_ids()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
