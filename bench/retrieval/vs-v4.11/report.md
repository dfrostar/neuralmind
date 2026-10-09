# Retrieval eval — `results-v4.11.1.json` vs `results-v4.12.0.json`

hit@5 / MRR / avg tokens, 30 questions per repo.

| Repo | old | new |
|---|---:|---:|
| requests | 90% / 0.82 / 913 | 100% / 0.83 / 752 |
| click | 87% / 0.76 / 721 | 100% / 0.87 / 658 |
| flask | 87% / 0.73 / 848 | 97% / 0.75 / 799 |
| rich | 80% / 0.59 / 912 | 90% / 0.66 / 797 |
| neuralmind | 57% / 0.46 / 1,259 | 80% / 0.64 / 1,145 |
| **pooled** | **80.0% / 0.671 / 930** | **93.3% / 0.750 / 830** |

hit@5 questions won / lost: **21 / 1** (exact McNemar p = 0.0000); per repo: requests +3, click +4, flask +3, rich +3, neuralmind +7. Mean MRR change +0.079 (paired bootstrap 95% interval [+0.024, +0.132]); mean tokens -10.8%.

Keep rule: **passes** — wins > losses, McNemar p < 0.05: yes; no repo drops >2 questions: yes; tokens ≤ +10%: yes.

Regression check: **passes**.
