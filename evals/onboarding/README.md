# Onboarding-lift eval (E1.5)

**Question:** does an agent that inherits a **committed team synapse memory**
retrieve better on its *first* queries than a **cold agent with no memory** —
and by how much?

That "onboarding lift" is NeuralMind's headline differentiator: the
usage-memory layer that static code-graph tools don't have. The faithfulness
eval (`evals/faithfulness/`) measures *answer quality from the graph*; this
measures *the gain from the learned layer on top of it*.

## How it works

A cold-vs-onboarded A/B over the faithfulness gold queries, sharing **one**
built index and differing in exactly one switch — `NEURALMIND_SYNAPSE_INJECT`:

| Arm | Synapse memory | Recall |
|-----|----------------|--------|
| **cold** | committed baseline present but never consulted | **off** |
| **onboarded** | committed team baseline replayed in | **on** |

Both arms are scored by the same offline `OfflineJudge` used by the
faithfulness eval. The **onboarding lift** (the headline + the CI gate) is the
**top-k module hit-rate gain** (onboarded − cold) — the share of a query's
expected modules that land in the ranked top-`RETRIEVAL_TOP_K` retrieval the
agent actually sees. That is precisely the slice associative recall re-ranks
and displaces within, so it is where the learned layer earns its keep; because
recall swaps the weakest hits rather than adding tokens, the lift is
budget-neutral by design.

Two further dimensions are scored and reported as **honest secondaries**, not
gated:

- **fact-recall** — mean expected-fact recall over the full L0–L3 window. At a
  fixed budget this is *budget-traded*: surfacing co-edited hubs displaces some
  fact-bearing text, so on the tiny reference fixture it sits slightly negative
  even as the headline hit-rate rises. That trade-off is the honest cost of the
  re-ranking, surfaced rather than hidden.
- **grounding** — expected-module coverage over the *full* context, which
  saturates (≈100% both arms) once every expected module already fits the
  window; the lift only becomes visible in the ranked top-k, which is why the
  headline is scored there.

This formalises the self-benchmark's Phase-3 synapse A/B
(`tests/benchmark/run.py`: top-k hit rate 71.7% → 83.3% with recall on) into a
committed-baseline eval — scored on the *same* top-k hit-rate metric.

### The committed team baseline

`seed_history.json` is a transparent, regenerable record of co-edit sessions —
groups of files a teammate edited together. The harness replays them through
the real reinforcement path (`activate_files`, the same one the file watcher
uses), teaching the synapse graph cross-cutting associations a textual search
can't recover (e.g. `users/crud.py` and `db/connection.py` are hubs touched
alongside almost every feature even though the words "authentication" or
"billing" never appear in them). No binary `synapses.db` is committed — the
history is the source of truth.

## Running it

```bash
# Validate the baseline + gold set + scorer — no heavy deps:
python -m evals.onboarding.runner --selfcheck

# Full cold-vs-onboarded A/B (needs chromadb + a built index):
python -m evals.onboarding.runner --run            # markdown report
python -m evals.onboarding.runner --run --json     # machine-readable
neuralmind eval --onboarding                        # same, via the CLI
```

Like `neuralmind eval`, the full A/B runs from a **source checkout** — the gold
set + committed baseline ship in the repo, not the PyPI wheel.

## CI gate

The self-benchmark job (`.github/workflows/ci-benchmark.yml`) asserts
**onboarding lift ≥ 0** on the built-in backend — i.e. the top-k module
hit-rate with committed team memory must never sit *below* cold. The floor is
conservative on the tiny reference fixture; the point is to catch regressions
in the recall mechanism, not to chase a number. As with the parity gate: if the
lift goes negative, fix the recall, don't lower the floor. (The fact-recall and
grounding secondaries are printed alongside it for visibility but are not
gated — see above for why neither is the right thing to gate at full budget.)
