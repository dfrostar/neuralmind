# NeuralMind v4.7.1: installers that can't destroy your config, and eight other fixes

**Type:** Patch release | **Theme:** Correctness and safety

This release fixes eight bugs found by testing v4.7.0 end to end. Two of them
could destroy user configuration. A third left credentials in plaintext in
the Bash output cache, under a header that said they had been redacted.

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

Every hook action now returns at once, writing nothing, unless the session's
directory already has `.neuralmind/`. That directory exists once
`neuralmind build` has run. Before, a globally installed hook would:

- build a full index from the prompt hook (graph, IR and vectors) in any
  directory with source files;
- create `.neuralmind/` from the session-start, edit, stale-guard, Bash-cache
  and pre-compact actions.

Read dedup already followed this rule. Prompt-time recall also no longer builds
an index in a project that has `.neuralmind/` but no index yet (for example,
one with only decision memory). It loads the existing index or injects nothing.

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

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | With global hooks, the first prompt in an unbuilt repo could block on a full index build until the hook timed out, and `.neuralmind/` appeared in every directory a session ran in. `neuralmind last` could replay AWS session credentials | In an unbuilt repo the hooks do nothing and add no context. In a built one, nothing changes except that recall never triggers a build. AWS CLI credentials are redacted in the cache |
| **Cursor / Cline / Claude Desktop** (MCP) | `install-mcp` on a config with a trailing comma removed every other server | The config is left untouched, and the command prints the entry to paste |
| **VS Code** (MCP) | JSONC was already left untouched. A config whose top level wasn't an object was overwritten | Both are left untouched |
| **Generic MCP client** | Unchanged | Unchanged |

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

## Related

- [CLI reference: install-hooks](../wiki/CLI-Reference.md#install-hooks) ·
  [install-mcp](../wiki/CLI-Reference.md#install-mcp-v0190) ·
  [scan-for-secrets](../wiki/CLI-Reference.md#scan-for-secrets)
- [Security Guide: Secret Management](../SECURITY-GUIDE.md#secret-management)
- [v4.7.0 release notes](RELEASE_NOTES_v4.7.0.md)
