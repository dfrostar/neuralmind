# Install NeuralMind anywhere

NeuralMind ships through five install paths. They all deliver the
same package — the `neuralmind` CLI, the `neuralmind-mcp` server, and
the Python module. Pick the one that fits how you already manage
Python on this machine.

> tl;dr: **pipx** for "always on PATH", **uv** for speed, **pip** for
> the default, **Docker** for "no Python on the host", and **source**
> for hacking on NeuralMind itself.

> **v0.15.0+:** `graphifyy` is now **optional**. NeuralMind ships a
> built-in tree-sitter graph backend, so `pip install neuralmind` alone
> can build an index — no second tool to install. The commands below add
> `graphifyy` only where you want graphify's richer graph (it takes
> priority where present). Drop it for the leanest install.

---

## 1. `pip` — the default

```bash
pip install neuralmind            # built-in tree-sitter backend, no graphify needed
# pip install neuralmind   # optional: add graphify's richer graph
```

Drops into your active environment. Works in venvs, conda envs, system
Python, anywhere `pip` works. If you don't have an opinion, pick this.

**Trade-offs:** the `neuralmind` CLI is only on PATH when that env is
activated. If you switch projects/envs a lot, `pipx` avoids the
reactivation dance.

---

## 2. `pipx` — global CLI, isolated env

```bash
pipx install neuralmind

# Optional — only if you want the graphify backend:
pipx inject neuralmind graphifyy
```

`pipx` puts each Python application in its own dedicated venv and
symlinks the entry points onto your PATH. `neuralmind` and
`neuralmind-mcp` are then available from any directory without
activating anything.

**Trade-offs:** you can't `import neuralmind` from your project's own
Python — pipx isolates the env. If you only ever invoke the CLI / MCP
server, that's not a problem; if you also script against the Python
API, use `pip` instead.

---

## 3. `uv pip` — fast, modern

```bash
uv pip install neuralmind
```

[uv](https://docs.astral.sh/uv/) is the Rust-based Python package
manager from Astral. Installs are ~10× faster than `pip` once the
resolver kicks in, and the disk format is compatible — your existing
venv works.

If you have a `pyproject.toml` or `uv` project, prefer:

```bash
uv add neuralmind
```

**Trade-offs:** `uv` is newer; some corporate Python policies still
require `pip`. The output is identical, so the choice is purely about
your tooling preference.

---

## 4. Docker — no Python on the host

```bash
# Pull (once a release is on GHCR)
docker pull ghcr.io/dfrostar/neuralmind:latest

# Or build locally from this repo
docker build -t neuralmind:dev .

# Build the index. Mount the project read-write, at the path the agent uses
docker run --rm -v "$PWD:$PWD" \
  ghcr.io/dfrostar/neuralmind \
  neuralmind build "$PWD"

# Run the MCP server over stdio. It takes no arguments: each tool call
# names its own project_path, so the container must resolve the same path
docker run --rm -i -v "$PWD:$PWD" \
  ghcr.io/dfrostar/neuralmind \
  neuralmind-mcp

# Run the graph view, published on the host's loopback only
docker run --rm -p 127.0.0.1:8787:8787 -v "$PWD:$PWD" \
  ghcr.io/dfrostar/neuralmind \
  neuralmind serve "$PWD" --host 0.0.0.0 --no-browser
```

The image is multi-stage: a `builder` stage produces the wheel; the
`runtime` stage is a slim Python image with `neuralmind` installed
and a non-root user. The `Dockerfile` lives in the repo root.

**Trade-offs:** the mount has to be writable. NeuralMind keeps its index
in the project's `.neuralmind/` on the host, so it persists between
runs, and the MCP server appends to its audit log on every tool call, so
on a read-only mount every call fails. The image doesn't bundle the
embedding model, so each fresh container downloads it on its first
build; the [deployment guide](../DEPLOYMENT-GUIDE.md#option-2-container-image-ghcr)
shows how to mount a pre-extracted one.

`serve` prints its URL with a token (`http://0.0.0.0:8787/?token=…`);
open it as `http://127.0.0.1:8787/?token=…`. Inside the container
`--host 0.0.0.0` is what lets Docker forward the port, and publishing on
`127.0.0.1` keeps it off the network. Leave the token on
([security guide](../SECURITY-GUIDE.md#access-control)).

> **Note:** GHCR auto-build lands in Phase 3 (v0.7.x). Today the
> Dockerfile is committed but you build it locally. The pull command
> above works once the auto-publish ships.

---

## 5. From source — for contributors

```bash
git clone https://github.com/dfrostar/neuralmind
cd neuralmind
pip install -e ".[dev]"
```

Editable install with the dev extras. Use this if you're patching
NeuralMind itself or want to run the test suite locally.

---

## Verify any install

The smoke test is the same regardless of install path:

```bash
python -c "import neuralmind; print(neuralmind.__version__)"
neuralmind --help
```

For pipx (no shared Python env), drop the `python -c` line and run
just `neuralmind --version` once that subcommand ships, or
`neuralmind --help`.

Then, from inside a project, run the **install doctor** (v0.12.0+) to
confirm every piece is wired up — code graph, semantic index, synapse
memory, MCP server, Claude Code hooks, query memory — and get the exact
fix for anything that isn't:

```bash
neuralmind doctor .
```

It exits non-zero when a check fails, so a provisioning script or CI step
can gate on it (`neuralmind doctor . && neuralmind wakeup .`). Add
`--json` for a machine-readable snapshot an agent can parse.

---

## Which one should *you* pick?

| You... | Pick |
|---|---|
| Don't have an opinion | `pip` |
| Want `neuralmind` on PATH globally without polluting your active env | `pipx` |
| Already use `uv` | `uv pip` or `uv add` |
| Don't want Python on the host machine | Docker |
| Are contributing code or running the test suite | From source |

All five resolve to the same package. You can switch later without
losing your `.neuralmind/` state — that's on disk in the project, not
in the install.

---

## Related

- [Setup-Guide.md](../wiki/Setup-Guide.md) — full first-time setup
  walkthrough for each integration (Claude Code, Cursor, Cline,
  Continue, Claude Desktop)
- [Scheduling-Guide.md](../wiki/Scheduling-Guide.md) — keep the index
  fresh on a cron / git hook / CI schedule
- [Integration-Guide.md](../wiki/Integration-Guide.md) — VS Code,
  JetBrains, CI/CD wiring
