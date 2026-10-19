# NeuralMind vs. Prompt caching (Anthropic / OpenAI)

## What prompt caching is

Anthropic and OpenAI both offer *prompt caching*: when you resend the same prefix on many requests, the provider caches the computed KV state and charges a discounted rate (Anthropic: ~10% of the normal input price) for the cached portion. It is a **pricing** optimization, not a **context** optimization.

## How NeuralMind differs

Prompt caching makes resending a large context cheaper. NeuralMind makes the context **smaller in the first place**. They solve different halves of the problem.

| Dimension | Prompt caching | NeuralMind |
|---|---|---|
| What it optimizes | Repeat cost of the same prefix | Size of the prefix itself |
| Discount mechanism | Provider-side cache hit | Client-side retrieval |
| Requires identical prefix | Yes | No |
| First-turn savings | 0% | 51–242× fewer tokens than pasting every source file (public benchmark) |
| Nth-turn savings (cached) | ~90% of cached portion | The same (plus cache on top) |
| Works offline | No | Yes |
| Tool-output savings | No | No (its PostToolUse hooks used to compress; measured, that added tokens — [benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md)) |
| Vendor lock-in | Yes (per-provider) | No |

## Worked example

`psf/requests` from NeuralMind's
[public benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)
(v4.12.0: 41,729 tokens to paste every source file, 816 mean tokens per
NeuralMind query), 100 queries/day, Claude Sonnet input at $3/MTok. Token counts
are measured; the dollar figures are arithmetic, not a measured bill:

| Strategy | First query | Subsequent queries | Monthly |
|---|---|---|---|
| Raw repo, no cache | 41,729 × $3/MTok ≈ $0.125 | $0.125 | ~$376 |
| Raw repo + prompt caching | $0.125 + cache write | ~$0.0125 (cache hit) | ~$40 |
| NeuralMind | ~$0.0024 (816 tokens) | ~$0.0024 | ~$7 |
| NeuralMind + prompt caching | ~$0.0024 + cache write | ~$0.00024 | ~$1 |

Caching on top of NeuralMind is not zero cost, but it is essentially free at this scale.

## When to pick which

- **Pick prompt caching alone** when your prompt is already small and mostly static (system prompts, short tool definitions).
- **Pick NeuralMind alone** when you don't want vendor-specific plumbing.
- **Combine them** for the cheapest possible sustained coding workload: NeuralMind shrinks the code context, and prompt caching amortizes the repeated project instructions.

---

[← Back to comparison index](./README.md)
