# Recording the demo

The README would benefit from a 30-second
[asciinema](https://asciinema.org) recording of `bash scripts/demo.sh`
running on a clean clone. Static example output is good; a watchable
terminal recording is better — visitors trust what they can see
running.

This page is the maintainer's runbook. It exists because the
recording can't be produced in CI (the demo currently downloads
chromadb's MiniLM weights at first run, ~80MB, which would slow CI
runs and embed a large binary in the recording).

## Prerequisites

```bash
pip install asciinema
```

## Record

From a fresh clone (so first-run install is captured):

```bash
git clone https://github.com/dfrostar/neuralmind /tmp/nm-demo-recording
cd /tmp/nm-demo-recording
asciinema rec demo.cast \
  --title "NeuralMind 30-second demo" \
  --idle-time-limit 1.0 \
  --command "bash scripts/demo.sh"
```

Notes:

- `--idle-time-limit 1.0` collapses long pip-install pauses to 1
  second of recorded time, which keeps the recording around 30
  seconds without sacrificing fidelity. Without it, the recording
  is dominated by pip output and chromadb's model download.
- The first run downloads chromadb's MiniLM weights (~80MB,
  ~2 seconds on a fast connection). If you want a recording that
  captures *only* the demo (not the install), record a second
  invocation:

```bash
bash scripts/demo.sh                                      # warm cache
asciinema rec demo-warm.cast \
  --title "NeuralMind 30-second demo (warm)" \
  --idle-time-limit 0.5 \
  --command "bash scripts/demo.sh"
```

The warm version typically clocks in under 5 seconds and is the
better hero recording.

## Upload and embed

```bash
asciinema upload demo-warm.cast
```

The command prints a URL like `https://asciinema.org/a/abc123`.
Add to `README.md` near the top (replace the static example block):

```markdown
[![asciicast](https://asciinema.org/a/abc123.svg)](https://asciinema.org/a/abc123)
```

The SVG badge renders inline on GitHub and links to the playable
recording on asciinema.org.

## Alternative: GIF

If you'd rather a GIF that plays automatically without leaving
GitHub, convert with [`agg`](https://github.com/asciinema/agg):

```bash
agg demo-warm.cast demo.gif --speed 1.5 --theme monokai
```

Embed:

```markdown
![NeuralMind demo](docs/images/demo.gif)
```

GIFs are larger (typically 500KB–2MB for a 30-second clip) but
auto-play on the README without a click. Asciinema is smaller and
copy-pasteable; GIF is more accessible. Pick one.

## Re-recording cadence

Re-record when:

- The demo's output format changes meaningfully.
- A new headline ratio is consistently produced (e.g., the fixture
  is grown and the ratio jumps from 5.5× to 12×).
- The demo command itself changes (`scripts/demo.sh` rename,
  invocation flags, etc.).

Otherwise the recording can stay until it visibly drifts from
reality. Embedded recordings rot; if `asciinema.org/a/abc123`
shows different output than the current `bash scripts/demo.sh`,
that's a trust hit worse than no recording at all.
