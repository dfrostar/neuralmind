# NeuralMind — honest public benchmark

Cost (context tokens) vs. correctness (**gold-file recall**, the objective def-site oracle — no LLM judge) across pinned real repositories. Every query is reported, including losses. Reproduce with `python -m evals.public.run`.

- **Tokenizer:** tiktoken o200k_base
- **Determinism:** synapse injection OFF and nothing is sampled, so a re-run on the same machine reproduces every number exactly. Across machines, recall, found-rate and MRR have matched exactly, while token counts differed slightly on some CI runners (see docs/benchmarks/public.md). The synapse *learning* lift is session-dependent and measured separately by the synapse A/B eval — not part of this fixed number.
- **Correctness oracle:** def-site (gold = symbol definition site)
- **Baselines:** `full-file` (paste every file), `ripgrep` (keyword → top files), `embedding-rag` (top-k chunks, same encoder), `neuralmind` (progressive disclosure + synapses)

## requests  `@0e322af877`

14 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 41729 | 1.00 |
| `ripgrep` | 0.79 | 71% | 26543  (1.6× fewer) | 0.60 |
| `embedding-rag` | 1.00 | 100% | 607  (68.8× fewer) | 0.96 |
| `neuralmind` | 0.93 | 86% | 928  (45.0× fewer) | 0.92 |

**Headline:** NeuralMind reaches **93% gold-file recall** at **45.0× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

### Where NeuralMind loses

| query | gold | retrieved files |
|---|---|---|
| `xfile-redirect-auth` | sessions.py, auth.py | sessions.py |
| `xfile-status-codes` | models.py, status_codes.py | models.py, exceptions.py |

## click  `@874ca2bc1c`

7 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 78514 | 1.00 |
| `ripgrep` | 0.79 | 71% | 45059  (1.7× fewer) | 0.60 |
| `embedding-rag` | 1.00 | 100% | 636  (123.4× fewer) | 0.60 |
| `neuralmind` | 1.00 | 100% | 711  (110.4× fewer) | 0.60 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **110.4× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._

## flask  `@c12a5d874c`

10 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 59013 | 1.00 |
| `ripgrep` | 0.85 | 80% | 26891  (2.2× fewer) | 0.65 |
| `embedding-rag` | 0.95 | 90% | 677  (87.2× fewer) | 0.70 |
| `neuralmind` | 0.85 | 80% | 723  (81.6× fewer) | 0.63 |

**Headline:** NeuralMind reaches **85% gold-file recall** at **81.6× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

### Where NeuralMind loses

| query | gold | retrieved files |
|---|---|---|
| `request-wrapper` | wrappers.py | app.py, README.md, helpers.py |
| `xfile-dispatch-context` | app.py, ctx.py | README.md, app.py, views.py |

## rich  `@7f580bdcf0`

9 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 232483 | 1.00 |
| `ripgrep` | 1.00 | 100% | 43437  (5.4× fewer) | 0.75 |
| `embedding-rag` | 1.00 | 100% | 669  (347.4× fewer) | 0.89 |
| `neuralmind` | 1.00 | 100% | 892  (260.7× fewer) | 0.78 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **260.7× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._
