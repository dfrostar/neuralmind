# NeuralMind v0.39.0 — `neuralmind probe` now tests real NL→code retrieval

**The headline:** the `neuralmind probe` self-test (introduced earlier) now
queries each symbol by its **docstring/intent**, not its name. That one change
turns the probe from a near-tautology into a real measurement of whether the
index can find code from a plain-English description — and a round of review
feedback hardened the edges.

## Why this changes

The first version of `probe` queried each symbol by its *humanized name*
(`authenticate_user` → `"authenticate user"`) and checked the file came back.
But NeuralMind embeds the symbol name *into* the indexed text, so that was close
to a **string-match tautology**: it read ~0.95 MRR on a healthy index and mostly
flagged name collisions rather than genuine retrieval gaps.

## What's new

**Query by rationale, not name.** NeuralMind already stores each symbol's
docstring as a `rationale` node, joined to its code by a `rationale_for` edge.
The probe now uses that text as the query (e.g. *"Raised when the exp claim is in
the past"*). Because it doesn't contain the symbol name, retrieving the right
code from it is a genuine **natural-language → code** test. Undocumented symbols
fall back to the humanized name, and the report **discloses the split** so a
mostly-fallback run can't masquerade as a strong score:

```
Retrieval self-probe — sample_project
Sampled 63 of 64 indexed symbols, retrieval depth k=10
Query source: 51 rationale, 12 label
============================================================
  answerability  : 98%  (file found in top-10)
  MRR            : 0.789
  recall@1/3/5   : 0.667 / 0.905 / 0.968
  blind spots    : 1
------------------------------------------------------------
Symbols the index couldn't retrieve from their own description (1 total):
  - get_me_endpoint()  (api/routes.py)   query: "GET /api/users/me — requires Authorization: Bearer header"
```

The MRR drop versus the old name-based number (≈0.95 → 0.789) is the *point* —
it's now measuring something real, and the lone blind spot is a genuine semantic
miss, not a name collision.

## Hardening (from review)

- **Code-only retrieval.** The probe now asks the backend for `file_type="code"`
  hits directly instead of over-fetching and post-filtering. A rationale-sourced
  query can rank rationale/document nodes above its own code, so the old fixed
  window could miss a file even when a code-only top-k would contain it.
- **Honest `index_size`.** "Sampled X of Y indexed symbols" now counts only code
  nodes, not the rationale/document pseudo-nodes — so the denominator means what
  it says.
- **Argument validation.** `--k` must be ≥ 1 and `--sample-size` ≥ 0 (`0` =
  all); bad values fail fast with a clear message and a non-zero exit instead of
  emitting a misleading all-zeros report.
- **No swallowed failures.** A backend/index error during search now fails the
  probe rather than being silently scored as a retrieval blind spot (which would
  corrupt `--baseline` comparisons).
- **`ks` is honored.** API callers can set the reported recall cutoffs via
  `retrieval_probe(ks=...)`.

## Per-agent expectations

| Agent | What changes in v0.39.0 |
|-------|--------------------------|
| **Claude Code** | `neuralmind probe .` now queries by docstring and prints a `Query source:` line. Read-only; no hook/session/memory changes. |
| **Cursor / Cline / generic MCP** | No tool-surface change; `probe` is a CLI diagnostic. |
| **Contributors / CI** | `retrieval_probe()` gains rationale extraction, code-only search, `ks` passthrough, and argument validation. `probe.py` adds `extract_rationales` / `normalize_rationale` and a `query_sources` tally in the report (and `--json`), so you can gate CI on recall/MRR *and* assert enough probes were rationale-backed. |

## Why it matters

A self-test that reads ~0.95 on every healthy repo can't tell a good index from
a mediocre one. Querying by intent makes `probe` discriminating: it now moves
when retrieval is actually weak, and the blind spots it names are the real places
an agent would come up empty on *your* code.
