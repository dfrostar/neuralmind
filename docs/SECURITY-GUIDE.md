# Security Hardening Guide

**Comprehensive security practices for deploying NeuralMind in enterprise environments.**

---

## Table of Contents

- [Security Model](#security-model)
- [Access Control](#access-control)
- [Data Protection](#data-protection)
- [Secret Management](#secret-management)
- [Audit & Compliance](#audit--compliance)
- [Threat Model](#threat-model)
- [Security Checklist](#security-checklist)

---

## Security Model

### Core Principles

1. **No Calls Home by Default** — NeuralMind makes no external network calls in its default configuration; it adds nothing to what your agent sends its model. One narrow, opt-in exception exists — see below.
2. **Local-First Processing** — All embeddings computed locally
3. **Explainability** — Every decision is auditable
4. **Least Privilege** — Users get minimum permissions needed
5. **Defense in Depth** — Multiple layers of protection

### What NeuralMind Does NOT Do

❌ Ingest video, image, or audio files — no code path accepts media of any kind
❌ Send source code to external APIs
❌ Collect telemetry or usage metrics
❌ Store credentials in indexes
❌ Cache queries in cloud storage
❌ Share data between customers/projects

**The one opt-in exception:** setting both `NEURALMIND_LLM_SEED=1` and
`ANTHROPIC_API_KEY` enables a documentation-synapse-seeding call that sends
only the text of `README.md`/`docs/architecture.md` to Anthropic's API —
never source code, never client data files, never media. Default is off;
the call fails open (never blocks indexing). Full disclosure, verification
steps, and how to keep it disabled:
[`compliance/THIRD_PARTY_LLM_DISCLOSURE.md`](compliance/THIRD_PARTY_LLM_DISCLOSURE.md).

---

## Access Control

NeuralMind does not authenticate anyone. Access to it is access to the OS
account and project directory it runs in, plus whatever can reach its MCP
server.

### Who can call the MCP server

- **Stdio (default).** The agent that launches `neuralmind-mcp` is the only
  caller. No network port is opened.
- **Streamable HTTP** (`NEURALMIND_MCP_TRANSPORT=streamable_http`) is an
  unfinished skeleton. It binds to `127.0.0.1:8765` and has no OAuth or other
  authentication, so don't expose it beyond the host.
- **Graph view** (`neuralmind serve`) binds to `127.0.0.1` by default and
  requires a per-session token. `--host` changes the bind address and keeps
  the token. Only `--no-auth` removes it.

### The role policy

Every MCP tool call goes through `MCPSecurityManager.secure_call`
(`neuralmind/mcp_security.py`). It checks the call's role against a per-tool
permission policy and a per-actor rate limit, then writes the decision to the
audit log.

The caller declares its own `actor` and `role` in the tool arguments. The role
defaults to `builder`, and any caller can declare `admin`. Treat the policy as
a guard rail for a well-behaved agent, not a boundary against a hostile caller.

Default roles (`DEFAULT_ROLE_POLICY`):

| Role | Tools |
|---|---|
| `admin` | All tools |
| `builder` | The `reader` set, plus `build`, document ingestion, and recording or invalidating decisions |
| `reader` | Retrieval (`wakeup`, `query`, `search`, `skeleton`) and read-only analytics, stats, and decision queries |

A few tools are admin-only by default, including `synaptic_neighbors`,
`structural_neighbors`, `next_likely`, `impact`, and `review`.

### Capping what a caller can claim

`security.roles` in `neuralmind-backend.yaml` replaces the default policy. A
role it doesn't list gets no tools, so leaving `admin` out keeps every caller
away from tools no listed role grants, however it declares itself:

```yaml
# neuralmind-backend.yaml, in the project root
security:
  roles:
    builder: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton, neuralmind_build]
    reader: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton]
  rate_limit:
    max_calls: 60
    window_seconds: 60
```

The rate limit keys on the declared actor, so it stops a runaway agent, not a
caller that changes its actor name.

### Per-user roles

NeuralMind has no user directory, LDAP, or OAuth integration, and SSO/SAML is
roadmap-only. If different people need different permissions, give each their
own OS account and checkout with its own `neuralmind-backend.yaml`; OS file
permissions then decide who can read the index.

---

## Data Protection

NeuralMind doesn't encrypt anything. Its state is plain files in the
project's `.neuralmind/` directory: the vector index (which holds indexed
source text), the code graph, learned synapses, the audit log (which records
query text), and the Bash output cache. There is no database server, so there
is nothing to encrypt separately from the filesystem.

### At rest

- **Restrict permissions.** `.neuralmind/` is created with your umask,
  usually readable by other accounts on the host:

  ```bash
  chmod -R go-rwx /path/to/project/.neuralmind
  ```

- **Use full-disk encryption on the host**: FileVault on macOS, LUKS on
  Linux, BitLocker on Windows. NeuralMind has no encryption setting of its
  own.

See [File permissions](DEPLOYMENT-GUIDE.md#file-permissions) in the
deployment guide.

### In transit

- **MCP over stdio** (the default) has no network hop.
- **The graph view and the daemon** are plain HTTP on `127.0.0.1` and require
  a token. NeuralMind serves no TLS and has no certificate options. To reach
  the graph view from another machine, use an SSH tunnel:

  ```bash
  ssh -N -L 8787:127.0.0.1:8787 user@host
  # then open http://127.0.0.1:8787/?token=… on your machine
  ```

  If you have to expose it, terminate TLS in a reverse proxy you operate and
  leave the token on.
- **Streamable HTTP MCP** (`NEURALMIND_MCP_TRANSPORT=streamable_http`) is an
  unfinished skeleton. It binds to `127.0.0.1:8765` with no authentication and
  no TLS, so don't expose it.
- **Outbound**, NeuralMind makes one request by default, the SHA-256-checked
  embedding-model download on a cold first build, plus opt-in documentation
  seeding. See [Outbound network](DEPLOYMENT-GUIDE.md#outbound-network).

---

## Secret Management

### Detecting Secrets in Code

Scanning is a **separate, explicit step** — `neuralmind build` does not
scan or redact by default. Run the scanner before you index, so that
credentials get removed and rotated at the source rather than scrubbed
downstream:

```bash
# Scan for exposed credentials
neuralmind scan-for-secrets .

# Output:
# NeuralMind secret scan — /home/dev/myproject
#
#   [HIGH ] .env:1  anthropic-api-key  (sk-a…(43 chars))
#   [HIGH ] src/config.py:8  aws-access-key-id  (AKIA…(20 chars))
#   [maybe] src/db.py:34  generic-secret-assignment  (9f8K…(28 chars))
#
#   2 high-confidence, 1 heuristic.
```

Two confidence tiers. `HIGH` means a vendor-specific shape (`sk-ant-`,
`AKIA`, a PEM block, a JWT, a connection-string password) — these
effectively never fire on prose. `maybe` means a generic
`SECRET=value` assignment that cleared an entropy threshold and a
placeholder denylist, so `password = "changeme"` is not reported.

Previews are truncated to a short prefix and never include the tail of
the secret, so scan output is safe to paste into an issue or a CI log.

**What the anchoring gives up.** Vendor patterns require a word boundary so
they do not fire inside a longer hex or base64 blob. Consequently two
credentials concatenated with no delimiter at all (`AKIA…EXAMPLEghp_…`)
match neither. Every realistic separator works — whitespace, newline, `=`,
`:`, `,`, quotes, brackets, URL parameters. Treat a clean scan as evidence,
not proof.

**Exit codes** (so CI can gate on it):

| Condition | Exit |
|-----------|------|
| No findings | `0` |
| Heuristic findings only | `0` (`1` with `--strict`) |
| Any high-confidence finding | `1` |
| Path does not exist | `2` |

Useful flags: `--json` for machine-readable output,
`--high-confidence-only` to suppress the heuristic tier, `--strict` to
fail on heuristic findings too.

The scanner does **not** apply `.neuralmindignore` by default. That file
tunes retrieval (it commonly excludes `docs/` and `tests/`), and inheriting
it would skip the places credentials actually sit. Pass
`--use-neuralmindignore` to opt in.

**Redaction at index time:**

```bash
# Scrub detected credentials from text before it enters the index
neuralmind build . --redact-secrets
```

Secrets are replaced with `[REDACTED:<kind>]` in **embedded text**
(document chunks and node descriptions), on all three backends.

It does **not** cover node labels, `graphify-out/graph.json`, or
`.neuralmind/index_ir.json` — those are written before the embedding step,
so a credential inside a symbol name or docstring still reaches them
verbatim. This is a **backstop, not a substitute** for removing the
credential: the value still exists in your working tree, and redacting the
index costs recall on any legitimately secret-shaped identifier. Fix the
source first.

`NEURALMIND_REDACT_SECRETS=1` is equivalent to the flag.

### What is scrubbed automatically

One thing *is* redacted with no flag: the PostToolUse Bash recovery
cache (`.neuralmind/last_output.json`). It stores whatever your commands
printed, so `printenv`, `aws configure list`, or a `curl -H
"Authorization: Bearer …"` would otherwise write a live credential to a
plaintext file. Credentials are stripped before the payload is written,
and the entry records which kinds were removed. Opt out with
`NEURALMIND_OUTPUT_REDACT=0` (not recommended).

`.neuralmind/` also carries its own `.gitignore` containing `*`, written
when the directory is created, so the state directory cannot be
committed by a `git add -A` even in a project whose own `.gitignore`
says nothing about it.

### Managing Secrets Properly

Indexing, querying, and the MCP server need no credentials: no database
password and no service account. Three opt-in paths read a secret from the
environment:

| Secret | Read by | What it's used for |
|---|---|---|
| `ANTHROPIC_API_KEY` | Documentation seeding, only with `NEURALMIND_LLM_SEED=1` | Sends `README.md` and `docs/architecture.md` text to Anthropic |
| `ANTHROPIC_API_KEY` | `neuralmind benchmark --public --judge`, from a source checkout | Sends context built from the pinned public benchmark repositories to Anthropic for grading. Your own code isn't part of it |
| `NEURALMIND_ISSUER_PRIVATE_KEY_HEX` | `neuralmind license issue`, `renew`, and `revoke` | Signs license files locally. Only the license issuer runs these; using a license doesn't need the key |

Provision and rotate these like any other credential, and set them only in the
environments that run those commands.

The advice below is for the code you index, so the scanner has nothing to
find.

**✅ Read credentials from the environment:**
```python
import os

DB_PASSWORD = os.getenv('DATABASE_PASSWORD')
API_KEY = os.getenv('API_KEY')

# Never hardcode!
```

**✅ Or from a secret manager:**
```python
import boto3

secrets_client = boto3.client('secretsmanager')

def get_db_password():
    response = secrets_client.get_secret_value(
        SecretId='myapp/database/password'
    )
    return response['SecretString']
```

**❌ Never commit secrets:**
```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo "*.key" >> .gitignore
echo "secrets.json" >> .gitignore

# Use git-secrets to prevent accidental commits
brew install git-secrets
git secrets --install
git secrets --register-aws
```

---

## Audit & Compliance

### Audit Trail

NeuralMind appends one JSON record per event to
`.neuralmind/audit_events.jsonl`:

- **Every MCP tool call**: `mcp_call` with status `success` or `failure`, or
  `mcp_call_denied` when the role policy or the rate limit refused it.
- **Every `build`, `wakeup`, `query`, and `search`**, including the query
  text, plus document ingestion and backend switches.

A query record, as `neuralmind query` wrote it:

```json
{
  "action": "query",
  "actor": "alice",
  "actor_role": "",
  "category": "audit",
  "details": {
    "hybrid_context": false,
    "learn": true,
    "question": "How does authentication work?",
    "search_hits": 4,
    "tokens": 388
  },
  "ip_address": "",
  "prev_sha256": "796b0584a16fcb3a09b377bec436b81601da2f8ad6b98f8eff7b11381d38820f",
  "sha256": "3f7905de591ecaa90f763fb1905b0686df2bbb3b40ddb1ea70d8034a6d2ece0b",
  "status": "success",
  "target": "myproject",
  "timestamp": "2026-10-04T17:55:41.424849+00:00"
}
```

And an MCP call the role policy refused (hashes and timestamp omitted):

```json
{
  "action": "mcp_call_denied",
  "actor": "claude-code",
  "actor_role": "",
  "category": "security",
  "details": {"reason": "rbac", "role": "reader"},
  "ip_address": "",
  "status": "denied",
  "target": "neuralmind_build"
}
```

What the fields do and don't tell you:

- **`actor`** is whatever name the MCP caller declares (default `anonymous`).
  For CLI commands it is `NEURALMIND_ACTOR` if set, otherwise the OS login.
  Nothing authenticates it.
- **The declared role** is in `details.role`. `actor_role` and `ip_address`
  are in the schema, but nothing fills them in, so they are always empty.
- **No record lists the files a query retrieved.** `search_hits` is a count.
- **`sha256`** chains each record to the previous one through `prev_sha256`.

Read, check, and export the log:

```bash
neuralmind audit recent . -n 50
neuralmind audit verify .      # walks the hash chain, exits 1 on a mismatch
neuralmind audit export . --format jsonl --since 2026-01-01 --until 2026-04-01 -o audit_Q1_2026.jsonl
neuralmind audit export . --format cef -o audit.cef    # for SIEM ingest
```

`--since` and `--until` compare ISO-8601 strings against UTC timestamps, so a
bare date means the start of that day. `--until 2026-04-01` takes in all of
March 31, and `--until 2026-03-31` would leave March 31 out.

`audit verify` catches an edited record or one deleted from the middle of the
log. It misses records removed from the end, and a chain recomputed by anyone
who can write the file, so ship `audit export` output off the host.
NeuralMind doesn't rotate or expire the log, and it has no report command:
build compliance reports from the export.

### NIST AI RMF Mapping

```
Evidence NeuralMind provides for each NIST AI RMF function:

GOVERN (Oversight)
├─ Per-tool permission policy (caller-declared roles)
├─ Audit log of MCP calls, builds, and queries
└─ Query provenance: each result names the code nodes it came from

MAP (Context)
├─ Which code a query retrieved, in the query result
└─ Similarity scores on search results

MEASURE (Performance)
├─ Context tokens per query, in the audit log
├─ Retrieval quality on your repo: recall@k, MRR (neuralmind probe)
└─ Token reduction on your repo (neuralmind benchmark)

MANAGE (Risk)
├─ Secret scanning before indexing (neuralmind scan-for-secrets)
├─ Per-actor rate limiting on MCP calls
└─ Refused calls (role policy, rate limit) in the audit log
```

NeuralMind has no anomaly detection or alerting. For that, feed
`neuralmind audit export` to your SIEM.

### SOC 2 Trust Services Criteria

NeuralMind has no SOC 2 report. A SOC 2 report covers a service
organization, and NeuralMind runs inside yours, so in your audit it is
software within your system boundary. These are the criteria it gives your
auditor evidence for:

```
CC6.1 / CC6.3 - Logical access, role-based permissions
   Evidence: stdio MCP transport by default; per-tool permission sets
   (admin / builder / reader). Each MCP call declares its own role and
   callers aren't authenticated, so binding identities to roles is yours

CC6.7 - Restricting transmission of information
   Evidence: by default, no telemetry and no repository content sent off
   the machine. Opt-in NEURALMIND_LLM_SEED=1 sends README.md and
   docs/architecture.md to Anthropic

CC7.1 - Detecting vulnerabilities
   Evidence: CycloneDX SBOM on every release, for your SCA scanner

CC7.2 - Monitoring for anomalies
   Evidence: hash-chained audit log, "neuralmind audit verify", /healthz

C1.2 - Disposing of confidential information
   Evidence: documented deletion procedure (docs/compliance/DATA_DELETION.md)
```

The full table, with what each criterion covers, is in
[COMPLIANCE-SUMMARY.md](COMPLIANCE-SUMMARY.md).

### CMMC 2.0

CMMC assesses a defense contractor's environment, not a tool. If NeuralMind
indexes source code that is CUI, the index is CUI too, and NeuralMind is an
asset inside your assessment scope:

```
AC.L2-3.1.1 / 3.1.2 - Authorized access, permitted functions
   Evidence: stdio MCP transport by default; per-tool permission sets
   Not provided: authentication. Each MCP call declares its own role, so
   binding authenticated identities to roles is yours

AU.L2-3.3.1 / 3.3.8 - Audit records, protection of audit information
   Evidence: append-only audit log with a SHA-256 hash chain. It shows a
   changed record mid-log, not truncation or a recomputed chain

SC.L2-3.13.11 / 3.13.16 - FIPS cryptography, CUI at rest
   Not provided: use FIPS-validated full-disk encryption on the host
```

The full Level 2 table, including what stays your responsibility, is in
[COMPLIANCE-SUMMARY.md](COMPLIANCE-SUMMARY.md).

---

## Threat Model

### Threats & Mitigations

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|-----------|
| **Unauthorized access to MCP** | Medium | High | Stdio transport by default (no network port); keep any HTTP transport on localhost. NeuralMind has no authentication of its own, and the server accepts any `project_path` its OS account can read, so confine that account |
| **Secrets exposed in code** | High | Critical | `neuralmind scan-for-secrets` before indexing. It is a separate step, not automatic. `build --redact-secrets` scrubs embedded text but not node labels or `graph.json`. The Bash output cache is redacted automatically |
| **Index data breach** | Low | High | None in NeuralMind itself: `.neuralmind/` isn't encrypted and is created with your umask, often world-readable. Restrict it with file permissions and use full-disk encryption. The audit log records calls made through NeuralMind, not direct reads of these files |
| **Query interception** | Low | Medium | Stdio MCP has no network hop. The graph view and daemon are plain HTTP on `127.0.0.1` with a token. NeuralMind serves no TLS, so reach them over an SSH tunnel or a TLS proxy you run |
| **Resource exhaustion (DoS)** | Medium | Medium | Per-actor rate limit on MCP calls (`security.rate_limit`, default 60 calls per 60 s). It is held in memory per server process and keyed on the declared actor, so a caller that changes its actor name gets a fresh limit. Denials go to the audit log. NeuralMind has no monitoring or alerting |
| **Insider threat** | Low | Critical | Hash-chained audit log of calls through NeuralMind. It detects an edited record, not tampering at the tail of the log or a chain recomputed by someone with write access, so ship `neuralmind audit export` off the host. Roles are caller-declared, so least privilege comes from OS accounts |
| **Configuration error** | Medium | High | The security checklist below. `neuralmind doctor` checks install health (graph, index, hooks, MCP, synapses), not security settings |

### Attack Scenarios

**Scenario 1: SQL injection through queries or tool arguments**
```
Attack: A crafted query or tool argument tries to inject SQL into
        NeuralMind's SQLite stores
Mitigation: Query text goes to the vector index, not into SQL. The SQLite
            stores (synapses, decisions, index metadata) bind caller-supplied
            values as parameters. SQL built with string formatting only
            interpolates placeholders and fixed internal names
Status: No known injection path. This comes from code review, not a
        penetration test
```

**Scenario 2: Privilege escalation**
```
Attack: A caller declares role "admin" to reach admin-only tools
Mitigation: None in NeuralMind itself: roles are caller-declared. Leave
            admin out of security.roles, and limit who can reach the
            MCP server. The policy comes from the neuralmind-backend.yaml of
            the project_path the call names, and a project without one gets
            the default policy, which includes admin
Status: ⚠️ Possible with the default policy, and against any readable
        project that has no security.roles
```

**Scenario 3: Data exfiltration**
```
Attack: A user copies the index or source text off the machine
Mitigation: None in NeuralMind itself. Anyone who can read .neuralmind/ can
            copy it directly, with no NeuralMind call. Calls through the MCP
            server are rate-limited by count, not bytes, and recorded in the
            audit log with actor, role, and tool; query and search events
            include the query text
Status: ⚠️ Not prevented. Use OS permissions and your DLP controls
```

---

## Security Checklist

Before deploying NeuralMind to production:

### Access & Authentication
- [ ] `security.roles` set in `neuralmind-backend.yaml`, without `admin` unless you need it
- [ ] MCP server reachable only by the agent that launched it (stdio), or the HTTP transport kept on localhost
- [ ] MFA on the OS accounts that can run the agent or read the project
- [ ] Regular access reviews scheduled

### Data Protection
- [ ] `.neuralmind/` restricted to its owner (`chmod -R go-rwx`)
- [ ] Full-disk encryption on every host that holds `.neuralmind/`
- [ ] Graph view and daemon reached only over loopback, an SSH tunnel, or a TLS proxy you run
- [ ] Secrets scanned (`neuralmind scan-for-secrets`) before indexing
- [ ] No hardcoded credentials
- [ ] Key rotation policy established

### Audit & Compliance
- [ ] `neuralmind audit verify` run on a schedule
- [ ] `neuralmind audit export` shipped off the host on a schedule
- [ ] Audit log treated as sensitive: it records query text
- [ ] Compliance mappings documented
- [ ] Regular audit log review

### Network Security
- [ ] Firewall rules restricting access
- [ ] No direct internet exposure
- [ ] VPN/private network for remote access
- [ ] DDoS protection enabled
- [ ] Network segmentation (if applicable)

### Infrastructure
- [ ] Automated backups tested (recovery verified)
- [ ] Security patches applied monthly
- [ ] Intrusion detection enabled
- [ ] Log aggregation configured
- [ ] Incident response plan documented

### Operations
- [ ] Security training for operators
- [ ] Least privilege for deployment accounts
- [ ] Change management process
- [ ] Disaster recovery drills scheduled
- [ ] Security scan results reviewed

---

## Reporting Security Issues

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, report it privately through
[GitHub Security Advisories](https://github.com/dfrostar/neuralmind/security)
("Report a vulnerability", preferred), or email `darren.frost@gmail.com` with
`[SECURITY] neuralmind:` in the subject.

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

Response targets and fix timelines by severity are in
[SECURITY.md](https://github.com/dfrostar/neuralmind/blob/main/SECURITY.md#reporting-a-vulnerability).

