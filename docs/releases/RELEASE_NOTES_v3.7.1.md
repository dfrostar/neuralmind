# NeuralMind v3.7.1 — the LLM-disclosure and dead-config-removal patch

**Release Date:** 2026-08-31

## Summary

A docs-and-hygiene patch, prompted by a client-facing compliance question:
can client media files ever reach a public-cloud LLM through NeuralMind?
The audit that answered it precisely (rather than by assertion) is this
release's core content. No runtime behavior changed for the default
configuration; one dead, never-wired-up config schema was removed.

## What's new

- **Third-party LLM disclosure.** Added
  [`docs/compliance/THIRD_PARTY_LLM_DISCLOSURE.md`](../compliance/THIRD_PARTY_LLM_DISCLOSURE.md),
  the single, code-cited answer to two questions: whether video/image/audio
  files can reach NeuralMind at all (they can't — no ingestion path exists
  anywhere in the codebase, in any deployment mode), and what the one real,
  opt-in exception to "no external network calls" actually is
  (`NEURALMIND_LLM_SEED=1` + `ANTHROPIC_API_KEY`, sending only
  README/architecture-doc prose, never source or client files, to
  Anthropic to seed synapse edges — fail-open, off by default).
- Corrected `COMPLIANCE-SUMMARY.md`, `SECURITY-GUIDE.md`,
  `PRIVACY-POLICY.md`, and `README.md`, which had stated "no external
  network calls" / "no third-party processor" as unqualified absolutes,
  to name the exception above precisely and cross-link the new disclosure
  doc.
- **Removed dead configuration:** `neuralmind/config.py`'s
  `LocalModelsConfig.fallback_to_api` (default `True`) and an
  `ApiConfig(provider="openrouter")` section were never read by any code
  path — schema-only, never wired to an actual call. Rather than wire them
  up, they were deleted, so a security reviewer grepping the codebase for
  `openrouter` finds nothing to ask about. Also confirmed and documented
  that Hugging Face is not a dependency of any kind (only `tokenizers`,
  used in-process; no `huggingface_hub`/`transformers`, no HF Hub fetch —
  the embedding model comes from a pinned, SHA256-verified S3 URL instead).
- Ecosystem debut posts and a registry-status correction for the
  a0-plugins/Agent Zero listings staged in v3.6.0.

## What the agent sees post-install

No new commands, hooks, or env vars — `NEURALMIND_LLM_SEED` and
`ANTHROPIC_API_KEY` already existed and behaved identically before this
release; this release only documents them accurately across every
compliance surface. If you're evaluating NeuralMind for a DPA/BAA that
prohibits undisclosed subprocessors, start at
[`THIRD_PARTY_LLM_DISCLOSURE.md`](../compliance/THIRD_PARTY_LLM_DISCLOSURE.md).

## Upgrading

```bash
pip install --upgrade neuralmind
```

Nothing to reconfigure. If you had `NEURALMIND_LLM_SEED`/`ANTHROPIC_API_KEY`
set, behavior is unchanged; if you didn't, it still isn't.
