# Build-All Operator Mode + `--scope` Flag Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** One command rebuilds every project with guaranteed per-scope isolation, so an operator managing 5+ repos never runs `neuralmind build` by hand.

**Architecture:** A project registry (`~/.config/neuralmind/projects.json`) stores known project paths and per-project scope preferences. A new `build-all` CLI command iterates them, spawning a build per project with the correct scope filter. The `--scope` flag filters nodes at embed time (code-only, content-only, docs-only), with separate index files per scope to prevent collisions.

**Tech Stack:** Python 3.12, turbovec (unchanged), SQLite (unchanged), argparse (unchanged), `~/.config/neuralmind/projects.json` (new).

---

## Current State

- `embed_nodes()` iterates `self.nodes` (the full graph) with no filtering
- Index path is always `<db>/index.tvim` regardless of what's being indexed
- No central registry of projects — operator must manually `cd` into each repo
- cmmc20 graph.json has `file_type` ∈ {`code`, `document`, `rationale`} — perfect for scope filtering
- `graphgen.py` already supports incremental extraction; `embed_nodes()` already supports incremental embedding via `content_hash`

---

## Tasks

### Task 1: Project registry module

**Objective:** Create a module to load/save known projects from `~/.config/neuralmind/projects.json`

**Files:**
- Create: `neuralmind/project_registry.py`
- Test: `tests/test_project_registry.py`

**Step 1: Write failing test**

```python
# tests/test_project_registry.py
import json
import tempfile
from pathlib import Path
from neuralmind.project_registry import ProjectRegistry, REGISTRY_PATH

def test_default_registry_path():
    assert REGISTRY_PATH == Path.home() / ".config" / "neuralmind" / "projects.json"

def test_empty_registry_on_first_use(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    assert reg.list_projects() == []

def test_add_and_list_project(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    reg.add_project("/home/user/cmmc20", scopes=["code", "content"])
    reg.add_project("/home/user/neuralmind", scopes=["code"])
    projects = reg.list_projects()
    assert len(projects) == 2
    assert projects[0]["path"] == "/home/user/cmmc20"
    assert projects[0]["scopes"] == ["code", "content"]

def test_remove_project(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    reg.add_project("/home/user/cmmc20", scopes=["code"])
    reg.remove_project("/home/user/cmmc20")
    assert reg.list_projects() == []

def test_persist_to_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    reg.add_project("/home/user/cmmc20", scopes=["code", "content"])
    
    # Reload from disk
    reg2 = ProjectRegistry()
    projects = reg2.list_projects()
    assert len(projects) == 1
    assert projects[0]["path"] == "/home/user/cmmc20"

def test_get_project(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    reg.add_project("/home/user/cmmc20", scopes=["code", "content"])
    proj = reg.get_project("/home/user/cmmc20")
    assert proj is not None
    assert proj["scopes"] == ["code", "content"]
    assert reg.get_project("/nonexistent") is None
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_project_registry.py -v`
Expected: FAIL — `No module named 'neuralmind.project_registry'`

**Step 3: Write minimal implementation**

```python
# neuralmind/project_registry.py
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
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_project_registry.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add tests/test_project_registry.py neuralmind/project_registry.py
git commit -m "feat: add project registry for multi-project operator mode"
```

---

### Task 2: Scope filtering in TurboVecEmbedder

**Objective:** Add a `--scope` filter so `embed_nodes()` only indexes code, content, or docs

**Files:**
- Modify: `neuralmind/turbovec_backend.py` (`TurboVecEmbedder` class)
- Test: `tests/test_turbovec_backend.py`

**Step 1: Write failing test**

```python
# Add to tests/test_turbovec_backend.py

def test_embed_nodes_scope_code_only(self) -> None:
    """With scope='code', document/rationale nodes are skipped."""
    be = self._backend()
    # Add a document node to the graph
    for node in be.nodes:
        if node.get("file_type") == "document":
            break
    else:
        # Inject a synthetic document node
        be.nodes.append({
            "id": "doc_1",
            "name": "readme",
            "label": "readme",
            "file_type": "document",
            "source_file": "README.md",
            "description": "A test doc",
            "community": 0,
        })
    stats = be.embed_nodes(scope="code")
    # Document node should not be embedded
    results = be.search("test doc", n=10)
    doc_results = [r for r in results if r["id"] == "doc_1"]
    assert len(doc_results) == 0

def test_embed_nodes_scope_content_only(self) -> None:
    """With scope='content', code nodes are skipped."""
    be = self._backend()
    stats = be.embed_nodes(scope="content")
    # Code nodes should not be embedded
    results = be.search("authenticate_user", n=10)
    code_results = [r for r in results if r["metadata"].get("file_type") == "code"]
    assert len(code_results) == 0

def test_embed_nodes_scope_all_explicit(self) -> None:
    """scope='all' is the default (no filtering)."""
    be = self._backend()
    stats_all = be.embed_nodes(scope="all")
    be.close()
    be2 = self._backend()
    stats_default = be2.embed_nodes()
    assert stats_all["added"] == stats_default["added"]
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_turbovec_backend.py::test_embed_nodes_scope_code_only -v`
Expected: FAIL — `TypeError: embed_nodes() got an unexpected keyword argument 'scope'`

**Step 3: Write minimal implementation**

Add to `neuralmind/turbovec_backend.py`:

```python
# Scope definitions: maps scope name -> set of file_type values to INCLUDE
SCOPE_FILTERS: dict[str, frozenset[str]] = {
    "code": frozenset({"code", "function", "class", "method", "module"}),
    "content": frozenset({"document", "rationale", "content", "policy", "sop", "decision", "meeting_note"}),
    "docs": frozenset({"document", "rationale"}),
    "all": frozenset(),  # empty = no filtering
}

# File-type extention-based fallback for when file_type is generic
SCOPE_EXTENSIONS: dict[str, frozenset[str]] = {
    "code": frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cs", ".c", ".cpp", ".h", ".rb", ".php", ".swift", ".kt"}),
    "content": frozenset({".md", ".mdx", ".txt", ".rst", ".docx", ".pdf"}),
    "docs": frozenset({".md", ".mdx", ".txt", ".rst"}),
    "all": frozenset(),
}
```

Modify `embed_nodes()` signature:

```python
def embed_nodes(self, force: bool = False, scope: str = "all") -> dict[str, int]:
    """Embed all nodes, optionally filtered by scope.

    scope: 'code' | 'content' | 'docs' | 'all'
    """
    if scope not in SCOPE_FILTERS:
        raise ValueError(f"Unknown scope '{scope}'. Valid: {list(SCOPE_FILTERS)}")
    ...
    # Inside the loop, after computing node_id and before the existing hash check:
    file_type = str(node.get("file_type", ""))
    source_file = str(node.get("source_file", ""))
    ext = Path(source_file).suffix.lower() if source_file else ""
    
    allowed_types = SCOPE_FILTERS.get(scope, frozenset())
    allowed_exts = SCOPE_EXTENSIONS.get(scope, frozenset())
    
    if scope != "all":
        if file_type and file_type not in allowed_types:
            # Try extension-based fallback
            if not (ext and ext in allowed_exts):
                continue
        elif not file_type and ext:
            if ext not in allowed_exts:
                continue
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_turbovec_backend.py -v -k "scope"`
Expected: 3 passed

**Step 5: Commit**

```bash
git add neuralmind/turbovec_backend.py tests/test_turbovec_backend.py
git commit -m "feat: add scope filtering (code/content/docs) to embed_nodes"
```

---

### Task 3: Per-scope index file naming

**Objective:** Separate index files per scope so code/content/docs indexes don't collide

**Files:**
- Modify: `neuralmind/turbovec_backend.py` (`_index_path` property)

**Step 1: Write failing test**

```python
def test_scope_creates_separate_index_files(self) -> None:
    """Different scopes write to different .tvim files."""
    be = self._backend()
    # Build code scope
    be.embed_nodes(scope="code")
    code_index = be._index_path
    be.close()
    
    be2 = self._backend()
    be2.embed_nodes(scope="content")
    content_index = be2._index_path
    be2.close()
    
    assert code_index != content_index
    assert code_index.exists()
    assert content_index.exists()
    assert "code" in code_index.name
    assert "content" in content_index.name
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_turbovec_backend.py::test_scope_creates_separate_index_files -v`
Expected: FAIL — index paths are identical

**Step 3: Write minimal implementation**

Modify `TurboVecEmbedder.__init__()` to accept a `scope` parameter:

```python
def __init__(
    self,
    project_path: str | Path,
    *,
    db_path: str | None = None,
    bit_width: int = _DEFAULT_BIT_WIDTH,
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
    scope: str = "all",
):
    ...
    self._scope = scope
    if scope != "all":
        self._index_path = self._dir / f"index.{scope}.tvim"
    else:
        self._index_path = self._dir / "index.tvim"
```

Also modify `_rebuild_index_from_store` and other places that hard-code `self._index_path.name` to use `self._index_path` directly.

**Step 4: Run test to verify pass**

Run: `pytest tests/test_turbovec_backend.py -v -k "scope"`
Expected: all scope tests pass

**Step 5: Commit**

```bash
git add neuralmind/turbovec_backend.py tests/test_turbovec_backend.py
git commit -m "feat: per-scope index file naming (index.code.tvim, index.content.tvim)"
```

---

### Task 4: Wire `--scope` flag into CLI

**Objective:** Add `--scope` argument to `cmd_build` and pass it through to `embed_nodes()`

**Files:**
- Modify: `neuralmind/cli.py` (`cmd_build`, argument parser)
- Test: `tests/test_cli.py`

**Step 1: Write failing test**

```python
# tests/test_cli.py
def test_build_with_scope_flag(tmp_path):
    """neuralmind build --scope=code should only embed code nodes."""
    from neuralmind.cli import cmd_build
    from unittest.mock import patch, MagicMock
    
    # Setup minimal project
    graph_dir = tmp_path / "graphify-out"
    graph_dir.mkdir()
    (graph_dir / "graph.json").write_text(json.dumps({
        "nodes": [
            {"id": "n1", "name": "func", "file_type": "code", "source_file": "a.py"},
            {"id": "n2", "name": "doc", "file_type": "document", "source_file": "a.md"},
        ],
        "links": []
    }))
    
    args = MagicMock()
    args.project_path = str(tmp_path)
    args.force = False
    args.scope = "code"
    args.bootstrap = None
    args.redact_secrets = False
    args.dry_run = False
    args.json = False
    
    with patch("neuralmind.cli.NeuralMind") as mock_mind:
        mock_instance = MagicMock()
        mock_instance.build.return_value = {"success": True}
        mock_mind.return_value = mock_instance
        
        cmd_build(args)
        
        mock_instance.build.assert_called_once_with(force=False, scope="code")
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_cli.py::test_build_with_scope_flag -v`
Expected: FAIL — `ArgumentError: unexpected argument 'scope'`

**Step 3: Write minimal implementation**

In `cli.py`:

1. Add to argument parser:
```python
build_p.add_argument(
    "--scope",
    choices=["all", "code", "content", "docs"],
    default="all",
    help="Index scope: code (source files), content (docs/chapters), docs (markdown only), all (default)",
)
```

2. Modify `cmd_build` to pass scope:
```python
result = mind.build(force=force, scope=args.scope)
```

3. Modify `NeuralMind.build()` signature to accept scope and pass to embedder.

**Step 4: Run test to verify pass**

Run: `pytest tests/test_cli.py -v -k "scope"`
Expected: pass

**Step 5: Commit**

```bash
git add neuralmind/cli.py neuralmind/core.py tests/test_cli.py
git commit -m "feat: add --scope flag to neuralmind build CLI"
```

---

### Task 5: `build-all` command

**Objective:** New `neuralmind build-all` command that iterates registered projects

**Files:**
- Modify: `neuralmind/cli.py` (new `cmd_build_all`, argument parser)
- Test: `tests/test_cli.py`

**Step 1: Write failing test**

```python
def test_build_all_command(tmp_path, monkeypatch):
    """build-all iterates registered projects."""
    from neuralmind.cli import cmd_build_all
    from neuralmind.project_registry import ProjectRegistry
    from unittest.mock import patch, MagicMock
    
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    reg.add_project("/home/user/cmmc20", scopes=["code", "content"])
    reg.add_project("/home/user/neuralmind", scopes=["code"])
    
    args = MagicMock()
    args.projects = None  # use registry
    
    with patch("neuralmind.cli.cmd_build") as mock_build:
        mock_build.return_value = None
        cmd_build_all(args)
        
        assert mock_build.call_count == 2
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_cli.py::test_build_all_command -v`
Expected: FAIL — `AttributeError: module has no attribute 'cmd_build_all'`

**Step 3: Write minimal implementation**

```python
def cmd_build_all(args):
    """Build indexes for all registered projects."""
    from neuralmind.project_registry import ProjectRegistry
    
    reg = ProjectRegistry()
    projects = reg.list_projects()
    
    if not projects:
        print("No projects registered. Add one with: neuralmind project add <path> [--scope=code,content]")
        return
    
    print(f"Building {len(projects)} projects...")
    print()
    
    summary = []
    for proj in projects:
        path = proj["path"]
        scopes = proj.get("scopes", ["all"])
        print(f"📁 {path}")
        for scope in scopes:
            print(f"   Scope: {scope}...", end=" ", flush=True)
            # Construct args for cmd_build
            build_args = argparse.Namespace(
                project_path=path,
                force=False,
                scope=scope,
                bootstrap=None,
                redact_secrets=False,
                dry_run=False,
                json=False,
                quiet=False,
            )
            try:
                cmd_build(build_args)
                print("done")
                summary.append(f"✓ {path} ({scope})")
            except SystemExit as e:
                print(f"failed (exit {e.code})")
                summary.append(f"✗ {path} ({scope}) — exit {e.code}")
        print()
    
    print("=" * 60)
    print("Summary:")
    for line in summary:
        print(f"  {line}")
```

Add to argument parser:
```python
build_all_p = subparsers.add_parser("build-all", help="Build all registered projects")
build_all_p.add_argument("--projects", help="Comma-separated list of project paths (optional, uses registry by default)")
build_all_p.add_argument("--scope", choices=["all", "code", "content", "docs"], default="all", help="Override scope for all projects")
build_all_p.set_defaults(func=cmd_build_all)
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_cli.py -v -k "build_all"`
Expected: pass

**Step 5: Commit**

```bash
git add neuralmind/cli.py tests/test_cli.py
git commit -m "feat: add build-all command for multi-project operator mode"
```

---

### Task 6: `project` management CLI subcommand

**Objective:** `neuralmind project add/remove/list` for managing the registry

**Files:**
- Modify: `neuralmind/cli.py` (new subparser)
- Test: `tests/test_cli.py`

**Step 1: Write failing test**

```python
def test_project_add_command(tmp_path, monkeypatch):
    """neuralmind project add <path> adds to registry."""
    from neuralmind.cli import cmd_project
    from neuralmind.project_registry import ProjectRegistry
    
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    
    import argparse
    args = argparse.Namespace(
        project_action="add",
        path="/home/user/cmmc20",
        scopes=["code", "content"],
    )
    cmd_project(args)
    
    reg = ProjectRegistry()
    projects = reg.list_projects()
    assert len(projects) == 1
    assert projects[0]["path"] == "/home/user/cmmc20"
    assert projects[0]["scopes"] == ["code", "content"]

def test_project_list_command(tmp_path, monkeypatch, capsys):
    """neuralmind project list prints registered projects."""
    from neuralmind.cli import cmd_project
    from neuralmind.project_registry import ProjectRegistry
    
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    reg.add_project("/home/user/cmmc20", scopes=["code"])
    
    args = argparse.Namespace(project_action="list", path=None, scopes=None)
    cmd_project(args)
    
    captured = capsys.readouterr()
    assert "cmmc20" in captured.out
    assert "code" in captured.out
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_cli.py::test_project_add_command -v`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
def cmd_project(args):
    """Manage registered projects."""
    from neuralmind.project_registry import ProjectRegistry
    
    reg = ProjectRegistry()
    action = args.project_action
    
    if action == "add":
        path = args.path
        scopes = args.scopes or ["all"]
        if not Path(path).exists():
            print(f"Error: path does not exist: {path}")
            sys.exit(1)
        reg.add_project(path, scopes=scopes)
        print(f"Added: {path} (scopes: {', '.join(scopes)})")
    
    elif action == "remove":
        path = args.path
        reg.remove_project(path)
        print(f"Removed: {path}")
    
    elif action == "list":
        projects = reg.list_projects()
        if not projects:
            print("No projects registered.")
            print("Add one with: neuralmind project add <path> [--scope=code,content,docs]")
            return
        print(f"Registered projects ({len(projects)}):")
        for p in projects:
            print(f"  {p['path']}  scopes={', '.join(p['scopes'])}")
    
    else:
        print(f"Unknown project action: {action}")
        sys.exit(1)
```

Add to argument parser:
```python
project_p = subparsers.add_parser("project", help="Manage registered projects")
project_sub = project_p.add_subparsers(dest="project_action")
project_add = project_sub.add_parser("add", help="Add a project to the registry")
project_add.add_argument("path", help="Project directory path")
project_add.add_argument("--scope", default="all", help="Comma-separated scopes (code,content,docs)")
project_sub.add_parser("list", help="List registered projects")
project_remove = project_sub.add_parser("remove", help="Remove a project from the registry")
project_remove.add_argument("path", help="Project directory path")
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_cli.py -v -k "project"`
Expected: pass

**Step 5: Commit**

```bash
git add neuralmind/cli.py tests/test_cli.py
git commit -m "feat: add neuralmind project add/remove/list CLI"
```

---

### Task 7: End-to-end validation on cmmc20

**Objective:** Run `neuralmind build-all --scope=code` on cmmc20 and verify isolation

**Files:** none (validation only)

**Step 1: Register cmmc20**

```bash
neuralmind project add /home/dtfrost/cmmc20 --scope=code,content
```

**Step 2: Run build-all**

```bash
cd /home/dtfrost/cmmc20 && neuralmind build-all --scope=code
```

Expected:
- ProgressReporter shows milestones
- All 6767 nodes processed (mostly skipped if unchanged)
- Summary reports success

**Step 3: Run with content scope**

```bash
cd /home/dtfrost/cmmc20 && neuralmind build --scope=content
```

Expected: Only markdown/document nodes embedded, separate `index.content.tvim` file created.

**Step 4: Verify isolation**

```bash
ls graphify-out/neuralmind_turbovec/index*.tvim
# Should show: index.code.tvim, index.content.tvim
```

**Step 5: Commit**

```bash
git add -A
git commit -m "fix: address review feedback from build-all implementation"
```

---

## Files Changed

| File | Change |
|------|--------|
| `neuralmind/project_registry.py` | NEW — project registry module |
| `neuralmind/turbovec_backend.py` | Add scope filtering + per-scope index naming |
| `neuralmind/core.py` | Pass scope through to embedder |
| `neuralmind/cli.py` | Add `--scope` flag, `build-all` cmd, `project` subcommand |
| `tests/test_project_registry.py` | NEW — registry tests |
| `tests/test_turbovec_backend.py` | Scope filtering tests |
| `tests/test_cli.py` | `--scope`, `build-all`, `project` tests |

---

## Risks & Tradeoffs

- **Index disk usage**: Per-scope indexes multiply disk by ~2-3x. Mitigated by 4-bit quantization (already default).
- **Scope detection**: Falls back to file extension when `file_type` is generic. May misclassify edge cases.
- **Concurrent `build-all`**: Currently sequential. Could be parallelized later with `ProcessPoolExecutor`.
- **Breaking change**: `embed_nodes()` signature changes (`scope` param). Only breaks direct callers — internal API.

---

## Open Questions

1. Should `build-all` support `--parallel` for concurrent builds?
2. Should `project add` auto-detect scopes from project structure (e.g., `chapters/` dir → content scope)?
3. How to handle a project in the registry whose path no longer exists on disk?

---

**Plan complete. Ready to execute task-by-task.**
