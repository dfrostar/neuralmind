"""Project registry for multi-project operator mode.

Stores known project paths and per-scope preferences in
``~/.config/neuralmind/projects.json``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_PATH = Path.home() / ".config" / "neuralmind" / "projects.json"


def _resolve_registry_path() -> Path:
    env_dir = os.environ.get("NEURALMIND_CONFIG_DIR")
    if env_dir:
        return Path(env_dir) / "projects.json"
    return DEFAULT_REGISTRY_PATH


class ProjectRegistry:
    """Manage known projects for ``neuralmind build-all``."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _resolve_registry_path()
        self._projects: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._projects = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._projects = data
        except (OSError, ValueError):
            self._projects = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._projects, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def add_project(self, path: str, scopes: list[str] | None = None) -> None:
        """Add or update a project in the registry."""
        abs_path = str(Path(path).resolve())
        scopes = scopes or ["code", "content", "docs"]
        # Remove existing entry for this path
        self._projects = [p for p in self._projects if p["path"] != abs_path]
        self._projects.append({"path": abs_path, "scopes": scopes})
        self._save()

    def remove_project(self, path: str) -> None:
        """Remove a project from the registry."""
        abs_path = str(Path(path).resolve())
        self._projects = [p for p in self._projects if p["path"] != abs_path]
        self._save()

    def list_projects(self) -> list[dict[str, Any]]:
        """Return all registered projects."""
        return list(self._projects)

    def get_project(self, path: str) -> dict[str, Any] | None:
        """Get a specific project's config."""
        abs_path = str(Path(path).resolve())
        for p in self._projects:
            if p["path"] == abs_path:
                return p
        return None


# Module-level convenience
REGISTRY_PATH = DEFAULT_REGISTRY_PATH
