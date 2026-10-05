# Retrieval eval — which spec 7 ranking changes earned a default (v4.6.0)

Raw output of `python -m evals.retrieval.run`. Each run asks 30 pre-registered
questions per repository (`evals/retrieval/questions/`, committed before any
ranking change was tried) under every flag configuration, read-only, and
applies the keep rule from spec 7:

* mean hit@5 across repos goes up, and it goes up on at least 3 repos;
* no repo drops by more than one question;
* average context tokens rise by at most 10%;
* the public 4-repo benchmark's gold-file recall doesn't drop.

Repos: requests, click, flask and rich at the public benchmark's pinned
commits; this repository (with its docs indexed — its `.neuralmindignore`
drops every markdown file, which would leave its six doc-answered questions
unanswerable); and one private 383-file repository, reported only in aggregate
(no per-question ranks, no question text). Every run re-ran the baseline after
all configurations and it reproduced exactly on all six repos.

| Directory | Baseline | What it decided |
|---|---|---|
| [`vs-v4.5/`](vs-v4.5/report.md) | v4.5.0 retrieval | Of nine configurations, only `bm25_unified` — one BM25 index over docs and code — passed: mean hit@5 72.8% → 79.4%, MRR 0.589 → 0.654, three repos up (flask +3, neuralmind +6, private +4 questions), requests −1, tokens +1.1%, public recall 93.75% → 95.00%. It became the v4.6.0 default. |
| [`on-v4.6/`](on-v4.6/report.md) | v4.6.0 (unified BM25 on) | No remaining item passed on top of it. The closest, the per-file cap, raised two repos and lost none (public recall 96.25%) but the rule asks for three. |

## Reproduce

```bash
python -m evals.retrieval.run --public-benchmark --out bench/retrieval/on-v4.6
python -m evals.retrieval.run --private ~/work/your-repo   # add your own repo, locally
```

## How to read the configurations

| Config | Flags |
|---|---|
| `baseline` | none (the release's defaults) |
| `v45_bm25` | `NEURALMIND_BM25_UNIFIED=0` (v4.5.0's docs-only keyword index) |
| `per_file` | `NEURALMIND_L3_PER_FILE=2` |
| `handoff` | `NEURALMIND_DOC_HANDOFF=1` |
| `hub` | `NEURALMIND_HUB_DAMPEN=1` |
| `code_bm25` | `NEURALMIND_BM25_CODE=1` (a second, code-only keyword list) |
| `bm25_off` | `NEURALMIND_BM25=0` |
| `intent` | `NEURALMIND_INTENT_RULES=1` |
| `bm25_unified` | `NEURALMIND_BM25_UNIFIED=1` |
| `intent_pool` | `NEURALMIND_INTENT_RULES=1 NEURALMIND_INTENT_POOL=1` |
| `unified_intent_pool` | both of the above |

`bm25_unified`, `intent_pool` and `unified_intent_pool` were designed after
seeing the first round's results; the public benchmark (40 queries, written
long before) is the holdout that keeps that honest.

## What didn't make it, and why

* **Intent rules** classify "how does X …", "where is X …" and "which X is …"
  questions as code (the old classifier sent all four of the spec's miss shapes
  to the docs). On their own they only re-order the four hits L3 already
  chose, so they move MRR (0.654 → 0.672 on v4.6) but never hit@5. Ranking the
  whole candidate pool by intent instead (`intent_pool`) cost click 8
  questions and the public benchmark 10 points.
* **Hub dampening** cost click 3–4 questions in both rounds: on small
  libraries the files a probe returns most often are central modules, not
  hubs.
* **A separate code-only keyword list** lifted the private repo most of all
  (+6 against v4.5) but cost requests 3; on top of the unified index it cost
  rich 4 and click 3. Fused at full RRF weight, symbol names that share common
  words outrank good vector hits. One index for both kinds of node is the
  version that held up.
* **Doc-to-code hand-off** helps only where docs name code (private +3,
  neuralmind +1 against v4.5); on top of the unified index it was a wash
  (neuralmind +2, private −1).

All of them stay available behind their flags, off by default.
