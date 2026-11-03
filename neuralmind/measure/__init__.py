# SPDX-License-Identifier: MIT
"""Measure what an agent's sessions spend tokens on.

``neuralmind measure sessions`` reads the transcripts your agents already keep
(Claude Code's ``~/.claude/projects``, Hermes's ``~/.hermes/state.db``), on this
machine, read-only, and reports what share of the prompt tokens they were billed
for was *exploration*: reading and searching code before changing it. Nothing is
sent anywhere and nothing is written unless ``--rows`` asks for it.

Definitions, the presence model and the pre-registered reading of the result are
in ``docs/specs/EXPLORATION-SHARE-SPEC.md``; keep this package in step with it.
``evals/exploration_share`` re-exports these modules for the spec's nightly job.

Stdlib only, plus tiktoken when available (``tokens.Tokenizer``).
"""
