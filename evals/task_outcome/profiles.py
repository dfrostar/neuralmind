"""Which repository a task-outcome study draws its tasks from, and how.

The pilot drew bug fixes from NeuralMind's own history, and its rules were
written for that layout: source under ``neuralmind/``, tests under ``tests/``.
A profile holds what changes with the repository, so another study applies
the same rules to another codebase. Changing a profile after its study's first
run is a change to that study's pre-registration and goes in its change log.

Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    # Shown to the agent: "You are working in a checkout of the <name> repository."
    name: str
    # A changed ``.py`` file is source when it is under one of these and under
    # none of ``excluded_prefixes``. ``""`` matches every path.
    source_prefixes: tuple[str, ...]
    excluded_prefixes: tuple[str, ...]
    # Fixes committed on or after this date (committer date, UTC) qualify.
    cutoff: str
    # Hermes-Agent's own code re-publishes its launchers for whatever
    # HERMES_HOME is active, so every test run and agent run in its checkout
    # gets a HERMES_HOME of its own inside the workspace.
    isolated_hermes_home: bool = False

    def source_files(self, changed: list[str]) -> list[str]:
        return [
            p
            for p in changed
            if p.endswith(".py")
            and any(p.startswith(prefix) for prefix in self.source_prefixes)
            and not any(p.startswith(prefix) for prefix in self.excluded_prefixes)
        ]


PROFILES = {
    # The pilot (docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md), unchanged.
    "neuralmind": Profile(
        name="NeuralMind",
        source_prefixes=("neuralmind/",),
        excluded_prefixes=(),
        cutoff="2026-07-01",
    ),
    # NousResearch/hermes-agent: modules and packages at the top level.
    "hermes-agent": Profile(
        name="hermes-agent",
        source_prefixes=("",),
        excluded_prefixes=("tests/", "tests-js/", "website/", "scripts/", "evals/"),
        cutoff="2026-09-15",
        isolated_hermes_home=True,
    ),
}

DEFAULT = "neuralmind"


def get(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError:
        raise SystemExit(
            f"unknown profile {name!r}; known: {', '.join(sorted(PROFILES))}"
        ) from None
