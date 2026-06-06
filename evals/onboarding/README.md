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

Both arms are scored by the same offline `OfflineJudge` (expected-fact recall +
grounding) used by the faithfulness eval. The **onboarding lift** is the
fact-recall gain (onboarded − cold). Because recall displaces the weakest hits
rather than adding tokens, the lift is budget-neutral by design.

This formalises the self-benchmark's Phase-3 synapse A/B
(`tests/benchmark/run.py`: top-k hit rate 71.7% → 83.3% with recall on) into a
committed-baseline eval.

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

The backend parity gate (`evals/parity/run.py`, run in
`.github/workflows/ci-benchmark.yml`) asserts **onboarding lift ≥ 0** —
committed team memory must never *hurt* retrieval. The floor is conservative on
the tiny reference fixture; the point is to catch regressions in the recall
mechanism, not to chase a number. As with the parity gate: if the lift goes
negative, fix the recall, don't lower the floor.
