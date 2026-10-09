# Upgrading NeuralMind

**How to upgrade, what to check afterwards, and how to roll back.**

---

## Before you upgrade

**Read the release notes** for every version between yours and the new one,
on the [releases page](https://github.com/dfrostar/neuralmind/releases) or in
`docs/releases/` in the repository. Releases that change behavior say so under
**Upgrade notes**.

**Snapshot `.neuralmind/`.** A build can recreate most of it, but not learned
synapses (`synapses.db`), recorded decisions (`memory.db`), or the audit log
(`audit_events.jsonl`). Rolling back also needs the index files the older
version wrote. First stop everything that opens the project's stores: agents
running `neuralmind-mcp`, `neuralmind watch`, `neuralmind serve`, and
`neuralmind daemon`. Then copy the whole directory:

```bash
cp -a .neuralmind .neuralmind.pre-upgrade
```

With nothing running, each SQLite database and its write-ahead log are copied
as a matching pair. The snapshot holds query text and indexed source, so
protect it like the source tree. For routine backups while agents are
running, use the
[backup script in the deployment guide](DEPLOYMENT-GUIDE.md#backup--recovery)
instead.

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

`doctor` exits 1 when any check fails and 0 otherwise (warnings don't fail
it), so a script can gate on it. v0.55.0 through v4.11.1 always exited 0: if
you're upgrading from one of those, a script that ran `doctor` under `set -e`
now stops on a failed check, and on those versions you read
`neuralmind doctor . --json`'s `status` field (`ok` / `warn` / `fail`)
instead.

## Moving off the ChromaDB backend

The ChromaDB backend has been deprecated since v0.46.0, and `turbovec` is the
default. turbovec installs on Linux, macOS arm64, and Windows AMD64. On other
platforms, such as Intel macOS, ChromaDB is still the only on-disk backend,
so keep `backend: chroma` there.

Elsewhere, if the project's `neuralmind-backend.yaml` has `backend: graph` or
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

An older version isn't guaranteed to read state that a newer one wrote, so
roll back the package and `.neuralmind/` together. Stop everything that opens
the project's stores, as above, then:

```bash
# 1. Save audit records written since the upgrade, while the newer version is
#    still installed. --since compares against UTC timestamps.
neuralmind audit export . --since 2026-10-04T15:00:00 -o audit-after-upgrade.jsonl

# 2. Reinstall the version you upgraded from
pip install "neuralmind==X.Y.Z"

# 3. Swap the snapshot back in, keeping the upgraded state aside
mv .neuralmind .neuralmind.upgraded
cp -a .neuralmind.pre-upgrade .neuralmind

# 4. Catch the index up with the code, and check it
neuralmind build .
neuralmind health .
```

Synapses learned and decisions recorded after the upgrade stay in
`.neuralmind.upgraded/`. The older version may not be able to read them.

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
