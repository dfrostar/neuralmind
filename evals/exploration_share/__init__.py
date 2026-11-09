"""Exploration share of the token bill.

What share of an agent session's prompt tokens is *exploration* (reading and
searching code before changing it), measured on Hermes sessions
(``~/.hermes/state.db``) and Claude Code transcripts (``~/.claude/projects``).
Definitions, presence model and the pre-registered reading of the result are in
``docs/specs/EXPLORATION-SHARE-SPEC.md``.

The collectors live in ``neuralmind/measure/`` and ship as
``neuralmind measure sessions``; the modules here re-export them, and
``python -m evals.exploration_share`` (the spec's nightly job) adds what that
command leaves out: appending to a rows file, ``--lag-hours``, ``--since`` and
``--until``, and summaries written to files. Keep the package in step with the spec.
"""

import sys
from pathlib import Path

try:
    import neuralmind.measure  # noqa: F401
except ImportError:
    # The nightly job has always needed only the standard library, and `import neuralmind`
    # runs the whole package's __init__ (PyYAML and more). Where those aren't installed,
    # load neuralmind/measure from this checkout alone, under a bare `neuralmind` package.
    import types

    for _name in [m for m in sys.modules if m == "neuralmind" or m.startswith("neuralmind.")]:
        del sys.modules[_name]
    _bare = types.ModuleType("neuralmind")
    _bare.__path__ = [str(Path(__file__).resolve().parents[2] / "neuralmind")]
    sys.modules["neuralmind"] = _bare
    import neuralmind.measure  # noqa: F401,E402
