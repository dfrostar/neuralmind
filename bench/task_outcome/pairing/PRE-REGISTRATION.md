# Pre-Registration — NeuralMind × Claude Code pairing benchmark (nm-bench)

Question: does a live NeuralMind codebase index change what a coding agent costs/solves on
real regression tasks from the hermes-agent repo?

Protocol text was first fixed 2026-10-22 15:46 UTC (docstring header of `select_tasks.py`);
this document formalizes it. **No agent run has been executed yet; zero budget consumed.**

## Frozen-at-setup facts
- Agent under test: Claude Code CLI 2.1.308 (`claude.version.txt`), Max subscription auth (`claude.auth.json` snapshot).
- Tool under test: NeuralMind, pinned commit `neuralmind.HEAD`, installed in `tool-venv`; launcher dir hashed before run #1 (`launcher.sha256.before`) and re-hashed after every run (tripwire = stop).
- Repo under test: hermes-agent blobless clone, HEAD `hermes-agent.HEAD`.
- Task window: non-merge commits on main, subject starts `fix`, committer date ≥ 2026-09-15,
  1–3 non-test `.py` files outside `tests/ tests-js/ website/ scripts/ evals/`, ≥1 changed `tests/**/test_*.py`.
- Order: sort by full SHA, shuffle `random.Random(20261022)`, walk in order.
- Oracle per candidate: workspace = `git archive <fix>^` (git-init'd); overlay fix's TEST files → "before";
  overlay all fix files → "after"; repeat on fresh copy; differing outcomes = flaky → reject; require ≥1 FAIL_TO_PASS.
  Collection-error before-run ⇒ every after-pass is FAIL_TO_PASS. Missing-module logic: candidate-side new names
  are legitimate; harness-side dep gaps are FATAL (walk aborts).
- Reject (recorded): fix ADDS test files; FAIL_TO_PASS about docs/wording/formatting; prompt leaking changed
  paths/basenames/stems, def/class names, ALL-CAPS diff tokens (minus generic stoplist), test names.
- Oracle-attempt cap: 120 (full 4-run oracle builds). Need ≥5 accepted tasks to freeze `tasks.json` (sha256);
  fewer ⇒ stop and publish exclusion audit as the result.
- Arms (run phase, only after tasks freeze): baseline `NEURALMIND_BYPASS=1` + `.bench-mcp.json = {}`;
  treatment = NeuralMind MCP server enabled; same model/prompt/seeds/timeout; `--strict-mcp-config`;
  `--max-budget-usd` per run; workspaces under `/tmp`-class scratch with per-run `HERMES_HOME`;
  env strips PYTHONPATH/PYTHONHOME + all NEURALMIND_* in harness.
- Cost metric: `total_cost_usd` if >0, else recorded-token equivalent at published rates, identical arithmetic per arm (subscription auth may report $0).
- Analysis: recommend scaling only if treatment median per-task cost improves by the pre-registered threshold AND solves no fewer tasks; small n decides only whether a bigger run is worth paying for.

## Deviations log (each timestamped; ALL precede agent run #1)
- **D1** [15:46] No `dev` extra in repo pyproject → test stack installed explicitly (pytest pytest-asyncio pytest-timeout pytest-mock pygments packaging).
- **D2** [15:49–17:13] Walk #1a attempts died on Hermes PYTHONPATH leakage (missing pygments under systemd; typing_extensions resolved from host venv). Fix: clean venv + strip PYTHONPATH/PYTHONHOME everywhere.
- **D3** [17:13–17:24] test-venv rebuilt (3.12), `.[all]` installed, psutil added manually, "collection verified" on ONE test file (58 tests) — insufficient verification, see D5.
- **D4** [18:03] Walk #1 completed: 120 oracle attempts, accepted=0, excluded=350; tasks.json frozen as `[]` (sha256 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945). No agent runs, no spend.
- **D5** [~20:00] WALK #1 VOIDED — root cause found in its own junit artifacts: every run was a collection-error
  artifact (`ModuleNotFoundError: yaml` recorded as single `<error>` testcase → "before=N after=N").
  Cause: repo gates ALL core deps to `python_version >= '3.14'`; the venv was 3.12, so `.[all]` resolved ZERO deps.
- **D6** [20:04] test-venv rebuilt on CPython 3.14.4 (`uv venv --seed`); HEAD `.[all]` + test stack; package under test uninstalled.
- **D7** [20:10] Window drift: HEAD replaced PyYAML with ruamel.yaml, but window code imports `yaml`. Installed `pyyaml==6.0.3` (pin from window pyproject).
- **D8** [20:15] Dep policy: union of dependencies+extras over all 121 pyproject variants changed on main since 2026-09-01 → 108 exact pins (max per name, `out/deps-union.txt`), installed individually. Tolerated 2 platform-impossible packages (`mautrix[encryption]`, `openwakeword`) logged in `out/deps-union-failures.txt`; if a sampled test imports them the walker aborts DEP-GAP rather than mis-exclude.
- **D9** [20:20] select_tasks.py hardened: DepGap fail-fast distinguishes candidate-side new modules (legit) from harness-side gaps (fatal abort).
- **D10** [20:22] Positive control (harness validation demanded by protocol): 3 sampled candidates, each rebuilt twice from scratch — 05e7e89175: 2 F2P; d1221d43b7: 2 F2P; 44f6d3bbee: 1 F2P; all deterministic, no dep gaps, imports resolve inside workspace. Harness declared capable of discrimination.
- **D11** [20:25] Walk #2 consumes a FRESH 120-attempt budget, same filter/seed/order (walk #1's attempts happened in a broken environment and are void). Walk #1 artifacts archived under `walk1-broken-env/`, retained for audit; its exclusions.json is NOT the result of this experiment.

## Frozen result (step 4 complete)
- **D12** [20:31] Walk #2 froze `tasks.json` after **5 of 120** oracle attempts — the first 5 leak-gate survivors ALL discriminated (walk #1 voided the identical prefix with collection-error artifacts).
  tasks = ef8222b932 (2 f2p/56 p2p), 9701123540 (1/26), 69316aa66f (1/11), e113c1b3af (1/3), b86be0c098 (2/5).
  **tasks.json sha256 = e058586485b6805c1adbb515e7b125eb06a6bfaae2ae7d1f0e725f1126712aaf** — file never edited after this point.

## Run-phase addendum (fixed BEFORE run #1)
- 5 tasks × 2 arms × 1 seed = 10 agent runs; order shuffled with seed 20261022; per-task NeuralMind index built ONCE and copied into treatment workspaces.
- Model: Claude Code CLI default subscription model, pinned by recording `claude --version` and the effective model string per run; identical both arms.
- Per-run wall timeout 1800s (subscription auth: `--max-budget-usd` reports $0 and cannot bind; wall timeout + max-turns 150 are the real caps). Worst-case: 10 × 30 min CLI time on the Max subscription, zero cash.
- Harness-failure rule: `terminal_reason: api_error`/crash = record nothing, stop, retry later; never scored as unsolved.
- Tripwire: `launcher.sha256.before` re-hashed after every run; any drift stops the sweep.

## Deviations added before run #1 (continued)
- **D13** [2026-10-23 15:32Z] Index-build wall timeout raised **1800s → 3600s** (`INDEX_WALL` in `run_bench.py`). Cause: the first Phase-A attempt (Oct 22 21:56–22:26Z) killed b86be0c098 mid-build at the 1800s cap while load average sat at 33 and the 27B Ollama server was loading concurrently. 69316aa66f (324,564 nodes — *larger* than b86's 322,938) completed the same phase in 1118s on a quiet box, so the cap was too tight for a contended box rather than too small for the work. b86 was confirmed genuinely incomplete — it stopped after `synapses.db` and never wrote `bm25_unified_index.json`, `metrics/`, or `build_status.json`, the last of which every successful build ends on. Handled under the harness-failure rule: nothing recorded, nothing scored, `runs.jsonl` never existed, zero agent budget consumed. The four indexes that reached `BUILD_OK` are reused unchanged; only b86 rebuilds. Verified immediately before relaunch: `tasks.json` sha256 still `e0585864…126712aaf`.
- **D14** [2026-10-23 15:32Z] Phase A+B launched as a **`systemd-run --user` unit** (`nm-runs`, soft `MemoryHigh=6G`, `Type=oneshot`, `--no-block`) rather than a bare background child, so session/gateway teardown cannot kill a multi-hour sweep mid-run. The previous attempt left no unit behind at all — that is why it stayed dead for 17 hours with nothing re-running it.

## FINAL RESULT — 2026-10-23 18:40Z — sweep complete, gate FAILS, do not scale

10/10 runs, `stopped_by: null`, zero timeouts, zero harness failures. `tasks.json` still sha256 `e0585864…126712aaf` (never edited post-freeze).

| | baseline | treatment |
|---|---|---|
| solved | **4/5** | **4/5** |
| median wall_s | 56.0 | 132.4 |
| median turns | 8 | 10 |
| median cost USD | 0.3704 | 0.3995 |
| total cost USD | 2.1879 | 2.2444 |
| NeuralMind tool calls | — | **0** |
| timed out | 0 | 0 |

**Pre-registered gate (treatment must *improve* median per-task cost AND solve no fewer): FAILED.** Median cost moved **+7.9% the wrong way**, solves identical. Recommendation: **do not scale.** Small-n was only ever a decide-whether-to-fund-a-bigger-run instrument, and it says no.

### The load-bearing finding is uptake, not cost

Every treatment run initialised cleanly:

```
mcp_servers: [{"name": "neuralmind", "status": "connected"}]
neuralmind tools exposed: 6  (search, query, wakeup, impact, skeleton, query_decisions)
neuralmind tool calls made: 0
```

Aggregate tool usage across all 7 transcripts that record calls: **62 Bash, 1 Edit, 0 mcp__neuralmind__*.** The agent solved 4/5 tasks identically with the index installed and never once consulted it. So the +7.9% is not a measured cost *of* NeuralMind — it is noise on an arm where the variable under test was never exercised. The honest conclusion: **this run measured nothing about retrieval quality, because the tool was never invoked.**

### A confound I hypothesised and then disproved

Treatment median wall time was 2.4× baseline (132.4s vs 56.0s) with the 2.1–2.7 GB `.neuralmind` index sitting inside the workspace, which looked like a harness artifact: multi-GB dir traversal slowing the agent's file commands. **It is not.** Normalising by turns: baseline **9.5 s/turn**, treatment **9.5 s/turn** — identical. The wall gap was entirely turn count (50 vs 57 turns). `.git/info/exclude` carries `.neuralmind/`, and per-turn latency confirms nothing was actually being paid for the index. Recorded so the next reader does not chase it.

### Protocol defect to fix before any future run

`explore_before_first_edit` is **mis-specified**: it counts `^(Read|Grep|Glob|Search|LS|Explore)$`, but this Claude Code build did ~all reading and grepping through `Bash` (62 Bash vs 1 Edit across the transcripts). The metric reads 0 on *every* run, arm included, and therefore measures nothing. Any future run must count Bash-with-file-subcommands (cat/sed/head/grep/rg/find) as exploration, or drop the metric.

**Interpretation for the product:** v4.20→v4.21 invested in discoverability (server instructions, 28→6 tools) and this run confirms discoverability was achieved — connected, six tools, exposed every time. Uptake remained zero. The wrong assumption was *"if agents can see it, they'll use it"*; a capable agent routes through one general escape hatch and bypasses specialised tools regardless of how legible they are. Another discoverability release is unlikely to move this number. The hook layer is where the measured win already exists (per-prompt recall names a changed file in 17/20 pilot tasks) without requiring the agent to choose the tool.

### Retention
Evidence kept: `out/runs.jsonl` (10 records), `transcripts/` (7 files, 1.4 MB), `PRE-REGISTRATION.md`, frozen `out/tasks.json`. The 240 agent/oracle workspace trees are reproducible from git and were pruned for disk (see 2026-10-23 cleanup): 73 G reclaimed from `walk1-broken-env/oracles`, with all **238 `_junit.xml` + 240 `_pytest.log`** preserved first in `~/walk1-broken-env-evidence.tar.gz` (478/478 members verified); walk #1's `out/` audit trail retained in place.

---

# Run #2 — 30-run confirmation sweep (protocol frozen 2026-10-24 17:2xZ, BEFORE run #1)

Protocol = the user's re-sent STEP 4/5 (2026-10-24): **5 tasks × 2 arms (baseline, neuralmind) × seeds {0,1,2} = 30 runs**, triples built in construction order (tasks.json order → arms (baseline, neuralmind) → seeds 0,1,2) then `random.Random(20261022).shuffle`. First triple `69316aa66f/neuralmind/0`; last three `e113c1b3af/baseline/0, 9701123540/neuralmind/2, e113c1b3af/neuralmind/0`. Harness `run_bench2.py`; frozen inputs unchanged (`tasks.json` sha256 `e0585864…126712aaf`, re-asserted inside the harness at start — mismatch = refuse to run).

**Pre-registered stop rule (restated verbatim from the protocol):** recommend the full 30-task run ONLY if the NeuralMind arm's median per-task cost change is −10% or better AND it solves no fewer tasks. Otherwise recommend stopping. Five tasks can't prove a benefit; this only decides whether a bigger test is worth paying for.

## Deviations & interpretation decisions — ALL recorded before Run #2 run #1
- **D15 [2026-10-24 ~17:10Z]** Run #2 differs from run #1 by construction: 3 seeds/arm (vs 1), arms renamed `treatment→neuralmind` (matches the frozen analyzer `evals.task_outcome.analyze`), model pinned `--model claude-sonnet-5-5` (probe-verified valid: canonical, firstParty, 1M ctx, list-priced; trivial probe $0.0241), `--permission-mode acceptEdits` + explicit `--allowedTools` (Read Edit Write Glob Grep `Bash(python -m pytest:*)` `Bash(git diff:*)` `Bash(git status:*)` `Bash(ls:*)`) replacing run #1's `--dangerously-skip-permissions`; `--setting-sources project` + `--no-session-persistence` added; `--max-turns` dropped (protocol's caps: wall 1800s + `--max-budget-usd 3`). Run #1 and Run #2 are separate experiments; run #1 numbers are not re-used.
- **D16** Neuralmind arm = **hooks AND MCP**: `neuralmind install-hooks <ws>` (project-scope only; `--global` never invoked — it would write the real `~/.claude/settings.json`). Run #1's arm was MCP-only; that zero-uptake finding is exactly why the hook layer is now part of the treatment. The real `~/.claude/settings.json` md5 `e68695bc4736cceb381db1b5cb327d2d` is re-asserted after the smoke gate (unchanged = proof nothing leaked to the user's config).
- **D17** Tool build: `tool-venv` upgraded from git-`b4a61c3e` editable (reported 4.20.0) to **PyPI `neuralmind==4.21.0`** — STEP 1's own conditional ("if pip index versions lists 4.21.0, install neuralmind==4.21.0") is now true; it was false on Oct 22. Diff b4a61c3e→v4.21.0 = 7 tag-window commits (synapse half-life fix #706; release/SBOM/docs chores). All five indexes rebuilt fresh on the new build (old trees deleted in Oct 23 cleanup).
- **D18** Run #1's 10 rows moved verbatim to `out/runs.jsonl.run1-archived` (sha recorded); `out/runs.jsonl` restarts empty for the 30-row matrix — `analyze.py:check_complete` demands the exact (task,arm,seed) grid and run #1 rows (arm `treatment`, field name `total_cost_usd`) would fail it. Run #1's authoritative copy also lives in git (`neuralmind/bench/task_outcome/pairing/runs.jsonl`) + evidence tarball.
- **D19** Index location `~/nm-bench/index/<id>` (run #1 built under `runs/index-<id>`, deleted). Built one at a time, seconds recorded to `out/index2-<id>.seconds`, logs `out/index2-<id>.log`; `BUILD_OK` marker only when `build_status.json` exists (terminal-artifact rule from the D13 lesson). Resume: completed indexes never rebuild.
- **D20** Prompt passed verbatim from frozen `tasks.json` — the re-sent STEP 4 wrapper tail is the *same instruction already embedded pre-freeze*; concatenating would double it and deviate from the sha256-frozen artifact.
- **D21** Timeout/stop semantics: wall-1800s kill ⇒ **record** `timed_out=true, cost_usd=null` (analyzer's pre-registered rule scores it unsolved at the $3 cap — worst case for its arm, never a free pass). A missing result event *without* wall timeout, or `terminal_reason` containing `api_error` ⇒ **record nothing, STOP, report, retry later** (relaunch resumes, recorded triples skipped). Budget-cap stops (`error_max_budget_usd`) are real outcomes under a pre-registered cap ⇒ recorded normally.
- **D22** `claude` invoked by absolute path (resolved at harness start; it lives in `~/.local/bin`, which the isolated PATH **scrubs from both arms** to keep the global uv-tool NeuralMind undiscoverable — run #1's proven mechanism; the scrub would otherwise break a bare `claude` lookup).
- **D23** Smoke gate (capability proof BEFORE matrix run #1, not recorded in runs.jsonl, analog of D10): neuralmind-arm micro-run on the first built index asserting — init event shows `mcp_servers: neuralmind connected`, ≥3 `mcp__neuralmind__*` tools exposed, ≥1 `mcp__neuralmind__*` tool_use actually made (proves the literal `--allowedTools mcp__neuralmind` authorizes the server), hooks present in `ws/.claude/settings.json`, real `~/.claude/settings.json` md5 unchanged. Any failure ⇒ STOP before any matrix run is recorded.
- **D24** `explore_calls_before_first_edit` = protocol definition (Read/Grep/Glob/Bash/mcp__* before first Edit/Write); the run #1 corrected file-op variant is also recorded (`explore_file_ops_refined`) for continuity. Rows carry the full protocol field set (`task,arm,seed,model,claude_code_version,neuralmind_version,budget_usd,timed_out,cost_usd,num_turns,terminal_reason,solved,tool_counts,mcp_calls,explore_calls_before_first_edit,transcript_sha256`) + extras (`wall_s,duration_ms,subtype,is_error,grade_detail,run_idx`).
- **Cost guard**: worst case 30×$3 = **$90** API-equivalent; run #1 base-rate ≈ $0.40/run ⇒ expected ≈ $12. Max subscription auth still reports per-run `total_cost_usd` at list price (`costBasis: list`).
- **Safety**: hermes bin tripwire (`safety/bin-sha256.step1.before`, verified OK 2026-10-24 17:02Z) re-checked via `sha256sum -c` after EVERY run + launcher content hash; drift ⇒ STOP. Fresh `HERMES_HOME=<ws>/.bench-hermes-home` per run; never `~/.hermes`. Transcripts local-only. Launched as `systemd-run --user` unit (D14 pattern — survives gateway teardown; two gateway restarts today).
- **STEP 5** executed after 30/30 by the orchestrator: `cd ~/nm-bench/neuralmind && test-venv/bin/python -m evals.task_outcome.analyze ~/nm-bench/out > out/report.txt` + per-arm table (total mcp_calls, median explore, median num_turns, solved runs) in the report. If the analyzer errors on a missing field ⇒ add the field to every row; never edit the analyzer.
