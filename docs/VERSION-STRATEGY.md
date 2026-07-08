# NeuralMind Version Strategy

**Status:** Active
**Version:** 0.41.x (current)
**Support Policy:** Semantic Versioning (SemVer), automated via release-please

---

## Versioning Scheme

NeuralMind uses **Semantic Versioning**: `MAJOR.MINOR.PATCH`.

```
v0.41.0
 │  │ └─ PATCH: bug fixes, security patches
 │  └─── MINOR: new features (and, while pre-1.0, occasional breaking changes)
 └────── MAJOR: reserved for the 1.0 stability guarantee
```

While the project is pre-1.0, release-please is configured with
`bump-minor-pre-major: true` (`release-please-config.json`), so `feat:` commits
bump the **minor** version and breaking changes are called out in the release
notes rather than forcing a `1.0` bump. A `1.0` release will mark the point at
which the CLI / MCP tool surface carries a stability guarantee.

---

## How releases actually happen (automated)

**Do not bump versions or edit `CHANGELOG.md` by hand — release-please owns
both.** The flow, per [`CLAUDE.md`](../CLAUDE.md) and the workflows in
`.github/workflows/`:

1. Land work as Conventional-Commit `feat:` / `fix:` commits on `main`.
2. **release-please** (`release-please.yml`) opens/updates a release PR that
   bumps `pyproject.toml` `[project].version`, updates
   `.release-please-manifest.json`, and writes `CHANGELOG.md` from the commit
   bodies.
3. Merging that PR tags `vX.Y.Z`, which fires:
   - **PyPI publish** (`release.yml`) via **OIDC trusted publishing** — no
     stored token; a `validate-version` job enforces that the tag matches
     `pyproject.toml`.
   - **GHCR publish** (`docker-publish.yml`) — multi-arch (`linux/amd64` +
     `linux/arm64`); `:latest` excludes pre-releases.
   - **SBOM** (`sbom.yml`) — a CycloneDX SBOM attached to the GitHub Release.
4. Documentation + SEO for a user-facing change ships in the **same PR as the
   feature** (the five-surface checklist in `CLAUDE.md`), not as a follow-up.

The single source of truth for the version is `pyproject.toml`;
`.release-please-manifest.json` mirrors it, and `release.yml` fails the release
if the tag disagrees.

---

## Breaking Changes Policy

**A breaking change is:**
- Removing or renaming a command, flag, or MCP tool
- Changing an output format (CLI or MCP) in a non-backward-compatible way
- Changing required dependencies or the minimum Python version
- Changing a default behaviour that callers rely on

**When shipping one (pre-1.0):**
1. Prefer a deprecation window — keep the old surface working for at least one
   minor release with a warning (e.g. `neuralmind learn` is retained as a
   deprecated no-op).
2. Mark the commit `feat!:` / include a `BREAKING CHANGE:` footer so
   release-please surfaces it prominently in the notes.
3. Provide migration guidance in the release notes.

Behaviour is gated via **environment variables**, not a feature-flag config
file (see `SECURITY.md` for the full off-switch inventory), e.g.
`NEURALMIND_BYPASS=1`, `NEURALMIND_SYNAPSE_INJECT=0`, `NEURALMIND_BM25=0`,
`NEURALMIND_REUSE_FEEDBACK=0`.

---

## Dependency Management

### Runtime dependencies (`pyproject.toml`)

| Package | Constraint | Role |
|---------|-----------|------|
| Python | `>=3.10` | Baseline (tested 3.10–3.12) |
| `mcp` | `>=1.27.2` | MCP server (base dependency; `[mcp]` extra is a no-op alias) |
| `turbovec`, `onnxruntime`, `tokenizers` | `>=0.7` / `>=1.16` / `>=0.15` | Default ChromaDB-free vector backend (platform-gated) |
| `chromadb` | `>=0.4.0` | Fallback backend on platforms without a turbovec wheel; opt-in elsewhere via `[chromadb]` |
| `numpy` | `>=1.20` | Vector math |
| `tree-sitter` + 10 grammars | `>=0.21` (PHP `>=0.22`) | Built-in graph backend (`graphgen.py`) |
| `pyyaml`, `toml` | `>=6.0` / `>=0.10` | Config parsing |

A pinned reproducible set lives in [`requirements-pinned.txt`](../requirements-pinned.txt),
annotated with CVE rationale where a version is held.

### Optional extras

| Extra | Contents | Use |
|-------|----------|-----|
| `[chromadb]` | `chromadb>=0.4.0` | Force the ChromaDB backend |
| `[mcp]`, `[turbovec]` | _(empty)_ | Back-compat aliases — the packages are now base deps |
| `[dev]` | pytest, black, ruff, mypy, pre-commit, … | Development / testing |
| `[all]` | everything | Convenience |

Dependabot (`.github/workflows` / `dependabot.yml`) watches pip + GitHub Actions
weekly; a dedicated `chromadb-cve-watch.yml` tracks the held ChromaDB CVE.

---

## Security Updates

Critical security fixes ship as PATCH releases as soon as an upstream fix is
available. When no fixed version exists (as with the current ChromaDB CVE), the
mitigation and reachability analysis are documented in `SECURITY.md` and
`requirements-pinned.txt`, and the CVE-watch workflow flags the moment a patched
release lands.

---

## Support Timeline

The latest published release is the supported one. Because releases are frequent
minor bumps and upgrades are non-breaking within the pre-1.0 line, there is no
separate LTS branch to maintain. Users pin exact versions for reproducibility via
`requirements-pinned.txt` and upgrade with `pip install -U neuralmind`.

A formal support window and stability guarantee are planned for the **v1.0**
release; see [`ROADMAP.md`](../ROADMAP.md).
