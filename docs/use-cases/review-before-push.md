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

## Dry-run first (v0.40.0+)

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

## See also

- [`neuralmind query --explain`](claude-code.md#understand-why-a-retrieval-answered-the-way-it-did-v0400) — understand why a specific retrieval answered the way it did
- [`neuralmind savings`](claude-code.md#track-cumulative-savings-v0400-requires-neuralmind_memory1) — track cumulative token savings across sessions
- [Full v0.40.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.40.0.md)
