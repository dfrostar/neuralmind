# Frequently Asked Questions

Quick answers to common NeuralMind questions.

---

## Installation & Setup

### "I installed NeuralMind but `neuralmind` command not found"

**Solution:**
```bash
# Check if installed
pip show neuralmind

# If installed, find where
python -c "import site; print(site.USER_BASE + '/bin')"

# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"

# Add to PATH (Windows PowerShell)
$env:Path += ";$env:APPDATA\Python\Python311\Scripts"
```

---

### "graphify build fails with 'unknown command'"

*(Only relevant if you installed the optional graphify backend — since
v0.15.0 NeuralMind builds the code graph itself.)*

**Solution:**
The command changed in newer versions. Use:
```bash
graphify update .    # New (v1.2+)
# NOT: graphify build .
```

---

### "neuralmind build takes forever on large codebase"

**Solutions:**

1. **Only the first build pays the full cost.** Later builds re-embed only the
   nodes whose content changed.
2. **Keep out what you don't need.** `build` already skips what `.gitignore`
   ignores. For anything else, such as generated or vendored code, add a
   `.neuralmindignore` to the project root (gitignore syntax):
   ```gitignore
   # .neuralmindignore
   dist/
   vendor/
   **/*.min.js
   ```
3. **In a CPU-limited container**, set `NEURALMIND_ORT_THREADS` to the CPU
   limit. ONNX Runtime otherwise sizes its thread pool to the host's cores.

There is no faster backend to switch to. `turbovec` is the default, and the
only other on-disk backend is the deprecated ChromaDB one.

---

## Usage & Queries

### "How do I search across multiple files?"

**Answer:** NeuralMind searches semantically across your entire codebase automatically.

```bash
# Just ask a question about the whole project
neuralmind query . "How is data validation handled throughout the codebase?"

# It will find relevant validation code in multiple files
```

---

### "Can I search for exact strings or exact identifiers?"

**Answer:** Yes — since v0.38.0, NeuralMind uses **hybrid search** (BM25 + vector) by
default. BM25 uses code-aware tokenisation, so queries like `"UserService"` or
`"get_auth_token"` score exact name matches above semantically similar but
textually different nodes.

```bash
neuralmind search . "UserService"      # BM25 exact-name match + semantic, merged via RRF
neuralmind query  . "UserService"      # Full 4-layer context, hybrid L3 search
```

Set `NEURALMIND_BM25=0` to revert to pure vector search if needed.

For raw string grep across files (not structured retrieval):
```bash
grep -r "authenticate" src/
```

---

### "Output is too long/verbose"

**Solutions:**
```bash
# 1. Ask more specific questions
neuralmind query . "How does password validation work?"  # Better than "How does auth work?"

# 2. Use JSON output and parse it
neuralmind query . "What endpoints are available?" --json | jq '.results | length'

# 3. Narrow scope
neuralmind query src/auth/ "How does login work?"  # Limits to one directory
```

---

### "Why is the same question giving different results?"

**Reasons:**
1. **Index changed** — Code was updated, rebuild with `neuralmind build .`
2. **Learning kicked in** — NeuralMind learns from your queries (improvement!)
3. **Randomness** — Small variations in embedding similarity

**Solution:** Results should be consistent. If they vary significantly, rebuild:
```bash
neuralmind build . --force
```

---

## Performance & Scaling

### "Is NeuralMind slow for large codebases?"

**The first build is the expensive step.** After that, builds are incremental,
and a query is a local index lookup, not another model call.

Build time and end-to-end query latency on large repos aren't benchmarked
yet, so measure your own:

```bash
time neuralmind build .
neuralmind stats .       # node count of the built index
neuralmind benchmark .   # token reduction on sample queries
```

The synapse layer's recall latency is benchmarked: run
`python -m tests.benchmark.latency` from a source checkout. Planning estimates
for big repos, labeled as estimates, are on
[Limits & Failure Modes](Limits-and-Failure-Modes#2-repo-size-index-time-memory--disk-envelope).

There is no server or database backend for large projects. Every backend
keeps its index in local files under `.neuralmind/`.

---

### "How much disk space does the index need?"

**Rough estimates:**
- 100K LOC → 50-100 MB
- 500K LOC → 200-500 MB
- 1M LOC → 500MB-2GB
- 10M LOC → 5-20GB

> Full size / index-time / memory envelope — with the honest "not yet measured at
> scale" caveats — is on the [Limits & Failure Modes](Limits-and-Failure-Modes#2-repo-size-index-time-memory--disk-envelope) page.

**Reclaiming space:** each build removes vectors for code that is no longer in
the graph. When those are more than half the store, the build keeps them as a
safety check and tells you, and `neuralmind build . --prune` removes them.
`.neuralmindignore` keeps paths out of the next build. Don't delete all of
`.neuralmind/` to save space. It also holds learned synapses
(`synapses.db`), recorded decisions (`memory.db`), and the audit log, and a
build can't recreate those. See
[Backup & Recovery](../DEPLOYMENT-GUIDE.md#backup--recovery).

---

### "Should I run NeuralMind on one codebase, a monorepo, or across several repos?"

**One codebase is the unit — and where NeuralMind is strongest.** Everything
is anchored to a single project root: the index in `graphify-out/`, and the
embeddings plus the learned synapse memory in `.neuralmind/`. One root = one
index + one namespaced memory.

- **A monorepo counts as one codebase** and is fully supported. Retrieval is
  community/cluster-aware, and builds are incremental — `neuralmind build .`
  re-embeds only changed nodes, so build time scales with churn, not repo
  size. (See the Growing Monorepo use case.)
- **Several *separate* repos → run one NeuralMind per repo.** There's no
  cross-repo "workspace" store today; each repo is its own independent brain
  with its own `.neuralmind/`. Nothing stops you running it on ten repos —
  they're just ten separate stores, not one unified one.
- **The memory compounds per codebase.** The synapse layer learns
  associations from how you actually work *in that repo*, so sustained use on
  one codebase sharpens recall over time. Splitting attention across many
  repos means each accumulates less learning signal.

Within a single codebase it's still flexible: memory namespaces isolate
`branch:<name>` / `personal` / `shared`, multiple agents (Claude Code,
Cursor, Cline) share the one store, and even multiple git worktrees can share
it with per-branch isolation.

---

## Features & Capabilities

### "Does NeuralMind support my language?"

**Supported (built-in tree-sitter, no graphify needed):**
- Python, TypeScript/JavaScript, Go, Rust, Java, C, C++, C#, Ruby, PHP
- Plus schema/doc artifacts: Markdown, OpenAPI/AsyncAPI (YAML), SQL DDL, Protocol Buffers

**Partial support:**
- Other languages can be ingested as plain text (less precise)

> The per-language [support matrix](Limits-and-Failure-Modes#3-language-support-matrix)
> spells out exactly what's indexed *and what's explicitly not modeled* per language
> (C/C++ macros & templates, dynamic-dispatch call resolution, SQL `ALTER`/`SELECT`,
> proto imports, OpenAPI `$ref`, …).

**If not supported:**
```bash
# Ingest each source file as a plain text document (Kotlin here)
find src -name '*.kt' -exec neuralmind ingest {} --project-path . \;
```

Pass the files one at a time. Given a directory, `neuralmind ingest` only
picks up document types (`.md`, `.txt`, `.rst`, `.pdf`, and similar), so it
would skip the source files.

Retrieval then works on the text, but the graph has no symbols, calls, or
imports for those files.

---

### "Can NeuralMind read test files?"

**Yes, but consider excluding them** with a `.neuralmindignore` in the project
root (gitignore syntax):
```gitignore
# .neuralmindignore
*.test.js
*.spec.py
test/
tests/
```

**Why?** Test code clutters the index without adding understanding.

---

### "Does NeuralMind work with private packages?"

**Yes!**
```bash
# If your project uses private packages, NeuralMind indexes:
# 1. Your code (always)
# 2. Local node_modules / site-packages (yes)
# 3. External PyPI/npm packages (no, stays private)

# NeuralMind indexes only local code and sends no telemetry
```

---

## Collaboration & Teams

### "How do team members share a NeuralMind index?"

**They don't share the index.** Each developer builds their own:

```bash
# Each developer on their machine
neuralmind build .
neuralmind install-hooks .
```

There is no shared index server or database backend, and real-time
cross-machine sync is roadmap-only. What a team can share is through git:

- **Backend settings:** commit `neuralmind-backend.yaml` so every checkout
  uses the same backend. It doesn't share a role policy: the MCP server
  ignores `security.roles`.
- **Learned memory (optional):** `neuralmind memory publish` writes
  `.neuralmind-team-memory.json`. Once it's committed, teammates' agents merge
  it on their next session start or build.

See [Rolling Out to a Team](../DEPLOYMENT-GUIDE.md#rolling-out-to-a-team).

---

### "Can I restrict who can use NeuralMind?"

**Partly.** NeuralMind doesn't authenticate users. Who can use it is decided by
who can run the agent that launches its MCP server (stdio, the default) and who
can read the project's `.neuralmind/` directory.

Within that, each MCP call declares its own role, and the server applies a
default per-tool policy. Any caller can declare `admin`. `security.roles` in
`neuralmind-backend.yaml` is parsed but not applied by the MCP server today, so
it can't cap that. See the
[Security Guide](../SECURITY-GUIDE.md#access-control).

---

## Security & Compliance

### "Does NeuralMind send data to external servers?"

**Not by default.**
- ✅ Indexing, embedding, retrieval and synapse learning run on your machine
- ✅ No telemetry
- ✅ No repository content transmitted by default — the one default outbound request is a public embedding-model download on first build, pre-seedable via `NEURALMIND_ONNX_MODEL_DIR` for air-gapped installs
- ⚠️ One opt-in feature, off by default: `NEURALMIND_LLM_SEED=1` (plus your own `ANTHROPIC_API_KEY`) sends README and architecture-doc prose to Anthropic to seed doc synapses
- Your agent still sends the context slice it selects to its own model provider; NeuralMind makes that slice smaller but does not control it

---

### "How do I ensure no secrets leak into the index?"

```bash
# 1. Scan for credentials before building (exits 1 on a high-confidence hit)
neuralmind scan-for-secrets .

# 2. Fix what it finds — remove from code AND rotate the credential.
#    A key that reached your git history is already compromised.

# 3. Optional backstop: scrub anything still present out of the index
neuralmind build . --redact-secrets

# 4. Verify
neuralmind scan-for-secrets .   # should report no findings
```

The scanner reads files directly, so it sees `.env` and other files the
indexer never touches. Two tiers: `HIGH` for vendor shapes (`sk-ant-`,
`AKIA`, PEM blocks, JWTs, connection-string passwords) and `maybe` for
generic `SECRET=value` assignments that pass an entropy check. Previews
never include the tail of a secret, so the output is safe to paste into
an issue.

Two protections need no flag:

- **The Bash recovery cache is redacted.**
  `.neuralmind/last_output.json` stores whatever your commands printed —
  `printenv` or a curl with an `Authorization` header would otherwise
  leave a live key in a plaintext file. Credentials are stripped before
  the write. Opt out with `NEURALMIND_OUTPUT_REDACT=0`.
- **`.neuralmind/` cannot be committed.** The directory is created with
  its own `.gitignore` containing `*`, so `git add -A` skips it even if
  your project's `.gitignore` says nothing about it. If you built with
  an older version, check whether it is already tracked —
  `git ls-files .neuralmind/` — and untrack it with
  `git rm -r --cached .neuralmind/`. `neuralmind build` warns when it
  detects this.

---

### "Can I use NeuralMind in a regulated industry?"

**Yes!** NeuralMind is built for compliance:
- ✅ NIST AI RMF audit trail
- ✅ SOC 2 compliance mapping
- ✅ GDPR-compliant (local processing)
- ✅ HIPAA-friendly (local processing, no calls home)

---

## Troubleshooting

### "NeuralMind build fails with 'No module named chromadb'"

The project selects the deprecated ChromaDB backend (`backend: graph` or
`backend: chroma` in `neuralmind-backend.yaml`), and ChromaDB isn't installed
by default. Either remove that line to use the default `turbovec` backend, or
install the extra:

```bash
pip install "neuralmind[chromadb]"
```

---

### "Queries return irrelevant results"

**Solutions:**
1. **Rebuild index** — Code changed, index is stale
   ```bash
   neuralmind build . --force
   ```

2. **Ask better questions** — Be more specific
   ```bash
   # Bad: "How does it work?"
   # Good: "How does user authentication work?"
   ```

3. **Let learning warm up** — NeuralMind improves with use, automatically
   via the synapse layer (no manual step). Install the hooks and optionally
   the watcher, then check what's been learned:
   ```bash
   neuralmind install-hooks .
   neuralmind watch &            # optional: learn from file edits
   neuralmind memory inspect .   # see what the synapse layer has learned
   ```

---

### "Why does my `serve` canvas stay quiet when I edit files?" *(v0.6.0+)*

You ran `neuralmind serve`, opened the graph view, edited a file in
your editor — and no node pulsed. The live feed (v0.6.0) depends on
two paths working: the in-process event bus, and the cross-process
JSONL bridge. When the canvas is silent, one of these is the
culprit. Check in this order:

1. **`.neuralmind/` directory exists in the project root.** The
   JSONL bridge writes to `<project>/.neuralmind/events.jsonl`,
   which the watcher and `serve` both need to find. If the directory
   doesn't exist (fresh clone, or you blew it away):

   ```bash
   neuralmind build .   # creates .neuralmind/ alongside graphify-out/
   ```

2. **`NEURALMIND_EVENT_LOG` is not set to `0`.** This env var
   disables the JSONL writer. If it's set in your shell config or
   the parent process of either `serve` or `watch`, the in-process
   feed still works for the *same* process but cross-process events
   never reach the canvas.

   ```bash
   env | grep NEURALMIND_EVENT_LOG   # should be empty or =1
   unset NEURALMIND_EVENT_LOG        # clear it if set
   ```

3. **Both processes target the same project root.** A common gotcha:
   `neuralmind serve` was started from `~/projects/foo` and
   `neuralmind watch` from `~/projects/foo/src/`. They write to
   *different* `.neuralmind/events.jsonl` files and never see each
   other. Run both from the project root, or pass an explicit
   `project_path`:

   ```bash
   neuralmind serve /abs/path/to/project &
   neuralmind watch /abs/path/to/project &
   ```

4. **The file watcher is actually running.** If you're relying on
   Claude Code's `PostToolUse` hooks for file events, those only
   fire on tool calls — they won't see your manual editor saves.
   For editor-driven pulses, start `neuralmind watch` separately:

   ```bash
   neuralmind watch . --quiet &
   ```

5. **The browser tab actually has the SSE stream open.** Open the
   browser devtools network tab and look for a long-lived request
   to `/api/events`. If it's missing or 404, refresh the page; if it
   401s, your token expired (re-open the URL `serve` printed).

6. **The synapse store is being reinforced.** If no agent is
   calling `neuralmind_query` or any other NeuralMind MCP tool, the
   synapse store has nothing to publish — the canvas pulses only
   when something actually happens. Trigger one manually:

   ```bash
   neuralmind query . "test query"
   ```

   You should see a pulse within ~1s.

If the canvas still stays quiet after all six, that's a bug — open
an issue with the output of `neuralmind stats .` and a
description of what you tried.

---

### "MCP server won't start"

`neuralmind-mcp` talks to your agent over stdio. It opens no port and takes
no command-line arguments, so there is no port to free and no flag to set.
Each tool call names the project it wants.

```bash
# Is the MCP SDK importable, and are the graph and index in place?
neuralmind doctor .

# Is the server registered with your agent? --print shows the config snippet
neuralmind install-mcp . --print

# Start it by hand to see any import error. It waits for input on stdin;
# Ctrl+C to stop.
neuralmind-mcp
```

`doctor` always exits 0, so read its output rather than its exit code.

---

## Pricing & Licensing

### "Is NeuralMind free?"

**Yes!**
- ✅ MIT License (fully open source)
- ✅ No subscription
- ✅ No usage limits
- ✅ Self-hosted (no cloud costs)

---

### "Can I use NeuralMind commercially?"

**Yes!** MIT License allows commercial use:
- ✅ Use in products
- ✅ Use in services
- ✅ Use in enterprises
- ✅ Modify for your needs

Just include the license text.

---

### "Is commercial support available?"

Coming in v1.0 (Q1 2027):
- Priority bug fixes
- Deployment consulting
- Custom integrations
- SLA guarantees

---

## Comparisons

### "How is NeuralMind different from Cursor @codebase?"

| Feature | NeuralMind | Cursor |
|---------|-----------|--------|
| Works everywhere | ✅ Yes | ❌ Cursor only |
| Works offline | ✅ Yes, once the first build has cached the embedding model | ❌ Cloud |
| Token reduction | Measured: 45–261× vs. pasting every source file ([public benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)) | Not measured by us |
| Cost | Free at 1 seat | Paid (Cursor) |
| Open source | ✅ MIT core | ❌ No |

---

### "Why not just use long context windows?"

```
Claude 3.5 Sonnet:
- Input: $3/1M tokens
- Output: $15/1M tokens

Traditional (50K tokens):
- Cost: $0.15 per query

With NeuralMind (800 tokens):
- Cost: $0.0024 per query
- Savings: 60× cheaper

Even with 200K token context limit available,
NeuralMind is 10× cheaper because the prompt is small.
```

---

### "Does NeuralMind replace Copilot?"

**No, they're complementary:**
- **Copilot** — Code completions, inline suggestions
- **NeuralMind** — Code understanding, context retrieval

Use both together for maximum productivity.

---

## Contact & Support

### "Where can I ask questions?"

- 📖 [GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions)
- 🐛 [Report Issues](https://github.com/dfrostar/neuralmind/issues)
- 📧 Email: hello@neuralmind.uk
- 🔒 Security issues: report privately, as described in [SECURITY.md](https://github.com/dfrostar/neuralmind/blob/main/SECURITY.md#reporting-a-vulnerability)

### "How do I report a bug?"

```bash
# 1. Reproduce the issue
# 2. Collect debug info
neuralmind --version
python --version
uname -a

# 3. Open GitHub issue with:
#    - Clear title
#    - Reproduction steps
#    - Expected vs actual behavior
#    - Debug output
```

### "Can I contribute?"

**Yes!** See [CONTRIBUTING.md](https://github.com/dfrostar/neuralmind/blob/main/CONTRIBUTING.md)

