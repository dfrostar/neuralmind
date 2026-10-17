# Hermes plugin debut on Reddit — 2026-10-15

Draft of the Reddit thread introducing the NeuralMind **Hermes-Agent plugin**
(v4.9.0+). It's drafted in this repo so `tests/test_docs_claims.py` checks every
claim before the text goes anywhere CI can't reach.

This is a different post from the 2026-08-28 Hermes copy
([ecosystem debut](./2026-08-28-ecosystem-debut.md), Post 3). That one
covered the **MCP server**, where the agent has to decide to call a tool. This
one covers the **plugin**, where context arrives on every turn without a tool
call. The August doc's "Shared numbers" table is also out of date (it predates
v4.12.0). Every figure here comes from the current `site/claims.json`.

## Before posting

- [ ] **Pick the subreddit and read its rules first.** As of 2026-10-14 there
      was no confirmed Hermes-Agent subreddit (the August venue note says the
      same: the community uses the Nous Research Discord and GitHub, and Reddit
      discussion of Hermes happens in r/LocalLLaMA). If a Hermes or Nous
      subreddit exists by posting time, prefer it and drop the one-paragraph
      intro to Hermes. If r/LocalLLaMA, check the self-promotion rule and use
      its flair for a project/resource post.
- [ ] **Don't post twice to r/LocalLLaMA in a short window.** If the August
      benchmark thread (Post 1) went up there recently, take this one to a
      different subreddit or wait.
- [ ] **Re-run** `NEURALMIND_ORT_THREADS=1 python -m evals.public.run` on
      your machine. If the table differs from `docs/benchmarks/public.md`,
      the post uses the new numbers.
- [ ] **Record the demo** (below). A Reddit post with a GIF or screenshot of
      the injected block will get far more attention than text alone.
- [ ] **Confirm** `hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable`
      still works on the current Hermes release (the manifest requires
      `>=0.21.5`).
- [ ] Do **not** mention the Hermes MCP catalog entry
      (NousResearch/hermes-agent#97207) unless you have checked its state on
      posting day. The plugin install below does not depend on it.

---

## Title options

1. **Hermes plugin that adds codebase memory to every turn: related files, past decisions, and a recap of your last session, with no tool call** *(recommended: says what it does)*
2. I wrote a Hermes-Agent plugin so the agent stops starting cold on my repo
3. Persistent code memory for Hermes-Agent: a `pre_llm_call` plugin, local index, published benchmark misses included

## Body (posting version, ~1,900 characters)

I built NeuralMind (MIT-licensed core, runs locally) and just shipped a Hermes-Agent plugin for it. I'd like feedback from people using Hermes on real codebases.

**Why:** Hermes could already use NeuralMind over MCP, but only when the model decided to call the tool. When it didn't, the turn started cold.

**What the plugin does:**

- **Every turn:** looks up your message in a local index of the repo and appends the matching files (with symbols and line numbers), the files linked to them, and any recorded decisions from git trailers. It goes on the user message, so Hermes's prompt cache isn't invalidated. If nothing matches, nothing is added.
- **First turn of a session:** a short recap of your last session in that repo, covering your prompts and the files you edited.
- **As you work:** successful edits and reads are recorded, so files you work on together get linked and links you stop using fade.

**Install:**

    pip install -U neuralmind
    neuralmind build /path/to/repo
    neuralmind install-hermes-plugin

**Numbers, misses included:** on 40 queries written before tuning, across requests, click, flask and rich, the right file was in the context for 40 of 40, at 51–242x fewer tokens than pasting whole files. 40 is a small sample: on a 150-question eval it gets the right file into the top five 93.3% of the time and misses 10. A bare vector lookup always costs fewer tokens and ranks the right file higher on two of the four repos. To reproduce, run `python -m evals.public.run` from a clone.

**What runs where:** the index lives in `<repo>/.neuralmind/` and there's no telemetry. The one exception is that the first build downloads the embedding model (SHA256-checked) unless you pre-seed it. Whatever the plugin adds goes to whichever model Hermes uses.

Repo: https://github.com/dfrostar/neuralmind

Does the per-turn block help on your setup, or is it noise?

## Long version (reference: fuller detail for replies)

I build NeuralMind, a local code-memory tool for coding agents (MIT-licensed core).
I just shipped a Hermes-Agent plugin for it and would like feedback from
people who use Hermes on real codebases.

**The problem.** Hermes could already use NeuralMind through MCP, but the
model had to *decide* to call the tool. When it didn't, the turn started cold:
no related files, no record of why the code is the way it is, nothing about
what you were doing yesterday. Hermes builds a good model of *you* across
sessions; it doesn't build one of your repo.

**What the plugin does.** It hooks Hermes's `pre_llm_call` and `post_tool_call`
and adds three things:

- **Every turn:** before the model runs, it looks up your message in the
  project's index and appends a short block listing the matching files with
  symbols and line numbers, the files linked to them, matching docs, and any
  recorded decisions (`Decision:` git trailers) your message touches. If the
  message doesn't match the code ("yes", "thanks"), nothing is added. The
  block goes on the user message, not the system prompt, **so Hermes's prompt
  cache isn't invalidated.**
- **First turn of a session:** a recap of the previous session in that
  project: the first and most recent prompts and the files edited. The header
  marks it as context, not instructions, so Hermes doesn't resume old work
  unless you ask "where were we?". No model call builds it.
- **After edits and reads:** when `write_file` / `patch` succeeds, or
  `read_file` reads a project file, it records that on a background thread.
  This is how it learns: files you work on together get a stronger link (a
  Hebbian "synapse" layer), and links you stop using decay. Recall starts out
  structural (calls, imports, inheritance from the build) and shifts toward
  how you actually work in the repo.

Here's what the model sees (example file names):

    ## NeuralMind associative recall

    Code matching this prompt:
    - src/uploader.py: upload_with_retry() L88, RetryPolicy L21
    - src/config.py: backoff_settings() L140
    Connected to it in the synapse graph:
    - src/http_client.py: send() L57
    Docs: docs/uploads.md

    ## NeuralMind decision provenance

    - `upload_with_retry`: retries live in the uploader, not the HTTP client,
      so the client stays safe for non-idempotent calls. (see commit 3f9c2ab)

**Install.**

    pip install -U neuralmind
    neuralmind build /path/to/repo
    neuralmind install-hermes-plugin            # follows whichever built repo Hermes is working in

Or let Hermes manage it:

    hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable

Start a new session (or restart the gateway) to load it. If you skip the path,
one install serves every repo you've built and does nothing in the rest.
Hermes Desktop and ACP editor sessions don't expose each session's directory,
so there you pin a project (`install-hermes-plugin /path`) or set
`NEURALMIND_PROJECT`.

**Numbers, including where it loses.** On a public benchmark of 40 queries
written before tuning, across `requests`, `click`, `flask` and `rich` pinned to
fixed commits, the gold file (the definition site of a named symbol, checkable
with one `rg`, no LLM judge) was in the context on 40 of 40 queries, at
51–242x fewer tokens than pasting whole files and 31–67x fewer than ripgrep
opening its top five files (which found the gold file on 32 of 40). 40 queries
is a small sample: on a larger 150-question retrieval eval the same build puts
a gold file in the top five 93.3% of the time and misses 10. A bare vector
lookup using the same encoder always costs fewer tokens and ranks the right
file higher on `flask` and `rich`. If all you need is "which file", use that.
NeuralMind spends the extra tokens on assembled context (map, signatures,
related candidates). The synapse layer isn't in those numbers because it learns
from your usage; CI checks that it never lowers hit rate, and I'm not quoting a
size for that because CI only checks the direction. Reproduce from a clone:
`pip install -e . tiktoken && python -m evals.public.run`.

**What runs where.** The index and synapse store are SQLite plus a local vector
store in `<repo>/.neuralmind/`. There's no telemetry and nothing goes out at
query time. The one exception: on a machine with no cached embedding model,
the first build downloads the all-MiniLM-L6-v2 ONNX archive over HTTPS and
checks its SHA256. Pre-seed `NEURALMIND_ONNX_MODEL_DIR` to skip that. Your
model still sees the block the plugin adds, so if Hermes points at an API,
that text goes to the API.

**Known gaps.** Edits made through `terminal` (a `sed`, say) aren't recorded,
and neither are subagent or cron turns: their messages are written by an agent
or a schedule, not by you.

Repo: https://github.com/dfrostar/neuralmind ·
Walkthrough: https://docs.neuralmind.uk/use-cases/hermes-agent.html

I'd especially like to hear: does the per-turn block help, or is it noise on
your workload? I can tune the cutoff for when it shows up
(`NEURALMIND_RECALL_MIN_SIMILARITY`).

---

## Pinned first comment (optional)

> Author here. To try it without the plugin first: `neuralmind query /path/to/repo "how does X work"`
> shows the context it would add, with its token count. To switch every hook
> action off without uninstalling: `NEURALMIND_BYPASS=1`. Uninstall:
> `neuralmind install-hermes-plugin --uninstall`.

## Replies to prepare

| Likely question | Answer from the repo |
|---|---|
| "Isn't this just RAG?" | Partly: the retrieval core is a vector index, and the bare version of it is benchmarked as a baseline. The plugin adds what plain RAG doesn't have: per-turn injection with no tool call, a session recap, decisions from git trailers, and links learned from edits. |
| "How fast is it?" | **Don't quote a figure.** No committed benchmark measures query latency end to end. Say it's a local index lookup, not another model call. |
| "Does it work with local models?" | Yes. The plugin only adds text to the message, so it doesn't depend on the model behind Hermes. NeuralMind itself sends nothing at query time; with a local model behind Hermes, the block doesn't go to any API either. |
| "Multiple repos?" | Install without a path. Each built repo keeps its own `.neuralmind/`. Pinning one project applies it to every Hermes session on that Hermes home (see `docs/wiki/Multi-Project-Scoping.md`). |
| "Pricing?" | Core is MIT and free. The paid Team tier is per `commercial-terms.json`. Don't post a price that isn't in that file. |

## Demo to record

1. A Hermes terminal session on an OSS repo (not a client repo): the first
   turn showing the recap, then a question showing the recall block. To
   capture what was injected, run `hermes logs` or ask the model to quote it.
2. `neuralmind query` with the token count visible, on the same repo.
3. Optional: `neuralmind stats` before and after a session to show the
   synapse store growing.

Don't put a stopwatch on any of these. No latency figure is allowed.

## Claim sources

| Claim | Source |
|---|---|
| Plugin hooks, per-turn block, appended to user message (cache untouched), first-turn recap, edit and read recording, the unrecorded cases | `docs/use-cases/hermes-agent.md` §2–§4; `neuralmind/hermes_plugin/plugin.yaml` |
| `hermes plugins install …#neuralmind/hermes_plugin --enable`, `requires_hermes >=0.21.5` | `docs/releases/RELEASE_NOTES_v4.10.0.md`; `plugin.yaml` |
| Project resolution, Desktop/ACP pin rule | `docs/use-cases/hermes-agent.md` §5; `CLAUDE.md` multi-project scoping |
| Reads recorded (v4.14.0+) | `docs/use-cases/hermes-agent.md` §4 |
| 40 of 40, 51–242x, 31–67x, ripgrep 32 of 40 | `site/claims.json` (`ratios`, `non_ratio_headline_claims`) → `docs/benchmarks/public.md`, v4.12.0 |
| 150-question eval: 93.3% top-5, 10 misses | `site/claims.json` note; `docs/wiki/Benchmarks.md` |
| Embedding baseline cheaper; higher MRR on flask (0.74 vs 0.72) and rich (0.94 vs 0.83) | `docs/benchmarks/public.md` per-repo tables |
| Synapse gate checks direction only | `site/claims.json` `non_ratio_headline_claims` |
| First-run ONNX download, SHA256-pinned, `NEURALMIND_ONNX_MODEL_DIR` | `neuralmind/onnx_embedder.py`; 2026-08-28 debut "Claim sources" |
| `NEURALMIND_BYPASS`, `NEURALMIND_RECALL_MIN_SIMILARITY` | `CLAUDE.md`; `docs/use-cases/hermes-agent.md` §3 |
