"""Python children NeuralMind starts don't import from the working directory.

``python -c`` and ``python -m`` put the working directory first on
``sys.path``. ``neuralmind build .`` inside click's ``src/click/``, which has a
``types.py``, died with ``onnx_embed failed``: the embedding child imported
click's ``types.py`` in place of the standard library's. Every child now goes
through ``neuralmind.child_python``: ``-P`` on Python 3.11+, an empty working
directory on 3.10. The ``safe_path`` fixture runs a test under both, by
switching ``HAS_SAFE_PATH`` off; ``-P`` itself only where it exists.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import neuralmind
from neuralmind import child_python

# Imports what the shadowing directory breaks, then checks it's off sys.path.
PROBE = (
    "import base64, importlib.util, json\n"
    "assert importlib.util.find_spec('cwd_probe') is None, 'working directory on sys.path'\n"
    "print('ok')\n"
)


@pytest.fixture(
    params=[
        pytest.param(
            True,
            id="dash-P",
            marks=pytest.mark.skipif(sys.version_info < (3, 11), reason="-P is new in 3.11"),
        ),
        pytest.param(False, id="empty-cwd"),
    ]
)
def safe_path(request, monkeypatch):
    monkeypatch.setattr(child_python, "HAS_SAFE_PATH", request.param)
    return request.param


@pytest.fixture
def shadowing_cwd(tmp_path, monkeypatch):
    """A working directory whose modules shadow the standard library's and fail.

    ``types.py`` and ``enum.py`` as in the report; ``base64.py`` because the
    embedding child imports it first, and an interpreter may have loaded
    ``types`` and ``enum`` at startup. ``cwd_probe.py`` shows whether the
    directory is on ``sys.path`` at all.
    """
    project = tmp_path / "project"
    project.mkdir()
    for name in ("types", "enum", "base64"):
        (project / f"{name}.py").write_text(
            f"raise ImportError('{name}.py came from the working directory')\n",
            encoding="utf-8",
        )
    (project / "cwd_probe.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(project)
    return project


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    with child_python.python_cwd() as cwd:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd,
            env=child_python.python_env(),
        )


def test_a_plain_child_imports_from_the_working_directory(shadowing_cwd):
    """The bug itself, so the tests below can't pass by accident."""
    done = subprocess.run(
        [sys.executable, "-c", PROBE], capture_output=True, text=True, timeout=120
    )
    assert done.returncode != 0
    assert "working directory" in done.stderr


def test_c_child_ignores_the_working_directory(shadowing_cwd, safe_path):
    done = _run(child_python.python_argv("-c", PROBE))
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


def test_m_child_ignores_the_working_directory_but_keeps_pythonpath(
    shadowing_cwd, tmp_path, monkeypatch, safe_path
):
    """``-m`` too: runpy imports ``types`` before the module runs. Unlike ``-I``,
    PYTHONPATH still counts; running a checkout's benchmark relies on it."""
    elsewhere = tmp_path / "on_pythonpath"
    elsewhere.mkdir()
    (elsewhere / "nm_probe_main.py").write_text(PROBE, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(elsewhere))
    done = _run(child_python.python_argv("-m", "nm_probe_main"))
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


def test_child_still_imports_neuralmind(shadowing_cwd, safe_path):
    """Found as installed (editable or wheel), not through the working directory."""
    done = _run(child_python.python_argv("-c", "import neuralmind.onnx_embedder"))
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize(
    "name",
    [
        "NEURALMIND_CONFIG_DIR",
        "NEURALMIND_DAEMON_HOME",
        "NEURALMIND_ONNX_MODEL_DIR",
        "NEURALMIND_RERANK_MODEL",
    ],
)
def test_relative_path_settings_still_resolve_in_the_child(
    shadowing_cwd, monkeypatch, safe_path, name
):
    """From 3.10's other working directory a relative setting would point
    elsewhere: a missed pre-seeded model is downloaded, a missed daemon home
    hides the daemon from the CLI that started it."""
    (shadowing_cwd / "configured").mkdir()
    monkeypatch.setenv(name, "configured")
    done = _run(
        child_python.python_argv("-c", f"import os; print(os.path.isdir(os.environ[{name!r}]))")
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "True"


class _ModelFreeEmbedder:
    """Has ``embed``, so ``_embed_matrix`` sends large inputs to child processes."""

    dim = 384

    def embed(self, texts):
        raise AssertionError("large inputs are embedded in child processes")

    __call__ = embed


def test_embedding_children_survive_a_shadowing_working_directory(
    shadowing_cwd, monkeypatch, safe_path
):
    """The reported failure, run against the real child: given no texts, it exits
    right after the imports that broke, so no model is needed."""
    np = pytest.importorskip("numpy")
    from neuralmind.turbovec_backend import TurboVecEmbedder

    backend = TurboVecEmbedder(str(shadowing_cwd), embed_fn=_ModelFreeEmbedder())
    real_run = subprocess.run
    children = []

    def run(argv, **kwargs):
        child = real_run(argv, **{**kwargs, "input": json.dumps({"texts": []})})
        children.append(child)
        n = len(json.loads(kwargs["input"])["texts"])
        data = base64.b64encode(np.zeros((n, 384), dtype=np.float32).tobytes()).decode("ascii")
        payload = json.dumps({"shape": [n, 384], "data": data})
        return subprocess.CompletedProcess(argv, child.returncode, payload, child.stderr)

    monkeypatch.setattr(subprocess, "run", run)
    texts = ["def convert(self, value, param, ctx): ..."] * (TurboVecEmbedder._EMBED_BATCH + 1)
    try:
        assert backend._embed_matrix(texts).shape == (len(texts), 384)
    finally:
        backend.close()
    assert [child.returncode for child in children] == [0, 0], children[0].stderr


def test_doc_evolver_children_start_clear_of_the_working_directory(
    shadowing_cwd, monkeypatch, safe_path
):
    from neuralmind import doc_evolver

    (shadowing_cwd / "export.ts").write_text(
        "function handleExport(data) {\n  return data;\n}\n", encoding="utf-8"
    )
    spot = doc_evolver.BlindSpot(name="handleExport", file_path="export.ts", line=1)
    evolver = doc_evolver.DocEvolver(shadowing_cwd, [spot])
    variant = doc_evolver.JSDocVariant(
        strategy=doc_evolver.MutationStrategy.LENGTH, lines=["Export the data."]
    )
    started = []

    def run(argv, **kwargs):
        cwd = kwargs.get("cwd")
        started.append((argv, cwd, os.listdir(cwd) if cwd else None))
        return subprocess.CompletedProcess(argv, 0, json.dumps({"context": ""}), "")

    monkeypatch.setattr(doc_evolver.subprocess, "run", run)
    evolver._evaluate_candidate(spot, variant)  # builds, then queries

    prefix = child_python.python_argv("-m", "neuralmind.cli")
    assert [argv[: len(prefix) + 1] for argv, _, _ in started] == [
        prefix + ["build"],
        prefix + ["query"],
    ]
    for _, cwd, contents in started:
        if safe_path:
            assert cwd is None
        else:
            assert contents == []  # an empty directory, not the project


def test_daemon_starts_clear_of_the_working_directory(tmp_path, monkeypatch, safe_path):
    """And still writes its discovery file where the CLI that started it looks,
    with ``NEURALMIND_DAEMON_HOME`` relative to the CLI's working directory."""
    from neuralmind import cli, daemon_client
    from neuralmind import daemon as daemon_mod

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Path.home() on Windows
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", ".daemon")
    clients = iter([None, SimpleNamespace(health=lambda: {"pid": 4242})])
    monkeypatch.setattr(daemon_client, "connect", lambda **_: next(clients))
    monkeypatch.setattr(daemon_mod, "read_discovery", lambda *_: {"port": 8765})
    started = []

    def popen(argv, **kwargs):
        kwargs["stdout"].close()  # the daemon log, normally the child's to keep
        started.append((argv, kwargs.get("cwd"), kwargs["env"]))

    monkeypatch.setattr(subprocess, "Popen", popen)
    cli.cmd_daemon(
        argparse.Namespace(
            action="start", foreground=False, host="127.0.0.1", port=8765, json=False
        )
    )

    [(argv, cwd, env)] = started
    assert argv == child_python.python_argv(
        "-m", "neuralmind.daemon", "--host", "127.0.0.1", "--port", "8765"
    )
    # 3.10: its own state directory, which outlives the call, not a temporary one.
    assert cwd == (None if safe_path else home / ".neuralmind")
    daemon_sees = Path(cwd or os.getcwd(), env["NEURALMIND_DAEMON_HOME"], "daemon.json")
    assert daemon_sees == Path.cwd() / daemon_mod.discovery_path()


def test_every_python_child_goes_through_child_python():
    """A new ``sys.executable`` spawn would have the same exposure.

    Exempt: the helper; hermes_install, which only records the path; and the
    Hermes plugin, which runs in Hermes's Python (no NeuralMind to import) and
    so sets PYTHONSAFEPATH and runs its child from its own directory.
    """
    package = Path(neuralmind.__file__).parent
    exempt = {"child_python.py", "hermes_install.py", "hermes_plugin/__init__.py"}
    spawners = [
        path.relative_to(package).as_posix()
        for path in sorted(package.rglob("*.py"))
        if "sys.executable" in path.read_text(encoding="utf-8")
    ]
    assert [name for name in spawners if name not in exempt] == []
