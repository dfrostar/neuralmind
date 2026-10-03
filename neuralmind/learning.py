"""learning.py — the switch that keeps a query from training the synapse layer.

Every query normally teaches NeuralMind: co-activated nodes are reinforced
(Hebbian learning) and the query is logged for later tuning. That is the
point in day-to-day use, and exactly wrong for measurement — an eval run
weekly would strengthen the very edges it measures. A read-only query reads
the learned layer (synapse recall still boosts results, so it sees what a
normal query would) without writing to it.

Ways to switch learning off:

* ``NeuralMind.query(..., learn=False)`` / ``search(..., learn=False)``
* ``neuralmind query --no-learn``
* the MCP tools' ``learn: false`` argument
* ``NEURALMIND_NO_LEARN=1`` — process-wide: CLI, MCP server and hooks
* measurement commands (``benchmark``, ``probe``, ``eval``) — always
"""

from __future__ import annotations

import os

NO_LEARN_ENV = "NEURALMIND_NO_LEARN"


def learning_disabled() -> bool:
    """True when ``NEURALMIND_NO_LEARN=1`` turns learning off process-wide."""
    return os.environ.get(NO_LEARN_ENV) == "1"


def should_learn(learn: bool | None) -> bool:
    """Resolve a call's ``learn`` argument against the process-wide switch.

    An explicit ``False`` always wins; ``None`` (the default) means "learn
    unless ``NEURALMIND_NO_LEARN=1``". The environment switch can't be
    overridden by ``True``: it exists so CI and eval harnesses can guarantee
    nothing they run writes to the learned layer.
    """
    if learning_disabled():
        return False
    return learn is not False
