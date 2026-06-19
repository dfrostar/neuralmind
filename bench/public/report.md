# NeuralMind — honest public benchmark

Cost (context tokens) vs. correctness (**gold-file recall**, the objective def-site oracle — no LLM judge) across pinned real repositories. Every query is reported, including losses. Reproduce with `python -m evals.public.run`.

- **Tokenizer:** tiktoken o200k_base
- **Determinism:** synapse injection OFF, so every backend's numbers reproduce exactly. The synapse *learning* lift is session-dependent and measured separately by the synapse A/B eval — not part of this fixed number.
- **Correctness oracle:** def-site (gold = symbol definition site)
- **Baselines:** `full-file` (paste every file), `ripgrep` (keyword → top files), `embedding-rag` (top-k chunks, same encoder), `neuralmind` (progressive disclosure + synapses)

## requests  `@0e322af877`

14 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 41729 | 1.00 |
| `ripgrep` | 0.79 | 71% | 26543  (1.6× fewer) | 0.60 |
| `embedding-rag` | 1.00 | 100% | 607  (68.8× fewer) | 0.96 |
| `neuralmind` | 1.00 | 100% | 1095  (38.1× fewer) | 0.96 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **38× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._

## click  `@874ca2bc1c`

7 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 78514 | 1.00 |
| `ripgrep` | 0.79 | 71% | 45059  (1.7× fewer) | 0.60 |
| `embedding-rag` | 1.00 | 100% | 649  (121.1× fewer) | 0.60 |
| `neuralmind` | 1.00 | 100% | 924  (85.0× fewer) | 0.60 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **85× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._
