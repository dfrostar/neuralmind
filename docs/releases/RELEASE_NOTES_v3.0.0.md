# Release Notes — v3.0.0 (August 2026)

**Tag:** v3.0.0 | **Published:** 2026-08-03

---

## TL;DR

NeuralMind v3.0.0 is a **license carve-out release**: the core engine stays MIT,
while `neuralmind/tier2/` (governance, seats, hash-chained audit, self-hosted
control plane) and `neuralmind/agent_os/` move to the source-available
**NeuralMind Commercial Modules License**. Releases up to and including v2.0.1
remain MIT in their entirety. This release also ships the full Agent OS stack,
Team license management, a clickwrap EULA, and cross-language type inference.

---

## ⚠ BREAKING CHANGES

| What | Impact |
|------|--------|
| `neuralmind/tier2/` and `neuralmind/agent_os/` now licensed under the NeuralMind Commercial Modules License (source-available) | If you use tier2 or Agent OS modules, you are now bound by the Commercial Modules License. The core engine remains MIT. |
| Releases up to and including v2.0.1 remain MIT in their entirety | No impact on existing MIT users — only new code (tier2 + Agent OS) is affected. |

---

## What's New

### License Carve-Out

The biggest structural change since v1.0. The core engine (`neuralmind/core`,
`neuralmind/synapses`, `neuralmind/context_selector`, `neuralmind/embedder`,
`neuralmind/mcp_server`) stays MIT. Two modules move to the source-available
Commercial Modules License:

- **`neuralmind/tier2/`** — governance, RBAC seats, hash-chained audit trail,
  self-hosted control plane
- **`neuralmind/agent_os/`** — multi-tenant operations engine (signals,
  experiments, correlator, promotion engine)

`pyproject.toml` license = `"MIT AND LicenseRef-NeuralMind-Commercial"`. The
boundary is live as of v3.0.0 — not proposed.

### Agent OS Stack (new package, additive)

Multi-tenant operations engine for running NeuralMind as a self-improving
product:

- CLI surface for multi-tenant operations
- Daemon wiring, correlator, promotion engine (v1.15.0)
- Dashboard sections for tenants, signals, experiments
- Multi-tenancy, RBAC, signal detection, experiments (v1.14.0)
- PostgreSQL migration schema and CLI
- Welch's t-test p-value on historical deltas

### Team License Management

- Clickwrap EULA on onboarding flow
- License issuance, revocation, renewal, and partner management
- CLI integration, license agreement, and tests
- DeepSeek V4 Pro + Flash QA fixes

### MCP: `neuralmind_ingest_document` RBAC + Security Page Link

- Ingest documents directly via MCP — previously CLI-only
- RBAC enforcement on document ingestion
- Security page link added for transparency

### Savings Report from MCP Server and Daemon

- Serve the savings report from the MCP server and daemon
- Accessible programmatically from any agent

### Cross-Language Type Inference (Type Verifier)

- Static type verification layer with cold-start synapse hardening
- Cross-language type inference: TypeScript, Go, Rust
- Thread-pool, AST cache, any severity, func index, persist batch

---

## What the Agent Actually Sees

Post-install, agents using NeuralMind via MCP or hooks:

1. **New tools**: `neuralmind_ingest_document` RBAC enforcement
2. **Agent OS tools**: multi-tenant operations (if licensed)
3. **Savings report**: accessible via MCP server/daemon
4. **Type verifier**: cross-language type inference available
5. **No change** to existing `wakeup()`, `query()`, `search()` — docs still surface as before

## Per-Agent Expectations

| Agent | Type Verifier | Agent OS | License Carve-Out | Notes |
|-------|---------------|----------|-------------------|-------|
| **Claude Code** | ✅ via hooks | ✅ via hooks | ✅ enforced | Auto-trigger on SessionStart |
| **Cursor** | ✅ via MCP | ✅ via MCP | ✅ enforced | Configure in `.cursorrules` |
| **Cline** | ✅ via MCP | ✅ via MCP | ✅ enforced | MCP-native workflow |
| **Generic MCP** | ✅ via MCP | ✅ via MCP | ✅ enforced | No CLI needed |

## Behaviour Controls

| Env Var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_LICENSE_MODE` | `auto` | `auto` enforces license boundary; `ignore` bypasses (testing only) |

## Verification

```bash
# 1. Build
python3 -m neuralmind build .

# 2. Verify license files
cat LICENSE # MIT
cat tier2/LICENSE # NeuralMind Commercial Modules License
cat agent_os/LICENSE # NeuralMind Commercial Modules License

# 3. Verify pyproject.toml
grep license pyproject.toml # "MIT AND LicenseRef-NeuralMind-Commercial"

# 4. Verify type verifier
python3 -m neuralmind type-check .

# 5. Verify agent-os
python3 -m neuralmind agent-os --help
```

## Behaviour Changes

| Change | Impact |
|--------|--------|
| `tier2/` and `agent_os/` licensed under Commercial Modules License | Source-available; free 1-seat use granted; OEM terms require executed agreement |
| `neuralmind_ingest_document` RBAC enforcement | Documents ingested via MCP now respect role-based access control |
| Savings report served from MCP/daemon | Programmatic access to savings data from any agent |

## Migration

```bash
pip install --upgrade neuralmind
```

Existing indexes, hooks, and synapses.db work unchanged. If you use tier2 or
Agent OS modules, review the Commercial Modules License. The core engine
remains MIT — no action required for core-only users.

## Tests

```bash
# Tier2 tests
pytest tests/test_tier2.py -q

# Agent OS tests
pytest tests/test_agent_os.py -q

# Type verifier tests
pytest tests/test_type_verifier.py -q

# Full suite: slow graph-building tests excluded (>40min hang)
```

## What's Next

- **v3.0.1** — SBOM republish, benchmark chart refresh
- **v3.0.2** — Agent OS extraction to private repo, dashboard rebrand
- **v3.1.0** — Synapse layer activation (reinforce on every query, explicit feedback CLI)
- **v3.2.0** — Scheduled decay, status dashboard, diagnostic "Is it learning?" page

## Thanks

The license carve-out was the most-requested structural change since v1.0.
This release ships it — the core engine stays MIT; tier2 and Agent OS move to
source-available. Honest boundaries, not vaporware.
