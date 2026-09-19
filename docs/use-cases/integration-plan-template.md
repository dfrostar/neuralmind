# NeuralMind Integration Plan Template

Output format for a single repo onboarding. Fill this in from the repo
analysis prompt result **and** the `neuralmind build --dry-run` measurement
(the plan should never guess a savings number, it must read it from
`--dry-run`). One file per repo: `integrations/<repo>/plan.md` (or
`docs/onboarding/<repo>-integration-plan.md`).

---

# Integration Plan — <PROJECT_NAME>

**Repo:** `<owner>/<repo>` · **Target:** `<REPO_DIR>` · **Date:** <YYYY-MM-DD>
**Status:** `draft | building | wired | verified`

## 1. Repo summary
> One short paragraph: what the repo does, its stack, and rough scale.

- **Languages (by LOC/file count):** Python `~N files (~N Loc)` · TypeScript `~N` · Go `~N` · [mixed]
- **Tooling:** `<package manager / build>` → entry at `<path>`
- **Entry points:** `main.py`, `src/<pkg>/__main__.py`, `pyproject.toml [project.scripts]`, server bootstrap
- **Key modules (≤10):** `dir/mod.py` — one-line role
- **Schema artifacts for document nodes:** OpenAPI `openapi.yaml` · SQL DDL · `.proto` · none

## 2. Recommended integration approach
Check the ONE primary path taken first, then secondary:

- [ ] **CLI (copy-paste / scripting)** — lowest friction; `quant`/`wakeup`/
      `query` piped into agents or docs.
- [ ] **MCP server** — `neuralmind install-mcp --all` (auto-detects Claude Code,
      Cursor, Cline, Claude Desktop). Hosts: `<list>`. Config is
      `project_path = <REPO_DIR>`. *(chosen)*
- [ ] **PostToolUse compression hooks** — `neuralmind install-hooks .`
      (compress Read/Bash/Grep output; biggest win for agent-heavy repos).
- [ ] **CI refresh** — add `<CI file>` job: `pip install neuralmind` +
      `neuralmind build .` on push to `main` (paths: `**.py`/`**.ts`/`**.go`).
- [ ] **Git hook / watch** — `neuralmind init-hook .` (rebuild on commit) and/or
      `neuralmind watch --reindex` for actively-developed repos.
- [ ] **Document ingestion** — `neuralmind learn <docs/>` if README/PDF/DOCX
      matter beyond code.

Wire command summary (exact commands to run in Build/Wire):
```bash
cd <REPO_DIR>
pip install neuralmind
neuralmind build --dry-run .      # measure before building
neuralmind build .                 # real build
<one of>  neuralmind install-mcp --all
        | neuralmind install-hooks .
        | neuralmind init-hook .
```

## 3. Key queries this repo will benefit from
> 5–10 concrete questions, derived from the repo analysis. These double as the
> acceptance set for Verify.

1. `How does <feature A> flow from entry point to persistence?`
2. `Where is <entity> defined and what consumes it?`
3. `How is auth / config / error handling wired?`
4. `Which module owns business rule <B>?`
5. `What does the CI release path look like?`
6. `How do I add a new <endpoint|rule|provider>?`
7. …

## 4. Estimated token savings
- Measured by `neuralmind build --dry-run .`:
  - Files scanned: `N` · Lines of code: `N,N00` · Languages: `<...>`
  - Est. token reduction: **`~Nx` per query**
- NeuralMind headline claim: 12–50× per query on real repos; cumulative
  dollar view via `neuralmind savings . --cost --queries-per-day <N>`.
- Note: only `neuralmind build` + real queries make the savings measurable;
  update this section after 1–2 weeks with `neuralmind savings .`.

## 5. Next steps
1. [ ] Run Build step (`neuralmind build .`) — index ready.
2. [ ] Run Wire step (commands from §2).
3. [ ] Run Verify step: fire all §3 queries, confirm each returns `Reduction:
      ≥10x` and the right files; run `neuralmind doctor`.
4. [ ] (2 weeks later) run `neuralmind savings .` and refresh §4.
5. [ ] File this plan at `<plan path>` for the next operator.

---

### Conventions
- **Never fabricate a savings number** — only carry it forward if it came from
  `neuralmind build --dry-run` or `neuralmind savings`.
- Use **absolute** `project_path` in MCP host configs; relative paths are the
  #1 shared-brain misconfiguration.
- Keep `.neuralmind/`, `graphify-out/`, and build output out of any index by
  scope/exclude rules if the repo is very large or has vendored code.
- These conventions mirror the existing `cmmc20` integration so every repo has
  the same shape.
