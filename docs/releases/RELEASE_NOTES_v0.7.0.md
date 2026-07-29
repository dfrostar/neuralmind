# NeuralMind v0.7.0 — install anywhere

**Release Date:** May 2026

## TL;DR

NeuralMind installs five ways now: `pip`, `pipx`, `uv`, Docker, and
source. Same package, same CLI, same MCP server, same live graph
view as v0.6.0 — every path. Plus a multi-stage `Dockerfile` in the
repo root, a PyPI keyword refresh, a P2 fix in the JSONL event log,
and a closed test-coverage gap on `/api/queries`.

No new product features. The brain is the same brain. v0.6.0 made
it visible; v0.7.0 makes it reachable.

No migration. Same `graph.json`, same `synapses.db`, same hooks. If
you're on v0.6.0 and your install path is fine, upgrading is
approximately zero work and approximately zero impact.

## What's new

### Install matrix — five paths

The README's Quick Start now leads with an install matrix instead of
a single `pip install` block:

| Method | Command | When to pick |
|---|---|---|
| **pip** | `pip install neuralmind graphifyy` | Default. Drops it in your active env. |
| **pipx** | `pipx install neuralmind && pipx inject neuralmind graphifyy` | Global CLI, no env pollution. |
| **uv** | `uv pip install neuralmind graphifyy` | Astral's fast Python tooling. |
| **Docker** | `docker build -t neuralmind:dev . && docker run --rm -v "$PWD:/project:ro" neuralmind:dev neuralmind --help` | Containerized — no Python on the host. |
| **From source** | `git clone … && pip install -e .` | Hacking on NeuralMind itself. |

All five paths deliver the same package. The verify snippet is also
unified:

```bash
neuralmind --help     # works for every install path

# For pip / uv / source (a Python env where neuralmind is importable):
python -c "import neuralmind; print(neuralmind.__version__)"
```

`python -c "import neuralmind"` is intentionally scoped: pipx isolates
the package in its own venv and Docker runs in-container, so neither
exposes `neuralmind` to your host Python.

Full walkthrough with pros and cons of each path:
[`docs/use-cases/install-paths.md`](docs/use-cases/install-paths.md).

### `Dockerfile` in the repo root

Multi-stage. The `builder` stage installs `build-essential`, builds
the project wheel via `python -m build`, and then pre-downloads every
transitive runtime dep (including `graphifyy`) as wheels via `pip
wheel`. The `runtime` stage is `python:3.12-slim` with the wheels
copied over and installed using `--no-index --find-links` so PyPI is
never reached at image-build time. A non-root `neuralmind` user owns
the runtime; port `8765` is exposed for `neuralmind serve`.

Documented patterns: mount a host project read-only at `/project` and
run either `neuralmind-mcp /project` for the MCP server or
`neuralmind serve /project --host 0.0.0.0 --no-auth` for the graph
view bound to the host port. For persistent index state, mount the
project directory read-write so `.neuralmind/` and `graphify-out/`
live on the host.

The GHCR auto-publish (`ghcr.io/dfrostar/neuralmind`) is deferred to
a later release. Build locally for now; the README's Docker row
documents this inline.

### PyPI keyword refresh

Eight new keywords on the PyPI package: `graph-view`, `code-graph`,
`obsidian-style`, `synapse-layer`, `hebbian-learning`,
`code-visualization`, `force-directed-graph`, `neuralmind-serve`. The
existing v0.5-era list missed every term the v0.6.0 product copy now
leads with. Search ranking on PyPI is fuzzy magic but discoverable
matching is a precondition for the install-anywhere story to land.

### `fix(event_log)`: rotation race — #115

`EventLogTailer` detected `logrotate`/`copytruncate` via the inode
check, then reopened the new file at end-of-file. Events written to
the new file between rotation detection and the next poll were
silently dropped — bursts during active rotation showed up truncated
on the live activity feed.

Fix: distinguish the initial open (seek to EOF, preserving the
no-history-replay behaviour) from a post-rotation reopen (seek to
offset 0, catching any already-written lines). The `reopen_at_start`
flag survives failed open attempts so the common rename-then-create
gap doesn't silently fall back to EOF on the next poll. The
file-vanished branch in the rotation-detection loop sets the same
flag.

Codex review on PR #112 surfaced the original bug; Codex P1 review
on PR #122 caught the failed-open subtlety in the first fix. Both
addressed in this release.

### `test(server)`: `/api/queries` regression coverage — #116

The replay-last-query route added in PR #105 was hand-tested for
happy-path / clamping / bad-input. v0.7.0 adds the no-`?n=` →
default 20 case explicitly so the documented default can't drift on
a future query-string parsing change.

## Behaviour controls (unchanged from v0.6.0)

| Env var | Default | Effect |
|---|---|---|
| `NEURALMIND_EVENT_LOG` | `1` | `0` disables the cross-process JSONL bridge entirely. |
| `NEURALMIND_BYPASS` | unset | `1` skips PostToolUse compression. |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | `0` skips prompt-time synapse recall. |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | `0` skips memory export to Claude Code's auto-memory. |

## Verification

Smoke against this release on each install path:

```bash
# pip
pip install neuralmind==0.7.0 graphifyy
neuralmind --help

# pipx
pipx install neuralmind==0.7.0
pipx inject neuralmind graphifyy
neuralmind --help

# uv
uv pip install neuralmind==0.7.0 graphifyy
neuralmind --help

# Docker
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
docker build -t neuralmind:dev .
docker run --rm neuralmind:dev neuralmind --help

# From source
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
pip install -e .
neuralmind --help
```

All five paths should print the same help output. The
[install-paths walkthrough](docs/use-cases/install-paths.md)
documents what each one costs you (env isolation, PATH behaviour,
persistence trade-offs).

## What's next

v0.8 — **Always-On.** systemd / launchd templates, a `/healthz`
endpoint for `neuralmind serve`, Aider MCP integration, Windows
Task Scheduler doc polish. Tracking issue: [#119](https://github.com/dfrostar/neuralmind/issues/119).

v0.8.x — **Enterprise-Ready.** GHCR / Docker Hub auto-build,
air-gapped install doc, SBOM publication on tagged releases, a
consolidated compliance one-pager. Tracking issue: [#120](https://github.com/dfrostar/neuralmind/issues/120).

## Thanks

Most of the v0.7.0 work was surface-area: bringing existing
documentation up to "five install paths" consistency, drafting a
container image that matches the rest of the project's
local-first / non-root / no-network-at-runtime conventions, and
landing the two deferred review-feedback patches the v0.6.0 merge
train held back. Small release. Sets up the v0.8 always-on story.
