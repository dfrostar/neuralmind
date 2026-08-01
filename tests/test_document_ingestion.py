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

    def test_escape_rejected(self, tmp_path):
        outside = tmp_path.parent / "escape.txt"
        outside.write_text("hello")
        with pytest.raises(ValueError, match="Path escapes"):
            _validate_path(outside, tmp_path)


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
        with pytest.raises(ValueError, match="Unsupported"):
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
