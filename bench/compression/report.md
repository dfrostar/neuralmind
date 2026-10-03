# Tool-output compression benchmark

Generated 2026-09-28 with NeuralMind 4.3.4 · tokenizer: tiktoken o200k_base · tool_response shapes: @anthropic-ai/claude-agent-sdk 0.3.283 sdk-tools.d.ts (Claude Code 2.1.283) · hook protocol per https://code.claude.com/docs/en/hooks, https://code.claude.com/docs/en/tools-reference (read 2026-09-28).

Reproduce: `python -m evals.compression.run --out bench/compression`. Method and caveats: [docs/benchmarks/compression.md](../../docs/benchmarks/compression.md).

## What Claude sees with the hooks installed

| Tool call | Calls | Hook responded | Tokens, no hook | Tokens, hooks as shipped | Change |
|---|---:|---:|---:|---:|---:|
| Read (whole file) | 136 | 0 | 597,002 | 597,002 | +0.0% |
| Bash | 16 | 0 | 32,581 | 32,581 | +0.0% |
| Grep, content mode | 48 | 0 | 55,800 | 55,800 | +0.0% |
| Grep, files_with_matches (default) | 48 | 0 | 2,062 | 2,062 | +0.0% |

## What the compressors produce (hypothetical: delivered instead of the result)

| Tool call | Calls a replacing hook could reach | Tokens, no hook | Tokens, compressor output | Change | What survives |
|---|---:|---:|---:|---:|---|
| Read (whole file) | 136 (110 compressed) | 597,002 | 79,008 | -86.8% | 93% of definitions named, 0% of source lines |
| Bash | 12 of 16 | 24,858 | 8,397 | -66.2% | 53% of must-keep lines |
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

| Command | Exit | Event | Hook responded | No hook | As shipped | Compressor only | Must-keep kept |
|---|---:|---|:---:|---:|---:|---:|---:|
| `pytest-verbose-pass` (test run (passing, -v)) | 0 | PostToolUse | no | 3,191 | 3,191 (+0.0%) | 3,139 | 100% |
| `pytest-quiet-pass` (test run (passing, -q)) | 0 | PostToolUse | no | 8 | 8 (+0.0%) | 8 | 100% |
| `pytest-failures` (test run (failing)) | 1 | PostToolUseFailure | no | 1,476 | 1,476 (+0.0%) | 429 † | 45% |
| `pytest-collect` (test listing) | 0 | PostToolUse | no | 1,651 | 1,651 (+0.0%) | 176 | 7% |
| `ruff-lint` (linter (errors)) | 1 | PostToolUseFailure | no | 2,622 | 2,622 (+0.0%) | 402 † | 9% |
| `mypy-strict` (type checker (errors)) | 1 | PostToolUseFailure | no | 2,581 | 2,581 (+0.0%) | 17,394 † | 100% |
| `python-crash` (crash traceback) | 1 | PostToolUseFailure | no | 1,044 | 1,044 (+0.0%) | 362 † | 62% |
| `pip-list` (package listing) | 0 | PostToolUse | no | 830 | 830 (+0.0%) | 830 | 100% |
| `next-build` (build log) | 0 | PostToolUse | no | 647 | 647 (+0.0%) | 647 | 100% |
| `neuralmind-build` (indexer progress log) | 0 | PostToolUse | no | 461 | 461 (+0.0%) | 464 | 100% |
| `git-log-stat` (git history) | 0 | PostToolUse | no | 2,466 | 2,466 (+0.0%) | 97 | 4% |
| `git-diff` (diff) | 0 | PostToolUse | no | 3,889 | 3,889 (+0.0%) | 152 | 0% |
| `grep-defs` (search via shell) | 0 | PostToolUse | no | 8,804 | 8,804 (+0.0%) | 594 | 6% |
| `find-files` (file listing) | 0 | PostToolUse | no | 395 | 395 (+0.0%) | 395 | 100% |
| `cat-source` (file dump) | 0 | PostToolUse | no | 458 | 458 (+0.0%) | 1,734 | 13% |
| `ls-long` (directory listing) | 0 | PostToolUse | no | 2,058 | 2,058 (+0.0%) | 161 | 5% |

† A failed command fires PostToolUseFailure, which cannot replace the result; the figure is what the compressor would have produced had anything been able to deliver it.
