# Module Template — Copy This for New Modules

Copy this structure when creating any new module in `neuralmind/` or `autopilot/modules/`. Fill in the bracketed sections.

```python
"""[ONE-LINE SUMMARY — ≤80 chars, imperative mood].

[CONTEXT PARAGRAPH — 2-4 sentences explaining why this module exists,
what problem it solves, and where it fits in the architecture.]

Example:
    >>> from [import_path] import [ClassName]
    >>> instance = [ClassName]([param]=...)
    >>> result = instance.[method](...)
    >>> [assertion on result]

See Also:
    - ``[peer_module_path]`` — [what it does in relation to this]
    - ``[consumer_module_path]`` — [who consumes this output]
    - ``tests/test_[module_name].py`` — test cases and usage patterns
    - ``docs/wiki/[relevant-page].md#section`` — high-level design

Version:
    [VERSION]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union
from pathlib import Path


# ── Result Types ──────────────────────────────────────────────────────────────

@dataclass
class [ResultName]:
    """Short one-liner for the result type.

    [Broader explanation of what this result contains + how to interpret it.
    1-3 sentences.]
    """

    value: [type]  # [explanation]
    raw: [type]    # [optional: pre-normalization]

    def is_valid(self) -> bool:
        """True if this result is within acceptable bounds."""
        ...


# ── Public API ────────────────────────────────────────────────────────────────

class [ModuleName]:
    """Short one-liner for the class.

    Longer description of the class's responsibility, its inputs,
    its outputs, and its failure mode. 2-4 sentences.

    Args:
        [param_1]: [description]
        [param_2]: [description]
        debug: If True, internal state is exposed via ``__repr__``.

    Raises:
        [SpecificError]: when [condition].
        ValueError: if [param] is [invalid condition].
    """

    def __init__(self, [param_1]: [type], [param_2]: [type] = ..., debug: bool = False) -> None:
        ...

    def [method_name](self, query: str) -> [ResultName]:
        """[One-line summary].

        Args:
            query: The search query string. Must be non-empty.

        Returns:
            A ``[ResultName]`` with the raw + normalized scores.

        Raises:
            ValueError: if ``query`` is empty.

        Example:
            >>> mod = [ModuleName]()
            >>> res = mod.[method]("test query")
            >>> res.is_valid()
            True
        """
        ...

    def _internal_helper(self, data: bytes) -> None:
        """[One-line summary — even for private methods].

        Args:
            data: [description]
        """
        ...
```

## Related Files

- `CODE-DOCUMENTATION-STANDARDS.md` — the standard this template satisfies
- `DOCUMENTATION-PROCESS.md` — the *when* and *who* for user-facing docs
- `CLAUDE.md` — the *what* for shipping features

---

*Last updated: 2026-07-19 for v0.53.0*
