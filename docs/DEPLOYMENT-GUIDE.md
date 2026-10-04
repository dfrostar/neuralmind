# Deployment Guide

**How NeuralMind runs, what it opens, what it writes, and how to deploy it
across a team.**

NeuralMind is a local tool. Each developer (or CI job) runs it against a
project checkout under their own OS account. It has no central server, no
shared index, and no database server to run. Every command and setting below
exists in the shipped code. If something you need isn't here, NeuralMind
doesn't do it yet.

---

## Table of Contents

- [What You Are Deploying](#what-you-are-deploying)
- [Deployment Options](#deployment-options)
- [Security Hardening](#security-hardening)
- [Index Size and Performance](#index-size-and-performance)
- [Monitoring](#monitoring)
- [Backup & Recovery](#backup--recovery)
- [Rolling Out to a Team](#rolling-out-to-a-team)
- [Troubleshooting](#troubleshooting)
- [Deployment Checklist](#deployment-checklist)

---

## What You Are Deploying

| Component | How it runs | Network |
|---|---|---|
| `neuralmind` CLI | Builds and queries the index, installs hooks | None, except the embedding-model download on a cold first build, and tiktoken's vocabulary if tiktoken is installed ([below](#outbound-network)) |
| `neuralmind-mcp` | MCP server, launched by the agent over stdio | None. Opens no port |
| `neuralmind serve` (optional) | Local graph-view UI | HTTP on `127.0.0.1:8787` by default, access token persisted across restarts |
| `neuralmind daemon start` (optional, experimental) | Keeps project state warm for faster repeat CLI queries | HTTP on `127.0.0.1:8787` by default, bearer token generated at each start |
| State | `<project>/.neuralmind/` | n/a |

`neuralmind-mcp` takes no command-line arguments. The agent passes the project
with each tool call, as the `project_path` argument, so one server process can
serve any project its OS account can read.

The MCP server also has a Streamable HTTP transport
(`NEURALMIND_MCP_TRANSPORT=streamable_http`). It is an unfinished skeleton: it
returns placeholder responses rather than handling MCP calls, has no
authentication, and binds to a hardcoded `127.0.0.1:8765`. Don't deploy it.
Use stdio.

---

## Deployment Options

### Option 1: Per-developer install (pip)

```bash
pip install neuralmind
cd /path/to/project
neuralmind build .           # builds .neuralmind/graph.json and the vector index
neuralmind install-mcp .     # registers neuralmind-mcp with Claude Code (--client or --all for others)
neuralmind install-hooks .   # Claude Code: session memory, prompt recall, stale-decision guard, Bash output cache (optional)
neuralmind init-hook .       # git post-commit index rebuild + pre-commit drift guard (optional)
```

`neuralmind build` parses the project with its built-in tree-sitter graph
backend. An external `graphify` install is optional. NeuralMind reads an
existing `graphify-out/graph.json` for backward compatibility, and
`neuralmind build . --regenerate-graph` replaces a stale one with the built-in
backend.

### Option 2: Container image (GHCR)

Every release tag publishes a multi-platform image (linux/amd64 and
linux/arm64) through `.github/workflows/docker-publish.yml`:

```bash
docker pull ghcr.io/dfrostar/neuralmind:vX.Y.Z   # pin a release tag
docker pull ghcr.io/dfrostar/neuralmind:latest   # moves with each stable release
```

Pick the tag from the [releases page](https://github.com/dfrostar/neuralmind/releases).
The image is built from the repo-root `Dockerfile`: a `python:3.12-slim` base,
NeuralMind and `graphifyy` installed from prebuilt wheels, running as the
non-root user `neuralmind`. The default command prints `neuralmind --help`, so
name the command you want.

Constraints to plan around:

- **Mount the project read-write.** NeuralMind writes `.neuralmind/` into the
  project, and the MCP server appends to the audit log on every tool call.
  On a read-only mount those calls fail. The `neuralmind` user in the container
  needs write access to the mount.
- **Mount the project at the same absolute path the agent uses.** The agent
  sends `project_path` as it sees it, and the container has to resolve the
  same path.
- **The image doesn't bundle the embedding model.** Without one, every fresh
  container downloads it on its first build, and `--rm` throws it away again.
  Copy the extracted model from a host that has built once
  (`~/.cache/neuralmind/onnx_models/all-MiniLM-L6-v2/onnx/`), mount it
  read-only, and point `NEURALMIND_ONNX_MODEL_DIR` at it. The image doesn't
  include tiktoken, so that keeps the container off the network
  ([below](#outbound-network)).

Build the index, then run the MCP server over stdio:

```bash
docker run --rm \
  -v /srv/myproject:/srv/myproject \
  -v /opt/models/all-MiniLM-L6-v2/onnx:/models/minilm:ro \
  -e NEURALMIND_ONNX_MODEL_DIR=/models/minilm \
  ghcr.io/dfrostar/neuralmind:vX.Y.Z neuralmind build /srv/myproject

# In the agent's MCP config: command "docker", with these args
docker run --rm -i \
  -v /srv/myproject:/srv/myproject \
  -v /opt/models/all-MiniLM-L6-v2/onnx:/models/minilm:ro \
  -e NEURALMIND_ONNX_MODEL_DIR=/models/minilm \
  ghcr.io/dfrostar/neuralmind:vX.Y.Z neuralmind-mcp
```

To reach the graph view from the host, bind it to all interfaces inside the
container and publish the port on the host's loopback only. Leave the token on:

```bash
docker run --rm -p 127.0.0.1:8787:8787 \
  -v /srv/myproject:/srv/myproject \
  -v /opt/models/all-MiniLM-L6-v2/onnx:/models/minilm:ro \
  -e NEURALMIND_ONNX_MODEL_DIR=/models/minilm \
  ghcr.io/dfrostar/neuralmind:vX.Y.Z \
  neuralmind serve /srv/myproject --host 0.0.0.0 --no-browser
```

The server prints the URL with its token (`http://0.0.0.0:8787/?token=…`).
Open it as `http://127.0.0.1:8787/?token=…` on the host.

The repository contains no Helm chart or Kubernetes manifests. NeuralMind has
no network service to scale. The MCP server is a stdio process owned by one
agent session.

### Option 3: CI

A CI job can install NeuralMind and use its exit codes as gates:

```bash
pip install neuralmind
neuralmind scan-for-secrets .   # exit 1 on any high-confidence finding
neuralmind build .
neuralmind health .             # exit 0 healthy, 1 stale, 2 no index
```

An index built in CI stays on that runner. Nothing publishes it to developers.

---

## Security Hardening

### Network exposure

- **MCP over stdio opens no port.** Only the agent that launched
  `neuralmind-mcp` can call it.
- **The graph view and the daemon are plain HTTP.** Neither serves TLS. Both
  bind to `127.0.0.1` by default and require a token. `neuralmind serve --host`
  changes the bind address but keeps the token. `--no-auth` removes it, so use
  `--no-auth` only on a host nobody else can reach.
- **The graph-view token persists.** It is stored in
  `~/.neuralmind/server-token.json` (mode `0600`) and reused on every restart,
  so a URL you shared stays valid. To revoke it, delete that file and restart
  `neuralmind serve`. The daemon generates a new token each time it starts.
- **`/healthz` on the graph view is unauthenticated** by design, so container
  health checks work without the token. It returns only `{"status": "ok",
  "version": "…"}`.
- To view the graph from another machine, use an SSH tunnel
  (`ssh -L 8787:127.0.0.1:8787 host`) rather than binding to a routable
  interface. If you do expose it, terminate TLS in a reverse proxy you
  operate. NeuralMind provides no TLS of its own.

### Outbound network

By default NeuralMind sends no telemetry and transmits no repository content
off your machine. It can make three outbound requests:

1. **Embedding-model download.** On a cold first build, NeuralMind downloads
   the `all-MiniLM-L6-v2` ONNX archive over HTTPS and checks it against a
   pinned SHA-256 before extracting it to `~/.cache/neuralmind/onnx_models/`.
   For air-gapped or egress-restricted hosts, pre-extract the model and set
   `NEURALMIND_ONNX_MODEL_DIR` to its folder. See the
   [air-gapped walkthrough](use-cases/air-gapped.md).
2. **Tokenizer vocabulary, only if tiktoken is installed.** NeuralMind
   doesn't install tiktoken (`requirements-pinned.txt` does pin it), but uses
   it for exact token counts when present. tiktoken downloads its
   `cl100k_base` vocabulary on first use. On offline hosts, pre-populate a
   cache and set `TIKTOKEN_CACHE_DIR`, or leave tiktoken uninstalled. If the
   download fails, NeuralMind falls back to approximate counts.
3. **Opt-in documentation seeding.** With both `NEURALMIND_LLM_SEED=1` and
   `ANTHROPIC_API_KEY` set, NeuralMind sends the text of `README.md` and
   `docs/architecture.md` to Anthropic's API. This is off by default. See
   [THIRD_PARTY_LLM_DISCLOSURE.md](compliance/THIRD_PARTY_LLM_DISCLOSURE.md).

Commands whose purpose is fetching, such as `pip install` or
`neuralmind benchmark --public` (which clones pinned public repositories from
a source checkout), reach the network when you run them.

Your agent still sends the context NeuralMind hands it to the agent's own
model. That egress belongs to the agent, not to NeuralMind.

### Access control

NeuralMind does not authenticate callers. Each MCP tool call declares its own
`actor` (default `anonymous`) and `role` (default `builder`). The server checks
the role against its default per-tool policy (`admin`, `builder`, `reader`)
and rate-limits each declared actor to 60 calls per 60 seconds. Any caller can
declare `admin`.

`security.roles` and `security.rate_limit` in `neuralmind-backend.yaml`
replace those defaults. A role the policy doesn't list gets no tools, so
leaving `admin` out caps what any caller can claim. (The MCP server in v4.5.1
and earlier ignored both settings.) Who can reach the MCP server, and which
directories its OS account can read, still decide who gets in at all.
See [SECURITY-GUIDE.md](SECURITY-GUIDE.md#access-control) for the full model.

### File permissions

`.neuralmind/` is created with your umask, typically `0755` with `0644`
files, so other accounts on a shared host can read it. It holds indexed source
text, the audit log (including query text), learned synapses, and a cache of
recent Bash output. Restrict it as you would the source tree:

```bash
chmod -R go-rwx /path/to/project/.neuralmind
```

NeuralMind doesn't encrypt its state. Use full-disk encryption on the host.

`.neuralmind/` contains its own `.gitignore` with `*`, so a `git add -A`
won't commit it.

### Secret scanning

Scanning is explicit, not automatic. Run it before you index. It exits
non-zero on high-confidence findings, so it works as a CI gate:

```bash
neuralmind scan-for-secrets .

# Output:
# NeuralMind secret scan — /srv/myproject
#
#   [HIGH ] src/config.py:42  aws-secret-access-key  (wJal…(40 chars))
#   [HIGH ] .env:3  github-token  (ghp_…(40 chars))
#
#   2 high-confidence, 0 heuristic.

# Remove and rotate those, then build. --redact-secrets is a backstop
# that scrubs anything still present out of the indexed text.
neuralmind build . --redact-secrets
```

See [SECURITY-GUIDE.md](SECURITY-GUIDE.md#secret-management) for what
redaction does and doesn't cover.

---

## Index Size and Performance

### Controlling what gets indexed

Add a `.neuralmindignore` file to the project root to keep paths out of the
index, such as generated code, vendored dependencies, or fixtures. It uses
`.gitignore` pattern syntax:

```gitignore
# .neuralmindignore
dist/
vendor/
**/*.min.js
tests/fixtures/
```

### Vector backend

| Backend | How to select | Status |
|---|---|---|
| `turbovec` | Default, no configuration | Installed with NeuralMind on Linux, macOS arm64, and Windows AMD64 |
| `chroma` / `graph` | `backend: chroma` in `neuralmind-backend.yaml`, plus `pip install "neuralmind[chromadb]"` | Deprecated. Required on other platforms (such as Intel macOS): pip installs ChromaDB there instead of turbovec, but doesn't select it, so without `backend: chroma` the first command fails |

Both backends store the index as local files under `.neuralmind/`. There is no
server backend. If you build your own image, use a glibc base such as
`python:3.12-slim`, not Alpine.

### Measuring on your codebase

NeuralMind publishes no scale limits. Measure your own repository:

```bash
neuralmind stats .       # node count for the built index
neuralmind benchmark .   # token reduction on sample queries
```

The embedder uses ONNX Runtime, which sizes its thread pool to the host's core
count. In a CPU-limited container, set `NEURALMIND_ORT_THREADS` to the CPU
limit.

---

## Monitoring

### Health checks

```bash
neuralmind health .          # exit 0 healthy, 1 stale index, 2 no index
neuralmind health . --json

neuralmind doctor .          # diagnoses graph, index, hooks, MCP, and synapses
neuralmind doctor . --json   # read "status": doctor always exits 0
```

`doctor` exits 0 even when a check fails, so don't use its exit code as a
health probe. Use `health`, or parse `doctor --json`.

While `neuralmind serve` is running:

```bash
curl http://127.0.0.1:8787/healthz
# {"status": "ok", "version": "…"}
```

### Metrics

There is no Prometheus exporter. The graph view has a token-gated
`/api/metrics` JSON endpoint, and `neuralmind metrics` reads the same store
(`.neuralmind/metrics/`), but nothing in the build or query path writes to it,
so both report nothing today. Use the audit log below instead: each `query`
event carries the token count of the context it returned, and
`neuralmind savings .` summarizes those events.

### Audit log

NeuralMind writes no application log file. Its durable record is the audit
log at `.neuralmind/audit_events.jsonl`. Every MCP tool call is recorded with
the declared actor and role and the outcome: allowed, denied by policy, denied
by rate limit, or failed. Builds, document ingestion, backend switches, and
every `wakeup`, `query`, and `search` are recorded too, including the query
text. For CLI calls, the actor is `NEURALMIND_ACTOR` if set, otherwise the OS
login.

```bash
neuralmind audit recent . -n 50
neuralmind audit verify .                                         # check the hash chain
neuralmind audit export . --format cef --since 2026-01-01 -o audit.cef   # or --format jsonl
```

Each record carries a SHA-256 hash chained to the previous one. `audit verify`
detects a record that was edited, or deleted from the middle of the log. It
can't detect tampering at the tail (records removed from the end, or the last
record edited with its hash stripped), or a chain recomputed by anyone with
write access to the file. To keep a copy outside the host's control, ship
`audit export` output to your SIEM.

NeuralMind doesn't rotate or expire the audit log. The file grows until you
archive it.

---

## Backup & Recovery

Most of `.neuralmind/` is rebuilt from source by `neuralmind build`. Three
stores aren't:

| File | Contents | Rebuildable? |
|---|---|---|
| `.neuralmind/synapses.db` | Learned associations (SQLite, WAL mode) | No |
| `.neuralmind/memory.db` | Recorded decisions (SQLite, WAL mode), if you use decision memory | No |
| `.neuralmind/audit_events.jsonl` | Audit log | No |
| `graph.json`, `index_ir.json`, `neuralmind_turbovec/`, caches | Graph and index | Yes, with `neuralmind build . --force` |

Use SQLite's online backup for the databases, so a backup taken while an agent
is writing stays consistent:

```bash
#!/bin/bash
# backup-neuralmind.sh <project>
set -euo pipefail
P="$1/.neuralmind"
DEST="/backups/neuralmind-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DEST"

sqlite3 "$P/synapses.db" ".backup '$DEST/synapses.db'"
if [ -f "$P/memory.db" ]; then sqlite3 "$P/memory.db" ".backup '$DEST/memory.db'"; fi
cp "$P/audit_events.jsonl" "$DEST/"
```

The audit log contains query text, and the synapse store names files and
symbols. Protect backups the way you protect the source tree.

To recover, first stop everything that opens the project's stores: agents
running `neuralmind-mcp`, `neuralmind watch`, `neuralmind serve`, and
`neuralmind daemon`. Then delete the `-wal` and `-shm` files of each database
you replace. If you leave them, SQLite replays the old write-ahead log over
the restored file and silently undoes the restore.

```bash
B=/backups/neuralmind-YYYYMMDD_HHMMSS
N=/path/to/project/.neuralmind
mkdir -p "$N"
rm -f "$N/synapses.db-wal" "$N/synapses.db-shm"
cp "$B/synapses.db" "$N/"
if [ -f "$B/memory.db" ]; then
  rm -f "$N/memory.db-wal" "$N/memory.db-shm"
  cp "$B/memory.db" "$N/"
fi
# Restore the audit log only if it's gone: overwriting it discards newer records
[ -f "$N/audit_events.jsonl" ] || cp "$B/audit_events.jsonl" "$N/"
neuralmind build /path/to/project                          # regenerates the graph and index
neuralmind audit verify /path/to/project
```

---

## Rolling Out to a Team

Each developer builds and queries their own index. There is no shared index
service, and real-time cross-machine sync is roadmap-only. Committing
`neuralmind-backend.yaml` shares backend settings and the role policy
([above](#access-control)).

Teams can optionally share learned memory through git.
`neuralmind memory publish` writes `.neuralmind-team-memory.json` (learned
weights between files and symbols, no source text). Once it's committed, each
teammate's agent merges it into its `shared` namespace on the next session
start or build. Set `NEURALMIND_TEAM_MEMORY=0` to turn the import off. Anyone
who can commit that file can influence what teammates' agents recall, so
review changes to it like code.

NeuralMind has no user directory or LDAP integration, and SSO/SAML is
roadmap-only. Per-person access comes from OS accounts and file permissions.

---

## Troubleshooting

```bash
neuralmind doctor .                      # start here: names each failing piece and its fix
neuralmind build . --force               # rebuild the index from scratch
neuralmind build . --regenerate-graph    # replace a stale graphify graph.json
neuralmind install-mcp                   # re-register the MCP server with your agent
```

- **The MCP server isn't responding.** It runs under your agent, so its
  stderr goes to the agent's MCP log, not to a NeuralMind log file. Check
  the agent's MCP logs first.
- **A tool call returns `security_denied`.** The declared role isn't allowed
  that tool by the default policy (for example, `reader` calling
  `neuralmind_build`), or the declared actor made more than 60 calls in 60
  seconds. Both cases are recorded: `neuralmind audit recent . --action mcp_call_denied`.
- **Calls fail in a container.** Check that the project mount is writable and
  sits at the same absolute path the agent sends as `project_path`.

---

## Deployment Checklist

- [ ] `neuralmind-mcp` runs over stdio. The Streamable HTTP transport is not used
- [ ] Only trusted agents can reach the MCP server, and `security.roles` leaves out `admin` unless you need it
- [ ] The OS account running the agent can read only the projects it should
- [ ] `.neuralmind/` restricted with file permissions, and the host disk encrypted
- [ ] `neuralmind scan-for-secrets` passes before the first build
- [ ] Embedding model pre-seeded with `NEURALMIND_ONNX_MODEL_DIR` on egress-restricted hosts
- [ ] `NEURALMIND_LLM_SEED` left unset unless approved
- [ ] Graph view and daemon left on `127.0.0.1` with the token on, and `~/.neuralmind/server-token.json` deleted to revoke a shared graph-view URL
- [ ] `audit export` shipped to your SIEM, and `audit verify` scheduled
- [ ] `synapses.db`, `memory.db`, and `audit_events.jsonl` backed up, and a restore tested
- [ ] Container image pinned to a release tag, not `latest`
