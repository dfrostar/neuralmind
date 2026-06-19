"""Honest public benchmark — NeuralMind vs. real baselines on real repos.

See ``docs/prd/public-benchmark.md`` for the methodology and the credibility
constraints this harness is built to satisfy. The headline metric is
deterministic **gold-file recall** (no LLM judge); the report pairs it with
context-token **cost** so the result is a cost/correctness frontier, never a
lone reduction ratio.
"""
