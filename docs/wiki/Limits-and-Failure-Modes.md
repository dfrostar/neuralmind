# Limits & Failure Modes

The honest "here's where it breaks" page. [`HONEST-ASSESSMENT.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/HONEST-ASSESSMENT.md)
answers *should you install it*; this page answers *where does it stop working,
and what do I do then*. Everything here is sourced from the shipped code and
release notes — no aspirational claims. If a number is an estimate, it says so.

If you came here from a "trust-me-bro numbers" critique: the reproducible
evidence lives on the **[Benchmarks](Benchmarks)** page and in
[`benchmarks/`](https://github.com/dfrostar/neuralmind/blob/main/benchmarks/README.md);
this page is the companion list of the rough edges those benchmarks *don't*
paper over.

---

## 1. When the compressed context is enough — and when it isn't

A NeuralMind query assembles four layers with hard token caps
([`neuralmind/context_selector.py`](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/context_selector.py)):

| Layer | What it carries | Default cap |
|---|---|---:|
| **L0** identity | project name, description, stats | **150 tok** |
| **L1** summary | top code clusters, type distribution, report digest | **600 tok** |
| **L2** on-demand | the communities semantic search + synapse recall pulled in | **800 tok** |
| **L3** search | the individual vector + BM25 hits, re-ranked by synapse energy | **1,000 tok** |

So a single query tops out at roughly **~2.5K tokens** of assembled context (the
caps are ceilings — most queries land well under). That budget is tuned for the
question NeuralMind is built to answer:

> *"Find and explain the code that bears on **this** question."*

**Where it's enough.** Locating the right files/symbols, understanding one
subsystem, answering "how does X work", seeding a focused change. The faithfulness
eval shows that at a **matched budget**, smart selection beats naive truncation
(**+0.143 expected-fact recall**, [Benchmarks](Benchmarks)) — i.e. the ~2.5K
tokens are *better-chosen* tokens, not just fewer.

**Where it gets thin.** A single ~2.5K-token window is a poor fit for work that
genuinely needs *broad* context at once:

- **Wide refactors touching many files simultaneously.** Renaming a symbol used in
  30 files, or a cross-cutting signature change, needs more breadth than one query
  budget holds. Retrieval finds the *seeds*; it doesn't hand you all 30 sites in
  one shot.
- **"Read everything and reason globally" tasks.** Whole-architecture rewrites,
  global invariants, "find every place that could be affected." These are
  O(repo) by nature; NeuralMind is O(query) by design (see
  [`HONEST-ASSESSMENT.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/HONEST-ASSESSMENT.md#what-4070-reduction-actually-means)).
- **Answers that depend on prose NeuralMind didn't index.** If the "why" lives in a
  Confluence page or a PR description, it isn't in the graph.

### What to do when one query isn't enough

You are not stuck with the default budget. In rough order of reach:

1. **`neuralmind review`** — instead of one query, seed spreading activation from
   the files you're *already* changing (`git diff --name-only`) and surface the
   **co-break candidates** you forgot to touch. This is the right tool for a
   multi-file change; it's also the `neuralmind_review` MCP tool so the agent can
   call it before proposing edits.
2. **Raise L2 recall depth.** The selector's L2 depth is clamped to
   `[L2_RECALL_K_MIN=2, L2_RECALL_K_MAX=6]`; the opt-in autotuner
   (`NEURALMIND_SELECTOR_AUTOTUNE=1`) widens it from the re-query rate. Inspect the
   current state with `neuralmind self-improve status`.
3. **Run several targeted queries**, one per concern, rather than one broad query.
   Retrieval is cheap; breadth comes from *more* queries, not a bigger single one.
4. **Bypass compression entirely for a tool call.** `NEURALMIND_BYPASS=1` skips the
   PostToolUse compression so the agent reads the full output of one `Read`/`Bash`/
   `Grep` — use it when you knowingly need the whole file in front of the model.

> **Rule of thumb.** If the task is "understand / locate / seed", trust the query.
> If it's "rewrite across the repo at once", use `review` to enumerate the blast
> radius first, then widen or bypass for the files that matter.

---

## 2. Repo-size, index-time, memory & disk envelope

NeuralMind has run on **1M+ LOC** codebases. The figures below are **rough
estimates** for planning, not measured SLAs — the rigorously-measured numbers are
the CI token-reduction floor and the public-benchmark recall on real OSS repos
(see [Benchmarks](Benchmarks)); large-real-repo *quality* and *latency* are
explicitly **not yet measured at scale** (a known gap on
[`ROADMAP.md`](https://github.com/dfrostar/neuralmind/blob/main/ROADMAP.md)).

| Repo size | First build | Disk (index) | Notes |
|---|---|---|---|
| ~5K LOC | seconds | a few MB | below this, skip NeuralMind and paste the code |
| 100K LOC | minutes | 50–100 MB | comfortable |
| 500K LOC | minutes | 200–500 MB | comfortable |
| 1M LOC | ~10–20 min | 500 MB–2 GB | the `~10–20 min for a 50K-line repo` setup line in [`HONEST-ASSESSMENT.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/HONEST-ASSESSMENT.md#setup-cost-realistic) scales up here |
| 10M LOC | trust-the-gate | 5–20 GB | not exercised in CI; turbovec's 8–16× smaller vectors matter most here |

Rules that hold regardless of size:

- **First build is the cost; re-builds are incremental.** `neuralmind watch --reindex`
  re-parses only changed files and re-embeds only their nodes — unchanged nodes are
  skipped by a content-hash check
  ([`neuralmind/embedder.py`](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/embedder.py)),
  so editing a handful of files costs a handful of files' work, not a full rescan.
- **`git pull` of 200 files re-indexes those 200 files, not the repo.** The
  content-hash skip is per-node, so a large pull touches only what actually changed.
  Honest caveat: there is **no published "200 files = N ms" latency number** yet —
  it's incremental by construction, but the wall-clock curve isn't benchmarked.
- **Disk is reclaimable.** The whole index regenerates from source; delete
  `graphify-out/neuralmind_db/` (or `.neuralmind/`) and rebuild.
- **Turbovec shrinks the memory/disk footprint** ~8–16× vs ChromaDB float32 vectors
  at retrieval parity — the lever that makes large monorepos practical
  ([Benchmarks → ChromaDB-free](Benchmarks)).

If a build OOMs on a very large tree, build incrementally and see
[Troubleshooting](Troubleshooting).

---

## 3. Language support matrix

NeuralMind's built-in **tree-sitter** backend indexes the ten languages below with
**no graphify dependency** (`neuralmind build .` works standalone), plus four
non-code schema/document artifacts. Structural coverage is **parity-gated in CI**
(symbol-for-symbol vs graphify, zero dangling edges) — but parity is *structural
correctness*, **not** per-language retrieval-quality scoring. The gold-fact /
faithfulness evals are still **Python-first**; quality on the other languages is
proven *structurally*, not yet *measured for answer quality* (gap tracked on
[`ROADMAP.md`](https://github.com/dfrostar/neuralmind/blob/main/ROADMAP.md)).

Source of truth for the parser: `_SUFFIX_LANG` in
[`neuralmind/graphgen.py`](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/graphgen.py).

### Code languages (tree-sitter)

| Language | Suffixes | Indexed | Honestly **not** modeled |
|---|---|---|---|
| **Python** | `.py` | full reference language; the eval gold set | — |
| **TypeScript** | `.ts` `.tsx` | types, functions, imports — 100% parity gate | type-level-only constructs are best-effort |
| **Go** | `.go` | types, funcs, methods, imports — 100% parity gate | — |
| **Rust** | `.rs` | structs, enums, traits, `impl` blocks, fields, free fns; `impl Trait for T`→`inherits`; `use`→`imports_from`; doc comments→rationale | macro-generated items; `target/` skipped |
| **Java** | `.java` | classes/interfaces/enums/records, methods, ctors, fields; `extends`/`implements`→`inherits`; `import`→`imports_from`; Javadoc→rationale | — |
| **C#** | `.cs` | class/interface/struct/record/enum, methods/ctors, fields/props/enum members; `base_list`→`inherits`; `using`→`imports_from` | — |
| **C** | `.c` `.h` | functions, struct/union/enum + fields/consts, typedefs; `#include "x.h"`→`imports_from`; header/impl pair collated | **macros not indexed as symbols**; `#ifdef` not evaluated |
| **C++** | `.cpp` `.cc` `.cxx` `.hpp` `.hh` `.hxx` | classes w/ member methods/fields, namespace-qualified ids, the C set above; base classes→`inherits` | **templates not specialized**; macros not indexed; `#ifdef` not evaluated |
| **Ruby** | `.rb` | `class`/`module`→type, `def`/`def self.`→function, constants→symbol; `Foo < Bar`→`inherits`; `require_relative`→`imports_from` | **no receiver-type call resolution**; `include`/`extend` mixins not modeled as inheritance; `attr_accessor` not emitted as fields |
| **PHP** | `.php` | class/interface/trait/enum→type, methods/fns→function, props/consts/enum cases→symbol; `extends`/`implements`→`inherits`; `use`→`imports_from`; `/** */`→rationale | **no `$obj->method` receiver-type resolution**; `require`/`include` path imports not modeled; trait-`use`-in-class-body not modeled as inheritance |

**Calls are heuristic by default** across all languages (best-effort, disclosed
per release). For **compiler-accurate** `calls`/`inherits` edges on Python /
TypeScript / Go, set `NEURALMIND_PRECISION=1` with a SCIP index (off by default,
[v0.17.0](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.17.0.md)).

### Schema & document artifacts (no tree-sitter parse)

| Artifact | Suffixes | Indexed | Honestly **not** modeled |
|---|---|---|---|
| **Markdown** | `.md` `.markdown` | file + one `document` node per heading | — |
| **OpenAPI / AsyncAPI** | `.yaml` `.yml` *(with an `openapi`/`asyncapi`/`swagger` key)* | one node per path+method (`POST /payments/charge`), per schema component, per channel | **`$ref` resolution**; plain YAML config is silently skipped (not an error) |
| **SQL DDL** | `.sql` | one node per `CREATE TABLE/VIEW/PROCEDURE/FUNCTION/TRIGGER/INDEX/TYPE` | **`ALTER` / `SELECT` not modeled** |
| **Protocol Buffers** | `.proto` | one node per `message` / `service` / `rpc` / `enum` | **`import` edges not modeled** |

**GraphQL** is planned for
[v0.42.0](https://github.com/dfrostar/neuralmind/blob/main/ROADMAP.md). Any other
file type can be indexed as plaintext (less precise) rather than parsed.

### Polyglot-monorepo guidance

Retrieval quality tracks **graph quality**, which tracks **per-language parser
quality**. A monorepo whose value is concentrated in a weak-coverage area (heavy
C++ template metaprogramming, macro-defined APIs, generated code) will see a lower
real-world ratio than the headline range — this is called out directly in
[`HONEST-ASSESSMENT.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/HONEST-ASSESSMENT.md#when-neuralmind-is-not-worth-it).
Practical move: index the strong-coverage languages and lean on `grep`/SCIP for the
weak ones; the tools compose.

---

## 4. The honest "thin evidence" list

Carried over from [`HONEST-ASSESSMENT.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/HONEST-ASSESSMENT.md#what-we-havent-measured-well-yet)
so it lives next to the limits it qualifies:

- **End-to-end cost** is **3–10×** on a real workload, *not* 40–70× — the headline
  is a *retrieval-input-token* reduction, not a total-bill reduction.
- **Per-language answer quality** is gated *structurally*, not *for answer
  faithfulness* — the faithfulness gold set is Python-first.
- **Large-real-repo quality and incremental latency** are "trust the gate," not yet
  measured at scale.
- **Community benchmarks** are still a small, mostly-maintainer-seeded set — outside
  numbers (even disappointing ones) are the most valuable contribution. Run
  `neuralmind benchmark . --contribute`.

For what the project *deliberately doesn't measure yet* (SWE-bench, Aider
agent-loop accuracy, multi-competitor head-to-heads), see the **"What we don't
measure yet"** section of [`benchmarks/README.md`](https://github.com/dfrostar/neuralmind/blob/main/benchmarks/README.md).

---

*See also:* [Benchmarks](Benchmarks) · [Architecture](Architecture) · [FAQ](FAQ) ·
[Troubleshooting](Troubleshooting) ·
[HONEST-ASSESSMENT.md](https://github.com/dfrostar/neuralmind/blob/main/docs/HONEST-ASSESSMENT.md)
