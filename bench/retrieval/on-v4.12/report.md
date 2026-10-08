# Retrieval eval

hit@5 / MRR / avg tokens per repo and configuration (30 questions each).

| Repo | baseline | l3_k4 | code_signal | auto_intent | l3_only | bm25_off |
|---|---:|---:|---:|---:|---:|---:|
| requests | 100% / 0.83 / 699 | 93% / 0.81 / 616 | 97% / 0.82 / 701 | 100% / 0.83 / 699 | 100% / 0.83 / 285 | 97% / 0.86 / 700 |
| click | 100% / 0.87 / 602 | 93% / 0.84 / 491 | 100% / 0.82 / 601 | 100% / 0.87 / 602 | 100% / 0.87 / 291 | 97% / 0.81 / 640 |
| flask | 93% / 0.74 / 744 | 87% / 0.72 / 652 | 93% / 0.74 / 756 | 93% / 0.74 / 744 | 93% / 0.74 / 343 | 90% / 0.77 / 762 |
| rich | 90% / 0.66 / 750 | 73% / 0.62 / 679 | 87% / 0.65 / 750 | 90% / 0.66 / 750 | 90% / 0.66 / 270 | 90% / 0.74 / 760 |
| neuralmind | 77% / 0.54 / 1,071 | 67% / 0.51 / 953 | 77% / 0.54 / 1,072 | 67% / 0.51 / 1,091 | 77% / 0.54 / 438 | 70% / 0.53 / 1,061 |
| **mean** | **92.0% / 0.729** | **82.7% / 0.701** | **90.7% / 0.714** | **90.0% / 0.723** | **92.0% / 0.729** | **88.7% / 0.742** |

Query latency p50 / p95 (ms), baseline configuration:

- requests: 19 / 30
- click: 20 / 28
- flask: 18 / 22
- rich: 18 / 60
- neuralmind: 74 / 552

## Keep rule (paired, against baseline)

| Config | hit@5 won / lost | McNemar p | Δ MRR [95% CI] | Worst repo (questions) | Δ tokens | Public recall | Keep |
|---|---:|---:|---:|---:|---:|---:|---|
| l3_k4 | 0 / 14 | 0.000 | -0.028 [-0.043, -0.014] | -5 | -12.6% | — | no |
| code_signal | 0 / 2 | 0.500 | -0.015 [-0.029, -0.004] | -1 | +0.4% | — | no |
| auto_intent | 0 / 3 | 0.250 | -0.005 [-0.015, +0.005] | -3 | +0.4% | — | no |
| l3_only | 0 / 0 | 1.000 | +0.000 [+0.000, +0.000] | +0 | -57.5% | — | no |
| bm25_off | 1 / 6 | 0.125 | +0.013 [-0.024, +0.050] | -2 | +1.9% | — | no |

Baseline reproduced exactly on all 5 repos (re-run after every configuration): the deltas above are the flags, not state left behind.
