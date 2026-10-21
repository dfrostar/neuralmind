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

1. **No Telemetry by Default** — NeuralMind sends no telemetry and transmits no repository content in its default configuration; its one default outbound request is a one-time public embedding-model download on first build (pre-seedable via `NEURALMIND_ONNX_MODEL_DIR`), and it adds nothing to what your agent sends its model. One narrow, opt-in exception exists — see below.
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

NeuralMind has no logins of its own. By default, access to it is access to
the OS account and project directory it runs in, plus whatever can reach its
MCP server. With `security.identity: os` *(v4.7.0+)* it takes each MCP
caller's identity from that OS account, which the OS authenticated
([below](#binding-roles-to-os-accounts-identity-os)).

### Who can call the MCP server

- **Stdio (default).** The agent that launches `neuralmind-mcp` is the only
  caller. No network port is opened.
- **Streamable HTTP** (`NEURALMIND_MCP_TRANSPORT=streamable_http`) is an
  unfinished skeleton. It binds to `127.0.0.1:8765` and has no OAuth or other
  authentication, so don't expose it beyond the host.
- **Graph view** (`neuralmind serve`) binds to `127.0.0.1` by default and
  requires an access token. `--host` changes the bind address and keeps the
  token. Only `--no-auth` removes it. The token persists across restarts in
  `~/.neuralmind/server-token.json` (mode `0600`), so a shared URL stays
  valid until you delete that file and restart the server.

### The role policy

Every MCP tool call goes through `MCPSecurityManager.secure_call`
(`neuralmind/mcp_security.py`). It checks the call's role against a per-tool
permission policy and a per-actor rate limit, then writes the decision to the
audit log.

By default the caller declares its own `actor` and `role` in the tool
arguments. The role defaults to `builder`, and any caller can declare `admin`.
In that mode, treat the policy as a guard rail for a well-behaved agent, not a
boundary against a hostile caller.

Default roles (`DEFAULT_ROLE_POLICY`):

| Role | Tools |
|---|---|
| `admin` | All tools |
| `builder` | The `reader` set, plus `build`, document ingestion, and recording or invalidating decisions |
| `reader` | Retrieval (`wakeup`, `query`, `search`, `skeleton`), the read-only structure and recall lookups (`review`, `impact`, `structural_neighbors`, `synaptic_neighbors`, `next_likely`), read-only analytics and stats, and the read-only decision-memory tools (`query_decisions`, `audit_decisions`, `memory_search`, `memory_timeline`, `memory_get`) |

No tool is admin-only by default. Through v4.8.0, `synaptic_neighbors`,
`structural_neighbors`, `next_likely`, `impact` and `review` were listed to
agents but refused to `builder` and `reader`, so an agent following the docs
got `security_denied` from `neuralmind_review`. They only read, like `query`,
and v4.8.1 grants them to both roles. A `security.roles` policy you wrote is
unaffected: it replaces the defaults, as described below.

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

The MCP server in v4.6.0 and earlier built its security manager without
reading this file, so both settings were ignored there.

An empty `roles: {}` grants nothing. If `roles`, `rate_limit`, or the
`security` section itself is malformed (not a mapping, a window under one
second, a value that isn't a whole number), the server refuses every MCP call
with `reason: config` instead of falling back to defaults that may be looser.

*(v4.8.0+)* Two more mistakes refuse every call with `reason: config` too:

- a policy file that doesn't parse, when its text outside comments names
  `security`, `roles`, `rate_limit`, `identity` or `require_encrypted_storage`
  (other unparseable files still read as empty, so a typo in backend tuning
  doesn't block the server);
- a `security:` or `roles:` key left empty, which YAML reads as `null` and is
  what's left when every entry under it is commented out. Write `roles: {}` to
  grant nothing, or remove the key to use the defaults. An empty
  `rate_limit:` still means the default limit.

v4.7.0 and earlier read both as "no policy" and applied the defaults, `admin`
included; v4.7.0 refused an unparseable file only when it named `identity` or
`require_encrypted_storage`.
`neuralmind doctor` reports each as a failed *Security policy* check. A
misspelled key (`role:` for `roles:`) is still read as absent, so after writing
a policy, call a tool you left out with `role: "admin"` and check that it
returns `security_denied`.

The server reads the policy once per project and keeps it until it exits, so
restart the MCP server (a new agent session, or reconnecting the server) after
editing `security:`.

The rate limit keys on the actor, so with declared identities it stops a
runaway agent, not a caller that changes its actor name. Under
`identity: os` it keys on the OS account.

### Binding roles to OS accounts (`identity: os`)

*(v4.7.0+)* Over the stdio transport, the MCP server runs as the OS account of
the agent that launched it, and the OS authenticated that account at login.
`security.identity: os` makes the server use it:

```yaml
security:
  identity: os
  users:
    alice: builder
    bob: reader
  default_role: reader     # optional; unset refuses accounts missing from users
```

- The actor is the account name from the OS (the passwd entry for the
  effective uid, or `GetUserNameW` on Windows), never `LOGNAME`, `USER` or
  `USERNAME`, which the launching process controls.
- The role comes from `users`, then `default_role`. The `actor` and `role` a
  call declares are ignored and kept in the audit log as `claimed_actor` and
  `claimed_role`.
- Every call is refused, with `reason: identity`, when the HTTP transport is in
  use, the account can't be read, the account has no role, the policy file is
  world-writable (POSIX), or the `security:` section is invalid. A policy file
  that names `identity` but doesn't parse is refused rather than ignored.
- Audit events written outside MCP (CLI builds and queries) take the OS account
  as their actor too, with `NEURALMIND_ACTOR` recorded as a claim.
- *(v4.17.1+)* The role applies off the MCP path too. Each daemon route needs
  the role the MCP tool doing the same thing needs (`/query`
  `neuralmind_query`, `/search` `neuralmind_search`, `/stats`
  `neuralmind_stats`, `/savings` `neuralmind_savings`, `/build`
  `neuralmind_build`, `/validate` `neuralmind_health`, or `neuralmind_build`
  with `write`), and so do `neuralmind build` and `neuralmind validate --write`
  (`neuralmind_build`). A refusal is logged as `security`/`call_denied` with
  the surface; the daemon answers `403` with `code: security_denied` and
  `reason` `rbac`, `identity` or `config`, and the CLI exits `1`. Before
  v4.17.1 a `reader` could build through the daemon or the CLI although MCP
  refused it. Other CLI commands and the hooks run with the account's own file
  permissions.

This makes roles and audit attribution trustworthy on a host where users have
separate OS accounts and an administrator owns the policy file. It doesn't stop
someone from doing as that account what the account can already do: read
`.neuralmind/` directly, or edit a policy file they own. Keep the file
writable only by its owner; `neuralmind doctor` warns when it's group-writable.

### The machine policy

*(v4.17.1+)* `neuralmind-backend.yaml` lives in the project root, and whoever
owns that directory can delete it, even when an administrator owns the file.
Before v4.17.1, deleting it switched `profile: cui`, `identity: os` and
`require_encrypted_storage` off with no warning. An administrator can put those
three settings where a project's owner can't reach them:

```yaml
# /etc/neuralmind/policy.yaml          (POSIX: root:root, mode 0644, directory 0755)
# C:\ProgramData\NeuralMind\policy.yaml (Windows: Administrators full control, Users read)
security:
  profile: cui
```

- It applies to every project on the machine, and only tightens: each setting
  takes the stricter of the machine's value and the project's, so neither file
  can loosen the other. With the project file deleted, the profile stays on and,
  with no `users` left, every MCP call is refused.
- It can hold only `profile`, `identity` and `require_encrypted_storage`. Roles
  (`users`, `default_role`, `roles`) and the audit checkpoint settings stay in
  each project's `neuralmind-backend.yaml`, so a user who manages to create the
  machine policy gains nothing.
- A machine policy that doesn't parse, names any other key, holds an invalid value (*v4.17.2+* including a `require_encrypted_storage` that isn't true or false, which a project file reads as on), or on POSIX isn't
  owned by root and writable only by root (the file and its directory) holds
  every project to the strictest settings, and `neuralmind doctor` fails the
  *Security policy* check with the reason.
- Its location is fixed. On Windows it's found through the shell, not the
  `%ProgramData%` variable, which any user can change.
- On Windows NeuralMind doesn't read ACLs, so restrict the folder yourself:
  `icacls "C:\ProgramData\NeuralMind" /inheritance:r /grant:r "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Users:(OI)(CI)RX"`.

`neuralmind doctor` names the machine policy on its *Security policy* and
*Security profile* lines when one applies.

### Per-user roles

NeuralMind has no user directory, LDAP, or OAuth integration, and SSO/SAML is
roadmap-only. For different permissions per person, give each an OS account
and map it in `security.users` with `identity: os`. OS file permissions still
decide who can read the index.

### Requiring encrypted storage

*(v4.7.0+)* NeuralMind doesn't encrypt `.neuralmind/` itself. The OpenSSL
inside a pip-installed `cryptography` wheel isn't FIPS-validated, so
in-process encryption wouldn't count as the FIPS-validated cryptography CMMC
asks for. It verifies the OS's full-disk encryption instead:

```yaml
security:
  require_encrypted_storage: true
```

With this set, NeuralMind checks for FileVault (macOS), dm-crypt/LUKS (Linux),
or BitLocker (Windows) on every volume that holds its state: the project root,
`.neuralmind/` (following a symlink), and a custom vector-index `db_path`. Only
an explicit `false` turns the setting off; a blank value counts as on. Until the check passes, it
refuses to build or query, MCP tools return `reason: storage`, hooks write
nothing, and the decision store won't open. A check that can't tell (a
container's overlay filesystem, BitLocker suspended, a timeout) counts as not
encrypted. The verdict goes into the audit log as a `storage_check` event once
per process. `neuralmind doctor` shows what the check sees, plus the OS FIPS
mode on Linux and Windows. macOS has no FIPS switch; FileVault uses Apple
corecrypto, which Apple lists in its CMVP certificates.

*(v4.13.0+)* NeuralMind's own code works with the OS FIPS mode on. Its MD5
and SHA-1 calls build ids and sort keys, not security controls, and pass
`usedforsecurity=False`, which a FIPS-mode OpenSSL allows; the audit log's hash
chain uses SHA-256. Earlier releases crashed with `UnsupportedDigestmodError`
in document ingestion (`neuralmind ingest`, `ingest-content`, book builds and
the `neuralmind_ingest_document` MCP tool) on a FIPS-mode host. CI runs the
test suite with the OpenSSL FIPS provider enforced
(`scripts/setup_fips_openssl.sh`). That covers the dependency code the
tests exercise, not every path (the embedding-model download isn't one), and
it tests the provider's algorithm restrictions, not your host's validated
module.

Team-tier licence and seat-manifest signatures are Ed25519, which FIPS 186-5
approves and the CI job verifies under the upstream provider. A FIPS policy
that disables EdDSA would make a valid Team licence read as invalid.

---

## Data Protection

NeuralMind doesn't encrypt anything itself. Its state is plain files in the
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
  Linux, BitLocker on Windows. *(v4.7.0+)*
  `security.require_encrypted_storage: true` makes NeuralMind refuse to run
  until it can see that encryption; see
  [Requiring encrypted storage](#requiring-encrypted-storage).

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
  leave the token on. *(v4.16.0+)* For a project under
  `security.profile: cui`, NeuralMind won't: `serve` refuses a non-loopback
  `--host` and `--no-auth`, and a daemon started that way refuses the project,
  so the SSH tunnel is the only route.
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

One thing *is* redacted with no flag: the PostToolUse Bash output
cache behind `neuralmind last` (`.neuralmind/last_output.json`). It
stores whatever your commands printed, so `printenv`,
`aws configure list`, or a `curl -H "Authorization: Bearer …"` would
otherwise write a live credential to a plaintext file. Credentials are stripped before the payload is written,
and the entry records which kinds were removed. Opt out with
`NEURALMIND_OUTPUT_REDACT=0` (not recommended).

Through v4.8.0 this cache missed some common shapes: the
`"SecretAccessKey"` and `"SessionToken"` JSON that `aws sts get-session-token`
prints, JSON keys such as `{"password": "…"}`, and the part of a bare value
after a `;` or `,` (`DB_PASSWORD=abc;rest`). If you ran such commands under
the hook on v4.8.0 or earlier, delete `.neuralmind/last_output.json` and
rotate what it held. v4.8.1 redacts all three.

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

- **`actor`** is, by default, whatever name the MCP caller declares (default
  `anonymous`). For CLI commands it is `NEURALMIND_ACTOR` if set, otherwise
  the OS login. Nothing authenticates it. *(v4.7.0+)* With
  `security.identity: os`, it is the OS account, read from the OS, for MCP
  calls and CLI events alike, and declared values are kept as
  `details.claimed_actor` and `details.claimed_role`.
- **The role the call ran with** is in `details.role`. `actor_role` and
  `ip_address` are in the schema, but nothing fills them in, so they are
  always empty.
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

`audit verify` catches an edited record, a record deleted from the middle of
the log, and, once the chain has started, any record without a `sha256` or
with a `prev_sha256` that doesn't match the record before it. So records
edited or appended with their hash removed fail too. It also fails on any
line that isn't a JSON object, where search and export skip it. v4.8.0 and
earlier accepted a record without a hash anywhere as a legacy line, skipped
lines they couldn't parse, and never compared `prev_sha256`, so all of those
passed.

Records from before the hash chain existed (written by versions before
v0.46.2) carry no hash. `verify` accepts them only ahead of the first hashed
record and reports how many there are; the chain doesn't cover them.

*(v4.17.1+)* The MCP server, the hooks, the CLI and the daemon all append to
the log, and each append now holds an OS lock on `.neuralmind/audit_events.lock`
while it reads the last hash and writes, as does `rotate`. Before v4.17.1 only
a per-process lock did, so two processes writing at once could chain to the
same record and `verify` reported an untouched log as tampered. If a log
written by an earlier version fails `verify` at a point where two records share
a `prev_sha256` and their timestamps are within a second, that was this race,
not an edit; a checkpoint taken since tells the two apart.

The chain alone can't detect records deleted from the end, or a chain
recomputed by anyone who can write the file: the hash has no secret key. A
passing chain is therefore weak evidence on its own.

#### Forwarding to syslog (v4.19.0+)

Set `security.audit_syslog` in `neuralmind-backend.yaml`, and every audit
record goes to syslog right after it is written, from the CLI, the MCP server,
the hooks and the daemon:

```yaml
security:
  audit_syslog: /dev/log          # or udp://host[:port], tcp://host[:port]
  audit_syslog_facility: local0   # the default
```

- **The body is the record as JSON**, `sha256` and `prev_sha256` included, in
  RFC 3164 form on a unix socket and RFC 5424 over the network. Severity is
  `info`, `warning` for a denied or failed record, and `err` for a gap record.
- **A record that can't be written raises an `alert`** (`audit_write_failed`)
  at once, sent straight to syslog rather than through the log that failed.
  Route `alert` to a person (CMMC AU.L2-3.3.4).
- **Nothing is silently dropped.** `.neuralmind/audit_forwarded.json` tracks
  the last record sent; records a dead target missed go out with the next
  append, or with `neuralmind audit forward`, across a rotation too. Records
  arrive at least once; deduplicate on `sha256`. `doctor`'s *Audit forwarding*
  line warns while any are waiting.
- **NeuralMind doesn't encrypt the connection.** Audit records hold query text,
  which can be CUI, so under `security.profile: cui` only a unix socket or a
  loopback address is accepted. Let the host's syslog daemon forward to the
  SIEM over TLS, in the host's validated module. For rsyslog:

```
# /etc/rsyslog.d/60-neuralmind.conf
global(DefaultNetstreamDriverCAFile="/etc/pki/tls/certs/siem-ca.pem")
local0.*  action(type="omfwd" target="siem.example" port="6514" protocol="tcp"
                 StreamDriver="gtls" StreamDriverMode="1" StreamDriverAuthMode="x509/name")
```

Forwarding is how the SIEM sees records live. Keep an `audit export` copy as
well: it is what you would restore the log from.

#### Checkpoints (v4.16.0+)

Signed, anchored checkpoints close both gaps (CMMC AU.L2-3.3.8, protection of
audit information). Set them up once, as the administrator:

```bash
# In the administrator's account, which developers can't read:
neuralmind audit keygen ~/.neuralmind-audit/checkpoint.pem
# Pin the printed key in the admin-owned neuralmind-backend.yaml:
#   security:
#     audit_checkpoint_key: MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...
#     audit_anchor_dir: /var/lib/neuralmind-anchor   # writable by the admin only
# Then, daily from the administrator's crontab:
neuralmind audit checkpoint /path/to/project --key ~/.neuralmind-audit/checkpoint.pem
```

Each checkpoint records how many records the log holds and the hashes of the
first and last, chains to the checkpoint before it, and is signed with the
ECDSA P-256 key (FIPS 186-5, available under every OpenSSL FIPS provider). On a
FIPS host, rebuild `cryptography` against the system OpenSSL
(`pip install --force-reinstall --no-cache-dir --no-binary cryptography cryptography`;
NeuralMind depends on `cryptography`, so without `--force-reinstall` pip keeps
the wheel already installed): the prebuilt wheel bundles its own OpenSSL, which
isn't FIPS-validated. Rebuilding only links the system library; confirm the
host's OpenSSL is configured to use its validated FIPS provider.
`audit verify` then fails when the log holds fewer records than a checkpoint
covers, when a covered record's hash changed (a recomputed chain), when a
signature doesn't verify against the pinned key, or when a checkpoint is
missing from every copy.

A checkpoint taken before the log was rotated is checked against the rotated
archive it covers, once that archive's own hash chain verifies. The newest checkpoint must always be found, in the log or
an archive beside it, so a rotation marker written by hand can't pass off a
replaced log as a rotated one. Only older checkpoints whose archive has been
pruned go unchecked, and `audit verify` counts them.

What each part protects against:

| Part | Without it |
|------|-----------|
| The signature, with the private key in another account | Someone who can write the log could rewrite it and write a matching checkpoint |
| The anchored copy, in a directory only the administrator can write | Deleting `.neuralmind/audit_checkpoints.jsonl` along with the newest records would leave nothing to compare against. Once checkpoints exist, `verify` fails while the anchored copy is missing, so unmounting it doesn't fall back to the local copy alone |
| A short interval | Records written since the newest checkpoint are covered by the chain alone |

`audit checkpoint --json` prints each checkpoint as one line for your SIEM, and
`audit verify --checkpoint FILE` checks the log against such a copy. Keep
shipping `audit export` output off the host as well: a checkpoint proves the
log is intact, and the export is the copy you would restore from.

NeuralMind doesn't rotate or expire the log on its own, and it has no report
command: build compliance reports from the export.

### NIST AI RMF Mapping

```
Evidence NeuralMind provides for each NIST AI RMF function:

GOVERN (Oversight)
├─ Per-tool permission policy (caller-declared roles, or OS accounts with identity: os)
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

NeuralMind has no anomaly detection. With `security.audit_syslog` set
*(v4.19.0+)*, your SIEM gets each record as it is written and can alert on it;
otherwise feed it `neuralmind audit export`.

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
   Evidence: CycloneDX SBOM for every release since v4.0.0, for your SCA scanner

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
   Evidence: stdio MCP transport; per-tool permission sets; with
   identity: os, roles bound to the OS account the OS authenticated
   Yours: OS accounts, and owning the policy file

AU.L2-3.3.1 / 3.3.8 - Audit records, protection of audit information
   Evidence: append-only audit log with a SHA-256 hash chain. It shows a
   changed record mid-log, a record without a hash after the chain starts,
   and an unreadable line, not records removed from the end or a
   recomputed chain

SC.L2-3.13.11 / 3.13.16 - FIPS cryptography, CUI at rest
   Evidence: require_encrypted_storage verifies full-disk encryption and
   refuses to run without it, with an audit record of each check
   Yours: the encryption itself, FIPS-validated (OS FIPS mode on)
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
| **Resource exhaustion (DoS)** | Medium | Medium | Per-actor rate limit on MCP calls (`security.rate_limit`, default 60 calls per 60 s; v4.6.0 and earlier ignored the setting). It is held in memory per server process and keyed on the declared actor, so a caller that changes its actor name gets a fresh limit. Denials go to the audit log. NeuralMind has no monitoring or alerting |
| **Insider threat** | Low | Critical | Hash-chained audit log of calls through NeuralMind. It detects an edited record, not records deleted from the end of the log or a chain recomputed by someone with write access, so ship `neuralmind audit export` off the host. Roles are caller-declared unless `security.identity: os` takes them from the OS account; either way, least privilege comes from OS accounts |
| **Configuration error** | Medium | High | The security checklist below. `neuralmind doctor` checks the security policy, storage encryption, the security profile, audit checkpoints and *(v4.18.0+)* failed audit writes alongside install health, but not the items on the checklist that live outside NeuralMind (OS accounts, disk encryption setup, the agent's model provider) |

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
Attack: A caller declares role "admin" to reach tools its own role
        lacks (no tool is admin-only by default; a security.roles
        policy can make some)
Mitigation: Set security.identity: os so the role comes from the OS
            account, not the call. Otherwise leave admin out of
            security.roles, and limit who can reach the MCP server
Status: ⚠️ Possible with the default (declared) identity
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
- [ ] `security.identity: os` with each OS account in `security.users`, and the policy file writable only by its owner
- [ ] `security.require_encrypted_storage: true` where the index holds CUI, and `neuralmind doctor` shows Storage encryption `ok`
- [ ] *(v4.16.0+)* `security.profile: cui` where the index holds CUI, and `neuralmind doctor` shows Security profile `ok`
- [ ] MCP server reachable only by the agent that launched it (stdio), or the HTTP transport kept on localhost
- [ ] MFA on the OS accounts that can run the agent or read the project
- [ ] Regular access reviews scheduled

### Data Protection
- [ ] `.neuralmind/` restricted to its owner (`chmod -R go-rwx`)
- [ ] Full-disk encryption on every host that holds `.neuralmind/`
- [ ] The home directory encrypted too: Claude Code's synapse export (code symbol names) and the query log are written there ([Data Deletion §2.2](compliance/DATA_DELETION.md#22-outside-the-project)). *(v4.18.0+)* Under `security.require_encrypted_storage` NeuralMind skips both when the home directory isn't verified, so an unencrypted home loses those copies rather than leaking them. Before v4.18.0 the check didn't cover the home directory, and `NEURALMIND_SYNAPSE_EXPORT=0` didn't stop the MCP export tool
- [ ] Graph view and daemon reached only over loopback, an SSH tunnel, or a TLS proxy you run
- [ ] Secrets scanned (`neuralmind scan-for-secrets`) before indexing
- [ ] No hardcoded credentials
- [ ] Key rotation policy established

### Audit & Compliance
- [ ] `neuralmind audit verify` run on a schedule
- [ ] `neuralmind audit export` shipped off the host on a schedule
- [ ] *(v4.19.0+)* `security.audit_syslog` forwarding each record to the host's syslog, and `alert` routed to a person
- [ ] *(v4.19.0+)* In an authorized system, `neuralmind hardening` passing on each host, run on a schedule ([SP 800-53 hardening guide](compliance/SP800-53-HARDENING.md))
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

