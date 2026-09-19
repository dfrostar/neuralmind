# NeuralMind Repo Onboarding Procedure

A repeatable, per-repo procedure for wiring NeuralMind into any codebase
(Python, Node.js, Go, or mixed). Replaces the current mechanical flow
(`install → build → query`) with an analyzed, planned, verified flow that
turns every integration into a documented, measurable artifact.

**Applies to:** the existing `cmmc20` integration, plus new targets
`cybersentinel-evolver` (Python security tool) and `agencyOS` (Python
business engine), and any future repo.

**Companion files:**
- [`docs/use-cases/repo-analysis-prompt.md`](repo-analysis-prompt.md) — the analysis prompt
- [`docs/use-cases/integration-plan-template.md`](integration-plan-template.md) — the plan output format

---

## The workflow — five steps

```
 Analyze → Plan → Build → Wire → Verify
```

Each step consumes the previous step's artifact and emits the next one.
The whole loop, including a full `neuralmind build`, targets **~10–15
minutes per repo**. Steps 1–2 are read-only; nothing is index-modified until
step 3, so a bad analysis is cheap to discard.

| Step | What you analyze | What you decide | Artifact you produce |
|------|------------------|-----------------|----------------------|
| 1. Analyze | repo source, manifests, config, docs | — (pure observation) | filled analysis brief |
| 2. Plan  | dry-run measurement + analysis brief | integration approach (CLI/MCP/hooks/CI/watch) | integration plan (
template) |
| 3. Build  | (no new analysis) | force vs incremental, graph backend | built `.neuralmind/` index + build stats |
| 4. Wire  | agent hosts present, CI files, git hooks | which agent/CI surfaces get NeuralMind | config edits, hooks, CI job, `.mcp.json` |
| 5. Verify | live query results, `doctor`, stats | ship it or adjust approach | passed acceptance set + `savings` baseline |

---

## Step 1 — Analyze

**Goal:** a read-only structural brief of the repo so you know what you're
indexing before you touch it.

1. Read the repo with the [repo analysis prompt](repo-analysis-prompt.md).
2. Fill the six sections: language/runtime profile, structure (entry points
   + key modules + schema artifacts), the 5–10 common agent questions,
   integration points (MCP / hooks / CI / watch), a coarse token-savings
   estimate, and risky/excluded paths.
3. Record the excerpt to `<repo>/docs/onboarding/analysis.md` (or a fleet
   tracker) so it outlives the session.

**Decision rule:** if the repo is tiny (< a few dozen files) or a thin
wrapper, mark it "CLI-only" now and skip steps 3–5's heavier wiring — a full
MCP+CI setup is overhead on a repo an agent rarely interrogates.

## Step 2 — Plan

**Goal:** an explicit, documented integration plan grounded in a *measured*
savings number, not a guess.

1. Run the measurement:
   ```bash
   cd <repo>            # e.g. /path/to/cybersentinel-evolver, /path/to/agencyOS
   neuralmind build --dry-run .
   # → Files scanned, Lines of code, Languages, Est. token reduction ~Nx
   ```
2. Open the [integration plan template](integration-plan-template.md) and fill
   it from the analysis brief + the `--dry-run` output. Read the savings
   multiplier from `--dry-run` — never fabricate it.
3. Choose the integration surface by repo type:

   | Repo type | Primary | Add if… |
   |-----------|---------|---------|
   | Security tool (e.g. `cybersentinel-evolver`) | CLI + MCP (agents use it interactively) | CI refresh if it ships rules; keep secrets out |
   | Business engine (e.g. `agencyOS`) | MCP + PostToolUse hooks (agent-heavy) | `watch --reindex` if actively developed; `learn` for docs |
   | Web/API app (e.g. `cmmc20`, Node/Go) | MCP + CI refresh | SCIP precision pass if you need compiler-accurate edges |

4. Commit the plan to `integrations/<repo>/plan.md` (or
   `docs/onboarding/<repo>-integration-plan.md` — pick once, fleet-wide).

**Token-savings mechanics:** NeuralMind's headline claim is 12–50× reduction
per query on real repos. The *project's* own number comes from
`neuralmind build --dry-run` (pre-build estimate) and then from real usage via
`neuralmind savings .` / `neuralmind savings --cost` (post-build, cumulative).
The plan records the dry-run estimate now and re-measures actuals in Verify.

## Step 3 — Build

**Goal:** a fresh, valid neural index.

```bash
cd <repo>
neuralmind build .            # auto-generates the code graph via tree-sitter backend
# or, for graphify's richer graph (takes priority automatically):
#   pip install graphifyy && graphify update . && neuralmind build .
```

- Supports Python, TypeScript, Node, Go, Rust, Java, C/C++, C#, Ruby, PHP in
  one mixed pass; OpenAPI/AsyncAPI, SQL DDL, and protobuf become document
  nodes automatically (v0.40.0+).
- **Decisions:** `--force` only when you want to re-embed everything
  (usually not needed); otherwise incremental is fine. Prefer the built-in
  backend unless the repo needs graphify's richer graph or compiler-accurate
  edges (`NEURALMIND_PRECISION=1` + a `*.scip` index for Python/TS/Go).
- **Artifact:** build statistics (nodes processed/embedded/skipped,
  communities, time) — record them in the plan.

## Step 4 — Wire

**Goal:** attach NeuralMind to the surfaces where agents actually work.

Exact commands (wire the ones the plan's §2 selected):

```bash
cd <repo>

# MCP — auto-register with every detected agent (Claude Code, Cursor, Cline,
# Claude Desktop); add --print to preview before writing.
neuralmind install-mcp --all
#   …or per client:  neuralmind install-mcp --client claude-code
# For a project-scoped .mcp.json (portable, committed):
#   { "mcpServers": { "neuralmind": { "command": "neuralmind-mcp", "args": ["."] } } }

# PostToolUse compression hooks (compress Read/Bash/Grep output)
neuralmind install-hooks .

# Auto-rebuild after every git commit (idempotent)
neuralmind init-hook .

# CI: add .github/workflows/update-neuralmind.yml → pip install neuralmind
#   + neuralmind build . on push to main, paths: **.py / **.ts / **.go
```

**Integration-point decisions:**
- **MCP** — the universal path; any agent host gets `neuralmind_wakeup`,
  `neuralmind_query`, `neuralmind_search`, `neuralmind_skeleton`,
  `neuralmind_recursive_query`, etc.
- **Hooks** — biggest token win for agent-heavy repos (compresses tool output
  the LLM would otherwise read in full).
- **CI/hook/watch** — keep the index fresh as the repo evolves; a stale index
  is the top cause of "wrong code surfaced" reports.

## Step 5 — Verify

**Goal:** prove the index answers the repo's real questions and the claimed
savings hold — before calling the repo "onboarded".

```bash
cd <repo>
neuralmind doctor                 # single health check: graph, index, synapses, MCP, hooks
neuralmind stats .                # Built: True, node/community counts

# Fire the acceptance set from the plan (§3). Each should return a compact,
# correct context with Reduction: ≥10x and the *right* files.
neuralmind query . "How does <feature A> flow from entry to persistence?"
neuralmind query . "<query 2>" --explain   # human breakdown of tokens saved
neuralmind wakeup .                        # L0+L1 project overview (~600 tok)
```

**Pass criteria:**
- `neuralmind doctor` reports the graph, index, and synapse store healthy and
  MCP/hooks registered.
- Every plan §3 query returns the expected module(s) at ≥10× reduction (a
  query that returns the *wrong* code fails the step — adjust scope or
  rebuild).
- Record a savings baseline: `neuralmind savings .` (and `--cost` for the
  dollar view). Re-run at ~2 weeks and backfill the plan's §4 with actuals.

**Decision rule:** if Verify fails on cold keys only (e.g. a semantically
overlapping term), the repo is still shippable — log the miss and note it for
the follow-up `savings` pass. If `doctor` fails, do not ship: it means the
index is stale or mis-wired.

---

## Applying this to the current target repos

| Repo | Type | Expected primary path |
|------|------|----------------------|
| `cmmc20` | CMMC SaaS (existing, reference) | already integrated — re-run Verify + capture savings baseline if not done |
| `cybersentinel-evolver` | Python security tool | CLI + MCP; keep any signatures/rules out of the index per risky-path list |
| `agencyOS` | Python business engine | MCP + PostToolUse hooks; `watch --reindex` given active development |

Same five steps, same templates, same failure rules — only the filled-in
answers differ. That is what makes the procedure repeatable.
