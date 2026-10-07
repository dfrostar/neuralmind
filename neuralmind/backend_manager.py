"""Backend factory and configuration loading for NeuralMind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .embedding_backend import EmbeddingBackend
from .in_memory_backend import InMemoryEmbeddingBackend

DEFAULT_BACKEND_CONFIG: dict[str, Any] = {
    # Hard-default to turbovec as of v0.46.0 — the ChromaDB-free path. "auto"
    # is accepted as an alias for turbovec for backward compatibility.
    # Selecting chroma/graph explicitly triggers a deprecation warning.
    "backend": "turbovec",
    "db_path": None,
    "hybrid_context": False,
    "security": {},
}

# The turbovec stack. All three must import for the turbovec backend to
# construct, so auto-detection gates on all of them. Base dependencies since
# v0.29.0 (previously the `[turbovec]` extra).
_TURBOVEC_DEPS = ("turbovec", "onnxruntime", "tokenizers")


def turbovec_available() -> bool:
    """True when the turbovec stack (turbovec + onnxruntime + tokenizers) is
    importable. These are base dependencies since v0.29.0, so this is normally
    True; it can be False only if a user force-uninstalled them."""
    import importlib.util

    return all(importlib.util.find_spec(mod) is not None for mod in _TURBOVEC_DEPS)


def resolve_backend(backend: str | None) -> str:
    """Resolve the ``auto`` default (or ``None``) to a concrete backend name.

    The shipped default is ``turbovec``: the ChromaDB-free path (base deps
    since v0.29.0). ``auto``, ``None``, and blanks are all accepted as aliases
    for turbovec for backward compatibility. ``graph`` / ``chroma`` /
    ``chromadb`` are deprecated and trigger a deprecation warning — they still
    work when the ``[chromadb]`` extra is installed.
    """
    # None, "", or a non-string (e.g. `backend: null` in YAML) all mean turbovec.
    if not isinstance(backend, str) or not backend.strip():
        return "turbovec"
    name = backend.strip().lower()
    if name == "auto":
        return "turbovec"
    if name in {"graph", "chroma", "chromadb"}:
        import warnings

        warnings.warn(
            f"the '{name}' backend (ChromaDB) is deprecated as of v0.46.0. "
            "Use the default turbovec backend (no config needed) or install "
            "`pip install neuralmind[chromadb]` if you need ChromaDB.",
            DeprecationWarning,
            stacklevel=2,
        )
        return name
    return name


# The backend names create_backend serves with TurboVecEmbedder.
TURBOVEC_BACKENDS = frozenset({"turbovec", "turboquant"})

_CONFIG_NAMES = ("neuralmind-backend.yaml", "neuralmind-backend.yml", "neuralmind-backend.json")


def backend_config_path(project_path: str | Path) -> Path | None:
    """The config file ``load_backend_config`` reads for this project, if any."""
    root = Path(project_path).resolve()
    for name in _CONFIG_NAMES:
        path = root / name
        if path.exists():
            return path
    return None


def read_backend_config_file(path: Path) -> dict[str, Any]:
    """Parse one config file. Raises on unreadable or malformed content."""
    with path.open(encoding="utf-8") as file:
        if path.suffix in {".yaml", ".yml"}:
            parsed = yaml.safe_load(file) or {}
        else:
            parsed = json.load(file) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"{path.name} must contain a mapping, not {type(parsed).__name__}")
    return parsed


def load_backend_config(project_path: str | Path) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    path = backend_config_path(project_path)
    if path is not None:
        try:
            loaded = read_backend_config_file(path)
        except Exception:
            loaded = {}

    config = DEFAULT_BACKEND_CONFIG.copy()
    config.update(loaded)
    return config


def project_backend(project_path: str | Path) -> str:
    """The backend a project's ``NeuralMind`` uses when no backend is passed.

    What ``neuralmind build`` and ``neuralmind doctor`` run with: the
    configured ``backend:``, resolved the same way ``BackendManager`` does.
    """
    return resolve_backend(load_backend_config(project_path).get("backend"))


def resolve_db_path(project_path: str | Path, db_path: str | Path | None) -> str | None:
    """A relative ``db_path`` names a directory in the project, not the CWD.

    ``db_path: vecdb`` in ``neuralmind-backend.yaml`` must mean the same
    directory whichever directory a command runs from. Absolute paths, ``~``
    paths and the in-memory backend's ``:memory:`` are left as they are.
    """
    if db_path is None:
        return None
    if str(db_path) == ":memory:":
        return ":memory:"
    path = Path(db_path).expanduser()
    if not path.is_absolute():
        path = Path(project_path).resolve() / path
    return str(path)


def create_backend(
    backend: str,
    project_path: str,
    db_path: str | None = None,
    scope: str = "all",
) -> EmbeddingBackend:
    normalized = resolve_backend(backend)
    if normalized in {"graph", "chroma", "chromadb"}:
        # Lazy import: keeps ChromaDB (a heavy tree) off the import path unless
        # the chroma backend is actually selected, so the turbovec backend can
        # run without it. See issue #204. As of v0.29.0 ChromaDB is an opt-in
        # extra, so a missing import means the user selected the chroma backend
        # without installing it — surface an actionable hint, not a raw
        # ModuleNotFoundError from deep in the import.
        try:
            from .embedder import GraphEmbedder
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.split(".")[0] == "chromadb":
                raise ModuleNotFoundError(
                    "the 'graph' (ChromaDB) backend needs ChromaDB, which is no "
                    "longer installed by default. Install it with "
                    '`pip install "neuralmind[chromadb]"`, or use the default '
                    "ChromaDB-free turbovec backend (remove `backend: graph` "
                    "from neuralmind-backend.yaml).",
                    name=exc.name,
                ) from exc
            raise

        return GraphEmbedder(project_path, db_path=db_path)
    if normalized in {"in_memory", "inmemory", "memory"}:
        return InMemoryEmbeddingBackend(project_path, db_path=db_path)
    if normalized in TURBOVEC_BACKENDS:
        # Lazy import, mirroring the chroma branch — keeps construction symmetric
        # and import-light. turbovec is the default backend since v0.29.0.
        from .turbovec_backend import TurboVecEmbedder

        return TurboVecEmbedder(project_path, db_path=db_path, scope=scope)
    raise ValueError(f"Unsupported backend: {backend}")


def _require_storage(project_path: str, location: str | Path | None) -> None:
    """Apply security.require_encrypted_storage to the vector index's location.

    Checked before the backend is created (a configured db_path may be on
    another volume) and again after, against the path it actually chose, which
    may sit behind a symlink. The backend creates an empty directory at most;
    nothing is indexed until build. Imported lazily: storage_guard reads the
    security config through this module.
    """
    from .storage_guard import enforce_storage_policy

    if location == ":memory:":  # the in-memory backend writes no file
        location = None
    enforce_storage_policy(project_path, location)


class BackendManager:
    """Coordinates backend selection and runtime backend switching."""

    def __init__(
        self,
        project_path: str,
        db_path: str | None = None,
        backend: str | None = None,
        scope: str = "all",
    ):
        self.project_path = str(Path(project_path).resolve())
        self.config = load_backend_config(self.project_path)
        # Resolve "auto" (and None) to a concrete backend up front so
        # backend_name reports the real backend ("turbovec"/"graph"), not "auto".
        selected_backend = resolve_backend(backend or self.config.get("backend"))
        selected_db_path = resolve_db_path(self.project_path, db_path or self.config.get("db_path"))
        self.backend_name = selected_backend
        _require_storage(self.project_path, selected_db_path)
        self.backend = create_backend(
            selected_backend, self.project_path, selected_db_path, scope=scope
        )
        _require_storage(self.project_path, getattr(self.backend, "db_path", None))

    def switch_backend(self, backend: str, db_path: str | None = None) -> EmbeddingBackend:
        if hasattr(self.backend, "close"):
            try:
                self.backend.close()
            except Exception:
                pass
        selected_db_path = resolve_db_path(self.project_path, db_path or self.config.get("db_path"))
        resolved = resolve_backend(backend)
        _require_storage(self.project_path, selected_db_path)
        self.backend_name = resolved
        self.backend = create_backend(resolved, self.project_path, selected_db_path)
        _require_storage(self.project_path, getattr(self.backend, "db_path", None))
        return self.backend
