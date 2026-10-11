# NeuralMind v4.15.0 — `scan-for-secrets` scans what you can commit, once: linked worktrees skipped, `.gitignore` honoured, each finding marked tracked or not

**Type:** Minor release | **Theme:** a secret scan whose findings you can act on — no repeats, no noise from files git never sees, and the one fact that decides urgency on every line

A 12-repository field audit (#635) found `neuralmind scan-for-secrets` hard
to read in the repositories that need it most. Repositories that keep their
worktrees inside the checkout (`.worktrees/<id>/`, `.claude/worktrees/<id>/`)
got every finding once per worktree, which buried the real ones. And none of
the HIGH findings across the 12 repositories was a committed secret: they
were an untracked `.env`, a Firebase client config and an environment lookup
with a localhost default. `build` already left those worktrees out (they were
gitignored), so the scan and the index disagreed about what the project is.

---

## What changed

- **Linked worktrees are skipped.** A directory whose `.git` is a file
  naming a `git worktree add` checkout is another copy of a repository, so
  the scan no longer walks it, whether or not `.gitignore` covers it. The
  report lists what it skipped. Submodules, which also have a `.git` file,
  and nested repositories are still scanned: they are separate code, and
  `build` indexes them.
- **`.gitignore` is honoured by default.** Inside a git repository the scan
  covers what `build` indexes, from the same `git ls-files` listing: tracked
  files and untracked files that `.gitignore` doesn't exclude. Ignored files
  can't be committed and aren't indexed. **`--include-ignored`** scans them
  too, for a full sweep. Outside a repository the scan reads everything, as
  before.
- **A clean scan says what it left out.** The text output ends with the
  worktrees and the number of gitignored files it skipped, with the flag that
  scans them, so a skipped `.env` is never a silent all-clear.
- **Each finding says whether git tracks its file.** `[tracked]` or
  `[untracked]` on each line, `"tracked": true | false` in `--json` (`null`
  outside a repository), and the summary counts high-confidence findings in
  tracked files. A credential in a tracked file is already in history, or one
  commit from it: rotate that one first.

Exit codes are unchanged: any high-confidence finding exits 1, so a CI gate
behaves as before on what it scans. The legacy `.neuralmind/last_output.json`
cache is still scanned explicitly, and `.neuralmindignore` still applies only
with `--use-neuralmindignore`.

## What the agent actually sees

An agent that runs the scan, or reads its output from a hook or CI log, gets
each finding once, labelled:

```
NeuralMind secret scan — /home/dev/myproject

  [HIGH ] src/config.py:8  aws-access-key-id  (AKIA…(20 chars))  [tracked]
  [HIGH ] scratch.py:1  anthropic-api-key  (sk-a…(108 chars))  [untracked]

  2 high-confidence (1 in tracked files), 0 heuristic.

  ...
  A credential in a tracked file is in git history: rotate it first.

  Skipped 2 linked worktrees (.claude/worktrees/a1, .worktrees/b2): other checkouts of a repository; run the scan inside one to check it.
  Skipped 1 file that .gitignore excludes (never committed or indexed). --include-ignored scans them too.
```

`--json` adds `tracked` to each finding and `gitignore_respected`,
`ignored_files_skipped` and `skipped_worktrees` to the report.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Nothing at runtime; `scan-for-secrets` is a CLI command. Its worktrees under `.claude/worktrees/` no longer repeat findings |
| Cursor / Cline / Continue (MCP) | Same |
| Hermes-Agent plugin | Same |
| Generic MCP client | Same |

## Upgrading

- **A gitignored file with a credential is no longer reported by default.**
  A CI step that relied on the scan failing on an ignored, uncommitted file
  (a `.env` written by an earlier step, say) should add `--include-ignored`.
  The report still counts the ignored files it skipped.
- A script that reads `--json` sees the new fields; none were removed.
- No index change, no rebuild.

## Reproduce

```bash
pytest tests/test_secret_scan_scope.py tests/test_secret_scan.py -v
```

`tests/test_secret_scan_scope.py` drives real git: two linked worktrees
inside the checkout are skipped and listed, a submodule and a nested
repository are still scanned, a gitignored `.env` is skipped and counted (and
found with `--include-ignored`), and each finding's `tracked` matches what
git tracks.

## Related

- #635 — the issue this release fixes
- #640 — the 12-repository field audit it came from
- [CLI reference: `scan-for-secrets`](../wiki/CLI-Reference.md#scan-for-secrets)
