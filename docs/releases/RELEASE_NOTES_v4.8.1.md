# NeuralMind v4.8.1 — installers that can't destroy your config, and the bug-hunt fixes

**Type:** Patch release | **Theme:** Fixes from an end-to-end bug hunt

This release fixes the high- and medium-severity bugs found by testing v4.7.0
end to end. v4.8.0 still has all of them. Two of the eight high-severity ones
could destroy user configuration. A third left credentials in plaintext in the Bash output cache,
under a header that said they had been redacted.

1. **`install-hooks` and `install-mcp` no longer overwrite a config they
   can't parse.** One trailing comma in `~/.claude/settings.json` was enough
   for `install-hooks --global` to replace the file with a bare `hooks` block,
   losing `permissions`, `model` and `env`. `--uninstall` deleted the file.
   `install-mcp` did the same to Cursor, Cline and Claude Desktop configs,
   removing every other MCP server along with the tokens in their `env`.
2. **The Bash output cache redacts what the AWS CLI prints.** It also redacts
   JSON password keys and a few other common shapes it used to miss.
3. **Hooks do nothing in a project you haven't built.** With a global install,
   the prompt hook used to run a full first-time build in whatever directory a
   session opened in. That took minutes on a real repository, far past the
   hook timeout.

The other five: one non-UTF-8 doc no longer fails the build, rebuilds no longer
duplicate doc edges, `watch --reindex` stops serving deleted symbols, and
`neuralmind export .` works without `--output`.

The medium-severity fixes are listed under [What changed](#what-changed). The
ones you're most likely to notice:

- Hooks keep working after the agent runs `cd` into a subdirectory.
- `neuralmind_review`, `neuralmind_impact` and the three neighbour tools no
  longer return `security_denied` under the default roles.
- The graph links calls, Python relative imports and C++ headers to the right
  nodes, and two files whose names differ only in punctuation or case no longer
  share one node.
- `neuralmind savings` stops counting builds and searches as saved queries.
- Negative feedback weakens the association it targets, and a penalty stays in
  place.

---

## What changed

### Installers refuse a config they can't round-trip

- **`install-hooks` (project or `--global`) and `install-hooks --uninstall`**
  now refuse when `settings.json` is not valid JSON, has a top level that isn't
  an object, or has a `hooks` value that isn't an object. The error names the
  file, says why, and leaves the file untouched. Exit code is 1:

  ```text
  Error: Refusing to modify ~/.claude/settings.json: it is not valid JSON
  (Expecting property name enclosed in double quotes: line 5 column 1 (char 94)).
  Fix the file (often a trailing comma), then re-run.
  ```

  An empty file still counts as no settings.
- **`install-mcp`** applies the same rule to every client: Claude Code, Cursor,
  Cline, Claude Desktop and VS Code. The VS Code path already worked this way.
  A config with comments or a trailing comma is reported as `skipped-jsonc`,
  and one whose top level isn't an object as `skipped-not-object`. Either way
  the file is not modified, and the command prints the entry to add by hand:

  ```text
  ✗ claude-desktop: skipped-jsonc → …/claude_desktop_config.json is not strict JSON
  (comments or a trailing comma?); left untouched. Add this entry by hand:
  { "mcpServers": { "neuralmind": { "command": "neuralmind-mcp", "args": [] } } }
  ```

  A skipped client no longer prints ✓ or "Restart the client".

### Secret redaction

These apply wherever redaction runs: the automatic Bash output cache behind
`neuralmind last`, `scan-for-secrets`, and `build --redact-secrets`.

- **AWS CLI JSON.** `aws sts get-session-token` and
  `aws configure export-credentials` print `"SecretAccessKey": "…"` and
  `"SessionToken": "…"`. Only the access-key ID used to be redacted. The
  secret key pattern now accepts quoted keys and the `SecretAccessKey`
  spelling, and a new `aws-session-token` pattern covers `SessionToken` /
  `AWS_SESSION_TOKEN`.
- **Quoted keys in the generic rule.** `{"password": "…"}` and
  `{'api_key': '…'}` are detected. The placeholder and entropy guards are
  unchanged, so `{"password": "changeme"}` and `{"api_key": "${API_KEY}"}`
  still aren't.
- **No leaked tail on bare values.** `DB_PASSWORD=Ab9xQ2mZpL;TAILSECRET99`, as
  `env` prints it, used to keep `;TAILSECRET99` after the marker. A bare value
  now continues through `,` or `;` unless whitespace or a new `key=` follows.
  `password=…,next=x` and `Server=db;Password=…;Database=app` still stop at
  the next key.
- **New high-confidence shapes:** GitLab personal access tokens (`glpat-`),
  Hugging Face tokens (`hf_`), and passwords in `http(s)://user:password@host`
  URLs, the form git remotes carry tokens in.

### Hooks act only in a built project

Every hook action now returns at once, writing nothing, unless the project
already has `.neuralmind/`. That directory exists once `neuralmind build` has
run. Before, a globally installed hook would:

- build a full index from the prompt hook (graph, IR and vectors) in any
  directory with source files;
- create `.neuralmind/` from the session-start, edit, stale-guard, Bash-cache
  and pre-compact actions.

Read dedup already followed this rule. Prompt-time recall also no longer builds
an index in a project that has `.neuralmind/` but no index yet (for example,
one with only decision memory). It loads the existing index or injects nothing.

The project is the nearest directory with `.neuralmind/`, starting from the
directory in the hook payload and going no higher than `$CLAUDE_PROJECT_DIR`.
Claude Code sets that variable for hooks, and the payload's directory follows
the agent's shell. Before, after `cd auth` the hooks treated `auth/` as the
project: they went silent, or, before the built-project rule, wrote a stray
`auth/.neuralmind/`. Without `$CLAUDE_PROJECT_DIR` only the payload's own
directory counts, so an unrelated `.neuralmind/` higher up is never used.

Hooks also fail open as documented. A payload that isn't a JSON object, or a
field of the wrong type, used to exit 1 with a traceback even under
`NEURALMIND_BYPASS=1`. The bypass is now checked before the payload is read,
and any error exits 0. The Read hook now finds the file text where Claude Code
puts it (`tool_response.file.content`), so Read sequences reach the synapse
layer.

### Indexing and retrieval

- **A non-UTF-8 Markdown, SQL, OpenAPI or proto file no longer fails the
  build.** It used to abort the whole build and wrongly tell you to install
  tree-sitter. These files are now decoded like code files: undecodable bytes
  become U+FFFD and the file is still indexed. A UTF-8 BOM no longer hides the
  first heading.
- **Incremental rebuilds no longer duplicate doc and schema edges.** Each
  no-change `neuralmind build` used to append another copy of every edge from
  Markdown and schema files (links 18 → 20 → 22 on a four-file project), and a
  renamed heading kept its old node. Doc and schema files are rebuilt from
  scratch on each build, so repeated builds produce the same graph. Rebuild
  once (`neuralmind build`) to drop duplicates already in your graph.
- **`watch --reindex` no longer serves deleted symbols.** An incremental
  `update_files` removed deleted symbols from the vector store but left the
  keyword (BM25) index and its generation stamp alone. A removed function kept
  coming back at the top of results, in every process, and each load printed a
  false "Index out of step… Run: neuralmind build". It now rewrites the keyword
  index and records the updated graph, as a full build does.
- **`neuralmind export .` works without `--output`.** The default invocation,
  and `--format pdf` without `--output`, crashed with `TypeError`. They now
  write `neuralmind_export.csv` / `.pdf` in the current directory, as
  documented.

### Hooks, installers and the dashboard

- **Default MCP roles can call the read-only lookup tools.**
  `neuralmind_review`, `neuralmind_impact`, `neuralmind_structural_neighbors`,
  `neuralmind_synaptic_neighbors` and `neuralmind_next_likely` were listed by
  `tools/list` but missing from every default role, so they returned
  `security_denied`. The `builder` and `reader` roles now include them. They
  only read, like `neuralmind_query`. A project that defines its own
  `security.roles` keeps exactly the policy it wrote.
- **`install-mcp` keeps a customised entry.** Re-running it used to reset a
  `neuralmind` entry with an absolute venv command (often needed, since MCP
  clients launch servers with a minimal `PATH`) to bare `neuralmind-mcp`, and
  dropped its `env`. An entry that already launches NeuralMind's server is now
  left as written. A stale one is replaced, keeping your other keys. For VS
  Code, settings that already nest `"mcp": {"servers": …}` no longer get a
  second, dotted `"mcp.servers"` key.
- **The dashboard escapes every value it renders.** A file or symbol name from
  an untrusted repository, such as `x" onmouseover="alert(1)" y="`, rendered
  as a live attribute, because quotes weren't escaped. Community ids, synapse
  weights and counts weren't escaped at all.

### Graph building

Run `neuralmind build` once after upgrading to pick these up.

- **Calls belong to the definition they're in.** A call inside `B.run` was
  attributed to `A.run`, the first function with that name. A nested
  function's calls could land on a same-named function in another file.
- **Python imports resolve like Python does.** `from .utils import x` in
  `pkg/a.py` linked the top-level `utils.py`, `from . import utils` linked
  nothing, and src-layout imports never resolved. Relative imports now resolve
  against the importer's package, and an import that climbs above the project
  links nothing.
- **Colliding names get their own nodes.** Ids fold case and punctuation, so
  `api/v1.py` and `api_v1.py` shared one node, as did `docs/安装.md` and
  `docs/使用.md`, and `Foo` / `foo`. Only colliding entities get new ids.
  Every other id is unchanged, so learned associations keep their keys.
- **`.h` headers parse as C++ in a C++ project** (or when the header itself
  uses C++ syntax). They used to go to the C grammar, which lost classes and
  namespaces.
- **The directory walk stays inside the project.** Outside git, it followed
  symlinks to directories elsewhere and recursed on a link like
  `src/loop -> ..`.
- **`.neuralmind.yaml` include/exclude globs apply to schema files** (`.sql`,
  `.proto`, OpenAPI), and to `watch --reindex`, as they already did to code
  and Markdown in a full build.
- **A malformed OpenAPI spec no longer aborts the build.** `title: 2024`, or
  `paths:` written as a list, failed the whole build. The spec now indexes
  what it can, and a file that still can't be read is skipped. The debug log
  names the file and the error type, not the parser's message, which can
  quote the spec's text.
- **A graph node with `"community": null` no longer fails the build.**
  graphify and hand-written graphs can carry it.
- **`.neuralmindignore` matches the way `.gitignore` does in git.** `[Oo]bj/`
  and `*.py[co]` never matched, `/**/gen` matched only at the root, `build/`
  also matched files named `build`, `!logs/keep.py` re-included a file under
  an ignored `logs/`, and escapes such as `\#` and `foo\ ` weren't read. A
  test checks the matcher against `git check-ignore`. The same matcher handles
  `.gitignore` outside a git repository.
- **Incremental builds notice more changes.** A file whose modification time
  went backwards (`mv backup.py a.py`, `cp -p`, a restore) or whose size
  changed is re-checked by content hash. When a new file defines a module or
  symbol that an unchanged file already referenced, that file is re-extracted,
  so its import and call edges appear without a full rebuild.

### Retrieval

- **`query --type code|docs` changes what's returned.** It used to re-boost
  the hits after the context was already built, so the output didn't change.
  It now replaces the detected intent before ranking.
- **`context_budget` trims whole lines from L3, then L2, then L1.** It used to
  cut the context at a character count, mid-word and starting with L0, while
  reporting the untrimmed size. L0 is never trimmed, so a budget smaller than
  L0 returns L0 whole. Hybrid-context highlights now count against the budget
  too.
- **A `--scope` build keeps its own keyword index.** After `build --scope
  docs`, a default query lost its code keyword hits, and `build --scope code`
  deleted the docs index. A non-default scope now writes
  `bm25_unified_index.<scope>.json` and its siblings. The default scope keeps
  its file names, so existing indexes stay valid.
- **A relative `db_path` in `neuralmind-backend.yaml` resolves against the
  project**, not the directory the command runs from. A query from another
  directory used to build a second index there.

### Numbers the CLI reports

- **`neuralmind savings` counts only queries and wakeups.** Builds, searches,
  MCP calls and ingestion each counted as a saved query charged a full
  baseline. An MCP query counted twice. Expect lower totals after upgrading.
  They are the correct ones.
- **`review`, `drift` and `ci-check` work in a monorepo subdirectory.** For a
  project at `services/billing`, git's repo-relative paths were joined onto
  the project path, so `review` said "Looks complete", `drift` checked 0
  symbols and `ci-check` skipped every file.
- **`neuralmind stats` through the daemon reports a built project as built.**
  It said `Built: False` for every project, because the daemon never loaded
  the index before answering.

### Synapse learning

- **Negative feedback works.** `neuralmind_feedback` with `negative`
  decayed the target's edges by their idle time, and those edges had just been
  used, so nothing changed (0.3 became 0.29999998 after ten calls). Each call
  now halves every edge touching the node, and its transitions. Long-term
  edges stop at the 0.20 floor.
- **Penalties stick.** The next decay used to lift a penalized long-term edge
  straight back to the 0.20 floor. The floor now holds only edges at or above
  it.
- **Ephemeral edges decay on the documented 1-day half-life.** They decayed on
  3 days.
- **Learned half-lives follow how often an edge is used per day.** They
  depended only on the lifetime activation count, so 10 uses in 2 days and 10
  in 1,000 days decayed alike.
- **PreCompact no longer erodes hubs.** Hub normalization shrank the same
  edges again on every compaction (1.0 → 0.5 → 0.25 …). It now caps a hub's
  total weight and leaves a hub within the cap alone. A hub above roughly 110
  edges can have long-term edges trimmed below the floor, and those then decay
  like other edges.
- **Rebuilds no longer promote call edges.** Each build counted as another
  activation, so after five builds of an unchanged graph its call paths became
  protected long-term edges. Removed calls kept being re-seeded. Structural
  edges now mirror the current build.
- **Concurrent writers wait instead of failing.** Decay, document seeding, hub
  normalization and synaptic tagging read before writing. When another process
  wrote in between, they failed at once with "database is locked", and tagging
  dropped its update. They now take the write lock first.
- **Edits close together form one batch.** The watcher flushed each file once
  that file alone had been quiet for the debounce window, so edits 0.5 s apart
  arrived one at a time and formed no cross-file associations. The batch now
  flushes once all edits go quiet. A file saved non-stop forces a flush after
  ten windows.

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | With global hooks, the first prompt in an unbuilt repo could block on a full index build until the hook timed out, and `.neuralmind/` appeared in every directory a session ran in. After `cd` into a subdirectory the hooks went silent. `neuralmind_review` after an edit returned `security_denied`. `neuralmind last` could replay AWS session credentials | In an unbuilt repo the hooks do nothing and add no context. In a built one, recall never triggers a build, and the hooks keep working from any subdirectory. `neuralmind_review` and `neuralmind_impact` answer. AWS CLI credentials are redacted in the cache |
| **Cursor / Cline / Claude Desktop** (MCP) | `install-mcp` on a config with a trailing comma removed every other server | The config is left untouched, and the command prints the entry to paste |
| **VS Code** (MCP) | JSONC was already left untouched. A config whose top level wasn't an object was overwritten | Both are left untouched |
| **Generic MCP client** | `neuralmind_review`, `neuralmind_impact` and the neighbour tools returned `security_denied` under the default roles | They answer under `builder` and `reader` |

## Environment variables

None added or changed.

## Upgrade notes

- **If you rely on hooks in a project you never built,** run `neuralmind build`
  there once. Hooks now treat `.neuralmind/` as the opt-in.
- **To clear doc-edge duplicates** left by earlier incremental builds, run
  `neuralmind build` once after upgrading.
- **If `install-hooks` or `install-mcp` now refuses a file,** it has a syntax
  error (usually a trailing comma). Fix the file and re-run, or paste the
  printed entry by hand.
- **Run `neuralmind build` once** to pick up the graph fixes (calls, imports,
  headers, colliding names). Entities whose names collided get new node ids,
  so associations learned for the merged node don't carry over to them.
- **`neuralmind savings` totals drop.** The old totals counted builds,
  searches and MCP calls as saved queries.
- **Check `.neuralmindignore` re-includes.** As in git, `!logs/keep.py` no
  longer brings a file back from under an ignored `logs/`. Write `logs/*`
  instead. Leading spaces in a pattern now count, as they do in git.
- **To keep the old MCP denials,** define `security.roles` for the project.
  The five read-only lookup tools are now in the default `builder` and
  `reader` roles.

## Related

- [CLI reference: install-hooks](../wiki/CLI-Reference.md#install-hooks) ·
  [install-mcp](../wiki/CLI-Reference.md#install-mcp-v0190) ·
  [scan-for-secrets](../wiki/CLI-Reference.md#scan-for-secrets)
- [Security Guide: Secret Management](../SECURITY-GUIDE.md#secret-management)
- [v4.8.0 release notes](RELEASE_NOTES_v4.8.0.md) ·
  [v4.7.0 release notes](RELEASE_NOTES_v4.7.0.md)
