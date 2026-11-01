"""One row per session, and the presence model both collectors share."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .classify import CATEGORIES, EXPLORATION

BLOCK = "block"
BLOCK_MARKER = "Code matching this prompt"


@dataclass
class SessionRow:
    agent: str  # "hermes" | "claude-code"
    session_id: str
    source: str  # the agent's own label
    source_group: str  # interactive | automated | subagent | benchmark
    started_at: float | None
    ended_at: float | None
    model: str | None
    tokenizer: str
    calls: int = 0
    # billing side
    prompt_tokens_billed: int = 0
    output_tokens_billed: int = 0
    # estimated, same tokenizer and presence model on both sides
    context_tokens_est: int = 0
    first_tokens: dict = field(default_factory=dict)  # kind -> tokens, counted once
    billed_tokens: dict = field(default_factory=dict)  # kind -> tokens summed over calls present
    tool_calls: dict = field(default_factory=dict)  # category -> count
    compactions: int = 0
    trims: int = 0  # calls at which the billing cap dropped the oldest messages

    def to_json(self) -> dict:
        return asdict(self)

    @property
    def exploration_share(self) -> float | None:
        if not self.context_tokens_est:
            return None
        return self.billed_tokens.get(EXPLORATION, 0) / self.context_tokens_est


class Context:
    """Messages present in the prompt, and what each API call pays for them.

    ``add(kind, tokens, droppable)`` records a message; ``call(overhead)``
    charges every present message, plus ``overhead`` tokens of prompt the
    transcript doesn't hold (system prompt, tool schemas), to one API call;
    ``compact()`` drops the messages a summary replaced (Hermes: rows flagged
    compacted or inactive; Claude Code: all of them) and keeps the rest;
    ``cap(budget)`` drops the oldest droppable messages until what is present
    fits the context size the provider billed for that call, which is how both
    agents trim (oldest tool results first) between compactions.
    """

    def __init__(self, row: SessionRow) -> None:
        self.row = row
        self._present: list[tuple[str, int, bool]] = []
        self.present_total = 0

    def add(self, kind: str, tokens: int, droppable: bool = True) -> None:
        if tokens <= 0:
            return
        self._present.append((kind, tokens, droppable))
        self.present_total += tokens
        self.row.first_tokens[kind] = self.row.first_tokens.get(kind, 0) + tokens

    def call(self, overhead: int = 0) -> None:
        self.row.calls += 1
        for kind, tokens, _ in self._present:
            self.row.context_tokens_est += tokens
            self.row.billed_tokens[kind] = self.row.billed_tokens.get(kind, 0) + tokens
        if overhead > 0:
            self.row.context_tokens_est += overhead
            self.row.billed_tokens["system"] = self.row.billed_tokens.get("system", 0) + overhead

    def compact(self) -> None:
        self.row.compactions += 1
        self._present = [p for p in self._present if not p[2]]
        self.present_total = sum(p[1] for p in self._present)

    def cap(self, budget: int) -> int:
        """Drop the oldest droppable messages until the present content fits ``budget``."""
        if self.present_total <= budget:
            return 0
        dropped = 0
        kept = []
        for p in self._present:
            if p[2] and self.present_total - dropped > budget:
                dropped += p[1]
                continue
            kept.append(p)
        self._present = kept
        self.present_total -= dropped
        if dropped:
            self.row.trims += 1
        return dropped


def count_tool(row: SessionRow, category: str) -> None:
    row.tool_calls[category] = row.tool_calls.get(category, 0) + 1


KINDS = ("system", "user", "assistant", BLOCK, "summary") + CATEGORIES
