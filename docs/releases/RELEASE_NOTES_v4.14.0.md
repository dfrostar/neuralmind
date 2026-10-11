# NeuralMind v4.14.0 — measure whether the synapse layer helps on your own repo, Hermes reads that train transitions, and public pages that say what isn't measured

**Type:** Minor release | **Theme:** check the learning instead of taking it on trust

A field user put NeuralMind to an adversarial review. The retrieval demos
showed the right symbols coming back, but nothing showed the synapse layer
making retrieval better over time, and the store had sat at 0 transitions for
two months. That was a fair hit. The CI synapse gate is directional and runs on
a ~500-line fixture; nothing published shows the layer paying off on a real
codebase. This release adds the measurement, closes one of the reasons a store
stays at 0 transitions, and makes the public pages say what is and isn't shown.

---

## What changed

### `neuralmind eval . --synapse-ab`

- Runs your `.neuralmind.eval.yaml` questions twice, read-only: with synapse
  recall on, then off (`NEURALMIND_SYNAPSE_INJECT=0` for the second run only).
  Each run sets the switch itself, so a shell that already exports
  `NEURALMIND_SYNAPSE_INJECT=0` still gets a real "on" run, and its value is
  restored afterwards.
- Under the usual summary it prints the "off" hit@1, hit@5 and MRR, how many
  questions synapse recall moved up or down, hit@5 won and lost with an exact
  McNemar p-value, and the size of the layer it read:

  ```
  NeuralMind eval — shop (12 questions, read-only)
    hit@1 50% · hit@5 83% · MRR 0.64
    ...
    synapse recall off: hit@1 42% · hit@5 83% · MRR 0.60
    synapse recall moved 2 question(s) up, 0 down, 10 unchanged · hit@5 0 won / 0 lost (exact McNemar p = 1.00)
    synapse layer read: 3,612 edges, seeded and learned (usage-learned: 41 LTP edges, 12 transitions)
  ```

  (illustrative).
- **What it measures.** The switch turns off the whole synapse layer, and that
  layer holds two kinds of edge: the call and import edges every build seeds
  from the code graph, and what usage taught it. So one run measures both
  together, and a fresh build can already show a difference. The usage-learned
  part is what the LTP-edge and transition counts track (seeding adds neither).
- The comparison is stored in `.neuralmind/eval_history.jsonl` with the run,
  and `neuralmind eval . --report` adds a **Synapse recall on vs off** table,
  one row per A/B run, with the edge, LTP-edge and transition counts beside
  the on and off scores. Whether the gap grows as LTP edges and transitions
  grow is the usage-learning signal. `--json` includes it as `synapse_ab`.

### The Hermes plugin learns transitions from reads

- It recorded only `write_file` and `patch`, so a Hermes session that read its
  way through a codebase taught the store nothing about the order.
- A successful `read_file` of a file inside the served project now records a
  transition step, as Claude Code's Read hook does
  (`neuralmind _hook read-activity`).
- The path is normalized first, so `src/a.py` and `sub/../src/a.py` are one
  file, not two with a false step between them.
- Reads outside the project, such as Hermes's own config or another
  repository, are never recorded. `NEURALMIND_NO_LEARN=1` turns it off with
  the rest of the learning.

### Public pages say what isn't measured

- `bench/public/results.json` already had a ripgrep baseline (keywords, top
  five files opened whole). The site, README, `docs/benchmarks/public.md` and
  the about page now quote it beside the whole-file figure: **31–67× fewer
  tokens, and ripgrep found the gold file on 32 of 40**. They also say that an
  agent reading only the matching lines pays less than this baseline, and that
  this isn't measured.
- New disclosures: task outcomes (time to fix, error rate) are not measured,
  and the synapse gate is directional, on a ~500-line fixture. Nothing
  published shows the layer paying off on a real codebase.
- `site/claims.json` registers the new figures and the two disclosures, and
  `tests/test_site_claims.py` recomputes the ripgrep range and found count from
  `bench/public/results.json`.

## What the agent actually sees

Nothing changes in hook output, MCP tools or response fields. An agent, or the
person running it, can check the synapse layer instead of trusting it:
`neuralmind eval . --synapse-ab --json` returns the on and off metrics side by
side. Under Hermes, a session that only reads files now builds transitions, so
`neuralmind next` has something to say about what usually follows.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Nothing at runtime; `eval --synapse-ab` is a CLI command you run |
| Cursor / Cline / Continue (MCP) | Same |
| Hermes-Agent plugin | A `read_file` of a file inside the project records a transition step, one background `neuralmind _hook read-activity` call per read |
| Generic MCP client | Same as Claude Code |

## Upgrading

- `eval --synapse-ab` is opt-in; a plain `neuralmind eval .` and its history
  rows are unchanged.
- Under Hermes, each `read_file` inside the project starts one short background
  NeuralMind process, as each edit already did. The plugin is a copy, so after
  `pip install -U neuralmind` re-run `neuralmind install-hermes-plugin` to pick
  it up.

## Reproduce

```bash
pytest tests/test_measurement_v450.py -k "synapse_ab or SynapseAB" -v
pytest tests/test_hermes_plugin.py -k read -v
pytest tests/test_hooks.py -k read_activity -v
pytest tests/test_site_claims.py -v
```

## Related

- [Does NeuralMind earn its place on your repo?](../use-cases/does-it-earn-its-place.md) — replay past incidents as gold questions, and A/B the synapse layer
- [Measure retrieval on your own repo](../use-cases/measure-retrieval-on-your-repo.md)
- [CLI reference: `eval`](../wiki/CLI-Reference.md)
- [The public benchmark](../benchmarks/public.md)
