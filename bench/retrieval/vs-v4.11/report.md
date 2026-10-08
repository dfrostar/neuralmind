# Retrieval eval — `results-v4.11.1.json` vs `results-v4.12.0.json`

hit@5 / MRR / avg tokens, 30 questions per repo.

| Repo | old | new |
|---|---:|---:|
| requests | 90% / 0.82 / 913 | 100% / 0.83 / 699 |
| click | 87% / 0.76 / 721 | 100% / 0.87 / 602 |
| flask | 87% / 0.73 / 848 | 93% / 0.74 / 744 |
| rich | 80% / 0.59 / 912 | 90% / 0.66 / 750 |
| neuralmind | 57% / 0.46 / 1,259 | 77% / 0.54 / 1,071 |
| **pooled** | **80.0% / 0.671 / 930** | **92.0% / 0.729 / 773** |

hit@5 questions won / lost: **20 / 2** (exact McNemar p = 0.0001); per repo: requests +3, click +4, flask +2, rich +3, neuralmind +6. Mean MRR change +0.057 (paired bootstrap 95% interval [+0.003, +0.109]); mean tokens -17.0%.

Keep rule: **passes** — wins > losses, McNemar p < 0.05: yes; no repo drops >2 questions: yes; tokens ≤ +10%: yes.

Regression check: **passes**.
