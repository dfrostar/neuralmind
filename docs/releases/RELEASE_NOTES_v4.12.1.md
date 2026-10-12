# NeuralMind v4.12.1 — `neuralmind doctor` exits 1 when a check fails, and example scripts rank below the code they show

**Type:** Patch release | **Theme:** a v0.55.0 regression in `doctor`'s exit code, a false failure it would have exposed, and example scripts that outranked the code they demonstrate

The CLI reference, the [install-paths walkthrough](../use-cases/install-paths.md)
(`neuralmind doctor . && neuralmind wakeup .`) and the v0.12.0 release notes
all say `neuralmind doctor` exits non-zero when a check fails, so a script or
CI step can gate on it. From v0.55.0 through v4.12.0 it always exited 0. This
release restores the exit code, and fixes a check that would otherwise have
failed such a gate on a working index.

It also finishes a v4.12.0 ranking change. v4.12.0 ranks test files below the
code they test; example scripts still outranked the code they demonstrate on a
repository indexed from its root. They now rank below it too.

---

## What changed

### CLI

- **`doctor` exits 1 when a check fails again.** v0.12.0 shipped it that way.
  In v0.55.0 the Tier 2 checks were inserted between the report and the
  `sys.exit(1)`, which ended up unreachable inside the new helper, and a lint
  pass later deleted it. So `neuralmind doctor . && neuralmind wakeup .` ran
  `wakeup` on a project with no graph. It now exits 1 when any check fails,
  with or without `--json` (the JSON report is printed first); warnings still
  exit 0. Regression tests run it on an unbuilt project.
- **`doctor` no longer fails on a repaired turbovec index.** When turbovec
  can't read an index, NeuralMind keeps it as `index.tvim.stale` and rebuilds
  it, and nothing removes the backup. The Turbovec compatibility check failed
  whenever that file existed, so it kept failing after the rebuild worked:
  with the exit code above, a gate on `doctor` would have stopped there. It
  now loads the live index (read-only, with turbovec's own loader) and fails
  only when that load fails. A leftover backup is named in an `ok` line, and
  you can delete it once you no longer need it.

### Query ranking

- **Example scripts rank below the code they demonstrate.** A hit from an
  `examples/`, `demos/` or `samples/` folder anywhere, or a top-level
  `example/`, `demo/` or `sample/` one, scores half, unless the question asks
  for an example. An example uses the words of a question about the feature
  it shows: on a freshly built pallets/click (commit `2247b35`, indexed from
  its root), "which files in this repo handle parsing command-line options?"
  led with `examples/repo/repo.py`, and 4 of 14 questions led with an example
  script.
  - On those 14 questions hit@1 went from 6 to 9 and MRR from 0.68 to 0.79;
    hit@5 stays 14 of 14 (the set it was checked on; not held out).
  - On the 120 retrieval-eval questions for requests, click, flask and rich,
    run on each repository indexed from its root (`--full-repo`): rich gains
    one question (hit@5 83% → 87%), click's MRR rises 0.75 → 0.76, and no
    question ranks lower.
  - The 150-question eval and the public benchmark index the libraries'
    source folders, which hold no examples: identical with and without it,
    question by question and byte for byte.
  - A singular `example/` or `demo/` deeper down is not an example folder:
    Java and Kotlin packages are folders, and Spring Initializr's default
    package is `com.example.demo`.
  - A neighbour that structural or synapse recall pulls in from a test or
    example file gets the same factor before it competes for a slot (synapse
    recall scales its energy before the pull-in threshold), and a test file
    inside an example folder is treated as a test. Neither changed a measured
    question.
  - `NEURALMIND_EXAMPLE_FILE_FACTOR=1` turns it off.
- **Two fixes to v4.12.0's test-file demotion.**
  - A question that names a test asks about tests too: `test_parse_option()`,
    `parse_test.go`, `cart.test.ts`, `UserServiceTest`.
  - Test and example folders are recognised inside the project only, so a
    graph that stores absolute paths doesn't turn a checkout under
    `~/work/tests/` or `~/work/examples/` into tests or examples.

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_EXAMPLE_FILE_FACTOR` | `0.5` | Score multiplier for example-script hits (`examples/`, `demos/`, `samples/`) unless the question asks for an example; `1` turns it off |

### Retrieval eval

- **Whole repositories:** `python -m evals.retrieval.run --full-repo` indexes
  requests, click, flask and rich from their clones' roots, docs, tests and
  examples included, as `neuralmind build .` would, and scores the same
  pre-registered questions with the source folder prefixed to each gold path.
  The standard run indexes only the source folders, as the public benchmark
  does, so example scripts never compete there. The `examples_equal` config
  turns the example demotion off for comparison. Raw output:
  [`bench/retrieval/examples-v4.12/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md).

### Scripts and docs

- `scripts/install-team.sh` waited on `doctor` for its container. The compose
  service has no long-running process yet, so there is no server to wait
  for; the script now checks that the CLI runs in a one-off container and
  stops if it doesn't.
- `scripts/e2e_team_tier.sh` captures `doctor`'s output before grepping it,
  so exit 1 under `pipefail` doesn't hide the Tier 2 check.
- [UPGRADING](../UPGRADING.md), the [FAQ](../wiki/FAQ.md), the
  [deployment guide](../DEPLOYMENT-GUIDE.md) and `docker-compose.yml` said
  doctor always exits 0. They now describe the exit code; the deployment
  guide and compose file point a liveness probe at `health`, which checks
  only the index.

## What the agent actually sees

On a repository with example scripts, a query's eight L3 hits lead with the
library code a question is about, and an example script that matches the
question's words shows up below it, unless the question asks for an example.
Nothing else in its context changes. An agent or provisioning script that runs
`neuralmind doctor` as a shell command now sees exit status 1 when a check
fails, alongside the same `[FAIL]` line and fix it printed before.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Query results rank example scripts below the code; no hook or MCP tool changed; `neuralmind doctor` run as a command exits 1 on a failed check |
| Cursor / Cline / Continue (MCP) | Same ranking change; no tool, argument or response field changed |
| Hermes-Agent plugin | Same |
| Generic MCP client | Same |

## Upgrading

- **`neuralmind doctor` can now exit 1.** A script that runs it under
  `set -e`, or reads its exit code, stops on a failed check where it went on
  before. To keep going, run `neuralmind doctor . || true`, or read
  `--json`'s `status` field (`ok` / `warn` / `fail`), which works on every
  version.
- **Example scripts rank lower.** To restore v4.12.0's ranking, set
  `NEURALMIND_EXAMPLE_FILE_FACTOR=1`.
- No rebuild, index format change or hook re-install.

## Reproduce

```bash
python -m evals.retrieval.run --configs baseline,examples_equal --public-benchmark --out bench/retrieval/examples-v4.12/source-dir
python -m evals.retrieval.run --full-repo --repos requests,click,flask,rich --configs baseline,examples_equal --out bench/retrieval/examples-v4.12/full-repo
```

## Related

- [CLI reference: `doctor`](../wiki/CLI-Reference.md#doctor-v0120)
- [Use case: A/B test a ranking change](../use-cases/ab-test-a-ranking-change.md)
- [v4.12.0 release notes](RELEASE_NOTES_v4.12.0.md)
