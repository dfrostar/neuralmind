# Tool-output compression benchmark

Generated 2026-10-03 with NeuralMind 4.3.4 · tokenizer: tiktoken o200k_base · tool_response shapes: @anthropic-ai/claude-agent-sdk 0.3.283 sdk-tools.d.ts (Claude Code 2.1.283) · hook protocol per https://code.claude.com/docs/en/hooks, https://code.claude.com/docs/en/tools-reference (read 2026-09-28).

Reproduce: `python -m evals.compression.run --out bench/compression`. Method and caveats: [docs/benchmarks/compression.md](../../docs/benchmarks/compression.md).

## What Claude sees with the hooks installed

| Tool call | Calls | Hook responded | Tokens, no hook | Tokens, hooks as shipped | Change |
|---|---:|---:|---:|---:|---:|
| Read (whole file) | 136 | 0 | 597,002 | 597,002 | +0.0% |
| Bash | 19 | 0 | 39,726 | 39,726 | +0.0% |
| Grep, content mode | 48 | 0 | 55,800 | 55,800 | +0.0% |
| Grep, files_with_matches (default) | 48 | 0 | 2,062 | 2,062 | +0.0% |

## With the opt-in replacement (`NEURALMIND_BASH_REPLACE=1`)

| Tool call | Calls | Replaced | Tokens, no hook | Tokens, opt-in | Change | Per call: mean (range) |
|---|---:|---:|---:|---:|---:|---|
| Bash, noisy logs | 5 | 4 | 8,253 | 1,490 | -81.9% | -54.8% (-96.5% to +0.0%) |
| Bash, content | 14 | 0 | 31,473 | 31,473 | +0.0% | +0.0% (+0.0% to +0.0%) |
| Read (whole file) | 136 | 0 | 597,002 | 597,002 | +0.0% | +0.0% (+0.0% to +0.0%) |
| Grep, content mode | 48 | 0 | 55,800 | 55,800 | +0.0% | +0.0% (+0.0% to +0.0%) |
| Grep, files_with_matches (default) | 48 | 0 | 2,062 | 2,062 | +0.0% | +0.0% (+0.0% to +0.0%) |

Must-keep lines that reach Claude on the replaced calls: lowest 100%, mean 100%.

Gates (the run fails if any fails):

- `replaced_bash_must_keep_min`: >= 0.95 on every replaced Bash call; measured 100% — pass
- `content_bash_replaced`: 0; measured 0 — pass
- `read_or_grep_replaced`: 0; measured 0 — pass
- `calls_over_baseline`: 0; measured 0 — pass
- `invalid_hook_json`: 0; measured 0 — pass

## What the compressors produce (hypothetical: delivered instead of the result)

| Tool call | Calls a replacing hook could reach | Tokens, no hook | Tokens, compressor output | Change | What survives |
|---|---:|---:|---:|---:|---|
| Read (whole file) | 136 (110 compressed) | 597,002 | 79,008 | -86.8% | 93% of definitions named, 0% of source lines |
| Bash | 15 of 19 | 32,003 | 9,093 | -71.6% | 60% of must-keep lines |
| Grep, content mode | 48 | 55,800 | 16,610 | -70.2% | 63% of matches |

`compress_read` returns files under 1,500 characters unchanged and replaces the rest with their skeleton, counted as Read would render it, line numbers included. Source lines kept are whole lines, counted with multiplicity, over the files it compressed.

Read, excluding the 3 files whose whole-file result is over 25,000 tokens (Claude Code may page those): -84.7%.

### Read, per repo

| Repo | Files | Hook responded | Compressor output vs. no hook | Definitions named | Source lines kept |
|---|---:|---:|---:|---:|---:|
| click | 16 | 0 | -87.1% | 95% | 0% |
| flask | 24 | 0 | -85.2% | 97% | 0% |
| requests | 18 | 0 | -81.8% | 94% | 0% |
| rich | 78 | 0 | -88.1% | 90% | 0% |

## Bash, per command

| Command | Kind | Exit | Event | Hook responded | No hook | As shipped | Opt-in | Must-keep kept, opt-in | Compressor only | Must-keep kept, compressor |
|---|---|---:|---|:---:|---:|---:|---:|---:|---:|---:|
| `pytest-verbose-pass` (test run (passing, -v)) | content | 0 | PostToolUse | no | 3,191 | 3,191 (+0.0%) | 3,191 (+0.0%) | — | 3,139 | 100% |
| `pytest-quiet-pass` (test run (passing, -q)) | content | 0 | PostToolUse | no | 8 | 8 (+0.0%) | 8 (+0.0%) | — | 8 | 100% |
| `pytest-failures` (test run (failing)) | content | 1 | PostToolUseFailure | no | 1,476 | 1,476 (+0.0%) | 1,476 (+0.0%) | — | 429 † | 45% |
| `pytest-collect` (test listing) | content | 0 | PostToolUse | no | 1,651 | 1,651 (+0.0%) | 1,651 (+0.0%) | — | 176 | 7% |
| `ruff-lint` (linter (errors)) | content | 1 | PostToolUseFailure | no | 2,622 | 2,622 (+0.0%) | 2,622 (+0.0%) | — | 402 † | 9% |
| `mypy-strict` (type checker (errors)) | content | 1 | PostToolUseFailure | no | 2,581 | 2,581 (+0.0%) | 2,581 (+0.0%) | — | 17,394 † | 100% |
| `python-crash` (crash traceback) | content | 1 | PostToolUseFailure | no | 1,044 | 1,044 (+0.0%) | 1,044 (+0.0%) | — | 362 † | 62% |
| `pip-list` (package listing) | content | 0 | PostToolUse | no | 830 | 830 (+0.0%) | 830 (+0.0%) | — | 830 | 100% |
| `next-build` (build log) | noisy-log | 0 | PostToolUse | no | 647 | 647 (+0.0%) | 647 (+0.0%) | — | 647 | 100% |
| `neuralmind-build` (indexer progress log) | noisy-log | 0 | PostToolUse | no | 461 | 461 (+0.0%) | 202 (-56.2%), replaced | 100% | 464 | 100% |
| `git-log-stat` (git history) | content | 0 | PostToolUse | no | 2,466 | 2,466 (+0.0%) | 2,466 (+0.0%) | — | 97 | 4% |
| `git-diff` (diff) | content | 0 | PostToolUse | no | 3,889 | 3,889 (+0.0%) | 3,889 (+0.0%) | — | 152 | 0% |
| `grep-defs` (search via shell) | content | 0 | PostToolUse | no | 8,804 | 8,804 (+0.0%) | 8,804 (+0.0%) | — | 594 | 6% |
| `find-files` (file listing) | content | 0 | PostToolUse | no | 395 | 395 (+0.0%) | 395 (+0.0%) | — | 395 | 100% |
| `cat-source` (file dump) | content | 0 | PostToolUse | no | 458 | 458 (+0.0%) | 458 (+0.0%) | — | 1,734 | 13% |
| `ls-long` (directory listing) | content | 0 | PostToolUse | no | 2,058 | 2,058 (+0.0%) | 2,058 (+0.0%) | — | 161 | 5% |
| `pip-install-requirements` (install log (fresh environment)) | noisy-log | 0 | PostToolUse | no | 2,225 | 2,225 (+0.0%) | 351 (-84.2%), replaced | 100% | 343 | 100% |
| `pip-install-editable` (install log (editable, dependencies present)) | noisy-log | 0 | PostToolUse | no | 4,720 | 4,720 (+0.0%) | 164 (-96.5%), replaced | 100% | 150 | 67% |
| `pip-install-satisfied` (install log (already installed)) | noisy-log | 0 | PostToolUse | no | 200 | 200 (+0.0%) | 126 (-37.0%), replaced | 100% | 203 | 100% |

† A failed command fires PostToolUseFailure, which cannot replace the result; the figure is what the compressor would have produced had anything been able to deliver it.

Must-keep kept, opt-in is shown for the calls the opt-in replaced. Every other call reaches Claude exactly as it does with no hook.
