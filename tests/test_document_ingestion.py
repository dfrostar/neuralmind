"""Tests for document_ingestion.py."""

from pathlib import Path
from unittest.mock import patch

import pytest

from neuralmind.content_node import ContentNode
from neuralmind.document_ingestion import (
    MAX_FILE_SIZE,
    _chunk_text,
    _sniff_file_type,
    _validate_path,
    ingest_directory,
    parse_document,
)


class TestValidatePath:
    def test_valid_path(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = _validate_path(f, tmp_path)
        assert result == f.resolve()

    def test_symlink_rejected(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("hello")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        with pytest.raises(ValueError, match="Symlinks not allowed"):
            _validate_path(link, tmp_path)

    def test_outside_root_allowed(self, tmp_path):
        """Files outside root are allowed (e.g., /tmp); only symlinks are rejected."""
        outside = tmp_path.parent / "escape.txt"
        outside.write_text("hello")
        # Should not raise — files outside root are permitted
        result = _validate_path(outside, tmp_path)
        assert result == outside.resolve()


class TestSniffFileType:
    def test_markdown_by_extension(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Hello\nWorld")
        assert _sniff_file_type(f) == "markdown"

    def test_text_plain(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world")
        assert _sniff_file_type(f) == "text"

    def test_pdf_magic_bytes(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"%PDF-1.4 fake pdf content")
        assert _sniff_file_type(f) == "pdf"

    def test_binary_rejected(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_bytes(b"\x7fELF binary content")
        assert _sniff_file_type(f) == "unknown"


class TestChunkText:
    def test_small_text_no_chunk(self):
        text = "Hello world"
        chunks = _chunk_text(text, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_large_text_chunked(self):
        text = "x" * 1000
        chunks = _chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) > 1


class TestParseDocument:
    def test_parse_markdown(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("# Title\n\nSome content here.")
        nodes = parse_document(f)
        assert len(nodes) == 1
        assert isinstance(nodes[0], ContentNode)
        assert nodes[0].label == "doc.md"
        assert "Title" in nodes[0].text

    def test_parse_text(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("Meeting notes\nAction items")
        nodes = parse_document(f)
        assert len(nodes) == 1
        assert nodes[0].content_type == "document_text"

    def test_file_too_large(self, tmp_path):
        f = tmp_path / "large.txt"
        f.write_text("small")

        class FakeStat:
            st_size = MAX_FILE_SIZE + 1

        # Patch Path.stat at class level to bypass PosixPath read-only restriction
        with patch.object(Path, "stat", lambda self, **kw: FakeStat()):
            with pytest.raises(ValueError, match="too large"):
                parse_document(f)

    def test_nonexistent_file(self, tmp_path):
        with pytest.raises(ValueError, match="File not found"):
            parse_document(tmp_path / "nonexistent.txt")

    def test_binary_rejected(self, tmp_path):
        f = tmp_path / "fake.md"
        f.write_bytes(b"\x7fELF not actually markdown")
        with pytest.raises(ValueError, match="Binary file rejected"):
            parse_document(f)


class TestIngestDirectory:
    def test_ingest_multiple_files(self, tmp_path):
        (tmp_path / "a.md").write_text("# A\nContent A")
        (tmp_path / "b.txt").write_text("Content B")
        nodes = ingest_directory(tmp_path)
        assert len(nodes) >= 2

    def test_ignores_symlinks(self, tmp_path):
        real = tmp_path / "real.txt"
        real.write_text("hello")
        link = tmp_path / "link.txt"
        link.symlink_to(real)
        nodes = ingest_directory(tmp_path)
        # Should only get the real file
        assert len([n for n in nodes if n.label == "real.txt"]) == 1

    def test_depth_limit(self, tmp_path):
        # Create deeply nested structure
        current = tmp_path
        for i in range(15):
            current = current / f"dir{i}"
            current.mkdir()
        (current / "deep.txt").write_text("deep content")
        # Should not crash, just stop at depth limit
        nodes = ingest_directory(tmp_path)
        # May or may not find deep file depending on limit
        assert isinstance(nodes, list)

    def test_skips_default_and_ignore_file_directories(self, tmp_path):
        (tmp_path / "keep.md").write_text("# Keep\n")

        venv = tmp_path / ".venv" / "pkg"
        venv.mkdir(parents=True)
        (venv / "ignored.md").write_text("# ignored")

        hidden = tmp_path / ".cache"
        hidden.mkdir()
        (hidden / "hidden.txt").write_text("hidden")

        build = tmp_path / "docs" / "_build"
        build.mkdir(parents=True)
        (build / "rendered.txt").write_text("rendered")

        notes = tmp_path / "notes"
        notes.mkdir()
        (notes / "skip.md").write_text("# skip")

        (tmp_path / ".gitignore").write_text("docs/_build/\n")
        (tmp_path / ".neuralmindignore").write_text("notes/\n")

        nodes = ingest_directory(tmp_path)
        labels = {n.label for n in nodes}

        assert "keep.md" in labels
        assert "ignored.md" not in labels
        assert "hidden.txt" not in labels
        assert "rendered.txt" not in labels
        assert "skip.md" not in labels

    def test_gitignore_negation_unignores_file(self, tmp_path):
        (tmp_path / "README.md").write_text("# Keep me\n")
        (tmp_path / "notes.md").write_text("# Skip me\n")
        (tmp_path / ".gitignore").write_text("*.md\n!README.md\n")

        nodes = ingest_directory(tmp_path)
        labels = {n.label for n in nodes}

        assert "README.md" in labels
        assert "notes.md" not in labels


class TestDotFileSecretsNeverIngested:
    """Regression: .env / dot-files were ingested as content, leaking
    credentials into the index (found by GLM-5.2 second-model review of
    PR #528, verified 2026-09-26)."""

    def test_env_file_never_ingested(self, tmp_path):
        (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test123\n")
        (tmp_path / "readme.md").write_text("# Real content\n")

        nodes = ingest_directory(tmp_path)
        labels = {n.label for n in nodes}

        assert ".env" not in labels, "secrets file leaked into content index"
        assert "readme.md" in labels

    def test_gitignore_itself_not_ingested(self, tmp_path):
        (tmp_path / ".gitignore").write_text("*.log\n")
        (tmp_path / "doc.md").write_text("# doc\n")

        nodes = ingest_directory(tmp_path)
        labels = {n.label for n in nodes}

        assert ".gitignore" not in labels
        assert "doc.md" in labels


class TestGitignoreSemantics:
    """Regression: the matcher mis-implemented gitignore anchoring rules
    (nested over-ignore, dead rooted patterns, dead **/ patterns — found by
    GLM-5.2 review, fixed 2026-09-26)."""

    def test_slash_anchors_glob_to_root(self):
        from neuralmind.document_ingestion import _matches_ignore

        # '*' must not cross '/' — docs/*.md matches docs/intro.md but not
        # docs/ch1/intro.md
        assert _matches_ignore("docs/intro.md", ("docs/*.md",))
        assert not _matches_ignore("docs/ch1/intro.md", ("docs/*.md",))

    def test_leading_slash_is_rooted(self):
        from neuralmind.document_ingestion import _matches_ignore

        assert _matches_ignore("vendor/lib.md", ("/vendor/",))
        assert not _matches_ignore("src/vendor/lib.md", ("/vendor/",))

    def test_double_star_matches_any_depth_including_root(self):
        from neuralmind.document_ingestion import _matches_ignore

        assert _matches_ignore("build_artifacts/foo.txt", ("**/build_artifacts",))
        assert _matches_ignore("nested/build_artifacts/x.txt", ("**/build_artifacts",))

    def test_unanchored_pattern_matches_directory_anywhere(self):
        from neuralmind.document_ingestion import _matches_ignore

        assert _matches_ignore("temporary/file.md", ("temp*",))
        assert not _matches_ignore("attempt/file.md", ("temp*",))

    def test_dir_only_trailing_slash(self):
        from neuralmind.document_ingestion import _matches_ignore

        assert _matches_ignore("build/out.js", ("build/",))
        assert not _matches_ignore("build.py", ("build/",))
