# Exploratory rerun: does v4.21.0 change what the agent does?

**Not pre-registered, and not a product claim.** After the
[pilot](../pilot/report.txt) found no cost difference, v4.21.0 added MCP server
instructions, a six-tool default `tools/list` and a code excerpt in the prompt
block ([release notes](../../../docs/releases/RELEASE_NOTES_v4.21.0.md)). This
rerun asks whether those changed the agent's behaviour on the same 20 tasks.

**Setup**

- `neuralmind` arm only, 20 tasks × 3 seeds = 60 runs, with NeuralMind built
  from commit `eee0a5be` (the v4.21.0 change; it reports itself as
  `neuralmind 4.18.1`, the version on `main` then). Same model
  (`claude-sonnet-5-5`), Claude Code (2.1.287), budget cap ($2), prompts and
  harness as the pilot; the harness is the one with the API-error fix from #692.
- **Baseline: the pilot's own 60 baseline runs**, reused. That arm never runs
  NeuralMind, so the change can't reach it; the runs are a day apart
  (2026-10-20 against 2026-10-21), a small confound.
- Two runs ended on a logged-out CLI. The harness recorded nothing for them
  and they were rerun after a new login.

**Result** ([report.txt](report.txt))

- The agent called a NeuralMind tool in **0 of 60** runs (0 of 60 in the pilot
  too), and never called ToolSearch, which a deferred tool needs first.
- Explore calls before the first edit: median 4.0 per task, the baseline's 4.0.
- Median cost change per task against the baseline: −2.1% (95% CI −6.9% to
  +6.5%), Wilcoxon p = 0.34; 18 of 20 tasks solved in each arm. Claim not
  supported.
- On the 9 tasks where the prompt block quoted code, explore calls before the
  first edit went from 3.0 (baseline) to 4.0, and on the other 11 from 4.3 to
  4.7: the excerpt didn't replace the agent's own search.

Transcripts are kept out of git (as in the pilot); each run records its
transcript's SHA-256.
