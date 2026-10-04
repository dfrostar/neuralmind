# Measure retrieval on your own repo

**Best for:** teams deciding whether NeuralMind helps on *their* codebase,
anyone tuning retrieval, and CI jobs that should catch a regression before the
agent does.

**Primary goal:** a retrieval score measured on your code, against answers you
trust, that you can compare week to week (v4.5.0+).

Token reduction says NeuralMind is cheap. It doesn't say the context contains
the right file. Generic questions ("How does authentication work?") and a fixed
50K-token baseline can't tell you either — and before v4.5.0, running the same
eval weekly quietly trained the synapse layer on its own test.

---

## 1. Write ten questions with gold answers

Start from drafts, then make them yours:

```bash
neuralmind eval . --suggest --write
```

That writes `.neuralmind.eval.yaml` from module docstrings and README headings,
with the defining file as gold. Rewrite each question the way a teammate would
ask it, and fix any gold file that isn't the one that answers it:

```yaml
- q: How are refunds issued when an order is cancelled?
  gold: [app/refunds.py]
- q: Which module validates a coupon code?
  gold: [app/coupons.py]
- q: How is shipping cost calculated for international orders?
  gold: [app/shipping.py]
```

Commit the file. A shared question set is a shared baseline: everyone's runs
measure the same thing, and a pull request that moves the numbers shows it.

## 2. Run it

```bash
neuralmind eval .
```

```
NeuralMind eval — myrepo (10 questions, read-only)
  hit@1 40% · hit@5 60% · MRR 0.50
  avg context 1,180 tokens · 6.2× vs gold files · 1,101.3× vs all indexed code (1,299,512 tokens, measured)
```

*(Illustrative numbers.)*

- **hit@1 / hit@5** — the gold file is the top file / in the top five the answer drew on.
- **MRR** — mean of 1 / rank of the first gold file; a miss scores 0.
- **× vs gold files** — how close the context is to what a perfect retriever would load.
- **× vs all indexed code** — the measured baseline: every code file the index covers (prose such as Markdown is left out).

The eval is **read-only**: it reads the learned synapse layer, so it measures
what your agent really gets, but writes nothing back. Run it every day and the
numbers only move when the code, the index or NeuralMind does.

## 3. Watch the trend

Every run appends to `.neuralmind/eval_history.jsonl` with its date, commit,
NeuralMind version and node count:

```bash
neuralmind eval . --report
```

```
| Date       | Commit  | NeuralMind | Nodes | Questions | hit@1 | hit@5 | MRR  | Avg tokens | × vs gold | × vs indexed |
|------------|---------|-----------|------:|----------:|------:|------:|-----:|-----------:|----------:|-------------:|
| 2026-10-01 | a1b2c3d | 4.5.0     | 8,960 |        10 |   40% |   60% | 0.50 |      1,180 |      6.2× |     1,101.3× |
```

That table is the format to paste into an issue or a post. It carries the
metrics and the question count only; add `--show-questions` when you want each
question, its gold file and its rank — and leave it off when the questions name
code you'd rather not publish.

## 4. Keep the rest of your numbers honest too

- `neuralmind build .` now indexes what git covers: gitignored copies no longer
  rank twice. `build --dry-run` shows what `.gitignore` keeps out.
- `neuralmind benchmark .` uses your eval questions when the file exists, and
  divides by the measured size of your code (`--naive-50k` for the old number).
- `neuralmind probe . --baseline old.json` compares only the symbols both runs
  sampled, so adding files can't pass for a quality change.
- In CI, `NEURALMIND_NO_LEARN=1` makes the whole job read-only.
- After upgrading NeuralMind, run `neuralmind build .` before you compare
  (v4.6.0+). The build writes the keyword index queries rank with; until it
  runs, the eval still measures the previous version's ranking.

## 5. See what a ranking change does on your questions *(v4.6.0+)*

Every v4.6.0 ranking change sits behind an environment variable read at query
time, so the same index and the same questions score both sides:

```bash
neuralmind eval .                                          # the default
NEURALMIND_BM25_UNIFIED=0 neuralmind eval . --no-history   # v4.5.0's keyword index
```

`--no-history` keeps the variant out of the trend — the history records the
version and commit, not the flags. v4.6.0 chose its own default this way, on 30
questions per repository across six repositories — pre-registered and committed
for the five public repos, plus a private 383-file repository: mean hit@5
72.8% → 79.4% (reproducible on demand, not a CI gate), with the losses
published: `requests` −1 question, `rich` MRR 0.71 → 0.60, a new `click`
public-benchmark miss, and the private 383-file repo at 73% / 0.60 against an
80% / 0.65 target. To try the research flags, or a
change of your own, see
[A/B-test a ranking change on your own repo](./ab-test-a-ranking-change.md).

---

## The potential use case: a retrieval gate on pull requests

Because the eval is read-only and the questions are committed, a CI job can run
`neuralmind eval . --json` on each pull request and fail when hit@5 drops below
the last run on `main` — the same way a test suite guards behaviour. A refactor
that renames the module every question points at shows up as a red check, not
as an agent that quietly starts answering from the wrong file.

Related: [Release notes v4.6.0](../releases/RELEASE_NOTES_v4.6.0.md) ·
[Release notes v4.5.0](../releases/RELEASE_NOTES_v4.5.0.md) ·
[A/B-test a ranking change](./ab-test-a-ranking-change.md) ·
[Does it work on your codebase?](./benchmark-your-repo.md) ·
[Recover from a stale code graph](./recover-from-a-stale-graph.md)
