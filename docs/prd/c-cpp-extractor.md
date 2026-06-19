# PRD: C and C++ language extractors

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-19
**Tracking branch:** `claude/c-cpp-extractor` · **Target:** v0.32.0

## 1. Background & strategic motivation

The competitive review put language breadth as a commodity axis we've been
closing: Rust (v0.27), Java (v0.28) took the bundled tree-sitter backend to five
languages. **C/C++ is the one gap that is also a competitive wedge.** The
competitor `codebase-memory-mcp` advertises "158 languages" but scored only
**0.58 on C** in its own paper — macro/preprocessor density is where naive
multi-language indexers fall apart. Shipping a C/C++ extractor that reaches
**structural parity with our Rust/Java bar** turns their weakest, loudest claim
into our talking point, and unlocks the enormous installed base of C/C++ repos
(kernels, embedded, game engines, systems code) that agents struggle with today.

This also de-risks the upcoming public launch: "how many languages?" and "does
it handle C?" are predictable first questions. Seven languages with C/C++ done
*honestly* (clear about what's in/out) is a stronger story than a big number
that falls over on real preprocessor-heavy code.

## 2. What already exists (the seam to mirror)

Adding a language is **additive and well-trodden** (`neuralmind/graphgen.py`):

- **`_SUFFIX_LANG`** — file-suffix → language name.
- **`_load_language(name)`** — lazy `import tree_sitter_<lang>` → `Language`.
- **`_EXTRACTORS`** — language → `(_extract_symbols, _resolve_edges)` pass pair.
- Two functions per language: **pass 1** emits file/function/class/field nodes +
  `contains` edges and populates name tables; **pass 2** resolves
  `imports_from` / `inherits` / `calls` edges.
- Everything downstream of `graph.json` (embeddings, selector, synapses) is
  language-agnostic — a new extractor integrates transparently as long as it
  emits the standard node kinds + edge relations from `neuralmind/ir.py`
  (`function`, `class`, `method`, `field`/`symbol`; `contains`, `calls`,
  `imports_from`, `inherits`, `rationale_for`).

The Rust (commit `6eea233`) and Java (`42c9516`) PRs are the exact template:
extractor code in `graphgen.py`, one grammar dep in `pyproject.toml`, a
`tests/fixtures/sample_project_<lang>/` fixture + `benchmark_queries_<lang>.json`
+ committed gold `graph.json` (via `tests/fixtures/_gen_graph.py
build_builtin_gold()`), a `_LANG_FIXTURES` entry in `evals/parity/run.py`,
`test_graphgen.py` cases, watcher ignores, and the docs/SEO sweep.

## 3. The gap (what v0.32.0 adds)

Two new extractors — **C** (`.c`/`.h`) and **C++** (`.cpp`/`.cc`/`.cxx` +
`.hpp`/`.hh`/`.hxx`) — reaching the **same structural-parity bar** the parity
gate already enforces for TS/Go/Rust/Java (≥90% symbol coverage, zero dangling
edges), plus the C/C++-specific edges that matter most:

1. **Symbols (parity MVP):** C → functions, `struct`/`union`, `enum` + constants,
   typedefs, top-level fields. C++ → adds `class`, member functions/**methods**,
   member fields, `enum class`, free functions, and **namespace-qualified ids**.
2. **`#include "local.h"` → `imports_from` edges** — local includes (quoted form)
   become file→file import edges, the C/C++ analogue of module imports. `<system>`
   includes are treated as external (no dangling edge).
3. **`inherits` edges** for C++ base classes (public/protected/private bases).
4. **`calls` edges** — bare-name best-effort, same heuristic as the other
   extractors (the SCIP precision pass remains the opt-in upgrade for exactness).
5. **Header/impl pairing** — `foo.h` and `foo.c`/`foo.cpp` resolve to a shared
   module key so a declaration in the header and its definition in the impl land
   in the same neighborhood (this is the C/C++-specific wrinkle Python/Java don't
   have).

### Explicitly scoped OUT of the MVP (stated honestly, not hidden)

- **Preprocessor macros** (`#define`, function-like macros) — *not* emitted as
  symbols in v0.32.0. This is the hard part the competitor failed; we index the
  parseable code (functions/types/calls) and defer macro-symbol extraction to a
  follow-up rather than ship something half-working. **The honesty bar:** the
  release notes will say plainly "macros are not yet indexed as symbols."
- **Templates** — C++ `template<...>` declarations are parsed and the
  function/class is emitted, but **specializations / instantiations are not
  resolved** (treated as one symbol). Documented.
- **Conditional compilation** — `#ifdef` blocks are indexed as visible code (we
  don't evaluate the preprocessor); documented.

## 4. Goals / non-goals

**Goals**
- C and C++ pass the existing **parity gate** (≥90% symbol coverage vs the gold
  graph, zero dangling edges) on dedicated fixtures — the same gate Rust/Java
  pass, no weaker bar.
- `neuralmind build` indexes a C/C++ repo with no external tooling (bundled
  tree-sitter), incremental updates, and the same retrieval quality downstream.
- Header/impl pairing + local-include edges work (the differentiated bit).

**Non-goals**
- Not a full preprocessor/semantic analyzer — macros, template instantiation,
  and `#ifdef` evaluation are out (and disclosed). SCIP precision remains the
  opt-in path to compiler-accurate edges.
- No gold *fact* set / faithfulness A/B for C/C++ initially — parity is
  **structural** (same as TS/Go today; no `evals/faithfulness` C set in v0.32.0).

## 5. Design notes (C/C++-specific)

- **Suffixes:** `.c`/`.h` → `c`; `.cpp`/`.cc`/`.cxx`/`.hpp`/`.hh`/`.hxx`/`.h++`
  → `cpp`. Ambiguity: `.h` is mapped to `c` (the safe default; tree-sitter-cpp is
  a superset, but C fixtures use `.h` and the C grammar parses them cleanly).
  Header-heavy C++ projects use `.hpp`; pure-`.h` C++ is a known minor limitation
  to note.
- **Module key for pairing:** strip the extension and any `include/`/`src/`
  prefix so `include/foo.h` and `src/foo.cpp` share a key — implemented as a
  small `_c_module_key(rel)` helper, the one new bit vs Rust/Java.
- **Namespaces:** walk `namespace_definition` recursively, carrying a `::`-joined
  prefix into emitted symbol ids so `Foo::Bar::baz()` is distinct from a global
  `baz()` (prevents false `calls`/`contains` merges).
- **Grammars:** `tree-sitter-c>=0.21.0`, `tree-sitter-cpp>=0.21.0` as base deps
  (pure-Python wheels, no platform markers needed — consistent with the existing
  five grammars).

## 6. Acceptance criteria

- [ ] `_SUFFIX_LANG` + `_load_language` + `_EXTRACTORS` wired for `c` and `cpp`;
      `_c_extract_symbols`/`_c_resolve_edges` and `_cpp_*` implemented.
- [ ] `tree-sitter-c` + `tree-sitter-cpp` added to `pyproject.toml` base deps.
- [ ] `tests/fixtures/sample_project_c/` and `sample_project_cpp/` — multi-file
      (auth/users/db/billing/api) fixtures with `.h`/`.c` and `.hpp`/`.cpp`
      pairs, `benchmark_queries_{c,cpp}.json`, and committed gold `graph.json`.
- [ ] `evals/parity/run.py` `_LANG_FIXTURES` gains `c` and `cpp`; both pass
      ≥90% symbol coverage and **zero dangling edges**.
- [ ] Local `#include "x.h"` produces `imports_from` edges; `<system>` includes
      produce none (no dangling); header/impl share a module key (test).
- [ ] C++ `inherits` edges for base classes; namespace-qualified symbol ids (test).
- [ ] `tests/test_graphgen.py` C/C++ cases (mirroring the Rust/Java blocks).
- [ ] Watcher ignores C/C++ build dirs (`build`, `CMakeFiles`, `cmake-build-*`).
- [ ] Docs + SEO: every "five languages / Python, TypeScript, Go, Rust, Java"
      surface bumped to **seven / + C, C++** (README banner+trail+table,
      `graphgen.py` docstring, `cli.py`, both HTML + meta/keywords,
      CLI-Reference, sitemap, `RELEASE_NOTES_v0.32.0.md`); keywords add
      `c-code-intelligence`, `cpp-indexing`, `c-cpp-mcp`.
- [ ] **Honesty in the notes:** macros-not-indexed, templates-not-specialized,
      and `#ifdef`-not-evaluated stated explicitly in release notes + docs.

## 7. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Macro-heavy real C looks under-indexed | Be explicit it's out of MVP; index functions/types/calls (the competitor's 0.58 came from trying and failing — we scope honestly). |
| `.h` ambiguity (C vs C++ header) | Default `.h`→C (grammar parses both); `.hpp` for C++; document the pure-`.h`-C++ edge case. |
| Header/impl pairing wrong key | Unit-test the `_c_module_key` normalization on `include/`+`src/` layouts. |
| tree-sitter-c/cpp API drift | Reuse the existing 0.21-vs-0.23 compat shim in `graphgen.py`. |
| Parity gate flakiness on new gold | Generate gold via the same `build_builtin_gold()` helper Rust/Java use; commit it; dangling-edge check in CI. |

## 8. Rollout

Per CLAUDE.md: PRD → build on `claude/c-cpp-extractor` → CI green (incl. the
parity gate for `c` + `cpp`) → hold for merge okay → merge cuts **v0.32.0** via
release-please, docs + SEO in the same PR. This is the last commodity-breadth
item; after it, the value-ordered next step is the **competitor benchmark
head-to-head** (filling the `codebase-memory-mcp` row in the public benchmark),
which is the credibility piece to land *before* the public launch.
