"""
namespaces.py — Resolve the active memory namespace (PRD 4).

The synapse store is git-agnostic: it writes to whatever namespace string
it was constructed with. This module decides *which* namespace that
should be for a given project, in priority order:

1. ``NEURALMIND_NAMESPACE`` env var — explicit per-process override.
2. ``memory_namespace`` in ``neuralmind-backend.yaml`` (or ``.yml`` /
   ``.json``) — a project-pinned namespace.
3. The current git branch — ``branch:<name>`` when the repo is on a
   non-default branch, so feature-branch learning stays isolated.
4. ``personal`` — not a git repo, detached HEAD, on the default branch,
   or git is unavailable. Memory behaves exactly as it did before
   namespaces existed.

Stdlib-only on purpose: the Claude Code hooks resolve a namespace on
every lifecycle event without importing the embedding stack (or even
PyYAML — the config probe falls back to a line scan when yaml isn't
importable). Branch detection is best-effort with a short timeout; a
weird git state must never fail a memory write.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from .synapses import BRANCH_NAMESPACE_PREFIX, DEFAULT_NAMESPACE, normalize_namespace

ENV_NAMESPACE = "NEURALMIND_NAMESPACE"
CONFIG_KEY = "memory_namespace"
GIT_TIMEOUT_SECONDS = 3

# Used only when `git symbolic-ref refs/remotes/origin/HEAD` can't name the
# default branch (no remote, fresh clone): branches with these names map to
# ``personal`` rather than ``branch:<name>``.
DEFAULT_BRANCH_FALLBACKS = frozenset({"main", "master"})

_CONFIG_FILENAMES = (
    "neuralmind-backend.yaml",
    "neuralmind-backend.yml",
    "neuralmind-backend.json",
)

# Matches a top-level `memory_namespace: value` line in YAML without needing
# PyYAML — quotes and trailing comments tolerated.
_YAML_KEY_RE = re.compile(
    r"^memory_namespace:\s*['\"]?([^'\"#\s]+)['\"]?\s*(?:#.*)?$", re.MULTILINE
)


def detect_git_branch(project_path: str | Path) -> str | None:
    """Best-effort current branch name, or None.

    Mirrors the CLI's git-subprocess pattern (`_maybe_detect_repo_url`):
    short timeout, stderr swallowed, any failure → None. A detached HEAD
    reports the literal ``HEAD`` and is treated as no branch.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(project_path), "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except Exception:
        return None
    branch = out.decode().strip()
    if not branch or branch == "HEAD":
        return None
    return branch


def detect_default_branch(project_path: str | Path) -> str | None:
    """The repo's default branch (from ``origin/HEAD``), or None."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(project_path), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except Exception:
        return None
    ref = out.decode().strip()  # e.g. "origin/main"
    if not ref:
        return None
    return ref.rsplit("/", 1)[-1] or None


def namespace_for_branch(branch: str) -> str:
    return f"{BRANCH_NAMESPACE_PREFIX}{branch}"


def config_namespace(project_path: str | Path, config: dict | None = None) -> str | None:
    """The project-pinned ``memory_namespace``, or None.

    Prefers an already-loaded backend config dict (the path NeuralMind core
    takes); otherwise probes the backend config files directly so the
    stdlib-only hook path works without PyYAML.
    """
    if isinstance(config, dict):
        value = config.get(CONFIG_KEY)
        if value:
            return str(value).strip() or None
    for name in _CONFIG_FILENAMES:
        path = Path(project_path) / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if name.endswith(".json"):
            try:
                parsed = json.loads(text)
            except ValueError:
                continue
            value = parsed.get(CONFIG_KEY) if isinstance(parsed, dict) else None
            if value:
                return str(value).strip() or None
            continue
        try:
            import yaml

            parsed = yaml.safe_load(text) or {}
            value = parsed.get(CONFIG_KEY) if isinstance(parsed, dict) else None
        except ImportError:
            match = _YAML_KEY_RE.search(text)
            value = match.group(1) if match else None
        except Exception:
            value = None
        if value:
            return str(value).strip() or None
    return None


def resolve_namespace(
    project_path: str | Path,
    config: dict | None = None,
    env: dict | None = None,
) -> str:
    """Resolve the active memory namespace for a project.

    Priority: env override → pinned config → ``branch:<name>`` on a
    non-default git branch → ``personal``. Never raises: an invalid
    override degrades to ``personal`` rather than blocking a write.
    """
    environ = os.environ if env is None else env
    override = (environ.get(ENV_NAMESPACE) or "").strip()
    if override:
        try:
            return normalize_namespace(override)
        except ValueError:
            pass
    pinned = config_namespace(project_path, config)
    if pinned:
        try:
            return normalize_namespace(pinned)
        except ValueError:
            pass
    branch = detect_git_branch(project_path)
    if branch:
        default = detect_default_branch(project_path)
        defaults = {default} if default else DEFAULT_BRANCH_FALLBACKS
        if branch not in defaults:
            try:
                return normalize_namespace(namespace_for_branch(branch))
            except ValueError:
                return DEFAULT_NAMESPACE
    return DEFAULT_NAMESPACE
