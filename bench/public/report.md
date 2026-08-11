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
| `embedding-rag` | 1.00 | 100% | 607  (68.7× fewer) | 0.96 |
| `neuralmind` | 0.96 | 93% | 930  (44.9× fewer) | 0.93 |

**Headline:** NeuralMind reaches **96% gold-file recall** at **44.9× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

### Where NeuralMind loses

| query | gold | retrieved files |
|---|---|---|
| `xfile-status-codes` | models.py, status_codes.py | models.py |

## click  `@874ca2bc1c`

7 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 78514 | 1.00 |
| `ripgrep` | 0.79 | 71% | 45059  (1.7× fewer) | 0.60 |
| `embedding-rag` | 1.00 | 100% | 634  (123.8× fewer) | 0.67 |
| `neuralmind` | 0.79 | 71% | 788  (99.6× fewer) | 0.52 |

**Headline:** NeuralMind reaches **79% gold-file recall** at **99.6× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

### Where NeuralMind loses

| query | gold | retrieved files |
|---|---|---|
| `echo-util` | utils.py | termui.py, _termui_impl.py, core.py |
| `xfile-command-help` | core.py, formatting.py | decorators.py, core.py |

## flask  `@c12a5d874c`

10 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 59013 | 1.00 |
| `ripgrep` | 0.85 | 80% | 26891  (2.2× fewer) | 0.65 |
| `embedding-rag` | 0.95 | 90% | 687  (85.9× fewer) | 0.73 |
| `neuralmind` | 0.95 | 90% | 772  (76.4× fewer) | 0.78 |

**Headline:** NeuralMind reaches **95% gold-file recall** at **76.4× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

### Where NeuralMind loses

| query | gold | retrieved files |
|---|---|---|
| `xfile-dispatch-context` | app.py, ctx.py | app.py, views.py |

## rich  `@7f580bdcf0`

9 pre-registered queries · retrieval stack: yes

| backend | gold-file recall | found-rate | mean tokens/query | MRR |
|---|---:|---:|---:|---:|
| `full-file` | 1.00 | 100% | 232483 | 1.00 |
| `ripgrep` | 1.00 | 100% | 43437  (5.4× fewer) | 0.75 |
| `embedding-rag` | 1.00 | 100% | 677  (343.2× fewer) | 0.94 |
| `neuralmind` | 1.00 | 100% | 905  (256.8× fewer) | 0.80 |

**Headline:** NeuralMind reaches **100% gold-file recall** at **256.8× fewer tokens** than pasting every file (which is recall 1.0 by definition, at full cost).

_No NeuralMind gold-file misses on this repo._
