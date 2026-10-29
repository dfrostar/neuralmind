# SPDX-License-Identifier: MIT
"""
G4 — Incremental re-extraction.

Tracks file content hashes to determine which files need re-extraction on
each build. Also resolves reverse edges (importers/callers) that may need
re-extraction when a dependency changes.

Part of Wave 5 — wired into build_graph() so `neuralmind build` skips
unchanged files.

Skip-path: if no cache exists (first run, corrupted), does a full
extraction. A file whose mtime and size match the cache is skipped; any
difference (older mtimes included) is confirmed with the content hash.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from neuralmind.graphgen import _DEFAULT_IGNORES as _GG_IGNORES

CACHE_FILE = ".neuralmind/extraction_cache.json"
IMPORTER_INDEX_FILE = ".neuralmind/importer_index.json"

# A package's entry file is imported by its directory's name.
_ENTRY_STEMS = frozenset({"__init__", "index", "mod"})


def _module_names(rels: list[str]) -> set[str]:
    """Names an import uses for ``rels``: ``pkg/d.py`` -> ``d``; a package entry
    such as ``pkg/__init__.py``, or any Go file, also by its directory."""
    names: set[str] = set()
    for rel in rels:
        path = PurePosixPath(rel)
        names.add(path.stem)
        if (path.stem in _ENTRY_STEMS or path.suffix == ".go") and path.parent.name:
            names.add(path.parent.name)
    return names


def _referable(names: set[str]) -> set[str]:
    """``names`` as code writes them: ``Ns::Foo`` and ``a.Foo`` also as ``Foo``; no dunders."""
    out = set(names)
    out.update(re.split(r"::|\.", n)[-1] for n in names)
    return {n for n in out if n and not (n.startswith("__") and n.endswith("__"))}


def _first_pass(root: Path, rels: list[str], parsers: dict[str, Any]) -> Any:
    """A builder holding what the build's first pass registers for ``rels`` as they are now."""
    from neuralmind import graphgen as gg

    b = gg._GraphBuilder()
    for rel in rels:
        lang = gg._SUFFIX_LANG.get(PurePosixPath(rel).suffix, "")
        spec = gg._EXTRACTORS.get(lang)
        if spec is None:
            continue
        try:
            if lang not in parsers:
                parsers[lang] = gg._make_parser(lang) if gg.language_available(lang) else None
            if parsers[lang] is None:
                continue
            src = (root / rel).read_bytes()
            file_id = gg._slug(rel)
            b.add_node(file_id, PurePosixPath(rel).name, "code", rel, 1)
            spec[0](b, parsers[lang].parse(src).root_node, src, rel, file_id)
        except Exception:
            continue  # fail-open: its module name still catches imports
    return b


def _symbols(b: Any) -> dict[tuple[str, str], list[str]]:
    """A builder's name tables as one map: functions, classes and module keys.

    Module keys too, because Java, C#, PHP and Ruby take them from a file's
    package or namespace line: a package rename moves every import of it.
    """
    tables = {("func", k): list(v) for k, v in b.func_by_name.items()}
    tables.update({("class", k): list(v) for k, v in b.class_by_name.items()})
    tables.update({("module", k): [v] for k, v in b.file_by_module.items()})
    tables.update({("package", k): list(v) for k, v in b.go_pkg_files.items()})
    return tables


def _names_defined_by(root: Path, rels: list[str]) -> set[str]:
    """Names another file would use to reach ``rels``: module names and symbols.

    Symbols are what the build's first pass registers for call and
    inheritance resolution, so a reference by bare name counts too.
    """
    b = _first_pass(root, rels, {})
    return _referable(_module_names(rels) | set(b.func_by_name) | set(b.class_by_name))


def _previous_symbols(nodes: list[dict[str, Any]]) -> dict[tuple[str, str], list[str]]:
    """What an incremental build registers for a kept file's ``nodes``."""
    from neuralmind import graphgen as gg

    b = gg._GraphBuilder()
    for node in nodes:
        gg._register_node_symbol(b, node)
    return _symbols(b)


def names_changed(
    root: Path, rels: list[str], previous: dict[str, list[dict[str, Any]]]
) -> set[str]:
    """Names whose definitions an edit to ``rels`` added, removed or reordered.

    A call resolves to the first project function of its name in build order,
    so a file that gains a function another file already defines can take
    over calls in files nobody edited (and losing one hands them back). A
    full build re-resolves those calls; an incremental build must re-extract
    the files that name them. ``previous`` holds each file's nodes from the
    last graph. Compared as registered, so a mismatch only re-extracts more.
    """
    names: set[str] = set()
    parsers: dict[str, Any] = {}
    for rel in rels:
        old = _previous_symbols(previous.get(rel, []))
        new = _symbols(_first_pass(root, [rel], parsers))
        names.update(key[1] for key in old.keys() | new.keys() if old.get(key) != new.get(key))
    return _referable(names)


def names_removed(rels: list[str], previous: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Names other files used to reach the deleted ``rels``."""
    names = _module_names(rels)
    for rel in rels:
        names.update(key[1] for key in _previous_symbols(previous.get(rel, [])))
    return _referable(names)


def files_naming(root: Path, rels: Any, names: set[str]) -> set[str]:
    """The files in ``rels`` whose text contains one of ``names``.

    A plain text match over-approximates (a comment counts), which only
    costs a re-extraction; it never misses a file that refers to a name.
    """
    if not names:
        return set()
    alternation = b"|".join(
        re.escape(n.encode("utf-8")) for n in sorted(names, key=len, reverse=True)
    )
    pattern = re.compile(rb"(?<![A-Za-z0-9_])(?:" + alternation + rb")(?![A-Za-z0-9_])")
    hits: set[str] = set()
    for rel in rels:
        try:
            if pattern.search((root / rel).read_bytes()):
                hits.add(rel)
        except OSError:
            continue
    return hits


@dataclass
class FileCache:
    """Per-file cache entry for incremental extraction."""

    path: str
    mtime: float
    content_hash: str
    extracted_at: float = 0.0
    size: int = -1  # -1: unknown (a cache written before sizes were kept)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "mtime": self.mtime,
            "content_hash": self.content_hash,
            "extracted_at": self.extracted_at,
            "size": self.size,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FileCache:
        return cls(
            path=d["path"],
            mtime=d["mtime"],
            content_hash=d["content_hash"],
            extracted_at=d.get("extracted_at", 0.0),
            size=d.get("size", -1),
        )


class IncrementalExtractor:
    """
    Tracks file content hashes to determine which files need
    re-extraction on each build. Also resolves reverse edges
    (importers/callers) that may need re-extraction when a
    dependency changes.

    Skip-path: if no cache exists (first run, corrupted), does
    a full extraction. If a file's mtime and size are unchanged
    from the last build, it's skipped.
    """

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path)
        self.cache_path = self.project_path / CACHE_FILE
        self._cache: dict[str, FileCache] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        try:
            if self.cache_path.exists():
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                for d in data.get("files", []):
                    fc = FileCache.from_dict(d)
                    self._cache[fc.path] = fc
        except Exception:
            self._cache = {}

    def _save_cache(self) -> None:
        """Persist cache to disk."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "files": [fc.to_dict() for fc in self._cache.values()],
                "saved_at": time.time(),
            }
            self.cache_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass  # fail-open

    def _content_hash(self, filepath: Path) -> str:
        """SHA-256 of file content. Returns empty string when unreadable."""
        if not filepath.exists():
            return ""
        try:
            return hashlib.sha256(filepath.read_bytes()).hexdigest()
        except Exception:
            return ""

    @staticmethod
    def _walk(root: Path, suffixes: frozenset[str]) -> list[Path]:
        """Files under ``root`` with a suffix in ``suffixes``, without the build's ignore files."""
        found = []
        for f in sorted(root.rglob("*")):
            if not (f.is_file() and f.suffix in suffixes):
                continue
            try:
                parts = Path(f.relative_to(root).as_posix()).parts
            except ValueError:
                continue
            # The graph walker's rule: skip dot-directories and the
            # canonical ignores. Not every dunder name: that hid each
            # __init__.py from change detection, so its edits never
            # reached the graph.
            if any(p.startswith(".") for p in parts[:-1]) or any(p in _GG_IGNORES for p in parts):
                continue
            found.append(f)
        return found

    def scan_files(
        self,
        root: Path,
        suffixes: frozenset[str],
        files: list[Path] | None = None,
    ) -> tuple[list[str], list[str], list[str]]:
        """
        Compare current files against cache to find changes.

        ``files`` is the list the build extracts from. Pass it: only those
        files are ever cached, so any other file the scan saw would count as
        added on every build. Without it, the scan walks ``root`` itself, which
        doesn't apply ``.gitignore``, ``.neuralmindignore`` or the config's
        globs. On NeuralMind's own repository that made 372 ignored files
        (``tests/``, ``docs/``, ``*.config.js``) "added" on every incremental
        build, and every build then searched the whole cache for their names.

        Returns: (added, modified, deleted) file path lists
        """
        if files is None:
            files = self._walk(root, suffixes)
        current_files: dict[str, tuple[float, int]] = {}
        for f in files:
            try:
                # POSIX, like the cache keys and the graph's paths: on
                # Windows str() gave backslashes, so no file in a
                # subdirectory ever matched its cache entry.
                stat = f.stat()
                current_files[f.relative_to(root).as_posix()] = (stat.st_mtime, stat.st_size)
            except (OSError, ValueError):
                continue

        cached_paths = set(self._cache.keys())
        current_paths = set(current_files.keys())

        added = sorted(current_paths - cached_paths)
        deleted = sorted(cached_paths - current_paths)
        modified = []

        # Any mtime or size difference -- an older mtime too, as after `mv` of
        # a backup or a checkout -- may be a change; the content hash decides.
        refreshed = False
        for rel in sorted(current_paths & cached_paths):
            cached = self._cache[rel]
            mtime, size = current_files[rel]
            if mtime == cached.mtime and (size == cached.size or cached.size < 0):
                continue
            if self._content_hash(root / rel) != cached.content_hash:
                modified.append(rel)
            else:
                # Same content: remember the new stat so it isn't hashed again.
                cached.mtime, cached.size = mtime, size
                refreshed = True
        if refreshed:
            self._save_cache()

        return added, modified, deleted

    def get_changed_with_dependents(
        self,
        root: Path,
        suffixes: frozenset[str],
        importer_index: dict[str, list[str]],
        files: list[Path] | None = None,
        previous: dict[str, list[dict[str, Any]]] | None = None,
    ) -> list[str]:
        """
        Get changed files plus files that import them (reverse edges).

        importer_index: maps file -> list of files that import it; used only
        without ``previous``.
        files: the build's file list, as :meth:`scan_files` takes it.
        previous: each file's nodes in the last graph. With it, files that
        name a function or class an edited or deleted file gained, lost or
        reordered are re-extracted too (see :func:`names_changed`), and
        importers aren't (see below).
        """
        added, modified, deleted = self.scan_files(root, suffixes, files)
        changed = set(added + modified + deleted)

        # An added file can satisfy an import or call an unchanged file
        # couldn't resolve at the last build (`from d import newfn` before d.py
        # existed). No edge records an unresolved reference, so the importer
        # index can't name those files: re-extract the ones that mention the
        # new file's module name or a symbol it defines. An edit or a deletion
        # that changes which functions a name can mean does the same.
        names = _names_defined_by(root, added) if added else set()
        if previous is not None:
            names |= names_changed(root, modified, previous)
            names |= names_removed(deleted, previous)
        named = self._files_naming(root, names, skip=changed) if names else set()

        # Importers of changed files, transitively. A build that passes
        # ``previous`` needs none of them: it keeps the edges unchanged files
        # have into re-extracted ones, and re-extracts every file whose calls
        # a change could move (above). On hermes-agent the closure was most of
        # the repository for an edit to a widely imported file (42 s against
        # 12 s, for the same graph). Without ``previous`` it stands in for
        # both. Never from the files that only name a changed symbol:
        # re-extracting one changes its calls, not its own symbols.
        to_check = list(changed) if previous is None else []
        checked: set[str] = set()
        while to_check:
            filepath = to_check.pop(0)
            if filepath in checked:
                continue
            checked.add(filepath)
            for importer in importer_index.get(filepath, []):
                if importer not in checked and importer not in changed:
                    changed.add(importer)
                    to_check.append(importer)

        changed |= named

        added_list = list(added)
        modified_list = [f for f in modified if f not in added]
        # Importers get added to modified for re-extraction
        importer_list = [
            f for f in changed if f not in added and f not in modified and f not in deleted
        ]

        return added_list + modified_list + importer_list

    def _files_naming(self, root: Path, names: set[str], skip: set[str]) -> set[str]:
        """Cached files, other than ``skip``, whose text contains one of ``names``."""
        return files_naming(root, [rel for rel in self._cache if rel not in skip], names)

    def update_cache(self, file_paths: list[str], root: Path) -> None:
        """Update cache entries for extracted files."""
        now = time.time()
        for rel in file_paths:
            full_path = root / rel
            try:
                stat = full_path.stat()
                self._cache[rel] = FileCache(
                    path=rel,
                    mtime=stat.st_mtime,
                    content_hash=self._content_hash(full_path),
                    extracted_at=now,
                    size=stat.st_size,
                )
            except (OSError, ValueError):
                continue
        self._save_cache()

    def remove_from_cache(self, file_paths: list[str]) -> None:
        """Remove deleted files from cache."""
        for p in file_paths:
            self._cache.pop(p, None)
        self._save_cache()

    def stats(self) -> dict:
        return {
            "n_cached": len(self._cache),
            "cache_file": str(self.cache_path),
        }


def build_importer_index_from_graph(graph: dict[str, Any]) -> dict[str, list[str]]:
    """Build importer_index from a graph's structural edges.

    Inverts the direction of imports_from/calls/inherits edges:
    if file A imports file B, the result maps B -> [A].

    The importer_index is the reverse-edge traversal map needed by
    get_changed_with_dependents(). It answers: "if file X changed,
    which files need re-extraction because they import/call/inherit
    from X?"
    """
    index: dict[str, list[str]] = {}

    # Build file_id -> source_file mapping
    file_nodes = [n for n in graph.get("nodes", []) if n.get("file_type") == "code"]
    file_by_id: dict[str, str] = {}
    for n in file_nodes:
        nid = n.get("id", "")
        sf = n.get("source_file", "")
        if nid == _slug(sf):  # file node id matches slug of its own path
            file_by_id[nid] = sf
        elif sf:
            file_by_id[nid] = sf

    # Invert structural edges: for each edge where target is in file B,
    # register the source's file as an importer of B
    reverse_relations = {"imports_from", "calls", "inherits", "contains"}
    # rationale_for (rationale→symbol) and describes (doc→code) are NOT
    # reversed — their direction is annotation→target, not dependency.
    for edge in graph.get("links", []):
        rel = edge.get("relation", "")
        if rel not in reverse_relations:
            continue
        target = edge.get("target", "")
        source = edge.get("source", "")
        # Find the file that owns target
        target_file = file_by_id.get(target, "")
        source_file = file_by_id.get(source, "")
        if target_file and source_file and target_file != source_file:
            if target_file not in index:
                index[target_file] = []
            if source_file not in index[target_file]:
                index[target_file].append(source_file)

    return index


def _slug(text: str) -> str:
    """Stable id fragment: collapse non-alphanumerics to single underscores."""
    import re

    slug_re = re.compile(r"[^a-zA-Z0-9]+")
    return slug_re.sub("_", text).strip("_").lower()


def save_importer_index(project_path: str | Path, index: dict[str, list[str]]) -> bool:
    """Persist importer_index to .neuralmind/ for subsequent builds.

    Returns False on any error (fail-open — never raises).
    """
    try:
        file_path = Path(project_path) / IMPORTER_INDEX_FILE
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def load_importer_index(project_path: str | Path) -> dict[str, list[str]]:
    """Load importer_index from .neuralmind/.

    Returns empty dict when the file doesn't exist, is unreadable, or
    contains malformed JSON (fail-open).
    """
    try:
        file_path = Path(project_path) / IMPORTER_INDEX_FILE
        if not file_path.exists():
            return {}
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        # Validate: every value must be a list of strings
        return {k: v for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}
