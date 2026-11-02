"""Integration test: chapter-level indexing via NeuralMind pipeline.

Uses the real ONNX embedder for chapter-level semantic similarity.
This is the SOTA path — chapter indexer + neural embeddings + BM25.

"""

import os
import sys
import tempfile

import pytest

# Synthetic chapters directory for standalone ChapterIndexer tests
CHAPTERS_DIR = os.path.join(tempfile.gettempdir(), "nm_test_chapters")


def ensure_test_chapters():
    """Create synthetic chapter files with H2 sections for section-level tests."""
    os.makedirs(CHAPTERS_DIR, exist_ok=True)
    chapters = [
        (
            "chapter_01.md",
            "# Chapter 1: Peptide Definition\n\n## Overview\n\nA peptide is a short chain of amino acids.\n",
        ),
        (
            "chapter_02.md",
            "# Chapter 2: Semaglutide\n\n## Mechanism\n\nSemaglutide is a GLP-1 agonist.\n\n## Usage\n\nFor diabetes.\n",
        ),
        (
            "chapter_03.md",
            "# Chapter 3: Retatrutide\n\n## Overview\n\nTriple agonist peptide.\n\n## FDA Approval\n\nPhase 3 trials ongoing.\n",
        ),
        ("chapter_04.md", "# Chapter 4: BPC-157\n\n## Research\n\nStudied for wound healing.\n"),
        (
            "chapter_05.md",
            "# Chapter 5: Safety\n\n## Warning\n\nBlack box warning for thyroid tumors.\n",
        ),
    ]
    for fname, content in chapters:
        with open(os.path.join(CHAPTERS_DIR, fname), "w") as f:
            f.write(content)
    return CHAPTERS_DIR


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "neuralmind"))


@pytest.fixture(scope="module")
def book_dirs(tmpdir_factory):
    base = tmpdir_factory.mktemp("book")
    book_dir = str(base)
    chapters_dir = str(base.mkdir("chapters"))
    # Write .neuralmind.yaml to set mode to prose
    config_path = os.path.join(book_dir, ".neuralmind.yaml")
    with open(config_path, "w") as f:
        f.write("mode: prose\n")
    # Create 11 chapter files with relevant content for the tests
    # Chapter 1: peptide definition
    with open(os.path.join(chapters_dir, "chapter_01.md"), "w") as f:
        f.write(
            "# Chapter 1: What is a peptide?\\n\\nA peptide is a short chain of amino acids.\\n"
        )
    # Chapter 2: semaglutide
    with open(os.path.join(chapters_dir, "chapter_02.md"), "w") as f:
        f.write("# Chapter 2: Semaglutide\\n\\nSemaglutide is a GLP-1 receptor agonist.\\n")
    # Chapter 3: retatrutide and black box warning
    with open(os.path.join(chapters_dir, "chapter_03.md"), "w") as f:
        f.write(
            "# Chapter 3: Retatrutide and Tirzepatide\\n\\nSemaglutide is a GLP-1 agonist. Tirzepatide is also discussed.\\n"
        )
    # Chapter 4: BPC-157
    with open(os.path.join(chapters_dir, "chapter_04.md"), "w") as f:
        f.write(
            "# Chapter 4: BPC-157\\n\\nBPC-157 is a peptide being studied for wound healing.\\n"
        )
    # Chapter 5: black box warning (thyroid)
    with open(os.path.join(chapters_dir, "chapter_05.md"), "w") as f:
        f.write(
            "# Chapter 5: Safety Warning\\n\\nSemaglutide has a black box warning for thyroid tumors.\\n"
        )
    # Chapter 6: future chapters
    with open(os.path.join(chapters_dir, "chapter_06.md"), "w") as f:
        f.write("# Chapter 6: Future Research\\n\\nMore studies are needed.\\n")
    # Chapter 7: oral peptide
    with open(os.path.join(chapters_dir, "chapter_07.md"), "w") as f:
        f.write("# Chapter 7: Oral Peptides\\n\\nOral peptide options are under investigation.\\n")
    # Chapter 8 to 11: filler
    for i in range(8, 12):
        with open(os.path.join(chapters_dir, f"chapter_{i:02d}.md"), "w") as f:
            f.write(f"# Chapter {i}\\n\\nThis is chapter {i}.\\n")
    return book_dir, chapters_dir


@pytest.fixture(scope="module")
def nm(book_dirs):
    """Build NeuralMind on peptide book with chapter-level indexing."""
    book_dir, _ = book_dirs
    from neuralmind import core

    nm = core.NeuralMind(book_dir, enable_synapses=False)
    nm._ensure_built()
    return nm


class TestChapterLevelIntegration:
    """End-to-end tests using the full NeuralMind pipeline."""

    def test_semaglutide_returns_fda_chapter(self, nm):
        """'How does semaglutide work?' should return Ch2 or Ch3."""
        ctx = nm.query("How does semaglutide work in the body?")
        text = ctx.context.lower()
        assert (
            "glp-1" in text or "semaglutide" in text
        ), f"Context should contain GLP-1 or semaglutide. Got: {text[:300]}"

    def test_retatrutide_returns_fda_chapter(self, nm):
        """'Is retatrutide FDA approved?' should return Ch3."""
        ctx = nm.query("Is retatrutide FDA approved?")
        text = ctx.context.lower()
        assert (
            "retatrutide" in text or "not yet fda" in text
        ), f"Context should contain retatrutide info. Got: {text[:300]}"

    def test_black_box_warning_returns_safety_chapter(self, nm):
        """'What is the black box warning?' should return Ch5."""
        ctx = nm.query("What is the black box warning on semaglutide?")
        text = ctx.context.lower()
        assert (
            "black box" in text or "thyroid" in text
        ), f"Context should contain black box/thyroid info. Got: {text[:300]}"

    def test_oral_peptide_returns_future_chapter(self, nm):
        """'Oral peptide options' should return Ch7."""
        ctx = nm.query("Will there be oral peptide options?")
        text = ctx.context.lower()
        assert "oral" in text, f"Context should contain oral peptide info. Got: {text[:300]}"

    def test_bpc157_returns_grey_market_chapter(self, nm):
        """'What is BPC-157?' should return Ch4."""
        ctx = nm.query("What is BPC-157?")
        text = ctx.context.lower()
        assert (
            "bpc" in text or "grey" in text
        ), f"Context should contain BPC-157/grey market info. Got: {text[:300]}"

    def test_what_is_peptide_returns_ch1(self, nm):
        """'What is a peptide?' should return Ch1 (definitions)."""
        ctx = nm.query("What exactly is a peptide?")
        text = ctx.context.lower()
        assert (
            "amino acid" in text or "peptide is" in text
        ), f"Context should contain peptide definition. Got: {text[:300]}"

    def test_medical_book_no_code_graph_language(self, nm):
        """Prose projects should not say 'Code repository'."""
        ctx = nm.query("What is semaglutide?")
        assert (
            "code repository" not in ctx.context.lower()
        ), "Medical book should not use code repository language"

    def test_no_synapse_language(self, nm):
        """Raw context should not mention synapses for a static book."""
        ctx = nm.query("What is semaglutide?")
        assert "synapse" not in ctx.context.lower(), "Book context should not mention synapses"


class TestChapterIndexerStandalone:
    """Tests for the prose path's ChapterIndexer (neuralmind.medical_retriever)
    on the synthetic chapters, with no embedder.
    """

    def test_multi_entity_search_merges(self):
        """Multi-entity search should merge results from multiple queries."""
        from neuralmind.medical_retriever import ChapterIndexer

        indexer = ChapterIndexer()
        indexer.index_directory(CHAPTERS_DIR)
        results = indexer.search_multi_entity(["semaglutide", "tirzepatide"], top_k=5)
        assert len(results) > 0
        # Should have deduplicated results
        sources = [r["source_file"] for r in results]
        assert len(sources) == len(set(sources)), "Results should be deduplicated"

        ensure_test_chapters()

    def test_chapter_section_two_level_indexing(self):
        """Two-level indexing should return chapter + section info."""
        from neuralmind.medical_retriever import ChapterIndexer

        indexer = ChapterIndexer()
        indexer.index_directory(CHAPTERS_DIR)
        # Chapter documents should have sections
        for doc in indexer._documents:
            assert hasattr(doc, "sections") or isinstance(doc, dict)

        ensure_test_chapters()

    def test_heading_tokens_extracted(self):
        """Heading tokens should be extracted from chapters."""
        from neuralmind.medical_retriever import ChapterIndexer

        indexer = ChapterIndexer()
        indexer.index_directory(CHAPTERS_DIR)
        found_headings = False
        for doc in indexer._documents:
            tokens = (
                doc.heading_tokens
                if hasattr(doc, "heading_tokens")
                else doc.get("heading_tokens", set())
            )
            if tokens:
                found_headings = True
                break
        assert found_headings, "No heading tokens found"
