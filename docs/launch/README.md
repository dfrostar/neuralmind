# Launch kit

Copy-paste-ready launch materials for NeuralMind, kept in the repo so they
survive across sessions and stay in sync with the shipped numbers.

**One hard rule for everything in this folder: disclosed-maker only.** Every
post here is written in the first person *as the author of the project*. We do
**not** write "unaffiliated end-user" posts, age or rent personas, or evade a
platform's self-promotion rules. The credibility of the benchmark work is the
whole point of the launch; sockpuppeting throws it away and breaks the rules of
every venue below. If a venue won't allow a disclosed maker to post, we don't
post there — we don't post under a disguise.

## Contents

| File | Venue | Notes |
|---|---|---|
| [`show-hn.md`](show-hn.md) | Hacker News (Show HN) | Title + body + first-comment context. Maker submits, discloses in the comment. |
| [`r-localllama.md`](r-localllama.md) | r/LocalLLaMA | Self-post, maker-disclosed, four-benefit block with live links. |
| [`awesome-mcp-servers.md`](awesome-mcp-servers.md) | `awesome-mcp-servers` PR | One-line directory entry + PR description. |
| [`hn-warmup-comments.md`](hn-warmup-comments.md) | Hacker News (other threads) | Genuine, on-topic, disclosed comments on adjacent posts. Not drive-by promo. |
| [`NEXT-SESSION.md`](NEXT-SESSION.md) | (internal) | Session handoff + "what we did" record + recommended next steps. Copy-paste to resume. |

## Live anchors (keep these accurate)

All posts cite these — update them here and in the posts together if the
numbers move.

- Repo: <https://github.com/dfrostar/neuralmind>
- Benchmark methodology + raw data: [`docs/benchmarks/public.md`](../benchmarks/public.md)
- Reproduce the headline number: `python -m evals.public.run`
- Reproduce the competitor row: `python -m evals.public.competitor`

### The four data-backed benefits (single source of truth: README "Why NeuralMind")

| Benefit | Measured result | Where |
|---|---|---|
| **Cheaper context** | 100% gold-file recall at **38–85× fewer tokens** than pasting files; beats `ripgrep` on both recall and cost | Public benchmark (`requests`, `click`) |
| **Finds the *right* code** | 100% gold-file recall, **MRR 0.96**; beats incumbent `codebase-memory-mcp` on ranking (0.96 vs 0.23) | Same benchmark |
| **Learns how you work** | Hebbian synapse layer: **+11.7 pts** top-k hit-rate (71.7%→83.3%), budget-neutral | Synapse A/B eval |
| **Better-grounded answers** | At matched budget, **faithfulness +0.143, grounding 1.00** | Faithfulness/parity gate |

*Honest-scope caveat carried in every post:* cost + accuracy run on real pinned
OSS repos (fully reproducible); learning + grounding are committed A/Bs on the
bundled reference fixture (real but smaller-scope). A well-tuned vector RAG ties
NeuralMind on pure findability and is cheaper on raw tokens — that's in the
table, not hidden.

## HN posting guidance (operational)

- Submit the **Show HN** yourself, as the maker. Title starts with `Show HN:`.
- Post the disclosure/context as the **first comment** immediately after
  submitting (HN convention) — see `show-hn.md`.
- Don't ask for upvotes anywhere. Don't post the link in unrelated threads.
- The warm-up comments in `hn-warmup-comments.md` are for *genuinely relevant*
  existing threads — they lead with something useful and disclose the
  affiliation when NeuralMind is mentioned. They are not a vote-ring.
- Best time: a weekday morning US Eastern. Be around to answer for the first
  few hours — engaged maker answers are what move a Show HN.
