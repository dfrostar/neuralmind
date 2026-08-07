# Licensing

NeuralMind is **open-core**. One repository, two licenses, one clear line:

| Tree | License | What it is |
|------|---------|------------|
| Everything except the directory below | [MIT](LICENSE) | The core engine: code graph, synapse learning, retrieval, MCP server, hooks, CLI, compliance annotation engine, VS Code extension. **All token savings live here and are free, forever.** |
| `neuralmind/tier2/` | [Commercial Modules License](neuralmind/tier2/LICENSE) (source-available) | Team-tier modules: seats, hash-chained audit, self-hosted control plane, license machinery. Every feature runs under the free 1-seat license; a paid Team license buys seats beyond one (5-50) plus support. |

**What this means in practice**

- The free tier is unaffected and perpetual: a 1-seat license auto-issues
  on first run (no signup, never expires) and the commercial modules'
  grant explicitly covers that use, including production use by its one
  named user.
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

**Direction of licensing**

- Code from the MIT core may import and depend on the Commercial Modules,
  but any such import merely *uses* the Commercial Modules under their
  license and does not alter the license of the MIT core.
- Nothing in the MIT license grants the right to copy, relicense, or
  incorporate Commercial Modules code into the MIT core, and no
  Contributor may submit Commercial Modules code or derivatives thereof
  into the MIT core under the MIT license.
- The MIT core remains independently operable and distributable without
  the presence or import of the Commercial Modules.
- Cheval-Volant LLC retains sole authority to determine the license terms
  of all contributions to the MIT core (MIT/permissive only). No copyleft
  code may be contributed in a manner that would "infect" the commercial
  modules.
