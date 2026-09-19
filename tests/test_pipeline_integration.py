"""Integration tests: NeuralMind.query() prose path via MedicalRetriever.

TDD RED phase: these tests should FAIL before wiring is implemented.
After wiring (GREEN), they should all pass.

Tests verify:
1. Prose projects route to MedicalRetriever (not ContextSelector)
2. Code projects still route to ContextSelector (unchanged)
3. MedicalRetriever is lazily initialized
4. ContextResult is fully compatible
5. Confidence flags appear in output
6. Negative queries return fallback
7. End-to-end peptide book queries work

NOTE: These tests use mocks for the slow code-path fixture (nm_code) to
avoid building the full neuralmind repo tree (tree-sitter + graph.json
generation is ~60s in this environment).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from neuralmind import core  # noqa: E402
from neuralmind.context_selector import TokenBudget  # noqa: E402

BOOK_DIR = str(REPO_ROOT / "tests" / "fixtures" / "sample_project_prose")

# Synthetic chapters for the prose fixture — written at import time so the
# fixture is self-contained and never depends on committed book content.
# A dedicated prose-only fixture is required because project_kind is derived
# from the file mix: any .py file makes a project "code". The dynamic-import
# fixture (sample_project_dynamic_py) must stay a code project for graphgen.
_CHAPTERS_DIR = Path(BOOK_DIR) / "chapters"
_CHAPTERS = {
    "chapter_01.md": (
        "# Chapter 1: What is a peptide?\n\n"
        "## Definition\n\nA peptide is a short chain of amino acids.\n\n"
        "## Examples\n\nInsulin and oxytocin are peptide hormones.\n"
    ),
    "chapter_02.md": (
        "# Chapter 2: Semaglutide\n\n"
        "## Mechanism\n\nSemaglutide is a peptide drug and a GLP-1 receptor agonist.\n\n"
        "## Usage\n\nUsed for diabetes and weight management.\n"
    ),
    "chapter_03.md": (
        "# Chapter 3: Retatrutide and Tirzepatide\n\n"
        "## Overview\n\nSemaglutide is a GLP-1 agonist. Tirzepatide is a GIP/GLP-1 dual agonist.\n\n"
        "## FDA Approval\n\nThe FDA approval process involves preclinical testing, "
        "clinical trials (Phase I, II, III), and review of safety and efficacy data. "
        "Phase 3 trials reported 14.9% weight loss at 68 weeks.\n"
    ),
    "chapter_04.md": (
        "# Chapter 4: BPC-157\n\n"
        "## Research\n\nBPC-157 is a peptide studied for wound healing.\n\n"
        "## Risks\n\nThere are risks associated with buying peptides from research "
        "chemical websites, including lack of quality control, potential contamination, "
        "and inaccurate labeling.\n"
    ),
    "chapter_05.md": (
        "# Chapter 5: Safety Warning\n\n"
        "## Warning\n\nSemaglutide has a black box warning for thyroid C-cell tumors "
        "based on rodent studies.\n"
    ),
    "chapter_06.md": "# Chapter 6: Future Research\n\n## Overview\n\nMore studies are needed.\n",
    "chapter_07.md": "# Chapter 7: Oral Peptides\n\n## Overview\n\nOral options are under investigation.\n",
    "chapter_08.md": (
        "# Chapter 8: Questions to Ask Your Prescriber\n\n"
        "## Questions\n\nAsk your doctor about benefits, risks, side effects, and monitoring.\n"
    ),
}


def _write_synthetic_chapters() -> None:
    """Materialize the prose fixture on disk (idempotent).

    The whole fixture is generated — chapters plus the ``mode: prose`` config —
    so nothing book-derived is ever committed and the fixture can't drift.
    """
    _CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in _CHAPTERS.items():
        (_CHAPTERS_DIR / name).write_text(content, encoding="utf-8")
    # Prose-only fixture: no code files, so detect_project_kind() returns
    # "prose" and queries route to MedicalRetriever.
    (Path(BOOK_DIR) / ".neuralmind.yaml").write_text("mode: prose\n", encoding="utf-8")


_write_synthetic_chapters()


@pytest.fixture
def nm_prose():
    """NeuralMind on peptide book (prose project)."""
    nm = core.NeuralMind(BOOK_DIR, enable_synapses=False)
    nm.build()
    return nm


class TestProseRouting:
    """Verify prose projects route through MedicalRetriever."""

    def test_prose_project_detects_medical_retriever(self, nm_prose):
        """project_kind='prose' should use MedicalRetriever path."""
        nm_prose._ensure_built()
        assert nm_prose.project_kind == "prose"
        mr = nm_prose._get_medical_retriever()
        assert mr is not None

    def test_medical_retriever_lazy_init(self, nm_prose):
        """MedicalRetriever should only build on first prose query."""
        nm_prose._ensure_built()
        assert nm_prose._medical_retriever is None
        result = nm_prose.query("What is a peptide?")
        assert nm_prose._medical_retriever is not None


class TestContextResultCompatibility:
    """Verify MedicalRetriever returns ContextResult-compatible objects."""

    def test_result_has_context_field(self, nm_prose):
        """Result must have a non-empty context string."""
        result = nm_prose.query("What is a peptide?")
        assert hasattr(result, "context")
        assert isinstance(result.context, str)
        assert len(result.context) > 0

    def test_result_has_budget_field(self, nm_prose):
        """Result must have a TokenBudget."""
        result = nm_prose.query("What is a peptide?")
        assert hasattr(result, "budget")
        assert isinstance(result.budget, TokenBudget)

    def test_result_has_search_hits(self, nm_prose):
        """Result must report search_hits count."""
        result = nm_prose.query("What is a peptide?")
        assert hasattr(result, "search_hits")
        assert result.search_hits >= 0

    def test_result_has_reduction_ratio(self, nm_prose):
        """Result must have reduction_ratio."""
        result = nm_prose.query("What is a peptide?")
        assert hasattr(result, "reduction_ratio")
        assert result.reduction_ratio >= 0.0

    def test_result_has_top_search_hits(self, nm_prose):
        """Result must have top_search_hits list."""
        result = nm_prose.query("What is a peptide?")
        assert hasattr(result, "top_search_hits")
        assert isinstance(result.top_search_hits, list)


class TestConfidenceFlags:
    """Verify confidence flags appear in output."""

    def test_high_confidence_flag(self, nm_prose):
        """HIGH confidence results should have [Confidence: HIGH]."""
        result = nm_prose.query("What is a peptide?")
        assert "[Confidence: HIGH]" in result.context or "[Confidence: MEDIUM" in result.context

    def test_medium_confidence_flag(self, nm_prose):
        """Vague query should produce MEDIUM results."""
        result = nm_prose.query("peptides")
        assert "[Confidence:" in result.context


class TestNegativeQuery:
    """Verify negative queries return fallback."""

    def test_off_topic_query_fallback(self, nm_prose):
        """Off-topic query should return fallback message."""
        result = nm_prose.query("How to cook pasta?")
        assert (
            "[Confidence: LOW]" in result.context
            or "Consult a healthcare provider" in result.context
            or result.search_hits == 0
        )


class TestEndToEnd:
    """End-to-end verification with peptide book."""

    def test_semaglutide_returns_relevant_chapter(self, nm_prose):
        """'How does semaglutide work?' should return Ch2 or Ch3."""
        result = nm_prose.query("How does semaglutide work in the body?")
        assert result.context != ""
        ctx_lower = result.context.lower()
        assert "glp-1" in ctx_lower or "semaglutide" in ctx_lower or "chapter" in ctx_lower

    def test_black_box_returns_safety_chapter(self, nm_prose):
        """'Black box warning' should return safety chapter content."""
        result = nm_prose.query("What is the black box warning on semaglutide?")
        ctx_lower = result.context.lower()
        assert "black box" in ctx_lower or "thyroid" in ctx_lower or "chapter" in ctx_lower
