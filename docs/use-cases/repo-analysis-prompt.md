# NeuralMind Repo Analysis Prompt (template)

Use this prompt to analyze ANY codebase before (or instead of) wiring up
NeuralMind. It runs against the repo's own source, README, build files,
and config. Output is a structured brief that feeds directly into
`neuralmind build --dry-run`, then `neuralmind build`.

Copy the block below, replace `<REPO_DIR>` and the bracketed placeholders,
and run it against the repo. Keep the prompt static; the *answers* change
per repo.

---

```text
You are performing a NeuralMind repo-onboarding analysis of the codebase at
<REPO_DIR> (project name: <PROJECT_NAME>, primary purpose: <ONE_LINE>).

Read the repo's source, README, package/build manifests, and config. Do NOT
build any index; this is a read-only analysis pass. Report facts only —
quote file paths and line references. Return your answer inside the exact
sections below, filling each one. If a section has no evidence, say "none".

## 1. Language & runtime profile
- List primary languages by file count and rough lines of code. Classify as
  Python / Node.js / Go / mixed.
- Note the build/tooling surface: package manager (requirements.txt,
  pyproject.toml/uv, package.json, go.mod), entry scripts, Makefile/scripts/.
- Note anything the tree-sitter backend supports out of the box
  (.py, .ts/.tsx, .go, .rs, .java, .c/.h, .cpp/.cc/.hpp, .cs, .rb, .php,
  plus OpenAPI/AsyncAPI .yaml, SQL DDL .sql, .proto). Flag files the
  backend will skip, so we can say so later.

## 2. Structure: entry points & key modules
- List the CLI/API entry points (main(), __main__.py, src/bin, entrypoint,
  server bootstrap).
- List the 5–10 most load-bearing modules/packages and one sentence each on
  what they do.
- List the top-level directories and one line on each.
- Identify the schema artifacts that yield document nodes (OpenAPI, SQL DDL,
  protobuf) if any exist.

## 3. Common developer / agent questions (5–10)
Write the concrete questions an AI coding agent will most often ask this
repo, e.g.:
  - "How does <feature X> flow from entry point to persistence?"
  - "Where is <entity> defined and what consumes it?"
  - "How is auth / config / error handling wired?"
  - "Which module owns business rule <Y>?"
  - "What does the CI release path look like?"

## 4. Integration points (where NeuralMind hooks in)
- MCP: which agent hosts are present (Claude Code, Cursor, Cline, Claude
  Desktop, Hermes)? Recommend `neuralmind install-mcp --all` or per-client.
- Hooks: is a code agent present that benefits from PostToolUse
  compression? (recommend `neuralmind install-hooks .`)
- CI: does repo use GitHub Actions / GitLab / Makefile targets? Recommend a
  `neuralmind build .` refresh job and/or `neuralmind init-hook .`.
- Watch: is the repo actively developed such that `neuralmind watch
  --reindex` or a scheduled rebuild is warranted?

## 5. Token-savings estimate
- Give a rough LOC estimate from your read.
- State the NeuralMind headline claim (12–50× reduction per query on real
  repos) and note that the repo's real number comes from `neuralmind build
  --dry-run` (files, LOC, languages, est. reduction), which should be run
  next as the Plan step.
- Do not fabricate a specific multiplier; compute it in the Plan step.

## 6. Risky / excluded paths
- List directories to keep out of the index (vendored code, build output,
  `.neuralmind/`, secrets-bearing dirs, fixtures with licenses, autopilot,
  large non-code assets) and the `.neuralmindignore`-style guidance.
```

---

## What changes per repo (keep this part OUT of the reusable prompt)

Everything else is constant. If you're onboarding a whole fleet, commit the
prompt block verbatim and only vary the three bracketed fields.
