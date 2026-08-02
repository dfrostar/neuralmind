# Golden-Suite Quality Eval — All Suites

**Date:** 2026-08-02
**Backend:** ChromaDB (default)
**Suites:** 11 (c, cpp, csharp, go, java, php, python, ruby, rust, typescript)

## Results

| Suite | Queries | MRR | Answerability | Recall@5 | Precision@5 | Gate |
|-------|--------:|----:|--------------:|---------:|------------:|:----:|
| c | 10 | 0.600 | 90% | 0.900 | 0.205 | PASS |
| cpp | 10 | 0.683 | 100% | 1.000 | 0.293 | PASS |
| csharp | 5 | 0.900 | 100% | 1.000 | 0.463 | PASS |
| go | 19 | 0.939 | 100% | 0.983 | 0.417 | PASS |
| java | 19 | 0.886 | 100% | 0.903 | 0.345 | PASS |
| php | 4 | 0.875 | 100% | 1.000 | 0.479 | PASS |
| python | 19 | 0.947 | 100% | 0.877 | 0.430 | PASS |
| ruby | 4 | 0.875 | 100% | 1.000 | 0.467 | PASS |
| rust | 19 | 0.974 | 100% | 0.956 | 0.364 | PASS |
| typescript | 19 | 0.947 | 100% | 0.912 | 0.372 | PASS |

**Overall: PASS** (all 11 suites pass the CI regression gate)

## Query Category Coverage

- architecture: 10+ queries per suite
- bug-localization: 4 (go, java, python, rust, typescript)
- refactor: 3 (go, java, python, rust, typescript)
- next-edit: 2 (go, java, python, rust, typescript)

## Raw Output

Full JSON: `evals/quality/baseline.json`
Run: `python3 -m neuralmind benchmark --quality --json`
