"""Moved to :mod:`neuralmind.measure.tokens` (``neuralmind measure sessions`` runs it).

This name keeps pointing at the same module object, so the spec's nightly job,
``python -m evals.exploration_share`` and the tests behave as they did.
"""

import sys

from neuralmind.measure import tokens

sys.modules[__name__] = tokens
