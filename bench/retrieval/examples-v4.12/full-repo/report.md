# Retrieval eval

hit@5 / MRR / avg tokens per repo and configuration (30 questions each).

| Repo | baseline | examples_equal |
|---|---:|---:|
| requests | 97% / 0.81 / 976 | 97% / 0.81 / 976 |
| click | 93% / 0.76 / 831 | 93% / 0.75 / 831 |
| flask | 90% / 0.74 / 929 | 90% / 0.74 / 929 |
| rich | 87% / 0.57 / 880 | 83% / 0.57 / 876 |
| **mean** | **91.7% / 0.721** | **90.8% / 0.716** |

Query latency p50 / p95 (ms), baseline configuration:

- requests: 5 / 6
- click: 5 / 7
- flask: 5 / 6
- rich: 4 / 5

## Keep rule (paired, against baseline)

| Config | hit@5 won / lost | McNemar p | Δ MRR [95% CI] | Worst repo (questions) | Δ tokens | Public recall | Keep |
|---|---:|---:|---:|---:|---:|---:|---|
| examples_equal | 0 / 1 | 1.000 | -0.006 [-0.015, -0.000] | -1 | -0.1% | — | no |

Baseline reproduced exactly on all 4 repos (re-run after every configuration): the deltas above are the flags, not state left behind.
