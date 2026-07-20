# Code Documentation Standards

> **Why this exists.** NeuralMind indexes markdown alongside code. Well-documented code = well-indexed code. A module with clear docstrings, examples, and contracts is discoverable by agents (and humans) who have never seen it before. A module without docs is a black box — even if the code is perfect.

This standard defines the minimum documentation a NeuralMind module must carry to be **indexable, discoverable, and mistake-proof**. It applies to:

- All `neuralmind/*.py` modules (core product)
- All `autopilot/modules/*.py` modules (licensing + operator)
- All `tests/test_*.py` modules (documentation via test names)

---

## The Core Insight

> NeuralMind indexes markdown. Markdown lives in `docs/`. Code lives in `neuralmind/`. The bridge is the **docstring + wiki cross-reference**.

A module is "well-documented" when an agent can query NeuralMind and get back:

1. **What it does** — the docstring one-liner
2. **Why it exists** — the module docstring context paragraph
3. **How to use it** — the `Example:` block in the class docstring
4. **How it fits** — the `## See Also:` cross-references
5. **How to test it** — the `tests/test_<module>.py` file and its test names

If any of these are missing, the module is invisible to NeuralMind queries.

---

## Module Template

Every new module MUST follow this structure:

```python
"""One-line summary (≤80 chars).

Context paragraph: why this module exists, what problem it solves,
and where it fits in the architecture. 2-4 sentences.

Example:
    >>> from neuralmind import example
    >>> ex = example.ExampleModule(backend="in_memory")
    >>> ex.run()

See Also:
    - ``neuralmind.peer_module`` — the consumer of this module's output
    - ``tests/test_example.py`` — test cases and usage patterns
    - ``docs/wiki/Architecture.md#example-section`` — high-level design

Version:
    0.53.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExampleResult:
    """What this result contains + how to interpret it."""

    value: float  # normalized 0..1
    raw: float    # pre-normalization value

    def is_valid(self) -> bool:
        """True if this result is within acceptable bounds."""
        return 0.0 <= self.value <= 1.0


class ExampleModule:
    """Short one-liner.

    Longer description of the module's responsibility, its inputs,
    its outputs, and its failure mode.

    Args:
        backend: Which backend to use (``"turbovec"``, ``"in_memory"``).
        threshold: Cutoff for the ``is_valid()`` check.
        debug: If True, internal state is exposed via ``__repr__``.

    Raises:
        BackendNotFoundError: if ``backend`` string is unknown.
        ValueError: if ``threshold`` is negative or NaN.
    """

    def __init__(self, backend: str = "turbovec", threshold: float = 0.5, debug: bool = False) -> None:
        if threshold < 0.0 or math.isnan(threshold):
            raise ValueError(f"threshold must be non-negative finite, got {threshold}")
        self._backend = backend
        self._threshold = threshold
        self._debug = debug

    def run(self, query: str) -> ExampleResult:
        """Run the module against a query.

        Args:
            query: The search query string. Must be non-empty.

        Returns:
            An ``ExampleResult`` with the raw + normalized scores.

        Raises:
            ValueError: if ``query`` is empty.

        Example:
            >>> mod = ExampleModule()
            >>> res = mod.run("test query")
            >>> res.is_valid()
            True
        """
        if not query:
            raise ValueError("query must be non-empty")
        # ... implementation
```

---

## Docstring Requirements

### Module-level docstring MUST contain:
1. **One-line summary** — ≤80 chars, imperative mood
2. **Context paragraph** — why this module exists
3. **Example block** — at least one `>>>` usage
4. **See Also** — cross-references to peers, tests, wiki
5. **Version** — the version that last modified the contract

### Class docstring MUST contain:
1. **One-line summary**
2. **Longer description** — responsibility + failure mode
3. **Args** — every `__init__` parameter documented
4. **Raises** — every exception the class can raise

### Method docstring MUST contain:
1. **One-line summary**
2. **Args** — every parameter
3. **Returns** — the return type + semantics
4. **Raises** — exceptions
5. **Example** — if the method is part of the public API

### Internal methods (`_private`) MUST contain:
1. **One-line summary** — even if terse
2. **At least one of:** Args, Returns, Raises — whichever applies

---

## Test as Documentation

Test names ARE documentation. They should read like specifications:

```python
# GOOD — reads like a spec
def test_decay_reduces_weight_by_half_life():
def test_tuner_beats_random_within_5_generations():
def test_license_rejects_tampered_signature():

# BAD — opaque
def test_decay_1():
def test_tuner_ok():
def test_license():
```

Every test module MUST have a module-level docstring that explains what aspect of the system it covers and links back to the module it tests.

---

## Wiki Cross-Reference

Every module with a public API MUST have a corresponding section in `docs/wiki/Architecture.md` or a dedicated `docs/wiki/<Module>-Guide.md`. The wiki section MUST:

1. Link to the module's source file
2. Link to the test file
3. Show a minimal usage example
4. Document the failure mode

---

## Indexability Checklist

Before merging a PR that adds or modifies a module:

- [ ] Module docstring has one-liner + context + example + see-also + version
- [ ] Every public class has a docstring with Args + Raises
- [ ] Every public method has a docstring with Args + Returns + Raises
- [ ] Test file exists with spec-style test names
- [ ] Wiki section exists and links to source + tests
- [ ] `neuralmind build` runs successfully after docs are added (verifies indexability)

---

## Anti-Patterns

| Anti-Pattern | Why It's Wrong | Fix |
|---|---|---|
| Docstring: "Does X." | No context, no example, no cross-ref | Add context + example + see-also |
| Missing Args section | Agent can't discover parameters | Document every `__init__` param |
| Missing Raises section | Agent can't handle failures | Document every exception |
| Test names like `test_1` | Unreadable as spec | Rename to `test_<what>_<condition>_<expected>` |
| No wiki section | Module invisible to NeuralMind queries | Add `docs/wiki/<Module>-Guide.md` |
| Docstring out of sync with code | Agent gets wrong info | Update docstring in same PR as code change |

---

## Relationship to Other Standards

- `DOCUMENTATION-PROCESS.md` — the *when* and *who* for user-facing docs
- `CLAUDE.md` — the *what* for shipping features
- `MODULE-TEMPLATE.md` — the canonical file template (copy this)
- This file — the *how* for code-level documentation

---

*Last updated: 2026-07-19 for v0.53.0*
