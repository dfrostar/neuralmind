# Does NeuralMind actually work on *your* codebase?

Don't take our word for it. CI gates a conservative token-reduction floor on a small committed fixture, and the public benchmark measures 46–263× on four pinned OSS repos — but your codebase isn't any of those. The only way to know what NeuralMind does for *you* is to run it on *your* code.

This walkthrough gets you from zero to a real before/after number on your repository in **under 5 minutes**, with no commitment beyond a pip install.

## What you'll have at the end

- A measured **reduction ratio** on your actual code, divided by the measured size of your code (v4.5.0+)
- A **retrieval-quality score** (recall@k / MRR / answerability) on your own code, plus a list of any symbols the index can't find — via `neuralmind probe`
- An **estimated monthly savings** in dollars, at your query volume and your model's pricing
- A **JSON blob** you can share with your team (or contribute back to the public community benchmarks — your choice, zero telemetry)

If the numbers don't justify the install — you uninstall and move on. Nothing else happens. NeuralMind never uploads anything.

## Step 1 — Install (60 seconds)

```bash
pip install neuralmind tiktoken
```

`graphifyy` builds the code knowledge graph NeuralMind reads from; `tiktoken` is needed for accurate OpenAI-model token counting. If you only care about a rough number, `tiktoken` is optional.

## Step 2 — Index your repo (2–3 minutes)

```bash
cd /path/to/your-project
neuralmind build .
```

The first build takes 1–3 minutes depending on repo size. Incremental rebuilds after code changes take seconds.

**Indexed with an earlier version?** Run `neuralmind build .` once after upgrading to v4.6.0. The build writes the keyword index that now covers docs and code together; queries never build, so until then every number below measures the previous version's ranking.

**Sanity check — make sure it worked:**

```bash
neuralmind stats .
```

You should see something like:
```
Project: your-project
Built: True
Nodes: 1,247
Communities: 23
```

If `Built: False`, the build step failed — see [Troubleshooting](../wiki/Troubleshooting.md).

## Step 3 — Run the benchmark

```bash
neuralmind benchmark .
```

Output on `psf/requests` v2.32.3 (verbatim, v4.5.0 — your numbers will vary):

```
Project: requests
Baseline: measured: 94,069 tokens in 36 indexed code files
Questions: generic
Wake-up tokens: 510
Avg query tokens: 1200.6
Avg reduction: 78.6x
Legacy reduction: 41.8x (vs the fixed 50K-token estimate used before v4.5.0)
Summary: 78.6x average token reduction vs measured: 94,069 tokens in 36 indexed code files
```

To reproduce it: `git clone --depth 1 --branch v2.32.3 https://github.com/psf/requests`,
then `neuralmind build .` and `neuralmind benchmark .` inside the checkout.

**The baseline line matters (v4.5.0+).** The ratio is the measured token count
of every code file the index covers over the tokens each question costs, so it
scales with your repo: a large repo reports a larger ratio than a small one for
the same context size. Three rules keep it honest:

- **Code only.** Markdown and other prose are left out whenever the index holds
  code — `requests`' `HISTORY.md` changelog alone is 15,088 tokens, and a
  changelog isn't what a code question would load. Tests count if your index
  covers them; leave them out with `.neuralmindignore` and both sides change
  together.
- **Same units as the context.** Both sides are counted at ~4 characters per
  token, so the ratio doesn't move with which tokenizer you have installed.
- **Measured at build.** `neuralmind build` caches it in
  `.neuralmind/baseline.json`; an index built before v4.5.0 is measured on the
  spot.

Before v4.5.0 every repo was divided by a fixed 50,000-token guess. The
`Legacy reduction` line repeats the run against it, and `--naive-50k` makes it
the headline. "Questions" reads `project eval` when the repo has a
`.neuralmind.eval.yaml` — see [Step 3d](#step-3d--score-it-against-your-own-questions-neuralmind-eval).

The public benchmark's 45.0× on `requests` is a different measurement — its
own 14 questions, against non-test source only — so the two numbers don't
compare directly.

**What those numbers mean for you:**

| Metric | What it says |
|---|---|
| **Wake-up tokens** | Cost of one "orient the agent" call at session start. ~500 tokens = ~$0.0015 on Claude Sonnet. |
| **Avg query tokens** | Cost of one code question (across NeuralMind's default 5-query sample). ~1,200 tokens = ~$0.0036 per question. |
| **Avg reduction** | How many times smaller NeuralMind's context is than all the code the index covers (the measured baseline). 78.6× means a question costs ~1.3% of pasting that code. |
| **Legacy reduction** | The same questions against the fixed 50K estimate — comparable with numbers from before v4.5.0 and with the community table. |

## Step 3b — Verify retrieval quality (v0.38.0+)

The plain benchmark tells you *how many tokens* NeuralMind saves. The `--quality` flag tells you *whether NeuralMind finds the right code*. Token reduction is the headline claim; retrieval quality is the fine print that makes it meaningful.

```bash
neuralmind benchmark . --quality
```

This runs 57 golden queries across three language fixtures, scores them against hand-labeled expected modules, and prints a markdown table:

```
| Suite      | Queries | MRR   | Answerability | Recall@5 | Gate |
|------------|--------:|------:|--------------:|---------:|:----:|
| go         |      19 | 0.939 |          100% |    0.860 | PASS |
| python     |      19 | 0.974 |          100% |    0.781 | PASS |
| typescript |      19 | 0.947 |          100% |    0.807 | PASS |
```

The CI gate (recall@5 ≥ 0.50, MRR ≥ 0.50) is a conservative floor that catches genuine ranking regressions — your baseline numbers will be well above it. The `--baseline` flag lets you track deltas across commits:

```bash
neuralmind benchmark . --quality --baseline evals/quality/baseline.json
```

**Four query categories (PRD 2 task types)** are tested — not just "how does X work?" but also:

| Category | Example query |
|---|---|
| **architecture** | "How does authentication work in this codebase?" |
| **bug-localization** | "Stripe webhooks are being rejected — where is the signature verified?" |
| **refactor** | "I need to add an email_verified column to users — which files would change?" |
| **next-edit** | "I just changed how JWT tokens are signed — what other files should I review?" |

If recall@5 is low on a particular category, it tells you where the retrieval index has blind spots.

**Automate it in CI (v0.38.0):** The bundled `.github/workflows/neuralmind-autoindex.yml` action rebuilds the index, runs the quality gate, and commits updated team memory on every push to main — no manual refresh needed. Copy it from the NeuralMind repo and add your project path to the workflow inputs.

## Step 3c — Probe retrieval on your own code (`neuralmind probe`)

Reduction proves NeuralMind is **cheap**. It says nothing about whether the
context it returns is **correct**. A 46× reduction that drops the one file your
question needed is a bad trade. `neuralmind probe` measures that second
dimension — on *your* code, with no labeling required:

```bash
neuralmind probe .
```

It samples indexed symbols, queries each one by its **docstring/intent** (e.g.
*"Raised when the exp claim is in the past"* — note that doesn't contain the
symbol name, so it's a real plain-English → code test, not a string match), asks
the index to retrieve the code back, and scores whether the right file came up:

```
Retrieval self-probe — your-project
Sampled 63 of 64 indexed symbols, retrieval depth k=10
Query source: 51 rationale, 12 label
============================================================
  answerability  : 98%  (file found in top-10)
  MRR            : 0.789
  recall@1/3/5   : 0.667 / 0.905 / 0.968
  blind spots    : 1
------------------------------------------------------------
Symbols the index couldn't retrieve from their own description (1 total):
  - get_me_endpoint()  (api/routes.py)   query: "GET /api/users/me — requires Authorization: Bearer header"
```

The `Query source` line is the honesty knob: `rationale` probes ask by docstring
(a real test), `label` probes fall back to the symbol name (weaker) for
undocumented code. A run that's mostly `label` is a sanity check, not a quality
score.

**What those numbers mean for you:**

| Metric | What it says |
|---|---|
| **answerability** | Of the symbols probed, the fraction whose own file showed up in the top-k. High = the agent can find things by description. |
| **MRR** | How *high* the right file ranks on average (1.0 = always first). |
| **recall@1/3/5** | The right file in the top 1 / 3 / 5 hits. |
| **blind spots** | The symbols that fell through entirely — the concrete places an agent would come up empty. |

The blind-spot list is the actionable part: those are real symbols in your repo
the index can't surface from a natural-language description. If a critical one
shows up there, that's a retrieval gap worth an issue.

**Track it over time.** The probe is deterministic per `--seed`, so you can save
a baseline and diff it after a refactor or a backend switch to catch a
regression before it ships:

```bash
neuralmind probe . --sample-size 100 --json > probe-baseline.json
# …later…
neuralmind probe . --sample-size 100 --baseline probe-baseline.json
```

Because `--json` is stable and machine-readable, you can also gate CI on a
per-repo recall or MRR floor. Unlike `neuralmind benchmark --quality` (which
scores ranking against the project's *golden* fixtures and is a contributor/CI
self-test), `probe` needs no labels and runs on **any** repo.


## Step 3d — Score it against your own questions (`neuralmind eval`)

Probe tests symbols against their own docstrings. The strongest test is the
questions your team actually asks, with the file that answers each (v4.5.0+):

```bash
neuralmind eval . --suggest --write   # draft .neuralmind.eval.yaml from docstrings + README
# edit the questions and gold files, commit the file
neuralmind eval .                     # hit@1 / hit@5 / MRR, read-only
neuralmind eval . --report            # the history, as a markdown table
```

The eval never trains the synapse layer it measures, and each run is recorded
with its commit and NeuralMind version so you can see a refactor or an upgrade
move the numbers. Walkthrough:
[Measure retrieval on your own repo](./measure-retrieval-on-your-repo.md).

**Comparing rankings (v4.6.0+).** Ranking changes are environment variables
read at query time, so the same eval scores the previous version's ranking —
`NEURALMIND_BM25_UNIFIED=0 neuralmind eval . --no-history` — or an
off-by-default research flag, without a rebuild. Walkthrough:
[A/B-test a ranking change on your own repo](./ab-test-a-ranking-change.md).

## Step 4 — Translate to real money

At **100 queries/day** on **Claude 3.5 Sonnet** ($3/MTok input):

- Naive (load relevant files, ~20K tokens/query): ~$180/month
- NeuralMind (46× reduction, ~430 tokens/query): ~$4/month
- **Saved: ~$176/month per developer**

Adjust for your model and volume — the math scales linearly. GPT-4o costs ~5× more than Sonnet, so savings are larger. Claude Haiku costs less, so savings are smaller in absolute terms but the ratio stays the same.

## Step 5 — Decide

You now have measured, reproducible numbers on **your code**, not ours. Three paths:

### Path A — Install and use it

If the savings justify it, nothing more to do — you've already installed. Start asking code questions:

```bash
neuralmind query . "How does authentication work?"
neuralmind skeleton src/auth/handlers.py
```

Claude Code users: install the hooks for session memory, prompt-time recall, and a stale-decision guard. They don't compress `Read`/`Bash`/`Grep` output ([benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md)):

```bash
neuralmind install-hooks .
```

### Path B — Share the numbers with your team

```bash
neuralmind benchmark . --contribute --submitter your-github-handle
```

That flag emits a JSON blob with your project name, numbers, and the exact command that produced them. **Nothing is uploaded.** You get a text blob to paste into Slack, a design doc, or a PR.

The blob carries two ratios (v4.5.0+, `schema_version: 2`): `avg_reduction_ratio`
against the fixed 50K estimate every community row compares on, reproduced by
the `verification_command` (`neuralmind benchmark . --naive-50k --json`), and
`measured_avg_reduction_ratio` against `full_codebase_tokens`, your measured
code (from a plain `neuralmind benchmark . --json`). On `requests` that is 41.8
and 78.6.

### Path C — Contribute to the public community benchmarks (optional)

If your project is open source (or the numbers are OK to share), drop the JSON blob into the community leaderboard:

- **Easy:** [open a benchmark submission issue](https://github.com/dfrostar/neuralmind/issues/new?template=community-benchmark.yml) — form fields map 1:1 to the `--contribute` output.
- **Direct PR:** add the entry to `docs/community-benchmarks.json` and run `python scripts/render_community_table.py --inject README.md`.

Every submission is auditable — entries include the exact `neuralmind benchmark` command that produced them.

## If the numbers *don't* look good on your repo

A few things to check before giving up:

1. **Is the graph actually built?** `neuralmind stats .` should report a non-zero node count. If it's tiny, `graphify` may have missed your language or the project structure.
2. **Tiny repos don't need this.** If your whole codebase is under 5K tokens, just paste it into the chat — there's nothing for NeuralMind to compress. On a repo that small the measured ratio can drop below 1×, and `benchmark` says so: the context is larger than the code it covers.
3. **Try a larger query set.** The default 5-query benchmark is representative, not exhaustive. Pass `sample_queries` if you use the Python API.
4. **Check the query intent** (v4.6.0+). `neuralmind query . "your question" --explain` prints the intent L3 ranked with — `Query intent     : docs (by classifier)` on a question about how your code behaves explains why a README ranks above the implementation *within* L3's four hits (a `docs` intent multiplies doc hits by 2.0 and code by 0.7). It can't explain the implementation missing from those four: in v4.6.0's eval, switching intent never changed hit@5. Collect a few of those questions in `.neuralmind.eval.yaml` and [A/B-test the research flags](./ab-test-a-ranking-change.md) on them before turning one on.
5. **Measure retrieval quality directly** with `neuralmind probe .` (see [Step 3b](#step-3b--is-it-retrieving-the-right-code-neuralmind-probe)). If answerability is high but reduction is low, retrieval is fine and the issue is elsewhere; if the blind-spot list is long, that's the gap. **Open an issue** with your probe numbers and repo characteristics — retrieval quality is the thing we most want to improve.

## Related

- [Use case: Cost optimization](./cost-optimization.md) — baseline → measure → report template for stakeholders
- [Use case: Claude Code user](./claude-code.md) — the full Claude Code workflow: MCP tools, hooks, session memory
- [Use case: Measure memory across a major refactor](./measure-memory-across-a-refactor.md) — the before/after version of this benchmark, with a real-world field report
- [Use case: A/B-test a ranking change on your own repo](./ab-test-a-ranking-change.md) — score a research flag, or your own change, before trusting it
- [Comparisons: vs long context windows](../comparisons/vs-long-context.md) — why 1M-token windows don't solve this

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
