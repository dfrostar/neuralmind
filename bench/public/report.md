# NeuralMind — honest public benchmark

Cost (context tokens) vs. correctness (**gold-file recall**, the objective def-site oracle — no LLM judge) across pinned real repositories. Every query is reported, including losses. Reproduce with `python -m evals.public.run`.

- **Tokenizer:** tiktoken o200k_base
- **Determinism:** synapse injection OFF and nothing is sampled, so a re-run on the same machine reproduces every number exactly. Across machines, recall and found-rate have matched exactly, while token counts, and now and then MRR, differed slightly between CI runners with and without AVX-512 (see docs/benchmarks/public.md). The synapse *learning* lift is session-dependent and measured separately by the synapse A/B eval — not part of this fixed number.
- **Correctness oracle:** def-site (gold = symbol definition site)
- **Baselines:** `full-file` (paste every file), `ripgrep` (keyword → top files), `embedding-rag` (top-k entries of the same vector index: names and docstrings, not code bodies), `neuralmind` (progressive disclosure + synapses)

## requests  `@0e322af877`

14 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 41729 | 1.00 |
| `ripgrep` | 0.79 | 71% | 26543  (1.6× fewer) | 0.60 |
| `embedding-rag` | 1.00 | 100% | 229  (181.9× fewer) | 0.92 |
| `neuralmind` | 1.00 | 100% | 816  (51.2× fewer) | 0.93 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **51.2× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._

## click  `@874ca2bc1c`

7 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 78514 | 1.00 |
| `ripgrep` | 0.79 | 71% | 45059  (1.7× fewer) | 0.60 |
| `embedding-rag` | 1.00 | 100% | 220  (357.5× fewer) | 0.86 |
| `neuralmind` | 1.00 | 100% | 670  (117.1× fewer) | 0.86 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **117.1× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._

## flask  `@c12a5d874c`

10 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 59013 | 1.00 |
| `ripgrep` | 0.85 | 80% | 26891  (2.2× fewer) | 0.65 |
| `embedding-rag` | 0.85 | 80% | 272  (217.0× fewer) | 0.74 |
| `neuralmind` | 1.00 | 100% | 861  (68.5× fewer) | 0.72 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **68.5× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._

## rich  `@7f580bdcf0`

9 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 232483 | 1.00 |
| `ripgrep` | 1.00 | 100% | 43437  (5.4× fewer) | 0.75 |
| `embedding-rag` | 1.00 | 100% | 236  (985.5× fewer) | 0.94 |
| `neuralmind` | 1.00 | 100% | 961  (242.0× fewer) | 0.83 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **242.0× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._
