"""Exploration share of the token bill.

What share of an agent session's prompt tokens is *exploration* (reading and
searching code before changing it), measured on Hermes sessions
(``~/.hermes/state.db``) and Claude Code transcripts (``~/.claude/projects``).
Definitions, presence model and the pre-registered reading of the result are in
``docs/specs/EXPLORATION-SHARE-SPEC.md``; keep this package in step with it.

Stdlib only, plus tiktoken when available (``tokens.Tokenizer``).
"""
