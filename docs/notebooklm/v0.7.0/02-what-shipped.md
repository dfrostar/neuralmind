# What shipped in NeuralMind v0.7.0

*Neutral third-person technical source for the NotebookLM video.
Concrete feature-by-feature breakdown of every change.*

---

NeuralMind v0.7.0 is a distribution release. It does not add product
features, change the synapse model, or alter the graph view
rendering. It expands install coverage, ships a container image
source, and lands the two non-blocking review-feedback patches the
v0.6.0 merge train deferred. The full set of changes can be grouped
into four categories.

The first category is the install matrix. The README now documents
five install paths under the Quick Start section. The default
remains `pip install neuralmind graphifyy`. Added are `pipx install
neuralmind` with a follow-up `pipx inject neuralmind graphifyy` for
the graph builder; `uv pip install neuralmind graphifyy` for users
on Astral's uv toolchain; `docker run ghcr.io/dfrostar/neuralmind`
for containerized usage; and the existing source install for
contributors. Every path resolves to the same wheel. The CLI entry
points — `neuralmind` and `neuralmind-mcp` — are identical
regardless of install method. The smoke test, also documented in
the README, is `python -c "import neuralmind; print(neuralmind.__version__)"`
followed by `neuralmind --help`. Both lines work for every install
path, with the small exception that pipx's isolated environment
means the `import neuralmind` line only works inside that pipx
venv.

The second category is the Dockerfile. The repo now ships a
multi-stage Dockerfile in the repository root. The builder stage
uses `python:3.12-slim`, installs build-essential, copies the source
tree, and produces a wheel via `python -m build`. The runtime stage
discards the build tools and the source, installs the wheel into a
clean `python:3.12-slim` image, creates a non-root `neuralmind`
user, exposes port 8765 (the default for `neuralmind serve`), and
defaults the container command to `neuralmind --help`. The
documented usage patterns are mounting the host project read-only
into `/project` and running either `neuralmind-mcp /project` for
the MCP server or `neuralmind serve /project --host 0.0.0.0
--no-auth` for the graph view bound to the host port. The
auto-publish of this image to GHCR is deferred to v0.8.x (Phase 3,
Enterprise-Ready); for v0.7.0, the Dockerfile is committed and
users build the image locally. The pull command in the README
documents the eventual GHCR tag so the README doesn't have to
change again when the auto-publish lands.

The third category is documentation. `docs/use-cases/install-paths.md`
is a new walkthrough page covering each install path with its
trade-off explained. `docs/wiki/Setup-Guide.md` gets an install
matrix table inserted before the existing 30-Second Setup section,
positioning the wiki page as the canonical landing for "how do I
install this." The five primary comparisons pages — vs Cursor, vs
Copilot, vs Aider, vs Cody, and vs Claude Projects — each gain an
"Install methods" row in their feature tables, naming the
competitor's install constraint (paid IDE, sign-in required, etc.)
alongside NeuralMind's five-path matrix. The `pyproject.toml`
keywords list is bumped with eight additions —
graph-view, code-graph, obsidian-style, synapse-layer, hebbian-learning,
code-visualization, force-directed-graph, and neuralmind-serve. These
are PyPI SEO terms; the existing v0.5-era list missed every term the
v0.6.0 product copy now leads with.

The fourth category is the two deferred review-feedback patches.
Issue 115 was a Codex-flagged P2 correctness bug in the event log
tailer: when logrotate or copytruncate replaces the events.jsonl
file mid-stream, the tailer reopened the new file at end-of-file
instead of beginning-of-file, silently dropping any lines written
before the next poll. The fix distinguishes the initial open (seek
to EOF, preserving the no-history-replay behaviour) from a
rotation-recovery reopen (seek to offset zero, catching any
already-written lines). A new test in tests/test_event_log.py
simulates the race window by writing three lines to the post-rotation
file before allowing the tailer to detect the rotation, and asserts
all three are delivered.

Issue 116 was a Copilot-flagged test coverage gap on the
/api/queries server route added in PR 105. The route was
hand-tested for happy path, clamping, and bad-input defaulting in
the original PR; v0.7.0 adds the explicit no-argument case
(`GET /api/queries` with no `n` parameter must default to 20) that
the existing parametrized tests didn't cover directly. The existing
two tests already cover happy-path and clamping behaviour, so the
116 work is small.

The marketing artifacts shipped with v0.7.0 are scoped to drafting
only — the maintainer's approval is required before any are
published. A new LinkedIn drafts block in `docs/LINKEDIN-POST-DRAFT.md`
covers two voices (feature-tour scannable and short
dev-honest). A new screencast script in `docs/SCREENCAST-v0.7.0.md`
covers a sixty-second three-beat video: pipx install, docker run,
both-canvases-pulsing side by side. A new NotebookLM source pack in
`docs/notebooklm/v0.7.0/` follows the v0.6.0 three-document
structure for AI-generated video and podcast overviews.

There are no breaking changes. The Python API is unchanged. CLI
arguments are unchanged. The `.neuralmind/` on-disk state format
is unchanged. Upgrade is a straight `pip install --upgrade
neuralmind` (or whatever install path the user is on); existing
projects continue to work. The minimum supported Python remains
3.10. The dependency floor for the chromadb, pyyaml, toml, and mcp
packages is unchanged.

The next release in the published roadmap is v0.8 — the "Always-On"
release covering systemd and launchd templates, the `/healthz`
endpoint for `neuralmind serve`, the Aider MCP integration, and the
Windows Task Scheduler documentation polish. v0.7.0 sets up that
release by ensuring the install story is robust before the always-on
story extends it.
