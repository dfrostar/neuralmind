"""Model pricing rate card — single source of truth for dollar costing.

Used by the ``savings --dollars`` CLI option to translate NeuralMind's
measured token counts into a defensible dollar figure. Rates are USD per 1M
tokens and reflect published list prices as of ``RATES_AS_OF``; keeping them
in one module means a provider price change is a one-line edit.

NeuralMind reduces the *input context* fed to the model, so token savings are
priced at each model's **input** rate (see ``input_cost``). Output pricing is
carried for completeness but is not what NeuralMind moves.
"""

from __future__ import annotations

RATES_AS_OF = "2026-07-15"


class ModelRate:
    """USD-per-1M-token rates for one model."""

    __slots__ = ("model_id", "input_per_million", "output_per_million", "provider")

    def __init__(
        self,
        model_id: str,
        input_per_million: float,
        output_per_million: float,
        provider: str = "",
    ) -> None:
        self.model_id = model_id
        self.input_per_million = input_per_million
        self.output_per_million = output_per_million
        self.provider = provider


# Keyed by canonical model id. Aliases (substring matches) are resolved by
# ``resolve()`` so callers may pass dated ids ("claude-3-5-sonnet-20241022")
# or short ids ("claude-3-5-sonnet").
DEFAULT_RATES: dict[str, ModelRate] = {
    "claude-3-5-sonnet": ModelRate("claude-3-5-sonnet", 3.00, 15.00, "Anthropic"),
    "claude-3-haiku": ModelRate("claude-3-haiku", 0.25, 1.25, "Anthropic"),
    "claude-3-opus": ModelRate("claude-3-opus", 15.00, 75.00, "Anthropic"),
    "gpt-4o-mini": ModelRate("gpt-4o-mini", 0.15, 0.60, "OpenAI"),
    "gpt-4o": ModelRate("gpt-4o", 2.50, 10.00, "OpenAI"),
    "gemini-1.5-flash": ModelRate("gemini-1.5-flash", 0.075, 0.30, "Google"),
    "gemini-1.5-pro": ModelRate("gemini-1.5-pro", 1.25, 5.00, "Google"),
}

DEFAULT_MODEL = "claude-3-5-sonnet"


def resolve(model: str) -> ModelRate:
    """Resolve a (possibly dated/aliased) model id to a ModelRate.

    Falls back to the default model rather than raising, so a report never
    crashes on an unseen id. Callers can detect the fallback by comparing
    ``rate.model_id`` to ``DEFAULT_MODEL``.
    """
    if model in DEFAULT_RATES:
        return DEFAULT_RATES[model]
    m = model.lower()
    for key, rate in DEFAULT_RATES.items():
        if key in m:
            return rate
    return DEFAULT_RATES[DEFAULT_MODEL]


def input_cost(tokens: int, model: str) -> float:
    """USD cost of ``tokens`` input/context tokens for ``model``."""
    return (tokens / 1_000_000) * resolve(model).input_per_million


def known_model_ids() -> list[str]:
    return list(DEFAULT_RATES.keys())
