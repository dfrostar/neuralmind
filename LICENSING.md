# Licensing

NeuralMind is **open-core**. One repository, two licenses, one clear line:

| Tree | License | What it is |
|------|---------|------------|
| Everything except the two directories below | [MIT](LICENSE) | The core engine: code graph, synapse learning, retrieval, MCP server, hooks, CLI, compliance annotation engine, VS Code extension. **All token savings live here and are free, forever.** |
| `neuralmind/tier2/` | [Commercial Modules License](neuralmind/tier2/LICENSE) (source-available) | Team-tier governance: seats, hash-chained audit, self-hosted control plane, license machinery. |
| `neuralmind/agent_os/` | [Commercial Modules License](neuralmind/agent_os/LICENSE) (source-available) | Enterprise orchestration: multi-tenant registry, per-tenant RBAC, anomaly signals, experiment governance. |

**What this means in practice**

- The free tier is unaffected: a 1-seat license auto-issues on first run
  (no signup, never expires) and the commercial modules' grant explicitly
  covers that use.
- The source stays in the repo and stays auditable — source-available,
  not closed.
- Team/production use of the commercial modules requires an executed
  agreement (template: [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md);
  canonical terms: [commercial-terms.json](commercial-terms.json)).
- Redistribution, managed-service hosting, and OEM embedding of the
  commercial modules require an agreement.
- **Forward-only:** every release up to and including v2.0.1 was
  published entirely under MIT and remains MIT permanently. The boundary
  takes effect with v3.0.0.

MIT code may import the commercial modules (e.g. the CLI lazily loads
tier2 for `neuralmind team …`); running them under the free-tier grant is
expressly permitted, so nothing about this split breaks a free user.
