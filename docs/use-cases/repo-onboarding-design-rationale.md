# Design Rationale — NeuralMind Repo Onboarding

Why the procedure, prompt, and plan template look the way they do.

---

## 1. Ground every design in the REAL command surface

The biggest failure risk in a doc like this is inventing a workflow that
doesn't match the tool. I read the canonical docs
(`neuralmind/docs/wiki/Setup-Guide.md`, `Integration-Guide.md`,
`CLI-Reference.md`) before designing, and every command referenced —
`neuralmind build`, `build --dry-run`, `query --explain`, `wakeup`, `stats`,
`doctor`, `savings`, `install-mcp --all`, `install-hooks`, `init-hook`,
`watch --reindex`, `learn` — is a real, documented CLI surface. The procedure
is *executable as written*, not aspirational.

Two features of the actual tool shaped the design meaningfully:
- **`neuralmind build --dry-run`** already emits files scored, lines of code,
  language breakdown, and an estimated reduction multiplier. That is the
  *right* source for a repo-specific token-savings estimate, so I made the
  Plan step read from it and *forbade* fabricating a number. This directly
  addresses the "token savings estimate" requirement with a measured value.
- **`neuralmind savings` / `savings --cost`** gives post-build actuals, so the
  procedure supports the estimate→actuals loop (record dry-run estimate in
  Plan, re-measure real savings at 2 weeks). This makes the savings claim
  verifiable and honest.

## 2. Why `Analyze → Plan → Build → Wire → Verify`

The stated current workflow is *mechanical* (`install → build → query`) — it
jumps straight to building an index before anyone knows what the repo is, what
it should answer, or where agents live. The five-step flow fixes that:

- **Analysis first.** You can't wire a codebase you haven't read. Analysis is
  read-only and cheap to discard, so a wrong read costs nothing before money
  is spent building/wiring.
- **Plan before build.** All decisions (approach, queries, savings, risk) get
  made and written down *before* the index is constructed — so rework is cheap
  and the choice is auditable. Build happens with a contract in hand.
- **Wire after build.** Index must exist before you attach it to agents;
  ordering prevents "wiring a dead index."
- **Verify ends it.** A success gate (`doctor` + acceptance queries ≥10× +
  savings baseline) is what separates "believed working" from "proven
  working" — and every existing/new repo gets exactly the same gate.

Each step declares **what you analyze → what you decide → what artifact you
produce**, which makes the process auditable and repeatable across the fleet
in a way a loose checklist isn't.

## 3. Language-agnostic by design (Python / Node / Go / mixed)

I leaned on the tree-sitter backend's real coverage (`.py`, `.ts/.tsx`,
`.go`, plus Rust/Java/C/C++/C#/Ruby/PHP, and OpenAPI/SQL/protobuf document
nodes) rather than asserting per-language custom logic. So:
- The prompt asks for a *language/runtime profile* (classify + tooling + which
  files the backend will skip) instead of hard-coding branch logic.
- The Build step is identical across languages because `build` already does
  the mixed-language pass for free. This satisfies "must work for Python,
  Node.js, Go" without maintaining three procedures.
- The one place language matters — whether to add a SCIP precision pass for
  compiler-accurate edges (Python/TS/Go support it) — is surfaced as an
  optional decision, not a requirement.

## 4. Token-savings: measured, never invented

The requirement "token savings estimate" is a trap if answered with vibes.
Design choice: the *only* authoritative multipliers are (a) `build --dry-run`
(estimate) and (b) `savings` (actuals). The NeuralMind headline 12–50× is
stated as a *claim to verify against the repo*, and both templates carry an
explicit "never fabricate this number" rule. This keeps every plan credible.

## 5. Repo-type → integration-surface routing

MCP/hooks/CI are all viable, but not equally valuable per repo. I added a
small decision table mapping repo type to primary surface:
- Security tools → CLI + MCP (used interactively; risk of indexing signatures).
- Business engines / agent-heavy → MCP + PostToolUse hooks (the token win).
- Web apps (+ Node/Go) → MCP + CI refresh.
This keeps the procedure *actionable* (a decision rule, not a menu) while
still general. Each target repo (`cmmc20`, `cybersentinel-evolver`,
`agencyOS`) maps to a row.

## 6. Templates reuse, don't re-invent

The plan template and analysis prompt are parameterized (fill-in) rather than
repo-specific, so onboarding N repos reuses the same two files N times. The
prompt even carves out "what changes per repo" from "the reusable constant
block." That directly meets the "repeatable across repos" constraint.

## 7. Safe defaults inherited from the real docs

- Absolute `project_path` in MCP configs (the docs call this the #1
  misconfiguration).
- Keep `.neuralmind/`, `graphify-out/`, vendored/build output, and secrets
  out of the index — the analysis prompt has a risky-path section, and the
  plan's conventions note it.
- The dedicated `neuralmind onboarding` command (v1.7.0) is a license/
  governance wizard, *not* repo analysis — so this new procedure is named to
  avoid confusion ("Repo Onboarding") and composes with it rather than
  duplicating it.

---

## Design decisions at a glance

| Requirement | Decision | Why |
|-------------|----------|-----|
| Repo analysis prompt | 6-section read-only brief, parameterized, committed to docs | Pure observation before any index cost; reusable forever |
| Token savings estimate | Read from `build --dry-run`, actualize via `savings`; never fabricate | Measured > claimed; honest, verifiable |
| Cross-language support | One procedure; rely on tree-sitter mixed pass | No per-language branches to maintain |
| Integration approach | Repo-type decision table (CLI/MCP/hooks/CI/watch) | Actionable routing, not a menu |
| Onboarding workflow | Analyze→Plan→Build→Wire→Verify w/ artifact-per-step + Verify gate | Auditable, rework-cheap, repeatable, ends proven |
| Plan output | Fill-in template file per repo | Same shape fleet-wide; diffable, commitable |
