"""Non-security hashes must say so, or NeuralMind crashes on a FIPS-mode host.

With the OS FIPS mode on (CMMC SC.L2-3.13.11 asks for it), OpenSSL refuses
MD5: ``hashlib.md5()`` raises ``UnsupportedDigestmodError``. Document ingestion
hashed parent directories with a bare ``hashlib.md5()`` to build node ids, so
``neuralmind ingest``, ``ingest-content``, book builds and the MCP
``neuralmind_ingest_document`` tool failed on exactly the hosts the compliance
docs tell operators to configure. ``usedforsecurity=False`` (Python 3.9+) tells OpenSSL
the digest is an identifier, not a security control, and it is allowed again.

SHA-1 still works in FIPS mode, but NIST is retiring it (SP 800-131A), and
RHEL's FIPS policy blocks Python's built-in BLAKE2 for security use. So every
MD5, SHA-1 and BLAKE2 call in the repo, product code and tests alike (the
``fips`` CI job runs the whole suite under the OpenSSL FIPS provider), must
pass ``usedforsecurity=False``. A security use of one of these is a bug to
fix, not something to flag.

Stdlib-only, so it runs without the full dep set.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: hashlib constructors that need ``usedforsecurity=False``.
WEAK_CONSTRUCTORS = {"md5", "sha1", "blake2b", "blake2s"}

#: ``hashlib.new()`` names a FIPS provider refuses or NIST is retiring.
WEAK_NEW_NAMES = WEAK_CONSTRUCTORS | {"md4", "md5-sha1", "ripemd160", "sm3", "whirlpool", "mdc2"}

#: Directories that hold no first-party Python.
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", ".neuralmind", "graphify-out", "site"}


def _flags_non_security(call: ast.Call) -> bool:
    return any(
        kw.arg == "usedforsecurity"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is False
        for kw in call.keywords
    )


def violations(source: str, filename: str = "<string>") -> list[str]:
    """Each weak-hash use in ``source`` that doesn't pass ``usedforsecurity=False``."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source, filename)):
        if isinstance(node, ast.ImportFrom) and node.module == "hashlib":
            for alias in node.names:
                if alias.name in WEAK_CONSTRUCTORS:
                    found.append(
                        f"{filename}:{node.lineno}: `from hashlib import {alias.name}`; "
                        f"call hashlib.{alias.name}(..., usedforsecurity=False) instead"
                    )
            continue
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "hashlib"
        ):
            continue
        if func.attr in WEAK_CONSTRUCTORS:
            weak = True
        elif func.attr == "new" and node.args:
            name = node.args[0]
            # A name only known at runtime could be any of them.
            weak = not isinstance(name, ast.Constant) or (str(name.value).lower() in WEAK_NEW_NAMES)
        else:
            weak = False
        if weak and not _flags_non_security(node):
            found.append(
                f"{filename}:{node.lineno}: hashlib.{func.attr}() without "
                "usedforsecurity=False fails on a FIPS-mode host"
            )
    return found


def _python_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if not SKIP_DIRS.intersection(rel.parts[:-1]):
            files.append(path)
    return files


def test_weak_hashes_are_marked_non_security():
    found: list[str] = []
    for path in _python_files():
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            found.extend(violations(source, str(path.relative_to(ROOT))))
        except SyntaxError:
            continue  # fixtures that aren't valid Python on purpose
    assert not found, "\n".join(found)


def test_scan_covers_the_package_and_tests():
    rels = {p.relative_to(ROOT).parts[0] for p in _python_files()}
    assert {"neuralmind", "tests"} <= rels


def test_scanner_catches_each_shape():
    src = (
        "import hashlib\n"
        "from hashlib import md5\n"
        "hashlib.md5(b'x')\n"
        "hashlib.sha1(b'x', usedforsecurity=True)\n"
        "hashlib.blake2b(b'x')\n"
        "hashlib.new('MD5')\n"
        "hashlib.new(algo)\n"
    )
    lines = sorted(int(v.split(":")[1]) for v in violations(src))
    assert lines == [2, 3, 4, 5, 6, 7]


def test_scanner_accepts_non_security_and_approved_hashes():
    src = (
        "import hashlib\n"
        "hashlib.md5(b'x', usedforsecurity=False)\n"
        "hashlib.sha1(b'x', usedforsecurity=False)\n"
        "hashlib.new('md5', usedforsecurity=False)\n"
        "hashlib.new(algo, usedforsecurity=False)\n"
        "hashlib.sha256(b'x')\n"
        "hashlib.new('sha512')\n"
        "hashlib.sha3_256(b'x')\n"
    )
    assert violations(src) == []
