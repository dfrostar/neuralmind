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

| Version  | Status              | Notes                                        |
| -------- | ------------------- | -------------------------------------------- |
| 0.41.x   | :white_check_mark:  | Current release; fixes land here.            |
| 0.40.x   | :warning:           | Critical fixes only.                         |
| ≤ 0.39.x | :x:                 | Unsupported — `pip install --upgrade neuralmind`. |

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

1. **Local Processing.** All embeddings are generated and stored locally. Since v0.29 the default backend is **ChromaDB-free** — embeddings come from a bundled `all-MiniLM-L6-v2` **ONNX** model run on `onnxruntime` (CPU), and vectors are stored in the on-disk `turbovec` index. There is **no cloud embedding API call** on any backend. The Hebbian synapse layer (v0.4+) and the directional transitions table (v0.11+) are SQLite-backed and also local.
2. **No External Transmission.** Code is not sent to external servers. The only outbound network event in the default install is a **one-time, SHA256-pinned** download of the ONNX model archive into `~/.cache/neuralmind/onnx_models/` (a static S3 artifact, not an API; a corrupted/swapped download fails loudly). Pre-stage it via `NEURALMIND_ONNX_MODEL_DIR` for air-gapped installs and there is **no network at install, build, query, or runtime**.
3. **Storage Locations** (all under the project, never committed unless noted):
   - Vector index (turbovec default, or ChromaDB if selected): `<project>/graphify-out/neuralmind_db/`
   - Input graph: `<project>/graphify-out/graph.json`; canonical IR (v0.23+): `<project>/.neuralmind/ir.json` (+ `ir.meta.json`)
   - Synapse store + directional transitions + namespaces: `<project>/.neuralmind/synapses.db`
   - BM25 keyword index (v0.38+): `<project>/.neuralmind/bm25_index.json`
   - Auto-memory file consumed by Claude Code: `<project>/.neuralmind/SYNAPSE_MEMORY.md`
   - PostToolUse Bash recovery cache (v0.10+): `<project>/.neuralmind/last_output.json` (single-slot, 2 MB cap, atomic writes)
   - Event log for the graph-view stream (v0.6+): `<project>/.neuralmind/events.jsonl`
   - MCP audit trail (v0.41): `<project>/.neuralmind/audit_events.jsonl`
   - **Committed** team-memory bundle (v0.30+, opt-in): `<project>/.neuralmind-team-memory.json` — travels with `git clone` (learned weights only, no source)
4. **What gets persisted.** Edge weights, transition counts, BM25 token postings, the most recent Bash command's stdout/stderr (capped), and MCP audit events. Source code itself is **not** duplicated into these files — only references (node ids, file paths). The committed team-memory bundle holds learned associations, not code.

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

1. **ChromaDB (opt-in fallback since v0.29).** ChromaDB is **no longer the default
   backend**. On mainstream platforms (Linux, Apple Silicon, Windows x64) the default
   is the ChromaDB-free `turbovec`/ONNX stack, so ChromaDB's dependency tree — and the
   advisory below — are **absent from the default install** entirely. ChromaDB is only
   pulled in as a transparent fallback on platforms turbovec has no wheel for (Intel
   macOS, Windows ARM) or when you explicitly select the `chroma` backend. If you do
   run ChromaDB, monitor their advisories.

   - **CVE-2026-45829 / GHSA-f4j7-r4q5-qw2c (chromadb ≥ 1.0.0, CRITICAL) —
     not in the default install, and not exploitable even when ChromaDB is used.**
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

2. **MCP Server.** If using the MCP server (`neuralmind.mcp_server`, **14 tools**), be aware:
   - It runs locally over stdio by default — no network port is opened.
   - RBAC is enabled by default (`neuralmind/mcp_security.py`) with three roles:
     - `admin` — all tools.
     - `builder` — `wakeup`, `query`, `search`, `build`, `stats`, `benchmark`, `skeleton`.
     - `reader` — the same retrieval set **minus `build`**.
     - Everything else is **admin-only by default**: the synapse family
       (`synaptic_neighbors`, `synapse_stats`, `synapse_decay`, `next_likely`,
       `export_synapse_memory`) plus the learning/feedback tools (`feedback`, `review`).
   - A per-actor **rate limiter** (`RateLimiter`, default 60 calls/min) is enforced
     alongside RBAC.
   - If you customize the role policy (backend config `security.roles` or
     `neuralmind/mcp_security.py`), audit it the same way you would any access-control change.
   - Audit events — actor, role, tool, RBAC decision, rate-limit hits — are written to
     `<project>/.neuralmind/audit_events.jsonl` on every tool call.

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

7. **Team memory bundle (v0.30+).** `neuralmind memory publish` writes a **committed** `<project>/.neuralmind-team-memory.json` that teammates inherit on their next session/build. Threat model: import is **MAX-merge only** (it can never *weaken* a teammate's existing weights), is written **only** to the `shared` namespace (never `personal`/`branch`), is content-hash-gated (imported once), and is subject to normal decay — so a malicious or over-eager bundle cannot permanently distort recall. It carries learned associations, **not source code**. Disable inheritance with `NEURALMIND_TEAM_MEMORY=0` (fail-open). Namespaces (v0.24+) keep `branch:`/`personal`/`shared`/`ephemeral` memory partitioned so a branch spike can't pollute `main`.

8. **Schema/artifact indexing (v0.40+).** OpenAPI/AsyncAPI (`.yaml`/`.yml`), SQL DDL (`.sql`), and Protocol Buffers (`.proto`) are indexed as `document` nodes alongside code. These can surface API/DB schemas in query results — apply the same secret-scanning hygiene you would for code (strip credentials from spec files before indexing). Plain YAML config without an `openapi`/`asyncapi`/`swagger` key is silently skipped.

9. **Reuse-feedback hook (v0.38+).** Edit/Write PostToolUse matchers detect when freshly-written code reaches for symbols already in the graph and feed that **reuse** signal into the synapse layer. Data flow is local only: file path + extracted symbol tokens → a synapse weight update; no diff or file content is stored. Disable with `NEURALMIND_REUSE_FEEDBACK=0`. The opt-in selector autotuner (`NEURALMIND_SELECTOR_AUTOTUNE=1`, v0.26+) likewise reads only local query-success signals to adjust L2 recall depth.

10. **Dependencies.** Keep them updated:
    ```bash
    pip install --upgrade neuralmind
    ```
    A **CycloneDX JSON** SBOM (`neuralmind-vX.Y.Z.sbom.json`, generated by Anchore `syft` over the full transitive tree) is attached to every release — see `.github/workflows/sbom.yml` and the [air-gapped install walkthrough](docs/use-cases/air-gapped.md).

### Privacy & behaviour controls (environment variables)

Every persistence/learning surface has an off-switch. For a locked-down or
air-gapped deployment, these are the knobs a security reviewer cares about
(defaults reflect a normal install; all are read from the process environment):

| Variable | Effect | Default |
|---|---|---|
| `NEURALMIND_MEMORY=0` | Disable local query-event logging | on |
| `NEURALMIND_LEARNING=0` | Disable Hebbian synapse learning from interactions | on |
| `NEURALMIND_SYNAPSE_INJECT=0` | Don't inject spreading-activation recall at prompt time | on |
| `NEURALMIND_SYNAPSE_EXPORT=0` | Don't write `SYNAPSE_MEMORY.md` / Claude Code auto-memory | on |
| `NEURALMIND_TEAM_MEMORY=0` | Don't import the committed team-memory bundle | on |
| `NEURALMIND_REUSE_FEEDBACK=0` | Disable the Edit/Write reuse-feedback signal | on |
| `NEURALMIND_OUTPUT_CACHE=0` | Disable the Bash recovery cache (`last_output.json`) | on |
| `NEURALMIND_EVENT_LOG=0` | Disable the `events.jsonl` graph-view bridge | on |
| `NEURALMIND_BYPASS=1` | Skip output compression for a single command | off |
| `NEURALMIND_SELECTOR_AUTOTUNE=1` | Opt **in** to selector auto-tuning (local query signals only) | off |
| `NEURALMIND_PRECISION=1` | Opt **in** to SCIP compiler-accurate call edges | off |
| `NEURALMIND_BM25=0` | Disable BM25 hybrid keyword search | on |
| `NEURALMIND_NAMESPACE=<name>` | Override the memory namespace (else resolved from git branch) | branch-resolved |
| `NEURALMIND_ONNX_MODEL_DIR=<dir>` | Use a pre-staged ONNX model (air-gapped; skips the one-time download) | `~/.cache/neuralmind/onnx_models/` |
| `NEURALMIND_NO_DAEMON=1` | Force direct mode (no warm-state daemon) | off |

Compression-tuning knobs (`NEURALMIND_BASH_TAIL`, `NEURALMIND_BASH_MAX_CHARS`,
`NEURALMIND_BASH_SMALL`, `NEURALMIND_SEARCH_MAX`, `NEURALMIND_OFFLOAD_THRESHOLD`,
`NEURALMIND_OUTPUT_CACHE_MAX`) change *how much* output is kept locally, not
*whether* anything leaves the machine — nothing does.

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

_This security policy is subject to change. Last updated: 2026-06-30 (v0.41.0 — ChromaDB-free ONNX default + no-cloud embedding story, the 14-tool MCP surface with builder/reader RBAC + per-actor rate limiting + `audit_events.jsonl`, the team-memory bundle threat model, schema-artifact indexing, the reuse-feedback hook, memory namespaces, and the full privacy/behaviour env-var table)._
