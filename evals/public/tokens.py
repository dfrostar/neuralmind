"""Token counting for the public benchmark.

Uses ``tiktoken`` (GPT-4o ``o200k_base`` → ``cl100k_base`` fallback) when
available, and a deterministic ~4-chars/token approximation otherwise, so the
harness still runs on a restricted network. The same encoder is applied to
every backend's assembled context, so the *comparison* between backends is
fair regardless of which path is taken — only the absolute scale shifts.
"""

from __future__ import annotations

import functools


@functools.lru_cache(maxsize=2)
def _encoder(name: str):  # pragma: no cover - depends on optional dep / network
    try:
        import tiktoken
    except Exception:
        return None
    try:
        return tiktoken.get_encoding(name)
    except Exception:
        return None


def count_tokens(text: str) -> int:
    """Count tokens in ``text`` with tiktoken, falling back to chars/4."""
    if not text:
        return 0
    enc = _encoder("o200k_base") or _encoder("cl100k_base")
    if enc is not None:  # pragma: no cover - exercised only with tiktoken present
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    # Deterministic approximation: ~4 chars/token, min 1 for non-empty text.
    return max(1, round(len(text) / 4))


def tokenizer_name() -> str:
    """Human-readable label for whichever tokenizer is active (for the report)."""
    if _encoder("o200k_base") is not None:  # pragma: no cover - dep dependent
        return "tiktoken o200k_base"
    if _encoder("cl100k_base") is not None:  # pragma: no cover - dep dependent
        return "tiktoken cl100k_base"
    return "approx (chars/4 — install tiktoken for exact counts)"
