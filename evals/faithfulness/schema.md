# `queries.json` schema — faithfulness eval query + gold-fact set

Versioned data contract for the faithfulness eval (issue
[#172](https://github.com/dfrostar/neuralmind/issues/172), task **E1.1**).
This file is the gold standard the offline judge scores answers against.

## Top-level object

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Bumped on any breaking change to this format. Currently `1`. |
| `_comment` | string | no | Human note; ignored by the loader. |
| `fixture` | string | yes | Repo-relative path to the code the gold facts are derived from (`tests/fixtures/sample_project`). |
| `queries` | array | yes | The query set (see below). N ≥ 15. |

## Query object

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable, unique slug. Used as the report key — **never renumber**; add new ids instead. |
| `question` | string | yes | The natural-language query posed to the answerer. |
| `shape` | string | no | Retrieval shape hint reused from `tests/fixtures/benchmark_queries.json`: `focused`, `cross-file`, or `identity`. |
| `expected_modules` | string[] | yes | Repo-relative module paths a correct, grounded answer should cite. Feeds the citation/grounding-rate dimension (E1.3). |
| `expected_facts` | object[] | yes | The rubric: key facts a correct answer must contain. Recall over these is the headline metric. |

## Fact object (`expected_facts[]`)

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable, unique-within-query slug for the fact. Lets the per-fact breakdown be diffed across runs. |
| `fact` | string | yes | Canonical natural-language statement of the fact. |
| `aliases` | string[] | no | Synonyms / identifiers / code symbols that also count as expressing the fact. Keeps the offline heuristic judge from being brittle to exact wording. |

### Authoring rules for facts

- Facts must be **verifiable against the `fixture` code**, not against
  general knowledge. Read the fixture before adding or editing a fact.
- A fact is a single checkable claim ("the password hash is verified"),
  not a paragraph. Prefer several small facts over one compound fact.
- `aliases` should include the concrete code symbols (`verify_password`,
  `JWT_SECRET`, `WEBHOOK_TOLERANCE_SEC`) a real answer would name, so a
  grounded answer scores even if it paraphrases the prose.

## Scoring dimensions (the judge contract, implemented across E1.1–E1.3)

The query set is designed to be scored on three dimensions. E1.1 ships
the data and the **expected-fact-recall** scorer; the other two are
specified here and stubbed in `runner.py` for E1.3.

1. **Expected-fact recall** *(E1.1, implemented).* Fraction of a query's
   `expected_facts` that the answer expresses. The offline judge matches
   a fact when the answer text contains the fact statement or any of its
   `aliases` (case-insensitive, whitespace-normalised). This is the
   headline, CI-gating number.
2. **Citation / grounding rate** *(E1.3, stubbed).* Fraction of the
   answer's claims that are attributable to one of `expected_modules`
   (or, more strictly, to retrieved context). Measures whether the
   answer is grounded in the codebase rather than the model's prior.
3. **Contradiction check** *(E1.3, stubbed).* Detects statements that
   conflict with the gold facts (e.g. claiming PostgreSQL when the
   fixture uses SQLite, or RS256 when it is HS256). A negative signal:
   an answer can have high recall yet still contradict the code.

The faithfulness **delta** the release reports (E1.4) is the difference
in these scores between an answer generated **with** NeuralMind context
and a naive baseline **without** it.

## Versioning policy

- Additive changes (new query, new fact, new alias) do **not** bump
  `schema_version`.
- Renaming/removing a field, or changing a field's type/meaning, bumps
  `schema_version` and requires updating `runner.py`'s loader + tests.
