# Retrieval eval — spec 7 work items

hit@5 / MRR / avg tokens per repo and configuration (30 questions each).

| Repo | baseline | roles_off |
|---|---:|---:|
| requests | 83% / 0.72 / 1,150 | 83% / 0.69 / 1,150 |
| click | 83% / 0.76 / 867 | 77% / 0.64 / 864 |
| flask | 83% / 0.72 / 966 | 83% / 0.65 / 931 |
| rich | 67% / 0.50 / 972 | 67% / 0.48 / 948 |
| **mean** | **79.2% / 0.672** | **77.5% / 0.615** |

## Keep rule

| Config | Δ mean hit@5 | Repos improved | Worst repo (questions) | Δ tokens | Public recall | Keep |
|---|---:|---:|---:|---:|---:|---|
| roles_off | -1.7% | 0 | -2 | -1.6% | — | no |

Baseline reproduced exactly on all 4 repos (re-run after every configuration): the deltas above are the flags, not state left behind.
