# NeuralMind v4.18.1 — every file in the package names its license

**Type:** Patch release | **Theme:** machine-readable licensing; nothing changes in behaviour

NeuralMind ships under two licenses: MIT for the core and the Commercial
Modules License for `neuralmind/tier2/` ([LICENSING.md](../../LICENSING.md)).
Until now the split was stated in the package metadata and in a LICENSE file in
`neuralmind/tier2/`, but not in the files themselves. A dependency scanner or a
legal reviewer reading an installed file couldn't tell which license it was
under.

From this release every Python file in the package says so in its first lines.

Nothing NeuralMind does changes. You don't need to upgrade unless your license
review reads the installed files.

---

## What changed in the package

**SPDX license tags.** 144 files under `neuralmind/` start with one:

```python
# SPDX-License-Identifier: MIT
```

or, under `neuralmind/tier2/`:

```python
# SPDX-License-Identifier: LicenseRef-NeuralMind-Commercial
```

The tag follows the shebang in the two files that have one (`cli.py`,
`mcp_server.py`). The demo's sample project (`neuralmind/demo_data/sample_project/`)
stays untagged: it stands in for a user's code, and its bundled graph pins each
symbol's line number, which a tag line would shift.
`tests/test_spdx_headers.py` fails on a missing or wrong tag, so a file moved
into or out of `tier2/` has to change its tag. The package's license
expression stays `MIT AND LicenseRef-NeuralMind-Commercial`.

The root `LICENSE` file still opens with a notice paragraph before the MIT
text, so GitHub's license detection still reports it as "NOASSERTION"
([#638](https://github.com/dfrostar/neuralmind/issues/638) stays open for that).

**`neuralmind data-locations` runs git by its full path.** It finds the git
hooks directory with `git rev-parse`, which it now runs by the absolute path
found on `PATH` at the time, rather than by name. The output is unchanged; with
no git installed it lists no git hook blocks, as before. This closes three
low-severity Bandit code-scanning alerts on the call.

## What changed around the package

These don't change what you install.

- **Type checking fails CI on new errors.** mypy ran in CI as advice, so the
  error count could only grow. It now runs against
  `scripts/mypy-baseline.txt`, the 305 errors mypy 2.4.0 reports today: an
  error not on the list fails CI, and so does a listed one that's gone until
  the list is lowered, so the count can only fall. See
  [SDLC policy §2.3](../compliance/SDLC_POLICY.md).
- **An incident response tabletop kit.**
  [`INCIDENT_TABLETOP.md`](../compliance/INCIDENT_TABLETOP.md) is a one-hour
  exercise for testing the [incident response plan](../compliance/INCIDENT_RESPONSE.md):
  a critical flaw in a dependency, then a leaked CI credential, in four timed
  parts with a record to fill in.
- **Federal attestation, corrected.** OMB M-26-05 (January 23, 2026) rescinded
  M-22-18 and M-23-16, the memos that had federal agencies collect CISA's
  Secure Software Development Attestation Form. Each agency now sets its own
  requirements and may still ask for that form, its own attestation, or an
  SBOM. [`SSDF.md`](../compliance/SSDF.md), [`NIST.md`](../compliance/NIST.md),
  the [compliance summary](../COMPLIANCE-SUMMARY.md) and
  [About](../about.html) no longer say agencies must collect the form.

## What your agent sees

The same as v4.18.0.

## Upgrading

```bash
pip install -U neuralmind
```

To see the tags in the installed package:

```bash
python - <<'EOF'
import pathlib, neuralmind
root = pathlib.Path(neuralmind.__file__).parent
for path in sorted(root.rglob("*.py"))[:5]:
    print(path.relative_to(root.parent), next(
        (l for l in path.read_text("utf-8").splitlines()[:2] if "SPDX" in l), None))
EOF
```

## Reproduce

```bash
pytest tests/test_spdx_headers.py tests/test_check_mypy_baseline.py tests/test_data_locations.py -v
```

## Related

- [LICENSING.md](../../LICENSING.md): which license covers what
- [v4.18.0 release notes](RELEASE_NOTES_v4.18.0.md): `neuralmind data-locations`
- [SSDF evidence](../compliance/SSDF.md)
