"""neuralmind_config.py — project-level ``.neuralmind.yaml`` config loader.

Reads the optional ``.neuralmind.yaml`` (or ``.neuralmind.yml``) file at a
project root and exposes the build-time knobs NeuralMind honors:

    mode: auto        # (default) detect prose vs code from the file tree
    mode: prose       # force heading-aware prose chunking
    mode: code        # force tree-sitter code extraction
    include:          # (optional) glob allowlist on relative paths (fnmatch)
      - "src/**"
    exclude:          # (optional) glob denylist, applied after include
      - "**/generated/**"

Example:
    >>> from pathlib import Path
    >>> from neuralmind.neuralmind_config import NeuralmindConfig
    >>> cfg = NeuralmindConfig.load(Path("/some/project"))
    >>> cfg.mode
    'auto'

Used by:
    - ``neuralmind.graphgen`` — builtin graph build (tree-sitter / prose pass)
    - ``neuralmind.core``     — NeuralMind.build() project-kind resolution

Missing files, unreadable YAML, and unknown values all degrade to the
defaults, so a project without a config file behaves exactly as before.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

# Config filenames probed at the project root, in priority order.
_CONFIG_FILENAMES = (".neuralmind.yaml", ".neuralmind.yml")

# Valid values for ``mode``. Anything else falls back to "auto".
_VALID_MODES = frozenset({"auto", "prose", "code"})

# Tolerant single-key scan used when PyYAML is unavailable or fails:
# matches a top-level ``mode: value`` line, ignoring quotes and comments.
_MODE_LINE_RE = re.compile(r"^mode:\s*['\"]?([^'\"#\s]+)['\"]?\s*(?:#.*)?$", re.MULTILINE)


@dataclass(frozen=True)
class NeuralmindConfig:
    """Parsed ``.neuralmind.yaml`` for one project.

    Attributes:
        mode: Project-kind override — ``"auto"`` (detect), ``"prose"``,
            or ``"code"``. Unknown or missing values normalize to ``"auto"``.
        include: Glob allowlist (POSIX-style relative paths). Empty means
            "everything the walker yields".
        exclude: Glob denylist applied after ``include``.
    """

    mode: str = "auto"
    include: tuple[str, ...] = field(default_factory=tuple)
    exclude: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def load(cls, project_path: str | Path) -> NeuralmindConfig:
        """Load the config for ``project_path``, falling back to defaults.

        Probes ``.neuralmind.yaml`` then ``.neuralmind.yml`` at the project
        root. Parsing prefers PyYAML; if it is unavailable or the document
        fails to parse, a stdlib regex scans the top-level ``mode:`` line.
        Any remaining failure yields the default ``NeuralmindConfig()``.
        """
        root = Path(project_path)
        for name in _CONFIG_FILENAMES:
            path = root / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = _parse_yaml(text) if name.endswith((".yaml", ".yml")) else None
            if parsed is not None:
                return cls(
                    mode=_normalize_mode(parsed.get("mode")),
                    include=_normalize_globs(parsed.get("include")),
                    exclude=_normalize_globs(parsed.get("exclude")),
                )
            # PyYAML missing or the document won't parse: salvage just the
            # ``mode:`` line — globs without a real parser invite surprises.
            match = _MODE_LINE_RE.search(text)
            return cls(mode=_normalize_mode(match.group(1) if match else None))
        return cls()

    def apply_globs(self, root: str | Path, files: list[Path]) -> list[Path]:
        """Filter ``files`` (paths under ``root``) through include/exclude.

        Matching runs against POSIX-style paths relative to ``root``. With no
        globs configured the list is returned unchanged (fast path). A file
        that cannot be expressed relative to ``root`` is kept (conservative).
        """
        if not self.include and not self.exclude:
            return files
        root_path = Path(root)
        kept: list[Path] = []
        for f in files:
            try:
                rel = f.relative_to(root_path).as_posix()
            except ValueError:
                kept.append(f)
                continue
            if self.include and not any(fnmatch(rel, pat) for pat in self.include):
                continue
            if self.exclude and any(fnmatch(rel, pat) for pat in self.exclude):
                continue
            kept.append(f)
        return kept


def _parse_yaml(text: str) -> dict[str, Any] | None:
    """Parse the config document via PyYAML, or None on any failure."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        parsed = yaml.safe_load(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_mode(raw: Any) -> str:
    """Coerce a raw mode value to one of ``_VALID_MODES`` (default ``auto``)."""
    if raw is not None and str(raw).strip().lower() in _VALID_MODES:
        return str(raw).strip().lower()
    return "auto"


def _normalize_globs(raw: Any) -> tuple[str, ...]:
    """Coerce a raw include/exclude value to a tuple of non-empty strings."""
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in raw if str(item).strip())
