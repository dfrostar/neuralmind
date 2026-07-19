"""Tests for B4 — hierarchical summarization (summarize.py)."""

from __future__ import annotations

from neuralmind.summarize import RaptorSummarizer, SummaryResult


class TestRaptorSummarizer:
    """RAPTOR-style recursive summarization."""

    def test_summarize_short_text(self) -> None:
        s = RaptorSummarizer(depth=3, max_tokens_per_layer=100)
        result = s.summarize("This is a short text.")
        assert isinstance(result, SummaryResult)
        assert result.text == "This is a short text."

    def test_summarize_long_text(self) -> None:
        s = RaptorSummarizer(depth=3, max_tokens_per_layer=50)
        # A long text with distinct paragraphs.
        text = "\n\n".join(
            f"Paragraph {i}. " + "This is sentence one. This is sentence two. " * 20
            for i in range(10)
        )
        result = s.summarize(text)
        assert isinstance(result, SummaryResult)
        assert len(result.text) <= len(text)
        assert result.depth_used > 0

    def test_summarize_empty(self) -> None:
        s = RaptorSummarizer()
        result = s.summarize("")
        assert result.text == ""
        assert result.depth_used == 0

    def test_summarize_none_layer(self) -> None:
        s = RaptorSummarizer(max_tokens_per_layer=100)
        result = s.summarize("Short text", layer=1)
        assert result.layer == 1
        assert result.tokens >= 0

    def test_chunk_split(self) -> None:
        s = RaptorSummarizer()
        text = "\n\n".join([f"Part {i} with enough content" for i in range(20)])
        chunks = s._chunk(text, max_chars=100)
        assert len(chunks) >= 2

    def test_chunk_small_text(self) -> None:
        s = RaptorSummarizer()
        chunks = s._chunk("tiny", max_chars=1000)
        assert len(chunks) == 1

    def test_score_chunks_heuristic(self) -> None:
        s = RaptorSummarizer()
        chunks = ["Short.", "This is a longer chunk with more content."]
        scored = s._score_chunks_heuristic(chunks)
        assert len(scored) == 2
        # Longer chunk should score higher.
        assert scored[0][1] == chunks[1]

    def test_score_chunks_semantic_fallback(self) -> None:
        s = RaptorSummarizer()

        # Pass a broken embed_fn; should fall back to heuristic.
        def broken_embed(t):
            raise ValueError("broken")

        s.embed_fn = broken_embed
        chunks = ["a" * 100, "b" * 500]
        scored = s._score_chunks_semantic(chunks)
        assert len(scored) == 2


class TestSummaryResult:
    """SummaryResult dataclass."""

    def test_tokens(self) -> None:
        r = SummaryResult(text="abcd" * 10, depth_used=1, source_length=100, layer=0)
        assert r.tokens == 10

    def test_empty_tokens(self) -> None:
        r = SummaryResult(text="", depth_used=0, source_length=0, layer=0)
        assert r.tokens == 0


class TestGetL2Summary:
    """get_l2_summary integration."""

    def test_no_project(self) -> None:
        from neuralmind.summarize import get_l2_summary

        assert get_l2_summary(1, store=None, project_path=None) == ""

    def test_no_store(self) -> None:
        from neuralmind.summarize import get_l2_summary

        assert get_l2_summary(1, store=None, project_path=None) == ""
