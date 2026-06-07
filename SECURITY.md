# Security Policy

## Executive Summary for Enterprise

NeuralMind is designed with **enterprise security as a first-class concern**:

- **No external API calls** – all processing happens locally on your machines
- **No data exfiltration** – your code never leaves your development environment
- **Fully auditable** – open-source code, MIT license, complete transparency
- **Zero telemetry** – no usage tracking, no analytics, no hidden data collection
- **Compliance-ready** – works with GDPR, HIPAA, and other regulatory frameworks
- **Supply-chain safe** – minimal dependencies, all vendorable, no cloud lock-in

---

## Supported Versions

Security fixes target the latest released minor version. Older 0.x
minors are unsupported once a newer minor ships — the practical
guidance is "stay on latest." Because NeuralMind is local-first with
no exfiltration surface, the patch urgency for older versions is
typically low.

| Version | Status              | Notes                                        |
| ------- | ------------------- | -------------------------------------------- |
| 0.11.x  | :white_check_mark:  | Current release; fixes land here.            |
| 0.10.x  | :warning:           | Critical fixes only.                         |
| ≤ 0.9.x | :x:                 | Unsupported — `pip install --upgrade neuralmind`. |

The supported window will widen when we tag v1.0.0.

## Reporting a Vulnerability

We take the security of NeuralMind seriously. If you have discovered a security vulnerability, please report it responsibly.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of these methods:

1. **GitHub Security Advisories** (Preferred)
   - Go to the [Security tab](https://github.com/dfrostar/neuralmind/security)
   - Click "Report a vulnerability"
   - Fill in the details

2. **Email**
   - `darren.frost@gmail.com` with `[SECURITY] neuralmind:` in the subject
   - PGP not currently offered; if you need it, GitHub Security Advisories
     is the encrypted path.

### What to Include

Please include the following information:

- Type of vulnerability (e.g., injection, authentication bypass, information disclosure)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability
- Suggested fix (if any)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Confirmation**: Within 1 week
- **Fix Timeline**: Depends on severity (see below)

### Severity Levels

| Severity | Description | Target Fix Time |
|----------|-------------|----------------|
| Critical | Remote code execution, data breach | 24-48 hours |
| High | Significant security impact | 1 week |
| Medium | Limited security impact | 2-4 weeks |
| Low | Minimal security impact | Next release |

## Security Considerations

### Data Handling

NeuralMind processes code from your projects. Here's what you should know:

1. **Local Processing.** All embeddings are generated and stored locally using ChromaDB. The Hebbian synapse layer (v0.4+) and the directional transitions table (v0.11+) are SQLite-backed and also local.
2. **No External Transmission.** Code is not sent to external servers (unless you point ChromaDB at a remote backend yourself).
3. **Storage Locations.**
   - Vector index: `<project>/graphify-out/neuralmind_db/`
   - Synapse store + transitions: `<project>/.neuralmind/synapses.db`
   - Auto-memory file consumed by Claude Code: `<project>/.neuralmind/SYNAPSE_MEMORY.md`
   - PostToolUse Bash recovery cache (v0.10+): `<project>/.neuralmind/last_output.json` (single-slot, 2 MB cap, atomic writes)
   - Event log for the graph-view stream (v0.6+): `<project>/.neuralmind/events.jsonl`
4. **What gets persisted.** Edge weights, transition counts, and the most recent Bash command's stdout/stderr (the latter capped). Source code itself is not duplicated into these files — only references (node ids, file paths).

### Best Practices for Enterprise Deployments

**For individuals:**
1. Ensure both index and synapse-state directories have appropriate permissions:
   ```bash
   chmod 700 graphify-out/neuralmind_db/      # ChromaDB vector index
   chmod 700 .neuralmind/                      # synapse store + memory + caches
   ```

2. Both directories are already in the bundled `.gitignore`, but confirm if you forked or copied this project's `.gitignore` selectively:
   ```
   graphify-out/neuralmind_db/
   .neuralmind/
   ```

**For enterprise/shared environments:**

1. **Centralized Index Storage**
   - Build the index on a secure, controlled machine
   - Store in a centralized location (shared filesystem, artifact repo)
   - Limit access to developers who need it (ACLs, RBAC)
   - Version-lock indexes to git commits for reproducibility

2. **Secrets Management**
   - NeuralMind never transmits code externally, but be cautious when processing repositories containing:
     - API keys or secrets (use `.gitignore` or secret scanning first)
     - Credentials
     - Proprietary algorithms
     - Personal data (PII)
   - Recommendation: Strip or mask secrets before indexing if at all possible

3. **Compliance & Audit Trails**
   - Log which teams/users access the index
   - Track changes to the knowledge graph with git commit history
   - Document your data retention policy (indexes can be regenerated)
   - Provide evidence of local-only processing to auditors

4. **On-Premise / Air-Gapped Deployments**
   - NeuralMind works without any internet access
   - Pre-build the index offline, then copy to disconnected environments
   - Perfectly suited for SCIF (Sensitive Compartmented Information Facility) or other classified environments

### Known Security Considerations

1. **ChromaDB.** We rely on ChromaDB for vector storage. Monitor their security advisories.

   - **CVE-2026-45829 / GHSA-f4j7-r4q5-qw2c (chromadb ≥ 1.0.0, CRITICAL) —
     not exploitable in NeuralMind.**
     This is a pre-authentication remote code-execution flaw in ChromaDB's
     *client/server* HTTP API (`/api/v2/.../collections`), triggered by a
     malicious model repository when `trust_remote_code=true`. NeuralMind
     embeds ChromaDB via `chromadb.PersistentClient` (local, on-disk) — it
     never starts the ChromaDB server, never exposes that endpoint, and never
     sets `trust_remote_code`. The vulnerable code path is therefore
     unreachable in NeuralMind's usage, so the recommended disposition for the
     corresponding Dependabot alert is to **dismiss it as "vulnerable code is
     not used."**
     - **No patched release exists yet.** Per the advisory, *every* published
       version is affected (`introduced: 1.0.0`, `last_affected: 1.5.9` — the
       current latest), so a version bump cannot resolve it. The pin will be
       bumped the moment ChromaDB ships a fixed release.
     - Severity: CRITICAL, `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H` (CWE-94).
     - References: [NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-45829) ·
       [GHSA-f4j7-r4q5-qw2c](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) ·
       [upstream issue](https://github.com/chroma-core/chroma/issues/6717).

2. **MCP Server.** If using the MCP server (`neuralmind.mcp_server`), be aware:
   - It runs locally over stdio by default — no network port is opened.
   - RBAC is enabled by default with three roles: `admin` (all tools), `builder` (retrieval tools — `wakeup`, `query`, `search`, `build`, `stats`, `benchmark`, `skeleton`), `reader` (read-only retrieval). The synapse-family tools (`synaptic_neighbors`, `synapse_stats`, `synapse_decay`, `next_likely`, `export_synapse_memory`) are **admin-only by default**.
   - If you customize the role policy in `neuralmind/mcp_security.py`, audit it the same way you would any access-control change.
   - Audit events are written to `<project>/.neuralmind/audit.jsonl` on every tool call.

3. **Claude Code hooks (PostToolUse, UserPromptSubmit, SessionStart, PreCompact).** Hooks execute the `neuralmind` CLI locally with the agent's environment.
   - Hooks are installed by explicit user action (`neuralmind install-hooks`) — never silently.
   - The Bash compression hook reads stdout/stderr and writes a single-slot recovery cache locally. It does not exfiltrate; it does not modify the agent's command.
   - `NEURALMIND_BYPASS=1` disables compression for a single command; `NEURALMIND_OUTPUT_CACHE=0` disables the cache entirely.
   - The synapse memory export (v0.4+) writes the per-project `SYNAPSE_MEMORY.md` and, when present, mirrors it into Claude Code's auto-memory directory at `~/.claude/projects/<slug>/memory/`. Disable via `NEURALMIND_SYNAPSE_EXPORT=0`.

4. **File watcher (`neuralmind watch`).** Watches the project tree and records file co-edits as synapse activations.
   - Honors `.gitignore`-style ignore patterns (`.git`, `.neuralmind`, `__pycache__`, `node_modules`, build dirs).
   - Records file *paths* and *order*, not file contents.
   - When run as a service via systemd/launchd templates ([always-on guide](docs/use-cases/always-on.md)), it runs under your user account with the user-level scope you grant.

5. **Graph view server (`neuralmind serve`).** Binds to `127.0.0.1` by default. If you expose it on a network interface, add a reverse proxy with auth in front. The `/healthz` endpoint is intentionally unauthenticated for Docker `HEALTHCHECK` and systemd `ExecStartPost` probes.

6. **Directional transitions (v0.11+).** The `synapse_transitions` table records `(from_node, to_node)` pairs derived from the watcher's edit order. The data shape is the same as the existing undirected synapses; the same local-only / no-exfiltration guarantees apply.

7. **Dependencies.** Keep them updated:
   ```bash
   pip install --upgrade neuralmind
   ```
   CycloneDX SBOM is attached to every release ([air-gapped install walkthrough](docs/use-cases/air-gapped.md)).

---

## Compliance Framework Alignment

NeuralMind is **designed to support** standard enterprise compliance requirements. Because it runs entirely locally and makes no external calls, it can fit into existing compliance workflows:

*Note: NeuralMind itself is not "certified" for any framework, but the tool's architecture aligns with the security requirements of these standards.*

### ✅ GDPR (General Data Protection Regulation)
- **Data Residency**: All code remains in your jurisdiction (on your machine/infrastructure)
- **No External Processing**: No third-party APIs, no cloud services
- **Data Deletion**: Delete `graphify-out/neuralmind_db/` to fully remove the index
- **Transparency**: Open-source code for full audit trail

### ✅ HIPAA (Health Insurance Portability and Accountability Act)
- **Encryption at Rest**: Store index on encrypted filesystems (you control encryption)
- **Access Controls**: Use OS-level permissions to restrict index access
- **Audit Logging**: All processing happens locally with no external calls
- **Business Associate Agreements**: No BAA needed (no external vendors processing your data)

### ✅ SOC 2 Type II
- **Security**: Local processing, no exfiltration, encrypted at rest (your choice)
- **Availability**: No dependencies on external services for core functionality
- **Confidentiality**: No data leaves your organization
- **Integrity**: Deterministic, reproducible indexing from your source code
- **Privacy**: No collection, no analytics, no tracking

### ✅ ISO 27001 / 27002
- **Information Security Management**: Runs entirely within your security perimeter
- **Access Controls**: Fine-grained OS-level permissions on index files
- **Encryption**: Compatible with whatever encryption strategy you use
- **Supplier Management**: Open-source, no hidden dependencies or data sharing agreements

### ✅ PCI DSS (Payment Card Industry Data Security Standard)
- **Local Processing**: Never transmits code to external networks
- **Network Segmentation**: Can run on completely isolated networks
- **Audit Capability**: Fully transparent, no black-box components
- **Change Management**: Source code control, open-source, version-locked

### ✅ FedRAMP / Government Compliance
- **Air-Gap Ready**: Works completely offline
- **On-Premise**: No cloud dependencies
- **Classified Environments**: Suitable for SCIF and other compartmented processing
- **Supply Chain Security**: Minimal dependencies, vendorable, no external calls

## Disclosure Policy

When we receive a security report:

1. We will confirm receipt within 48 hours
2. We will investigate and validate the issue
3. We will work on a fix
4. We will release a patch
5. We will credit the reporter (unless they prefer anonymity)

## Security Updates

Security updates are announced through:

- [GitHub Security Advisories](https://github.com/dfrostar/neuralmind/security/advisories)
- [Release Notes](https://github.com/dfrostar/neuralmind/releases)

## Auditability & Explainability

One of the biggest enterprise concerns with AI tools is the "black box" problem — models make decisions without clear justification, leading to hallucinations and liability.

### How NeuralMind Solves This

NeuralMind is **transparent by design**:

#### Full Query Provenance

When NeuralMind answers a question, it provides complete metadata about the context:

- **Which layers were used** – L0 (identity), L1 (summary), L2 (on-demand modules), L3 (semantic search)
- **Which code communities were loaded** – Specific clusters of related code
- **Search quality metrics** – Number of semantic hits, relevance scores
- **Token budget breakdown** – Exactly how many tokens came from each layer
- **Reduction ratio** – How much you saved vs. loading the full codebase

You can always:
- **Reproduce any result** – Same query + same codebase = same context (deterministic)
- **Audit the decision path** – See exactly which code entities and clusters were selected
- **Verify completeness** – Check if all relevant code was captured
- **Understand the tradeoffs** – View the token budget breakdown by layer

#### Transparency by Design

All processing is local and observable:
- No hidden cloud processing or external model calls
- No black-box ranking algorithms (semantic search is transparent)
- Can read the source code selection in full
- Every decision is reproducible and explainable

This is critical for regulated industries (healthcare, finance, legal, government) where AI recommendations must be auditable and verifiable.

---

## Acknowledgments

We thank all security researchers who help keep NeuralMind and its users safe.

---

_This security policy is subject to change. Last updated: 2026-05-28 (v0.11.0 — covers PostToolUse hooks, MCP RBAC defaults, directional transitions, recovery cache, watcher trust model)._
