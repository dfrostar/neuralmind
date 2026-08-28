# Agent Zero `a0-plugins` submission

`neuralmind/` is the ready-to-submit index entry for
[agent0ai/a0-plugins](https://github.com/agent0ai/a0-plugins), the
community registry surfaced inside Agent Zero. It has never been submitted
(verified 2026-08-27: no entry, no open or closed PR, no dfrostar activity
in that repo), so this directory is staged, not live.

## What the registry actually takes

The registry is an **index only** — one folder per plugin containing
`index.yaml` and an optional thumbnail. It is *not* where `plugin.yaml`
goes: their CI fetches the `github` URL from `index.yaml` and requires
`plugin.yaml` at that repository's root, with a `name` that exactly matches
the index folder name. Ours: `name: neuralmind` ↔ `plugins/neuralmind/`.

Their CI limits (validated locally by `tests/test_skill_manifest.py`):

| Rule | Ours |
|------|------|
| `index.yaml` ≤ 2000 chars; only `title`/`description`/`github`/`tags`/`screenshots` | 647 chars, no extra fields |
| `title` ≤ 50 chars, `description` ≤ 500 chars | 39 / 480 |
| `tags` ≤ 5 strings | 5 |
| Thumbnail square, ≤ 20 KB | 288×288, ~19 KB |
| Folder name `^[a-z0-9_]+$`, one plugin per PR, no extra files | ✓ |

## How to submit

1. Fork `agent0ai/a0-plugins`.
2. Copy `integrations/a0-plugins/neuralmind/` to `plugins/neuralmind/` in
   the fork — the folder must contain **only** `index.yaml` and
   `thumbnail.png`.
3. Open a PR adding exactly that one folder. Their CI validates first, then
   a human maintainer reviews. A PR failing checks with 7+ days of no
   activity is auto-closed.

## Claims

Every number in `index.yaml` must trace to `site/claims.json` (the 12-50×
range is the published real-repo positioning). The description was written
after this directory's draft-era wording carried an unsourced "12-70×" —
see the claims gate in `tests/test_site_claims.py`, which now scans registry
manifests too. Change `claims.json` first, copy second.
