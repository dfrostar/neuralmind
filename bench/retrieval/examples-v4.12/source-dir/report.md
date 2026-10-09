# Retrieval eval

hit@5 / MRR / avg tokens per repo and configuration (30 questions each).

| Repo | baseline | examples_equal |
|---|---:|---:|
| requests | 100% / 0.83 / 751 | 100% / 0.83 / 751 |
| click | 100% / 0.83 / 660 | 100% / 0.83 / 660 |
| flask | 97% / 0.77 / 796 | 97% / 0.77 / 796 |
| rich | 90% / 0.66 / 792 | 90% / 0.66 / 792 |
| neuralmind | 80% / 0.64 / 1,146 | 80% / 0.64 / 1,146 |
| **mean** | **93.3% / 0.746** | **93.3% / 0.746** |

Query latency p50 / p95 (ms), baseline configuration:

- requests: 4 / 6
- click: 4 / 5
- flask: 4 / 6
- rich: 4 / 5
- neuralmind: 7 / 13

## Keep rule (paired, against baseline)

| Config | hit@5 won / lost | McNemar p | Δ MRR [95% CI] | Worst repo (questions) | Δ tokens | Public recall | Keep |
|---|---:|---:|---:|---:|---:|---:|---|
| examples_equal | 0 / 0 | 1.000 | +0.000 [+0.000, +0.000] | +0 | +0.0% | 100.00% | no |

Public benchmark baseline recall: 100.00%.

Baseline reproduced exactly on all 5 repos (re-run after every configuration): the deltas above are the flags, not state left behind.
