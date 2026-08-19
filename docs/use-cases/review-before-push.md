# Use Case: Review Before Push — Diff-Aware Co-Break Detection

## What you're solving for

You've made changes to a few files. You're about to open a PR. But large codebases have hidden dependencies — call-graph edges, synapse associations from past edits, import chains — that static linters don't track. Something you didn't touch might break because it relied on an invariant you just changed. You want to know *before* CI tells you.

## Setup (one time)

```bash
pip install neuralmind
cd your-project
neuralmind build .         # builds the knowledge graph + synapse store
neuralmind watch .         # starts the file watcher to learn associations
```

The synapse layer needs a few sessions of real editing before it has meaningful weights. `neuralmind watch` runs in the background and accumulates co-activation patterns as you edit.

## The workflow

**Before opening a PR**, run:

```bash
neuralmind review .
```

NeuralMind reads `git diff --name-only main` (or pass `--base <ref>` for a different base), maps each changed file to its graph nodes, and runs spreading activation from those seed nodes across the synapse graph. The output is a ranked table of co-break candidates — nodes most strongly associated with your changes that you haven't touched yet:

```
Changed files (3): src/auth/handlers.py, src/auth/middleware.py, src/session/store.py

Co-break candidates:
  1. src/session/store.py:SessionStore.validate   weight 0.84   activations 12
  2. tests/test_auth_middleware.py                weight 0.71   activations  8
  3. src/auth/token_validator.py:check_expiry     weight 0.58   activations  6
  4. docs/auth-flow.md                            weight 0.31   activations  3
```

Higher weight = stronger learned association. Activations = how many co-editing sessions established the link.

## Dry-run first (v0.39.0+)

To estimate savings before building the index:

```bash
neuralmind build . --dry-run
```

Shows estimated token savings by language, file count, and reduction ratio — without touching the vector store.

## As an MCP tool (for agents)

```
neuralmind_review(project_path=".", changed_files=["src/auth/handlers.py"])
```

The agent can call this automatically after editing a file, get the co-break candidates back as structured JSON, and decide whether to investigate before continuing. Useful in agentic loops where the agent makes a series of edits and wants to catch cascading breaks early.

## What changes for you

| Before | After |
|---|---|
| Push, wait for CI, get a cryptic failure about a file you didn't touch | `neuralmind review` surfaces candidates before you push |
| "I wonder if changing this touches the auth flow" is a gut-feel question | Spreading activation gives a ranked, weighted answer |
| Synapse edges are invisible — you don't know what the model has learned | `neuralmind query --explain` shows which synapses influenced a retrieval |

## Limitations

- Co-break candidates are ranked by learned association strength, not by static analysis. A high-weight candidate might not actually break — it just co-activates with your changes most often in history.
- The synapse layer needs editing history to have meaningful weights. On a freshly built index with no `watch` sessions, spreading activation will return empty or low-confidence results.
- Call-graph edges (from the structural graph) complement synapse weights but don't replace a type-checker or test suite. Use this as a pre-push hint, not a guarantee.

> **Want the static side of this?** `neuralmind review` ranks co-break candidates by *learned association* (what you edit together). For the *structural* answer — the exact callers, importers, and subclasses a change would touch, straight from the code graph and available with no editing history — run [`neuralmind structural <symbol> --blast-radius`](blast-radius-before-a-rename.md) (v0.42.0+). Structure says what *can* break; synapses say what *usually* co-changes. Use both before a risky refactor.

> **Want to know if the change itself is off, not just what it touches?** `neuralmind review` and `--blast-radius` both answer "what else does this affect?" — they say nothing about whether the change you made is internally consistent with its own siblings. For that, [`neuralmind drift`](claude-code.md#flag-a-commit-that-drifts-from-its-own-patterns-v320) (v3.2.0+) reads the same diff and flags a changed symbol that skips an association a strong majority of its peers share — the eleventh handler that quietly forgot the auth check the other ten all have. Run it alongside `review`: one tells you what a change might break elsewhere, the other tells you if the change is drifting from the pattern it's supposed to follow.

## As a pre-commit hook

Both `review` and `drift` are diff-aware, so both fit naturally into a git hook instead of a manual pre-push habit:

```bash
neuralmind init-hook .   # installs post-commit rebuild + pre-commit drift guard
```

`init-hook` wires `neuralmind drift . --staged` into `pre-commit` (warn-only
by default, `--strict` to block). `review` isn't installed automatically —
its co-break candidates are advisory judgment calls, better suited to a
manual check before opening a PR than a hook every commit runs through.

## See also

- [Blast radius before a rename](blast-radius-before-a-rename.md) — the static-graph complement: every caller/importer/subclass a change would touch (v0.42.0+)
- [`neuralmind drift`](claude-code.md#flag-a-commit-that-drifts-from-its-own-patterns-v320) — flag a changed symbol that breaks a pattern its peers share, at commit time (v3.2.0+)
- [`neuralmind query --explain`](claude-code.md#understand-why-a-retrieval-answered-the-way-it-did-v0400) — understand why a specific retrieval answered the way it did
- [`neuralmind savings`](claude-code.md#track-cumulative-savings-v0400-requires-neuralmind_memory1) — track cumulative token savings across sessions
- [Full v0.39.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.39.0.md)
- [Full v3.2.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v3.2.0.md)
