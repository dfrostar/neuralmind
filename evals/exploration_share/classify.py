"""Moved to :mod:`neuralmind.measure.classify` (``neuralmind measure sessions`` runs it).

This name keeps pointing at the same module object, so the spec's nightly job,
``python -m evals.exploration_share`` and the tests behave as they did.
"""

import sys

from neuralmind.measure import classify

sys.modules[__name__] = classify
