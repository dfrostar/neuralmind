# Release operations notes

Operational record of release-pipeline incidents and the recovery playbook,
so the next occurrence costs minutes instead of a day.

## 2026-07-21 — release-please version-state corruption

**Symptom:** the release PR proposed `0.37.0` on a repo whose released line
was `1.x`, with a changelog draft reaching back to 0.30-era commits.

**Background:** the v1.4.0 release PR (#388) merged while `release.yml`'s
test job was red (two tests assumed the optional `[chromadb]` extra), so the
dispatched publish failed; the v1.4.0 tag/release were then deleted by hand.
Release-please subsequently lost its version baseline — `pyproject.toml`,
`neuralmind/__init__.py`, and `.release-please-manifest.json` all said
`1.4.0`, but the next release PR was computed from a years-old baseline.

**Fix:** a commit on `main` carrying a `Release-As: 1.5.0` footer (the
commit that added this file). This is release-please's one-shot override:
it rewrites the open release PR to the forced version and leaves no
persistent state behind — unlike `"release-as"` in
`release-please-config.json`, which pins every future release until
removed.

**Playbook when the release PR proposes a wrong version:**

1. Do NOT merge the wrong release PR — it rewrites `pyproject.toml` /
   `CHANGELOG.md` to the wrong version and publishes it to PyPI.
2. Land a commit on `main` whose message ends with a `Release-As: X.Y.Z`
   footer (empty commit is fine: `git commit --allow-empty`).
3. Wait for the next release-please run to rewrite the open release PR;
   verify its title and diff before merging.
4. Never delete a tag/release to "retry" a failed publish — fix the cause
   and re-dispatch `release.yml` with the existing tag instead
   (`gh workflow run release.yml -f tag=vX.Y.Z`). Releases on this repo
   are immutable; deletion is what corrupts release-please's baseline.
