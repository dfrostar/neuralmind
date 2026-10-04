"""Tool-output compression benchmark — what the PostToolUse hooks do to tokens.

Drives the real hook entry point (``neuralmind.hooks.run_hook``) with payloads
shaped like Claude Code's, and models delivery with the documented hook
protocol, so the report says what the model actually sees rather than what the
compressor functions return in isolation. See ``docs/benchmarks/compression.md``.
"""
