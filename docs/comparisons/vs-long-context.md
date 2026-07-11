# NeuralMind vs. Long context windows (Claude 1M, Gemini 2M, Projects)

## The premise

"Why not just stuff the whole codebase into a 1M or 2M context window?"

It works — for a while. Then the bill arrives.

## The numbers

Consider a 50,000-token codebase and 100 queries/day.

| Approach | Tokens per query | Monthly input cost (Claude Sonnet) |
|---|---|---|
| Full codebase every turn | 50,000 | ~$450 |
| NeuralMind query | ~800 | ~$7 |

Long context windows make it *possible* to stuff everything in. They do not make it *cheap*. Input tokens are billed per token — a 1M context at $3/MTok is $3 per message.

## Other dimensions

| Dimension | Long context | NeuralMind |
|---|---|---|
| Cost scaling | Linear in codebase size | Roughly flat (~800 tokens/query) |
| Recall quality | Strong on small repos, degrades on large ones (needle-in-haystack effects) | Stable — retrieval focuses the window |
| Latency | Increases with context size | Roughly flat |
| Provider lock-in | Ties you to 1M+ models | Model-agnostic |
| Works offline | No | Yes |
| Prompt caching savings | Possible, but full repo still loaded | Context is small enough that caching is secondary |

## When to pick which

- **Use raw long context** for one-off exploration on small repos where you don't mind the bill.
- **Use NeuralMind** for sustained coding work — the per-query savings compound daily, and retrieval quality actually *improves* as the repo grows (more signal for clustering), where raw long context gets worse.

The two also compose: feed NeuralMind's output into a long-context model and you get both focus and headroom.

---

[← Back to comparison index](./README.md)
