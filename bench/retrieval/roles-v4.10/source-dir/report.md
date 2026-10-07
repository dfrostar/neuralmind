# Retrieval eval — spec 7 work items

hit@5 / MRR / avg tokens per repo and configuration (30 questions each).

| Repo | baseline | roles_off |
|---|---:|---:|
| requests | 90% / 0.81 / 914 | 90% / 0.81 / 914 |
| click | 87% / 0.76 / 721 | 87% / 0.76 / 721 |
| flask | 87% / 0.73 / 847 | 87% / 0.73 / 847 |
| rich | 80% / 0.59 / 916 | 80% / 0.59 / 916 |
| neuralmind | 70% / 0.55 / 1,240 | 57% / 0.45 / 1,218 |
| **mean** | **82.7% / 0.690** | **80.0% / 0.669** |

## Keep rule

| Config | Δ mean hit@5 | Repos improved | Worst repo (questions) | Δ tokens | Public recall | Keep |
|---|---:|---:|---:|---:|---:|---|
| roles_off | -2.7% | 0 | -4 | -0.4% | 95.00% | no |

Public benchmark baseline recall: 95.00%.

Baseline reproduced exactly on all 5 repos (re-run after every configuration): the deltas above are the flags, not state left behind.
