# SPDX-License-Identifier: MIT
"""Token counting: tiktoken ``o200k_base`` (the public benchmark's tokenizer),
or characters ÷ 4 when tiktoken is missing, with the row saying which."""

from __future__ import annotations


class Tokenizer:
    def __init__(self, force_estimate: bool = False) -> None:
        self._enc = None
        if not force_estimate:
            try:
                import tiktoken

                self._enc = tiktoken.get_encoding("o200k_base")
            except Exception:  # tiktoken missing or its data unavailable
                self._enc = None
        self.name = "o200k_base" if self._enc is not None else "chars/4"
        self.estimate = self._enc is None

    def count(self, text: str | None) -> int:
        if not text:
            return 0
        if self._enc is None:
            return max(1, len(text) // 4)
        return len(self._enc.encode(text, disallowed_special=()))
