# Upgrading NeuralMind

**How to upgrade, what to check afterwards, and how to roll back.**

---

## Before you upgrade

**Read the release notes** for every version between yours and the new one,
on the [releases page](https://github.com/dfrostar/neuralmind/releases) or in
`docs/releases/` in the repository. Releases that change behavior say so under
**Upgrade notes**.

**Back up the state a build can't recreate.** Most of `.neuralmind/` is
rebuilt from source, but three stores aren't: learned synapses
(`synapses.db`), recorded decisions (`memory.db`), and the audit log
(`audit_events.jsonl`). The
[backup script in the deployment guide](DEPLOYMENT-GUIDE.md#backup--recovery)
copies them safely while an agent is running.

## Upgrade

```bash
pip install --upgrade neuralmind
neuralmind --version

cd /path/to/project
neuralmind build .     # incremental: re-embeds only what changed
neuralmind health .    # exit 0 healthy, 1 stale, 2 no index
```

For the container image, pull the new release tag
(`ghcr.io/dfrostar/neuralmind:vX.Y.Z`) from the releases page.

Then check the install:

```bash
neuralmind doctor .    # graph, index, hooks, MCP, synapses
```

`doctor` always exits 0, so read its output rather than its exit code.

## Moving off the ChromaDB backend

The ChromaDB backend has been deprecated since v0.46.0, and `turbovec` is the
default. If the project's `neuralmind-backend.yaml` has `backend: graph` or
`backend: chroma`:

1. Delete that line, or change it to `backend: turbovec`.
2. Rebuild into the new backend:

   ```bash
   neuralmind build . --force
   ```

3. Once queries look right, delete the old ChromaDB store at
   `.neuralmind/neuralmind_db/`.

Learned synapses and recorded decisions aren't stored in the vector backend,
so they carry over.

NeuralMind has no other backends to migrate to. Backends are chosen only with
`backend:` in `neuralmind-backend.yaml`, and the choices are `turbovec`, the
deprecated `chroma`/`graph`, and `in_memory`. See
[COMPATIBILITY.md](COMPATIBILITY.md#embedding-backend-compatibility).

## Rolling back

```bash
pip install "neuralmind==X.Y.Z"   # the version you upgraded from
```

Then restore `.neuralmind/` from the backup you took before upgrading. An
older version isn't guaranteed to read state that a newer one wrote. After
restoring, run `neuralmind build .` and `neuralmind health .`.

## Upgrading many projects

The package is upgraded once per Python environment. Each project's index
then needs its own build:

```bash
pip install --upgrade neuralmind

for p in "$HOME"/projects/*/; do
    [ -d "$p/.neuralmind" ] || continue
    neuralmind build "$p" && neuralmind health "$p" > /dev/null \
        || echo "check $p"
done
```

## Supported versions

Security fixes land on the latest minor release, and the previous minor gets
critical fixes only. See
[Supported Versions](https://github.com/dfrostar/neuralmind/blob/main/SECURITY.md#supported-versions)
in SECURITY.md.

---

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/dfrostar/neuralmind/issues)
- **Discussions:** [GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions)
- **Docs:** [Setup Guide](https://github.com/dfrostar/neuralmind/wiki/Setup-Guide)
- **Troubleshooting:** [Troubleshooting Guide](https://github.com/dfrostar/neuralmind/wiki/Troubleshooting)
