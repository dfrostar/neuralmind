# NeuralMind v4.20.1 — Intel macOS and Windows ARM work again out of the box

**Type:** Patch release | **Theme:** the default backend falls back to ChromaDB where turbovec has no wheel, and `neuralmind demo` runs there

turbovec publishes wheels for Linux, Apple Silicon macOS and 64-bit Windows.
On every other platform, notably Intel macOS and Windows ARM, `pip install
neuralmind` installs ChromaDB in its place. That has been the design since the
default install went ChromaDB-free (#251): the default backend was `auto`,
which used turbovec where it was installed and ChromaDB where it wasn't.

v0.46.0 made the default a fixed `turbovec` and dropped that fallback, but
left the install markers as they were. From v0.46.0 to v4.20.0, on those
platforms, a default install selected a backend it didn't have: `neuralmind
build`, and everything that builds, failed with `No module named 'turbovec'`
unless the project set `backend: graph`. `neuralmind demo` failed the same
way. Some of our docs described setting `backend: chroma` there as required.

This release restores the fallback. Nothing changes where turbovec is
installed.

---

## What changed

### The default backend falls back to ChromaDB where turbovec isn't installed

With no backend configured, or with `backend: auto` or `backend: turbovec`,
NeuralMind uses turbovec when its stack (`turbovec`, `onnxruntime`,
`tokenizers`) imports, and ChromaDB when it doesn't and ChromaDB does. That is
the install you get on Intel macOS and Windows ARM.

- **No deprecation warning for it.** Choosing `backend: graph` or `chroma`
  yourself still warns that ChromaDB is deprecated; the fallback doesn't,
  since you didn't choose it.
- **`neuralmind doctor` shows it.** Its *Backend* line reports the backend in
  use, `graph (auto-selected; turbovec stack not installed)` on those
  platforms. It also stops calling a project with no
  `neuralmind-backend.yaml` "pinned via neuralmind-backend.yaml", which it
  had done since v0.46.0, and says so when a file names `turbovec` but
  ChromaDB serves it.
- **An existing `backend: chroma` keeps working** and can stay or go: the
  default now selects the same backend there.

### A missing backend says what to install

If neither turbovec nor ChromaDB is installed (say, both were uninstalled),
NeuralMind used to fail deep inside a build with a bare `ModuleNotFoundError`.
It now stops when it creates the backend, with what to install:

```
the turbovec backend needs turbovec, which isn't installed. Install it with
`pip install turbovec onnxruntime tokenizers`; where turbovec has no wheel
(Intel macOS, Windows ARM), install ChromaDB instead with
`pip install "neuralmind[chromadb]"`.
```

### `neuralmind demo` on ChromaDB

The demo's bundled index and question vectors (v4.19.0) are turbovec's. On a
ChromaDB install the demo now builds the sample's index with the embedding
model instead, which downloads it once, and says so:

```
[demo] this install uses the ChromaDB backend (turbovec has no wheel for this
platform), so the demo builds the sample's index with the embedding model,
which downloads it once.
```

Offline, it exits 1 with one line saying the model couldn't be downloaded, not
a traceback. With no vector backend at all it exits 1 with the install hint
above. The demo runs offline, with nothing downloaded, where turbovec is
installed: Linux, Apple Silicon macOS and 64-bit Windows.

### Also: an idle association's decay rate relaxes back to the default

Each learned association has a half-life of its own, learned from how often it
was reinforced: between 3 and 120 days, beside the namespace default of 30 days
for personal and branch memory and 60 for the team's shared baseline. The
design blends that learned rate back toward the default the longer an
association sits idle, but the blend was computed only by `reinforce()`, at
the moment it set the last-activation time, where it changes nothing. So an
idle association kept its learned rate for as long as it stayed idle.

What that did, on the schedules `tests/test_learned_decay.py` replays:

| Association | Before | Now |
|---|---|---|
| Used three times, a month apart (learns a half-life under 15 days) | Pruned after two idle months | Kept after two idle months, pruned within five |
| Used every day for ten days (learns one over 60 days) | Kept its long half-life however long it sat | Slides toward 30 days while idle; still above 80% of full weight after two idle weeks |
| Used five or more times | Held at the long-term floor | Unchanged |

`decay()` now integrates the blend over the idle time. The integral has a
closed form (`learned_decay.blended_decay_factor`, mirrored in the SQL), so a
decay pass still charges only the time since the previous one, and many passes
still decay a weight exactly as much as one pass at the end. The code index is
unaffected: this changes how long learned associations steer recall, not what
search can find.

---

## What the agent sees

On Linux, Apple Silicon macOS and 64-bit Windows: nothing changes.

On Intel macOS and Windows ARM, every integration works without a
`neuralmind-backend.yaml`:

| Agent | Before (v0.46.0 to v4.20.0) | After |
|---|---|---|
| Claude Code (hooks + MCP) | Anything that built or read the index failed with `No module named 'turbovec'` until `backend: graph` was set | Works on the default install |
| Cursor / Cline / generic MCP | The same failure on every tool that reads the index | Works on the default install |
| Hermes-Agent plugin | The same failure; no context from the index | Works on the default install |

The first build on those platforms downloads ChromaDB's embedding model once.
For an air-gapped install, stage ChromaDB's model cache as the
[air-gapped walkthrough](../use-cases/air-gapped.md) describes.

---

## Upgrading

`pip install -U neuralmind`. On Intel macOS and Windows ARM you can delete a
`backend: chroma` line you added only to make NeuralMind run; it is harmless
to keep.

## Tests

- `tests/test_backend_manager.py`: the default and `turbovec` resolve to
  ChromaDB when only ChromaDB is installed, with no deprecation warning; stay
  turbovec when its stack is installed or when nothing is; explicit backends
  are never rerouted; a missing turbovec names what to install.
- `tests/test_doctor.py`: no config file reads as auto-selected, on either
  backend; a `turbovec` pin served by ChromaDB says so.
- `tests/test_cli.py::TestCLIDemoWithoutTurbovec`: on ChromaDB the demo says
  it is building with the model and exits 1 with one line when offline; with
  no backend it exits 1 with the install hint.
- `tests/test_learned_decay.py`: `blended_decay_factor` matches a numerical
  integral of the blended rate, composes exactly across passes and reduces to
  the plain half-life when the rates agree; `decay()` computes the same factor
  in SQL for personal, branch and shared memory (`TestDecayAppliesTheBlend`,
  which fails on v4.20.0); `TestForgettingInPractice` replays the schedules
  above.
