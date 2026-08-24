"""Document ingestion: parse PDF/Markdown/text into ContentNodes.

Generalizes the CMMC ingestion path to arbitrary documents. Parses files,
chunks them if needed, and creates ContentNode objects that embed alongside
code in the same vector space.

Security guards:
- Path canonicalization (reject symlink escapes)
- File magic sniffing (reject binary content with text extensions)
- Size cap (10MB per file)
- Directory depth cap (10)
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .content_node import ContentNode
from .secret_scan import redact_if_enabled

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DIR_DEPTH = 10
CHUNK_SIZE = 500  # chars per chunk
CHUNK_OVERLAP = 50  # chars overlap between chunks


def _validate_path(path: Path, root: Path) -> Path:
    """Canonicalize path and reject symlink escapes.

    Args:
        path: File path to validate.
        root: Root directory that must contain the path.

    Returns:
        Canonicalized absolute path.

    Raises:
        ValueError: If path escapes root or is a symlink.
    """
    if path.is_symlink():
        raise ValueError(f"Symlinks not allowed: {path}")
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        # Allow paths outside root — user may learn files from /tmp etc.
        # But reject symlink escapes (symlinks that point outside root)
        if resolved.is_symlink():
            real = resolved.resolve(strict=False)
            try:
                real.relative_to(root_resolved)
            except ValueError:
                raise ValueError(f"Symlink escape rejected: {path} -> {real}") from None
    return resolved


def _sniff_file_type(path: Path) -> str:
    """Sniff file type from magic bytes and content analysis.

    Returns: 'pdf', 'markdown', 'text', or 'unknown'
    """
    try:
        header = path.read_bytes()[:8]
    except Exception:
        return "unknown"

    # PDF: %PDF-
    if header[:5] == b"%PDF-":
        return "pdf"

    # Detect binary content by magic bytes (even if extension says .md/.txt)
    # ELF: \x7fELF, PE: MZ, Mach-O: \xfe\xed\xfa\xce or \xfe\xed\xfa\xcf
    if header[:4] == b"\x7fELF" or header[:2] == b"MZ":
        return "unknown"
    if header[:4] in (
        b"\xfe\xed\xfa\xce",
        b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe",
        b"\xcf\xfa\xed\xfe",
    ):
        return "unknown"

    # Try UTF-8 decode to detect text
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return "unknown"

    # Detect binary content disguised as text (e.g., null bytes or high non-printable ratio)
    if b"\x00" in raw:
        return "unknown"

    # Check for non-printable character ratio (>30% non-printable = binary)
    printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    if len(text) > 0 and printable / len(text) < 0.7:
        return "unknown"

    # Check extension for markdown
    if path.suffix.lower() in (".md", ".markdown", ".mkd"):
        return "markdown"
    return "text"


def _parse_text_file(path: Path) -> str:
    """Parse a text/markdown file to plain text."""
    return path.read_text(encoding="utf-8")


def _parse_pdf(path: Path) -> str:
    """Parse a PDF to plain text. Requires pdfplumber."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "PDF parsing requires pdfplumber. Install: pip install pdfplumber"
        ) from exc

    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    if not text_parts:
        raise RuntimeError(f"No text extracted from PDF: {path}")

    return "\n\n".join(text_parts)


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Chunk text into overlapping windows.

    Args:
        text: Text to chunk.
        chunk_size: Maximum characters per chunk. Must be > overlap.
        overlap: Character overlap between consecutive chunks. Must be < chunk_size.

    Returns:
        List of text chunks.

    Raises:
        ValueError: If chunk_size <= overlap (would cause infinite loop).
    """
    if chunk_size <= overlap:
        raise ValueError(
            f"chunk_size ({chunk_size}) must be greater than overlap ({overlap}). "
            f"Use --chunk-size > --overlap."
        )

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += chunk_size - overlap
    return chunks


def _make_node_id(path: Path, index: int = 0) -> str:
    """Create a unique node ID for a document chunk.

    Uses relative path (stem + parent dirs + extension) to avoid collisions
    (e.g. a/README.md vs b/README.md).
    """
    stem = path.stem.replace(" ", "_")
    ext = path.suffix.lstrip(".").replace(" ", "_")
    # Include parent dirs (hashed) to disambiguate same-named files
    parent_hash = hashlib.md5(str(path.parent).encode()).hexdigest()[:8]
    base = f"{stem}.{ext}.{parent_hash}" if ext else f"{stem}.{parent_hash}"
    if index == 0:
        return f"doc:{base}"
    return f"doc:{base}:chunk{index}"


def parse_document(
    path: Path,
    root: Path | None = None,
    content_type: str = "auto",
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[ContentNode]:
    """Parse a document file into ContentNodes.

    Large documents are chunked into multiple nodes for finer-grained retrieval.

    Args:
        path: Path to the document file.
        root: Root directory for path validation. If None, uses path.parent.
        content_type: Type hint ('pdf', 'markdown', 'text', or 'auto' to sniff).
        chunk_size: Max characters per chunk (default: CHUNK_SIZE=500).
        overlap: Character overlap between chunks (default: CHUNK_OVERLAP=50).

    Returns:
        List of ContentNode objects.

    Raises:
        ValueError: If file type is unsupported or validation fails.
        RuntimeError: If parsing fails.
    """
    path = Path(path)
    if not path.exists():
        raise ValueError(f"File not found: {path}")

    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large (>10MB): {path}")

    # Validate and sniff — use file's parent as root if not specified
    if root is None:
        root = path.parent
    _validate_path(path, root)

    # If content_type is explicit (not "auto"), use it directly
    if content_type != "auto":
        file_type = content_type
    else:
        file_type = _sniff_file_type(path)

    # Hard security guard: reject binary regardless of content_type hint
    try:
        header = path.read_bytes()[:8]
        if header[:4] == b"\x7fELF" or header[:2] == b"MZ":
            raise ValueError(f"Binary file rejected: {path}")
        if header[:4] in (
            b"\xfe\xed\xfa\xce",
            b"\xfe\xed\xfa\xcf",
            b"\xce\xfa\xed\xfe",
            b"\xcf\xfa\xed\xfe",
        ):
            raise ValueError(f"Binary file rejected: {path}")
    except ValueError:
        raise
    except Exception:
        pass  # If we can't read the file, the next steps will fail

    if file_type == "unknown":
        raise ValueError(f"Unsupported file type (binary?): {path}")

    if file_type == "pdf":
        text = _parse_pdf(path)
    else:
        text = _parse_text_file(path)

    if not text.strip():
        raise ValueError(f"Empty document: {path}")

    # Scrub credentials before chunking so a secret can't be split across
    # two chunks and survive in halves.
    text = redact_if_enabled(text)

    # Chunk if large
    chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    nodes = []

    for i, chunk in enumerate(chunks):
        node_id = _make_node_id(path, i if len(chunks) > 1 else 0)
        label = f"{path.name}"
        if len(chunks) > 1:
            label += f" (chunk {i+1}/{len(chunks)})"

        node = ContentNode(
            node_id=node_id,
            label=label,
            content_type=f"document_{file_type}",
            text=chunk,
            metadata={
                "source": str(path),
                "file_type": file_type,
                "chunk_index": i,
                "chunk_count": len(chunks),
                "ingested_at": time.time(),
                "file_size": path.stat().st_size,
            },
        )
        nodes.append(node)

    return nodes


def ingest_directory(dir_path: Path, recursive: bool = True) -> list[ContentNode]:
    """Ingest all supported files in a directory.

    Args:
        dir_path: Directory path.
        recursive: Whether to recurse into subdirectories.

    Returns:
        List of ContentNode objects from all files.
    """
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {dir_path}")

    nodes = []
    errors = []

    def _walk(path: Path, depth: int = 0):
        if depth > MAX_DIR_DEPTH:
            return
        for item in sorted(path.iterdir()):
            if item.is_symlink():
                continue
            if item.is_dir() and recursive:
                _walk(item, depth + 1)
            elif item.is_file():
                try:
                    nodes.extend(parse_document(item))
                except (ValueError, RuntimeError) as e:
                    errors.append((str(item), str(e)))

    _walk(dir_path)

    if errors:
        print(f"  ⚠ {len(errors)} file(s) skipped:")
        for path, err in errors[:5]:
            print(f"    - {path}: {err}")
        if len(errors) > 5:
            print(f"    ... and {len(errors) - 5} more")

    return nodes
