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

A fresh build already seeds the synapse graph with the code's structure (calls, imports, inheritance), so `review` answers on day one. `neuralmind watch` runs in the background and adds co-editing associations as you work; what those add on top of the structural seeds is not yet measured (see "What it measures as" below).

## The workflow

**Before opening a PR**, run:

```bash
neuralmind review .
```

NeuralMind reads `git diff --name-only main` (or pass `--base <ref>` for a different base), maps each changed file to its graph nodes, and runs spreading activation from those seed nodes across the synapse graph. The output is a ranked table of co-break candidates — nodes most strongly associated with your changes that you haven't touched yet:

```
NeuralMind review — my-project  (diff against: HEAD)

Changed files (3):
  • src/auth/handlers.py
  • src/auth/middleware.py
  • src/session/store.py

Co-break candidates — files NOT in diff but strongly associated (4):
  0.782 ████████  src/auth/tokens.py
  0.654 ██████    tests/test_auth_middleware.py
  0.431 ████      src/auth/token_validator.py
  0.198 ██        config/settings.py

Ranked by association in the synapse graph: structural coupling (calls,
imports, inheritance) on a fresh index, plus files edited together once
the project has been used. Consider whether your change also needs to
touch them.
```

Higher weight = stronger association. On a fresh index that association is structural; co-editing strengthens or adds links as the project is used.

## What it measures as

Measured on real commits *(v4.25.0, [pre-registered](../specs/REVIEW-DRIFT-EVAL-SPEC.md), [results](https://github.com/dfrostar/neuralmind/blob/main/bench/review_drift/2026-11-02/README.md))*: on 119 commits of requests, click, flask and rich that changed several files, each indexed cold at the parent commit, every changed file was held out in turn and `review` was asked to name it from the others. It put the missing file in its top ten on 63% of 430 pairs and in its top five on 45%. Ranking the repository's files by how often they changed together with the seed files over the previous 300 commits (`git log`, no NeuralMind) managed 65% and 55%; direct structural adjacency 53% and 40%. The two methods miss different pairs: either one hit 79% at ten. So on a repository you have just indexed, `review` is a structural coupling list that is right about six times in ten, and the git log is as good. Whether weeks of learned co-editing lift it past the git log is the open question, and `neuralmind eval . --synapse-ab` is how to ask it on your repository.

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

- Co-break candidates are ranked by association strength in the synapse graph, not by static analysis of your change. A high-weight candidate might not actually break — it is coupled to what you changed, structurally or by co-editing.
- On a freshly built index the graph holds only structural seeds, and the measured result above is for that case: about as good as `git log` co-change, not better. Learned associations from `watch` and the hooks are added as the project is used; their effect on this list is unmeasured.
- Call-graph edges complement synapse weights but don't replace a type-checker or test suite. Use this as a pre-push hint, not a guarantee.

> **Want the static side of this?** `neuralmind review` ranks co-break candidates by *learned association* (what you edit together). For the *structural* answer — the exact callers, importers, and subclasses a change would touch, straight from the code graph and available with no editing history — run [`neuralmind structural <symbol> --blast-radius`](blast-radius-before-a-rename.md) (v0.42.0+). Structure says what *can* break; synapses say what *usually* co-changes. Use both before a risky refactor.

> **Want to know if the change itself is off, not just what it touches?** `neuralmind review` and `--blast-radius` both answer "what else does this affect?" — they say nothing about whether the change you made is internally consistent with its own siblings. For that, [`neuralmind drift`](claude-code.md#flag-a-commit-that-drifts-from-its-own-patterns-v320) (v3.2.0+) reads the same diff and flags a changed symbol that skips an association a strong majority of its peers share — the eleventh handler that quietly forgot the auth check the other ten all have. It is quiet by design, and on the same measurement it was as quiet on bugs as on everything else: run on the pre-fix code of 121 real bug fixes in the four public repositories, it flagged a changed symbol on 5%, and on 5% of 121 matched non-fix commits; most of its findings were test functions skipping a fixture their siblings use ([results](https://github.com/dfrostar/neuralmind/blob/main/bench/review_drift/2026-11-02/README.md)). Run it alongside `review` as a pre-commit guard that costs nothing; don't expect it to catch most bugs.

## As a pre-commit hook

Both `review` and `drift` are diff-aware, so both fit naturally into a git hook instead of a manual pre-push habit:

```bash
neuralmind init-hook .   # post-commit decision scan + rebuild, pre-commit drift guard
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
