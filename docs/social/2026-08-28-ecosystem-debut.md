# Ecosystem debut posts — 2026-08-28

Launch copy for NeuralMind's first public posts in the agent-host
communities. Drafted in-repo so `tests/test_docs_claims.py` vets every
claim before any of it is pasted somewhere no CI can reach — same reason
`docs/social/` is a scanned glob in the first place.

## Registry status as of 2026-08-28 (verified today, not assumed)

| Registry | State | Evidence |
|---|---|---|
| **ClawHub** (OpenClaw) | **Live.** Community channel, not official. Skill package `neuralmind` v1.0.0, owner `dfrostar`, 51 downloads. | `clawhub.ai/api/v1/packages/neuralmind`; listing at [clawhub.ai/dfrostar/skills/neuralmind](https://clawhub.ai/dfrostar/skills/neuralmind) |
| **Agent Zero** `a0-plugins` | **Submitted, validator green, awaiting maintainer review.** Not merged. | [agent0ai/a0-plugins#499](https://github.com/agent0ai/a0-plugins/pull/499) — "Validate Plugin PR" succeeded 2026-08-28 in 12s; no reviewer assigned |
| **Hermes-Agent** MCP catalog | **Submitted, review comments resolved, awaiting merge.** Not merged, and no formal review — the Reviewers panel still reads "No reviews". Labels `type/feature`, `tool/mcp`, `P3`. | [NousResearch/hermes-agent#97207](https://github.com/NousResearch/hermes-agent/pull/97207); Enough1122 (Contributor) flagged the manifest's network claim as unverified by their CI 2026-08-28, then confirmed at head `bccabd6` on 2026-08-29 "no further items from me" — a plain comment, not an approving review. Maintainer alt-glitch has labelled it but not reviewed or merged |

**Wording rule that follows:** ClawHub may be described as *listed* /
*installable today*. Agent Zero and Hermes are **"submitted, validator
green, awaiting review"** — never "listed", "available in", or "shipping
with" until the PR merges. If either merges before posting, upgrade that
line and nothing else.

## Venue note — three of these four are not on Reddit

Only r/LocalLLaMA is a subreddit. The three host communities gather
elsewhere, so the posts below are written for the venue each community
actually uses:

| Community | Where it actually is |
|---|---|
| Local-model / self-hosting | **r/LocalLLaMA** (subreddit) |
| OpenClaw | Discord + GitHub Discussions on `openclaw/openclaw`; ClawHub is the registry, not a forum |
| Hermes-Agent | **Nous Research Discord**, `#agent` channel + GitHub Discussions. No dedicated subreddit — Hermes discussion on Reddit happens in r/LocalLLaMA and r/selfhosted |
| Agent Zero | Discord (~4.6k members) + GitHub Discussions on `agent0ai/agent-zero` + Skool. No subreddit |

Posting the host-specific copy to r/LocalLLaMA as three separate threads
would read as spam. Post **one** thread to r/LocalLLaMA (Post 1); take
Posts 2–4 to their own communities.

---

## Shared numbers — every figure any of the four posts may use

All of these trace to `site/claims.json` and the sources it names. Nothing
outside this block goes in a post.

| Figure | Value | Evidence level |
|---|---|---|
| Gold-file recall, public benchmark | 93.75% weighted mean; per repo 0.96 / 0.79 / 0.95 / 1.00 | reproducible |
| Recall band (never round the floor away) | 79-100% per repo | reproducible |
| Found-rate | 90% across 40 queries | reproducible |
| Token reduction vs pasting whole files | 44.9x - 256.8x per repo | reproducible |
| Mean tokens per query, NeuralMind | 772 - 930 across the four repos | reproducible |
| Mean tokens per query, full-file baseline | 41,729 - 232,483 | reproducible |
| Corpus | 40 pre-registered queries, 4 repos pinned to fixed SHAs | reproducible |
| Real-repo positioning range | 12-50x, directional, field-reported | field-report |
| Synapse A/B lift | CI gates *direction* (recall-on >= recall-off) at a neutral budget; observed band +3.5 to +14 pts on passing hosts, -1.75 pts on AVX-512 hosts where the gate fails | ci-gated on direction only; the negative mode is an open bug |
| MCP tools exposed | 21 | `grep -c '^def tool_' neuralmind/mcp_server.py` |

**Forbidden in every post:** any query-latency figure (nothing in the repo
produces one — speed is described as mechanism only); "12-70x"; "63.6x";
"1,486-node"; "100% recall"; any fixed synapse-lift magnitude; the name of
any private client; and any absolute privacy claim about the whole
workflow. Scope privacy claims to NeuralMind's own behaviour.

---

## Post 1 — r/LocalLLaMA

**Title:** I benchmarked my own local code-memory MCP server against ripgrep and a vector RAG on 4 pinned repos. It loses to the vector baseline on one of them.

**Body:**

I build NeuralMind, a local MCP server that gives coding agents persistent memory of a codebase. Rather than post the ratio and stop, here's the benchmark including the parts that don't flatter it.

**What it does.** It parses a repo into a weighted graph of symbols, then answers a question with progressive disclosure — project identity, then architecture, then the relevant cluster, then semantic search — instead of pasting files. On top of that sits a Hebbian synapse layer: files that get used together have their edge strengthened, unused edges decay, so retrieval adapts to how you actually work on that repo. Index and synapse store are SQLite plus a local vector store on your disk.

**On "local."** No telemetry, no calls home, nothing at query time. I'll be precise about the one exception rather than say "makes no network calls", because that would be false: the first time it embeds on a machine with no cached model, NeuralMind's *own* embedder fetches the all-MiniLM-L6-v2 ONNX archive over HTTPS and verifies it against a pinned SHA256. It checks `$NEURALMIND_ONNX_MODEL_DIR` and two local cache locations first, so pre-seeding either one removes even that request — which is how the air-gapped path works. Plus the obvious one: install pulls from PyPI. And your agent still sends whatever slice it picks to whatever model you point it at. If that model is local, the whole loop is; if it's an API, NeuralMind changed how *much* leaves, not *whether*.

**The benchmark.** 40 queries pre-registered before any tuning, across `requests`, `click`, `flask` and `rich`, each pinned to a fixed commit SHA. The gold file for each query is the definition site of a named symbol — verifiable with one `rg`, no LLM judge in the headline. Cost and correctness are reported together, because a token ratio without a correctness number is meaningless.

    repo       backend         recall   tokens/query   vs full-file
    requests   full-file        1.00       41,729          1x
    requests   ripgrep          0.79       26,543          1.6x
    requests   embedding-rag    1.00          607         69x
    requests   neuralmind       0.96          930       44.9x

    click      neuralmind       0.79          788       99.6x
    click      embedding-rag    1.00          634      123.8x
    flask      neuralmind       0.95          772       76.4x
    rich       neuralmind       1.00          905      256.8x

Aggregate: 93.75% weighted mean gold-file recall, 79-100% per repo, 90% found-rate.

**Where it loses, plainly:**

- `click` is the weakest repo in the corpus — 0.79 recall, 2 of 7 queries missed, and it also trails on rank quality there (MRR 0.52 vs 0.67 for the vector baseline). Every miss is published with the files it retrieved instead.
- The `embedding-rag` baseline matches or beats it on recall on three of four repos, always at fewer tokens. That baseline is NeuralMind's *own encoder* doing bare top-k retrieval, so the gap is exactly what the assembly layer costs. If all you need is "which file", a bare vector index is cheaper and you should use one. NeuralMind spends the extra tokens on assembled context — map, signatures, call edges — which is about answering, not locating.
- 4 misses out of 40 total. Recall is a findability metric; it does not measure whether the answer was right.

**The finding I didn't expect.** Regenerating this page moved the numbers twice in one audit — same query set, different retrieval-code commits — and a CI run later produced different results for identical code depending on which cloud CPU the job landed on. Bit-identical per host, divergent across hosts, because float kernels differ across CPU generations and one near-tied ranking decision flipped with them. Without regeneration on every retrieval-path change, a benchmark snapshot's shelf life is one commit. That's the actual lesson, more than any single ratio.

**Not in the benchmark on purpose:** the synapse layer. It learns from *your* usage, so it can't be part of a fixed reproducible number — injection is off for all of the above. It's measured separately by an A/B eval that CI gates on direction only (recall-on >= recall-off, at a neutral token budget), with an observed band of +3.5 to +14 pts top-k hit rate. I'm not quoting a single figure for it, because CI gates the sign, not the size. One caveat I'd rather state than have you find: on AVX-512 hosts that same A/B currently measures -1.75 pts, and the gate fails there. It's a host-dependent ranking bug, root-caused and open — not something the gate was widened to accept.

    pip install neuralmind
    neuralmind build /path/to/repo
    neuralmind install-mcp --all      # or point any MCP client at neuralmind-mcp

Reproduce the table from a clean clone — `pip install -e . tiktoken` then `python -m evals.public.run`. The harness ships in the source tree, not the wheel. Every number above is in `site/claims.json` with the command that produces it; MIT core. Happy to be told where the methodology is wrong.

---

## Post 2 — OpenClaw (Discord `#plugins` / GitHub Discussions)

**Title:** NeuralMind on ClawHub — persistent codebase memory for OpenClaw, 21 MCP tools, local

**Body:**

NeuralMind is now on ClawHub as a community skill. It gives OpenClaw persistent memory of a codebase: a weighted graph of symbols answered by progressive disclosure, plus a synapse layer that strengthens edges between files you use together and decays the ones you don't.

Two ways in, and they are not the same thing:

**Skill only** — drives the `neuralmind` CLI through your terminal tool:

    pip install neuralmind
    openclaw skills install @dfrostar/neuralmind

**MCP server** — the full 21 tools as first-class tools:

    pip install neuralmind
    neuralmind build /absolute/path/to/repo
    openclaw mcp set neuralmind '{"command":"neuralmind-mcp","args":[]}'
    openclaw mcp show neuralmind

**The gotcha that will bite you.** OpenClaw starts the server detached, so its working directory is not your project. `neuralmind-mcp` takes no launch arguments — every tool resolves its own `project_path`, relative to wherever the *server* process happens to be. Pass an absolute path, not `.`. As of the current release the server says so out loud instead of failing quietly: `neuralmind_stats` returns `built: false` with a hint naming the directory your relative path actually resolved to, and `wakeup` / `query` / `search` return that hint as an explicit error rather than silently indexing the wrong tree.

**Why it's worth the setup.** Every host pointed at the same project path reinforces the same synapse store. If you also run Claude Code or Hermes on that repo, they share one learned memory — associations another agent built are visible to this one.

On numbers: 93.75% mean gold-file recall (79-100% per repo, `click` weakest at 0.79) at 44.9-256.8x fewer tokens than pasting whole files, across 40 pre-registered queries on 4 pinned repos. Every miss is published, and a bare vector baseline beats it on one of the four. Reproduce with `python -m evals.public.run`. No telemetry and nothing on the wire at query time. One exception, stated precisely: the first embed on a machine with no cached model has NeuralMind's own embedder fetch the MiniLM ONNX archive over HTTPS, SHA256-pinned. Set `NEURALMIND_ONNX_MODEL_DIR` (or pre-seed `~/.cache/neuralmind/onnx_models/`) and even that goes away.

Listing: clawhub.ai/dfrostar/skills/neuralmind · Source: github.com/dfrostar/neuralmind

---

## Post 3 — Hermes-Agent (Nous Research Discord `#agent` / GitHub Discussions)

**Title:** NeuralMind MCP for Hermes — persistent codebase memory, 21 tools, no bridge process

**Body:**

Hermes already builds a model of *you* across sessions. NeuralMind does the same thing for a *codebase*: a weighted symbol graph answered by progressive disclosure, plus a Hebbian synapse layer that learns which files move together from real usage and decays what you stop touching.

Hermes has a native MCP client, so the `neuralmind_*` tools arrive alongside `terminal` and `read_file` — no bridge.

    pip install neuralmind
    pip install mcp            # minimal Hermes installs need this explicitly
    neuralmind build /absolute/path/to/repo
    hermes mcp add             # or edit ~/.hermes/config.yaml
    hermes mcp test neuralmind # should report 21 tools

Skipping MCP entirely also works — the portable skill installs straight from GitHub and drives the CLI through `terminal`:

    hermes skills install dfrostar/neuralmind/skills/neuralmind

**Absolute paths matter here.** Hermes runs the server as a long-lived background process, so `project_path="."` resolves against the server's directory, not your repo. Pass the absolute path; the server now returns an explicit hint naming the wrong directory instead of building an index of it.

A catalog entry is **submitted and awaiting merge** — NousResearch/hermes-agent#97207, labelled `type/feature` / `tool/mcp` / `P3`. A contributor reviewed the manifest, and the points they raised are resolved; that sign-off was a comment rather than a formal approving review, and no maintainer has reviewed or merged it. It is not merged, so for now this is a manual `hermes mcp add`.

Numbers, with the losses attached: 93.75% mean gold-file recall (79-100% per repo) at 44.9-256.8x fewer tokens than pasting whole files, over 40 pre-registered queries on 4 SHA-pinned repos; 4 misses, all published; a bare vector-RAG baseline using the same encoder beats it on `click`. Reproduce: `python -m evals.public.run`. No telemetry and nothing on the wire at query time. The one exception, which the catalog manifest now spells out after review feedback: on a machine with no cached model, NeuralMind's own embedder fetches the MiniLM ONNX archive over HTTPS, SHA256-pinned, the first time it embeds — `NEURALMIND_ONNX_MODEL_DIR` pre-seeds around it. And your model still sees whatever slice the agent picks.

Source: github.com/dfrostar/neuralmind

---

## Post 4 — Agent Zero (Discord / GitHub Discussions)

**Title:** NeuralMind — codebase memory over MCP for Agent Zero (registry PR open, validator green)

**Body:**

NeuralMind indexes a repo into a weighted code graph, answers questions by progressive disclosure instead of file dumps, and learns which files belong together from co-activation — so retrieval sharpens on the repo you actually work in.

Wire it up through Agent Zero's MCP configuration, pointed at `neuralmind-mcp`:

    pip install neuralmind
    neuralmind build /absolute/path/to/repo
    # then add to Agent Zero's MCP config:
    #   command: neuralmind-mcp
    #   args: []

That exposes 21 tools — query, search, structural and synaptic neighbours, impact analysis, health, savings, review, and the synapse-store tools.

**Use absolute paths.** Agent Zero starts the server detached, so a relative `project_path` resolves against the server's directory. The server reports the directory it actually resolved rather than indexing the wrong tree, but the fix is yours: pass the absolute path.

A registry entry is **submitted to `a0-plugins` and awaiting maintainer review** — agent0ai/a0-plugins#499, plugin validator green. Not merged yet, so install is manual for now.

Where it stands on numbers: 93.75% mean gold-file recall, 79-100% per repo (`click` is the weakest at 0.79, 2 of 7 queries missed), 90% found-rate, at 44.9-256.8x fewer tokens than pasting whole files — 40 pre-registered queries across four SHA-pinned OSS repos. Every miss is published, including the repo where a bare vector baseline beats it outright. Reproduce with `python -m evals.public.run`. MIT core, no telemetry, and no repository content transmitted — one first-build model download aside, pre-seedable.

Source: github.com/dfrostar/neuralmind

---

## Demo material to record before posting

Everything below has to be recorded on a real machine — none of it can be
produced from CI output alone. Grouped by which post needs it.

### Needed by all four posts

1. **Fresh-install smoke, cold machine.** Capture the whole terminal:

       pip install neuralmind
       neuralmind build /absolute/path/to/some-oss-repo
       neuralmind stats /absolute/path/to/some-oss-repo

   Capture: wall-clock of the build, node/edge counts, that it completes
   with no network error. This is what someone piloting the install sees.

2. **A real query, tokens visible.** Same repo:

       neuralmind query /abs/path "how does authentication work"
       neuralmind savings /abs/path

   Capture: the assembled context and the token count. This is the single
   most persuasive asset and nothing in the repo currently produces a
   shareable recording of it.

3. **Benchmark regeneration on your hardware.**

       python -m evals.public.run

   Capture: the full table plus the host CPU model. Two reasons — it
   confirms the published table still reproduces at posting time, and given
   the cross-host float divergence already found, you want to know *before*
   posting whether your machine reproduces the committed numbers or is a
   third data point. **If your run disagrees with the committed table, the
   posts get the new numbers, not the old ones.**

### Post 1 (r/LocalLLaMA) additionally needs

4. **The offline claim, actually demonstrated.** Build and query with the
   network off (or the interface down) after a warm install. Capture the
   sequence proving the *runtime* needs no network. Without this, the
   local-first framing is a claim rather than a demo — and r/LocalLLaMA is
   the one audience that will test it.
5. **Optional but strong: the synapse layer learning.** Two `next_likely`
   or `synaptic_neighbors` calls on the same node, before and after a work
   session that touches a cluster of files, showing the ranking change.
   Label the observed lift as a band, never a fixed figure.

### Post 2 (OpenClaw) additionally needs

6. **The full registration sequence, live:**

       openclaw skills install @dfrostar/neuralmind
       openclaw mcp set neuralmind '{"command":"neuralmind-mcp","args":[]}'
       openclaw mcp show neuralmind

   Capture the tool list showing 21 tools. **Confirm the verify subcommand
   before posting** — the repo documents `openclaw mcp show`; check it
   against the CLI you have and fix `skills/neuralmind/SKILL.md`,
   `docs/wiki/Integration-Guide.md` and the README together if it differs.
7. **The absolute-path guard firing.** Call `neuralmind_stats` with `"."`
   under the detached server and capture the `built: false` + hint output,
   then the same call with an absolute path succeeding. It turns the gotcha
   paragraph into a demonstration.

### Post 3 (Hermes) additionally needs

8. **`hermes mcp test neuralmind` output showing 21 tools**, on an install
   where `pip install mcp` was needed, so the extra step is visibly
   justified rather than asserted.
9. **The skill-only path** — `hermes skills install
   dfrostar/neuralmind/skills/neuralmind` followed by a query driven
   through `terminal`, proving the no-MCP route works.

### Post 4 (Agent Zero) additionally needs

10. **A screenshot of the tools loaded inside Agent Zero's UI.** This is the
    only one of the four hosts with a GUI worth screenshotting, and the
    community there is visual. Nothing else in the repo has ever captured
    this.

### Do not record / do not claim

- No stopwatch on a query. There is still no committed end-to-end latency
  benchmark, so no post may quote one. `tests/benchmark/latency.py` measures
  the synapse layer only, and deliberately excludes embedding and vector
  search.
- Nothing recorded against a private client repo. Use OSS repos for every
  capture.

---

## Claim sources

| Claim in the posts | Source |
|---|---|
| 93.75% mean recall, 79-100% per repo, 90% found-rate, 40 queries / 4 pinned repos | `site/claims.json` `non_ratio_headline_claims` -> `docs/benchmarks/public.md`; `python -m evals.public.run` |
| 44.9x / 99.6x / 76.4x / 256.8x, and the 44.9-256.8x band | `site/claims.json` `ratios`, evidence `reproducible` |
| Per-repo token counts (930 / 788 / 772 / 905) and full-file baselines (41,729 / 78,514 / 59,013 / 232,483) | `docs/benchmarks/public.md` results tables |
| `click` weakest: 0.79 recall, 2 of 7 misses, MRR 0.52 vs 0.67 | `docs/benchmarks/public.md`, "Where it missed" + `click` table |
| `embedding-rag` matches/beats on 3 of 4 repos, always cheaper, and is NeuralMind's own encoder | `docs/benchmarks/public.md`, "The baselines" + "What the numbers honestly say" #2 |
| Benchmark moved twice in one audit; cross-host float divergence | `docs/benchmarks/public.md`, "The corpus"; `docs/social/2026-08-19-claims-integrity-linkedin.md` |
| Synapse A/B gated on direction, band +3.5 to +14 pts on passing hosts and -1.75 pts on AVX-512 hosts | `site/claims.json` `non_ratio_headline_claims` note; `docs/benchmarks/public.md` "What this benchmark does not measure"; `tests/test_benchmark_regression.py` docstring |
| 21 MCP tools | `grep -c '^def tool_' neuralmind/mcp_server.py` = 21 |
| ClawHub live, v1.0.0, community channel, owner `dfrostar` | `clawhub.ai/api/v1/packages/neuralmind`, fetched 2026-08-28 |
| a0-plugins submitted, validator green, not merged | agent0ai/a0-plugins#499 checks page, "Validate Plugin PR" succeeded 2026-08-28 |
| Hermes catalog submitted, labels `type/feature` / `tool/mcp` / `P3`, not merged, contributor review resolved, no formal review recorded | NousResearch/hermes-agent#97207, checked 2026-08-29 09:00Z |
| The one outbound request: NeuralMind's own embedder fetches the SHA256-pinned all-MiniLM-L6-v2 ONNX archive on first embed when no cached model is found | `neuralmind/onnx_embedder.py` (`_ARCHIVE_URL`, `_download_into`, resolution order `$NEURALMIND_ONNX_MODEL_DIR` → `~/.cache/neuralmind/onnx_models/` → `~/.cache/chroma/onnx_models/` → download). Verified in code 2026-08-28, not taken from the docs |
| "transmits no repository content", no telemetry | `README.md`; `neuralmind/onnx_embedder.py`, `daemon_client.py`, `local_client.py` read directly. The older phrasing is now itself a FORBIDDEN pattern — it was false on a cold install | <!-- claims-guard:allow — row names the retired phrase in order to record its retirement -->
| Detached-host absolute-path guard and its hint behaviour | `skills/neuralmind/SKILL.md` "Pass a real path, not `.`"; `neuralmind/mcp_server.py` |
| Host commands (`openclaw mcp set/show`, `hermes mcp add/test`, `hermes skills install`) | `skills/neuralmind/SKILL.md`; `docs/wiki/Integration-Guide.md` |
| ClawHub install command `openclaw skills install @dfrostar/neuralmind` | The live ClawHub listing page, 2026-08-28 |
