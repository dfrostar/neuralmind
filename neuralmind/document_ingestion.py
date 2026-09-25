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
import re
import time
from fnmatch import fnmatch
from pathlib import Path

from .content_node import ContentNode
from .secret_scan import redact_if_enabled

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DIR_DEPTH = 10
CHUNK_SIZE = 500  # chars per chunk
CHUNK_OVERLAP = 50  # chars overlap between chunks


def _load_ignore_patterns(project_path: Path, filename: str) -> frozenset[str]:
    """Load .gitignore-style patterns from ``filename`` under ``project_path``."""
    ignore_path = project_path / filename
    if not ignore_path.exists():
        return frozenset()
    try:
        content = ignore_path.read_text(encoding="utf-8")
    except OSError:
        return frozenset()

    patterns: set[str] = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.add(line)
    return frozenset(patterns)


def _matches_ignore(rel_path: str, patterns: frozenset[str]) -> bool:
    """Check if project-relative ``rel_path`` matches any ignore pattern."""
    if not patterns:
        return False

    parts = rel_path.split("/")
    for pattern in patterns:
        cleaned = pattern.rstrip("/")
        if fnmatch(rel_path, pattern):
            return True
        if "/" not in cleaned and fnmatch(parts[-1], cleaned):
            return True
        if any(fnmatch(part, cleaned) for part in parts[:-1]):
            return True
        if rel_path.startswith(cleaned + "/"):
            return True
    return False


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


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def chunk_by_heading(text: str, *, max_section_chars: int = 500) -> list[dict]:
    """Split markdown text on H1/H2/H3 boundaries.

    Sections longer than ``max_section_chars`` fall back to ``_chunk_text()``
    within that section (preserving heading metadata on each chunk).

    Headings inside fenced code blocks (````` or ``~~~``) are NOT treated as
    section boundaries.

    Args:
        text: Markdown text to split.
        max_section_chars: Maximum characters per section before fallback
            chunking kicks in.

    Returns:
        List of dicts with keys: ``heading``, ``level``, ``content``,
        ``start_line``, ``end_line``.
    """
    lines = text.split("\n")
    # Find all headings (skipping those inside fenced code blocks)
    headings: list[tuple[int, int, str]] = []  # (line_idx, level, text)
    in_fence = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            heading_text = m.group(2).strip()
            if heading_text:
                headings.append((i, level, heading_text))

    if not headings:
        # No headings found — treat the whole text as one section
        return [
            {
                "heading": "",
                "level": 0,
                "content": text.strip(),
                "start_line": 1,
                "end_line": len(lines),
            }
        ]

    result: list[dict] = []
    for idx, (line_idx, level, heading_text) in enumerate(headings):
        # Section content runs from the line after the heading to the next
        # heading (or end of file).
        start = line_idx + 1
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        # Skip fenced code blocks inside content
        content_lines: list[str] = []
        cf = False
        for j in range(start, end):
            s = lines[j].strip()
            if s.startswith(("```", "~~~")):
                cf = not cf
                continue
            if cf:
                continue
            content_lines.append(lines[j])
        section_text = "\n".join(content_lines).strip()

        if len(section_text) <= max_section_chars:
            result.append(
                {
                    "heading": heading_text,
                    "level": level,
                    "content": section_text,
                    "start_line": line_idx + 1,
                    "end_line": end,
                }
            )
        else:
            # Fall back to overlapping chunks within this section
            sub_chunks = _chunk_text(
                section_text, chunk_size=max_section_chars, overlap=CHUNK_OVERLAP
            )
            for chunk_idx, chunk in enumerate(sub_chunks):
                result.append(
                    {
                        "heading": (
                            f"{heading_text} (part {chunk_idx + 1})"
                            if len(sub_chunks) > 1
                            else heading_text
                        ),
                        "level": level,
                        "content": chunk,
                        "start_line": line_idx + 1,
                        "end_line": end,
                    }
                )
    return result


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


def _extract_heading_hierarchy(text: str, max_lines: int = 50) -> list[dict[str, str]]:
    """Extract markdown heading hierarchy from the start of a document.

    Returns a list of {"level": "H1", "text": "..."} entries.
    """
    import re

    headings = []
    for line in text.split("\n")[:max_lines]:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            level = f"H{len(match.group(1))}"
            headings.append({"level": level, "text": match.group(2).strip()})
    return headings


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

    # Use heading-aware chunking for markdown files. Small files are fine:
    # chunk_by_heading() returns one section for short texts and sub-chunks
    # anything longer than chunk_size, so gating on length here only lost
    # chapter/section metadata for short documents.
    use_heading_chunking = file_type == "markdown" or path.suffix.lower() in (
        ".md",
        ".markdown",
        ".mkd",
    )

    if use_heading_chunking:
        sections = chunk_by_heading(text, max_section_chars=chunk_size)
        chunks = []
        current_chapter = path.stem.replace("-", " ").replace("_", " ").title()
        current_section = "Overview"

        for section in sections:
            heading = section.get("heading", "")
            level = section.get("level", 0)
            content = section.get("content", "")

            # chunk_by_heading strips the heading line from the section body;
            # put it back so the node text carries its own title (retrieval,
            # BM25, and the document_text contract all expect the heading in
            # the text). Heading-only sections (a title with no body) still
            # yield a node instead of silently vanishing — silently dropping
            # them made heading-only documents fail with "No content
            # extracted" and a CLI exit(1).
            if heading:
                heading_line = f"{'#' * (level or 1)} {heading}"
                section_text = (
                    f"{heading_line}\n\n{content}".strip() if content.strip() else heading_line
                )
            else:
                section_text = content

            if not section_text.strip():
                continue

            if level == 1:
                current_chapter = heading
                current_section = "Overview"
            elif level == 2:
                current_section = heading

            # If section is small enough, keep as one chunk
            if len(section_text) <= chunk_size:
                chunks.append(
                    {
                        "text": section_text,
                        "chapter": current_chapter,
                        "section": current_section,
                        "heading": heading,
                        "level": level,
                    }
                )
            else:
                # Sub-chunk large sections (chunk the heading + body text so
                # the first part carries the title, matching the pre-heading-
                # chunking contract of storing original document text)
                sub_chunks = _chunk_text(section_text, chunk_size=chunk_size, overlap=overlap)
                for sub_idx, sub in enumerate(sub_chunks):
                    chunk_label = (
                        f"{heading} (part {sub_idx + 1})" if len(sub_chunks) > 1 else heading
                    )
                    chunks.append(
                        {
                            "text": sub,
                            "chapter": current_chapter,
                            "section": chunk_label,
                            "heading": heading,
                            "level": level,
                        }
                    )
    else:
        # For small files or non-markdown, use simple chunking
        raw_chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        chunks = []
        current_chapter = path.stem.replace("-", " ").replace("_", " ").title()
        for chunk_text in raw_chunks:
            chunks.append(
                {
                    "text": chunk_text,
                    "chapter": current_chapter,
                    "section": "Overview",
                    "heading": "",
                    "level": 0,
                }
            )

    nodes = []
    for i, chunk_info in enumerate(chunks):
        node_id = _make_node_id(path, i if len(chunks) > 1 else 0)
        label = f"{path.name}"
        if len(chunks) > 1:
            section = chunk_info.get("section", "")
            label += f" ({section})" if section else f" (chunk {i+1}/{len(chunks)})"

        metadata = {
            "source": str(path),
            "file_type": file_type,
            "chunk_index": i,
            "chunk_count": len(chunks),
            "ingested_at": time.time(),
            "file_size": path.stat().st_size,
            "chapter": chunk_info.get("chapter", ""),
            "section": chunk_info.get("section", ""),
            "heading": chunk_info.get("heading", ""),
            "heading_level": chunk_info.get("level", 0),
        }

        node = ContentNode(
            node_id=node_id,
            label=label,
            content_type=f"document_{file_type}",
            text=chunk_info["text"],
            metadata=metadata,
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
    dir_path = dir_path.resolve()

    nodes = []
    errors = []
    root = dir_path
    from .graphgen import _DEFAULT_IGNORES, _is_ignored, _parse_ignore_file

    neuralmindignore = _parse_ignore_file(root)
    gitignore = _load_ignore_patterns(root, ".gitignore")

    def _walk(path: Path, depth: int = 0):
        if depth > MAX_DIR_DEPTH:
            return
        for item in sorted(path.iterdir()):
            if item.is_symlink():
                continue
            rel = item.relative_to(root).as_posix()
            if item.is_dir() and recursive:
                if (
                    item.name.startswith(".")
                    or item.name in _DEFAULT_IGNORES
                    or _is_ignored(rel, neuralmindignore)
                    or _matches_ignore(rel, gitignore)
                ):
                    continue
                _walk(item, depth + 1)
            elif item.is_file():
                if _is_ignored(rel, neuralmindignore) or _matches_ignore(rel, gitignore):
                    continue
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
