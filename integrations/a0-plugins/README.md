# Agent Zero `a0-plugins` submission

`neuralmind/` is the index entry for
[agent0ai/a0-plugins](https://github.com/agent0ai/a0-plugins), the
community registry surfaced inside Agent Zero's in-app Plugin Hub.

**Status (verified 2026-09-09): merged and listed.**
[agent0ai/a0-plugins#499](https://github.com/agent0ai/a0-plugins/pull/499)
was merged on 2026-08-31 (merge commit `ff281d5`, by maintainer 3clyp50,
with no formal review — their practice is validate-then-merge).
`plugins/neuralmind/` is on their `main`, and the generated `index.json`
release asset that Agent Zero's Plugin Hub fetches at runtime carries the
entry, so it is visible in the app's Plugins → Browse tab today. The
registry auto-opened
[agent0ai/a0-plugins#505](https://github.com/agent0ai/a0-plugins/discussions/505)
as the plugin's discussion thread.

**Wording rule.** NeuralMind may be described as *listed in Agent Zero's
Plugin Hub*. Do not say it *works out of the box* there. The Hub's Install
button clones this repository into `usr/plugins/neuralmind/` and nothing
else: no `pip install`, no MCP registration (`plugin.yaml` is metadata only
and there is no `hooks.py`). What the clone does contribute is the
`skills/` directory, which Agent Zero scans for `SKILL.md` files — so the
portable skill (and anything else under `skills/`) becomes an Agent Zero
skill. The MCP server is still wired by hand: `pip install neuralmind`
where Agent Zero runs, then Settings → MCP → External MCP Servers pointed
at `neuralmind-mcp`, as `index.yaml` itself says.

## Where the listing text lives

This directory mirrors the **merged** entry byte-for-byte. During review the
listing was changed on the fork side (commits `6f48388` and `2ffb96d`,
2026-08-29/30: the description was folded into a `>-` block and the network
claim scoped to name the one-time embedding-model download), and those
changes were not back-ported here until 2026-09-09. Keep the two in step in
this direction:

1. Edit `neuralmind/index.yaml` here first (the claims gate below scans it).
2. Open a **new** single-folder PR against `agent0ai/a0-plugins` replacing
   `plugins/neuralmind/` — the merged fork branch no longer updates
   anything. Their CI validates, a maintainer merges, and `index.json` is
   regenerated automatically on merge.

**Keep the description a folded block (`>-`).** The single-line form failed
their `yaml.safe_load` — `Local-first: no telemetry` inside a plain scalar
is a nested-mapping error (a0-bot on #499, 2026-08-29) — and
`tests/test_skill_manifest.py` rejects a plain scalar containing `: ` for
the same reason.

## What the registry actually takes

The registry is an **index only** — one folder per plugin containing
`index.yaml` and an optional thumbnail. It is *not* where `plugin.yaml`
goes: their CI fetches the `github` URL from `index.yaml` and requires
`plugin.yaml` at that repository's root, with a `name` that exactly matches
the index folder name. Ours: `name: neuralmind` ↔ `plugins/neuralmind/`.

Their CI limits (validated locally by `tests/test_skill_manifest.py`):

| Rule | Ours |
|------|------|
| `index.yaml` ≤ 2000 chars; only `title`/`description`/`github`/`tags`/`screenshots` | 676 chars, no extra fields |
| `title` ≤ 50 chars, `description` ≤ 500 chars | 39 / 492 |
| `tags` ≤ 5 strings | 5 |
| Thumbnail square, ≤ 20 KB | 288×288, ~19 KB |
| Folder name `^[a-z0-9_]+$`, one plugin per PR, no extra files | ✓ |

The entry carries no `version`, `stars`, or `updated` fields (most entries
don't), so inside the Hub it never appears under the *New* or *Popular*
filters and the Hub cannot offer an update for it — users find it via
search, the `mcp` tag, or the *All* list.

## Claims

Every number in `index.yaml` must trace to `site/claims.json` (the 12-50×
range is the published real-repo positioning). The description was written
after this directory's draft-era wording carried an unsourced "12-70×" —
see the claims gate in `tests/test_site_claims.py`, which now scans registry
manifests too. Change `claims.json` first, copy second.
