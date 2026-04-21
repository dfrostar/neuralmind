# NeuralMind vs. Prompt caching (Anthropic / OpenAI)

## What prompt caching is

Anthropic and OpenAI both offer *prompt caching*: when you resend the same prefix on many requests, the provider caches the computed KV state and charges a discounted rate (Anthropic: ~10% of the normal input price) for the cached portion. It is a **pricing** optimization, not a **context** optimization.

## How NeuralMind differs

Prompt caching makes resending a large context cheaper. NeuralMind makes the context **smaller in the first place**. They solve different halves of the problem.

| Dimension | Prompt caching | NeuralMind |
|---|---|---|
| What it optimizes | Repeat cost of the same prefix | Size of the prefix itself |
| Discount mechanism | Provider-side cache hit | Client-side retrieval + compression |
| Requires identical prefix | Yes | No |
| First-turn savings | 0% | 40–70× |
| Nth-turn savings (cached) | ~90% of cached portion | 40–70× (plus cache on top) |
| Works offline | No | Yes |
| Tool-output savings | No | Yes |
| Vendor lock-in | Yes (per-provider) | No |

## Worked example

50,000-token codebase, 100 queries/day, Claude Sonnet input at $3/MTok:

| Strategy | First query | Subsequent queries | Monthly |
|---|---|---|---|
| Raw repo, no cache | 50K × $3/MTok = $0.15 | $0.15 | ~$450 |
| Raw repo + prompt caching | $0.15 + cache write | ~$0.015 (cache hit) | ~$50 |
| NeuralMind | ~$0.0024 (800 tokens) | ~$0.0024 | ~$7 |
| NeuralMind + prompt caching | ~$0.0024 + cache write | ~$0.00024 | ~$1 |

Caching on top of NeuralMind is not zero cost, but it is essentially free at this scale.

## When to pick which

- **Pick prompt caching alone** when your prompt is already small and mostly static (system prompts, short tool definitions).
- **Pick NeuralMind alone** when you don't want vendor-specific plumbing.
- **Combine them** for the cheapest possible sustained coding workload: NeuralMind compresses the code context, and prompt caching amortizes the repeated project instructions.

---

[← Back to comparison index](./README.md)
