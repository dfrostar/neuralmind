# NeuralMind v0.32.0 — C and C++ join the bundled backend (seven languages)

**Release Date:** June 2026

## TL;DR

The bundled tree-sitter backend now indexes **C** (`.c`/`.h`) and **C++**
(`.cpp`/`.cc`/`.cxx` + `.hpp`/`.hh`/`.hxx`) — taking NeuralMind to **seven
languages** (Python, TypeScript, Go, Rust, Java, C, C++) with **no external
tooling**. Both pass the same structural-parity gate as Rust/Java: **100% symbol
coverage, zero dangling edges**.

```bash
neuralmind build /path/to/your/c-or-cpp/project   # bundled — nothing extra to install
```

## Why this one matters

Language breadth is commodity — but C/C++ is also where naive multi-language
indexers fall over. A widely-cited competitor advertises 158 languages yet scored
**0.58 on C** in its own paper, because preprocessor/macro density wrecks a
shallow parse. NeuralMind takes the opposite tack: index the parseable code at
**full parity** and be **honest about what's out of scope**, rather than claim a
language it can't actually serve.

## What it indexes

- **Functions** — free functions, `static` helpers, and C++ member functions /
  methods (including out-of-line `Foo::bar` definitions across header/impl).
- **Types** — C `struct`/`union`/`enum` (+ fields and enum constants), `typedef`
  aliases; C++ `class`/`struct` with member fields, plus **namespace-qualified
  ids** so `app::auth::JwtCodec` never collides with a global of the same name.
- **`#include "local.h"` → `imports_from` edges.** Quoted local includes become
  file→file import edges; `<system>` headers are treated as external (no dangling
  edge). This is the C/C++ analogue of module imports.
- **Header/impl pairing.** `foo.h` and `foo.c`/`foo.cpp` resolve to a shared
  module key, so a declaration and its definition land in the same neighborhood.
- **C++ inheritance** — base classes produce `inherits` edges.
- **Calls** — bare-name best-effort, same heuristic as the other languages; the
  opt-in **SCIP precision pass** remains the path to compiler-accurate edges.

## Honestly out of scope (disclosed, not hidden)

So you know exactly what you're getting:

- **Preprocessor macros are not indexed as symbols.** `#define`s (incl.
  function-like macros) are skipped — this is precisely where shallow indexers
  overclaim, so we don't. The parseable functions/types/calls around them are
  indexed normally.
- **Templates are not specialized.** A `template<...>` class/function is emitted
  as one symbol; instantiations/specializations aren't resolved.
- **`#ifdef` is not evaluated** — conditionally-compiled code is indexed as
  visible (we don't run the preprocessor).

These are deliberate MVP boundaries, tracked as follow-ups. The structural-parity
gate proves the in-scope coverage is real, not aspirational.

## Per-agent expectations

| Agent | What changes in v0.32.0 |
|-------|--------------------------|
| **All** | `neuralmind build` now indexes C/C++ projects out of the box; retrieval, progressive disclosure, and the synapse layer work identically to the other five languages. |
| **Claude Code / Cursor / Cline / generic MCP** | No config change — drop NeuralMind on a C/C++ repo and query it. |

## What ships

- **`neuralmind/graphgen.py`** — `c` and `cpp` extractors behind the existing
  `_SUFFIX_LANG` / `_EXTRACTORS` seam.
- **`tree-sitter-c` / `tree-sitter-cpp`** added to base deps.
- Fixtures `tests/fixtures/sample_project_{c,cpp}` + committed gold graphs,
  registered in the parity gate (`evals/parity/run.py`) and `test_graphgen.py`.
- Watcher ignores `CMakeFiles`.
- PRD: `docs/prd/c-cpp-extractor.md`.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration. C/C++ files are picked up automatically on the next
`neuralmind build`.
