# Keep decision memory honest across commits

**Best for:** teams, and agents, that record architecture decisions with
`neuralmind decisions record` or the MCP decision tools, and want a decision to
stop steering edits once the code it describes has moved on.

**Primary goal:** a decision goes STALE as soon as a commit changes what it
describes, your agent is warned before it edits that code, and a decision that
still holds is one command away from ACTIVE again (v4.6.0+).

A recorded decision is a claim about code at a point in time: "sessions live in
Postgres because…". Once someone moves sessions to Redis, the rationale is
history, and an agent that still trusts it will "fix" the new code back toward
the old design. Before v4.6.0 a decision went stale only when someone ran
`neuralmind decisions invalidate`. Now the commit history retires it.

---

## 1. Set up once

```bash
neuralmind init-hook .       # post-commit: decisions scan, then index rebuild
neuralmind install-hooks .   # Claude Code: the PreToolUse stale-decision guard
```

On a checkout where you ran `init-hook` before v4.6.0, run it again: it
replaces its managed block in `.git/hooks/post-commit` in place and leaves other
tools' hook lines alone.

## 2. Record a decision when you make it

```bash
neuralmind decisions record \
  --title "Sessions live in Postgres" \
  --rationale "One datastore to back up and fail over; session reads are a small share of load" \
  --files auth/session.py auth/middleware.py
```

Agents can do the same over MCP with `neuralmind_record_decision`. Name files
relative to the project root (absolute paths work too). Later questions find it
by meaning as well as by its words (v4.7.0+): see
[Find the decision behind the code when you don't know its words](./find-decisions-by-meaning.md).

Recording before you commit is fine. Recording fingerprints each file with its
git blob id. When the commit stores exactly those blobs, it carries the code
the decision describes, so it leaves the decision ACTIVE, however quickly you
commit. Edit one of those files again first and the commit marks it STALE.

## 3. Commit: stale decisions are reported

Months later someone moves sessions to Redis and commits:

```
$ git commit -am "Move sessions to Redis"
[neuralmind] 1 decision(s) marked STALE by commit 3f9c2ab:
  - Sessions live in Postgres (5b1e0c7a-…) — commit 3f9c2ab changed auth/session.py since this decision was recorded
  Review: neuralmind decisions audit --stale   Still valid? neuralmind decisions restore <id>
[neuralmind] Rebuilding neural index...
```

The reason is kept on the decision itself (`Marked STALE: commit 3f9c2ab
changed auth/session.py since this decision was recorded` in its evidence), and
any decision that lists it in `dependency_constraints` goes STALE with it.

## 4. Your agent is warned before it edits

The next time Claude Code is about to edit `auth/session.py`, the PreToolUse
guard adds this to its context. It never blocks the edit:

```
[neuralmind stale-guard] 1 decision(s) governing auth/session.py are no longer ACTIVE. Their rationale may not hold — verify before relying on them:
- [STALE] Sessions live in Postgres (id 5b1e0c7a-…, confidence 1.00, updated 2026-10-03): One datastore to back up and fail over; … — commit 3f9c2ab changed auth/session.py since this decision was recorded
If a STALE decision still holds after you check the code, `neuralmind decisions restore <id>` re-anchors it to HEAD.
```

## 5. Still true? Restore it. Not true? Retire it.

```bash
neuralmind decisions audit --stale                                     # what went stale
neuralmind decisions restore 5b1e0c7a-…                                # still holds: ACTIVE again, anchored to HEAD
neuralmind decisions invalidate 5b1e0c7a-… --reason "sessions moved to Redis"   # no longer holds
neuralmind decisions record --title "Sessions live in Redis" …        # and record the new one
```

`restore` and `invalidate` take the full id that `scan`, `audit` and the guard
print.

## How the scan decides

| Situation | Result |
|---|---|
| A commit stores a file the decision names differently from how the decision saw it | **STALE**. Any change counts; there is no diff analysis |
| The commit stores every changed file exactly as the decision saw it (its fingerprints, taken when it was recorded, amended or restored) | Stays ACTIVE: this commit carries the decision |
| The decision is anchored to the new commit itself | Stays ACTIVE |
| The decision has no fingerprint for a changed file (recorded before v4.6.0, or the file didn't exist yet) | **STALE** |
| A file is deleted or renamed | STALE (both sides of a rename count) |
| A merge commit | Everything it brought into the branch counts |
| Project in a subdirectory of the repository, or a linked worktree | Works; `init-hook` names the project by its path from the repository root |
| Another decision depends on a stale one | STALE too (cascade) |

Run it by hand any time with `neuralmind decisions scan .`
(`--json` for scripts). It never creates a decision store in a project without
one, and it always exits 0, so it can't fail the commit it follows.

## Limits

- **Conservative by design.** A whitespace change to `auth/session.py` marks
  the decision STALE too. That's the point: a false alarm costs one
  `restore`, a missed one lets stale rationale steer an edit.
- **Pulls and rebases don't run post-commit hooks.** A decision whose files
  changed only in commits you pulled stays ACTIVE until one of your own
  commits touches those files.
- **Exact paths.** A decision that names a directory isn't matched by changes
  to files inside it. List the files.

## Turn it off

`NEURALMIND_DECISION_SCAN=0` makes the scan a no-op. To remove it from the git
hook, delete the `neuralmind decisions scan` line from the managed block in
`.git/hooks/post-commit`.

## Related

- [Release notes v4.6.0](../releases/RELEASE_NOTES_v4.6.0.md)
- CLI reference: [`decisions`](../wiki/CLI-Reference.md#decisions-v410) ·
  [`decisions scan`](../wiki/CLI-Reference.md#decisions-scan-v460) ·
  [`init-hook`](../wiki/CLI-Reference.md#init-hook)
- [Decision provenance](./decision-provenance.md) — the lighter-weight
  alternative: a `Decision:` trailer in the commit message, recalled with
  `neuralmind why`
