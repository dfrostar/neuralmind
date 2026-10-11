# NeuralMind v4.13.0 — the index stays fresh after pulls, merges, branch switches and rebases, and the git hooks work whatever PATH the git client has

**Type:** Minor release | **Theme:** `neuralmind init-hook` keeps the index in step with the checked-out tree — not only with local commits — without making git wait, and without touching throwaway worktrees

Until now `init-hook` installed one rebuild hook, `post-commit`. A `git pull`
that brought in merged work, a branch switch, a merge or a rebase changed the
files on disk without a local commit, and the index went on describing the old
tree until the next one, with nothing to say so. The hook also found
`neuralmind` with `command -v`, so a git client whose PATH lacks the install
directory — GUI clients, IDEs, agents started by launchd or systemd, with
pipx and venv installs living in `~/.local/bin` — skipped it without a word.
And every commit waited for the rebuild. The field report is #630.

---

## What changed

### Git hooks

- **Pulls, merges, branch switches and rebases rebuild the index.**
  `init-hook` now also installs `post-merge` (merges and pulls),
  `post-checkout` (only a branch checkout that lands on a different commit:
  file checkouts and `git checkout -b` from the current commit don't rebuild)
  and `post-rewrite` (rebases and amends). `post-commit` keeps its decision
  scan, which runs synchronously because it reads HEAD.
- **The hooks work from any git client.** `init-hook` resolves the
  `neuralmind` path when you run it and writes it into the hooks, with
  `command -v neuralmind` as the fallback, so a commit from a client whose
  PATH lacks it still rebuilds. It prints the path it baked in, and says so
  when it found none. The pre-commit drift guard uses the same path, so it no
  longer skips silently either; `--strict` still blocks the commit on a drift.
- **git doesn't wait.** The rebuild runs in the background and logs to
  `.neuralmind/hook-build.log`. A lock in `.neuralmind/` serializes builds:
  an event that arrives while one runs leaves a pending flag and the running
  build goes round once more, so a burst of events (a rebase, a pull right
  after a commit) costs at most one extra build, and an event that lands
  while the lock is being released still gets its build. The lock records
  the build's PID, so a lock left by a build that died is cleared on the next
  event, while a build that runs for over an hour keeps its lock. The hooks
  don't stop an existing hook that runs under `set -e`. `--sync` keeps the
  foreground rebuild.
- **Throwaway worktrees are left alone.** Linked worktrees share a
  repository's hooks (#316). The hooks now rebuild only a project that has
  been built — `.neuralmind/build_status.json`, the same test the session
  hooks use, because those create `.neuralmind/` in any repository they run
  in. A worktree gets rebuilds once someone runs `neuralmind build` there,
  and not before. The decision scan keeps its own precondition: a decision
  store to scan.
- Each block still sits between the `neuralmind-hook-start` / `-end`
  sentinels, contains no `exit`, and runs after whatever the hook already
  held (git-lfs installs `post-checkout` and `post-merge`), so other tools'
  hooks keep working.

## What the agent actually sees

The index an agent queries matches the checked-out tree after a pull, branch
switch, merge or rebase, not only after a local commit. A commit an agent
makes returns before the rebuild finishes, and the hook prints one line —
`[neuralmind] Rebuilding the index in the background (log: ./.neuralmind/hook-build.log)` —
instead of the two it printed around a foreground rebuild. A commit in a
worktree nobody built prints nothing from NeuralMind.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | The index follows git operations, not only commits; commits it runs return before the rebuild; no Claude Code hook, MCP tool or response field changed |
| Cursor / Cline / Continue (MCP) | Same |
| Hermes-Agent plugin | Same |
| Generic MCP client | Same |

## Upgrading

- **Re-run `neuralmind init-hook .`** in each repository to get the new
  hooks; the managed blocks are replaced in place.
- **Build once first.** The hooks rebuild only a built project; in a
  repository that has never been built, run `neuralmind build .` (`init-hook`
  warns when there is no index yet).
- **The rebuild no longer blocks the commit.** A script that commits and then
  queries straight away may see the previous build until the background one
  finishes. `neuralmind init-hook . --sync` keeps the foreground rebuild.
- Re-run `init-hook` after moving or reinstalling NeuralMind so the hooks
  name the new path; until then they fall back to PATH.
- No index format change.

## Reproduce

```bash
pytest tests/test_init_hook_lifecycle.py -v
```

The end-to-end tests drive real git with a fake `neuralmind` that records its
calls, a PATH that cannot find it, and a deliberately slow build: git returns
before the build ends, each new trigger rebuilds, a file checkout doesn't, a
burst of three commits costs two builds, a dead build's lock is cleared, and a
worktree whose `.neuralmind/` a session hook created is left alone while the
main checkout rebuilds.

## Related

- #630 — the field report this release fixes
- #316 — worktrees and NeuralMind state
- [CLI reference: `init-hook`](../wiki/CLI-Reference.md#init-hook)
- [Branch-isolated memory](../use-cases/branch-isolated-memory.md)
