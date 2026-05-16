# Why NeuralMind v0.6.1 is about install paths, not features

*Founder-narrative source for the NotebookLM video. First-person,
conversational. Use as the "why does this release exist" arc.*

---

NeuralMind v0.6.0 was the big release. We made the brain visible —
the live activity feed, the pulse rings, the moment the pitch
flipped from "code RAG" to "associative memory you can watch
learn." If you read the v0.6.0 release notes, you'd be forgiven for
thinking the next thing we'd ship would be another features release.

It isn't. v0.6.1 is a distribution release.

The reason is a thing I noticed during the v0.6.0 launch week. The
release notes shipped, the LinkedIn post went up, the screencast
hit eight thousand views. People came to the repo. And then a
fraction of them never installed NeuralMind, because their first
question wasn't "is this useful?" — it was "do I `pip install` this,
or do I `pipx install` this, or do I add it to my `uv` project, or
do I run it in Docker?"

If you've shipped open-source Python tools before, you know this
question. The answer is "it depends on your tooling preferences,"
and that answer is the worst possible thing to put in front of
someone who's still deciding whether to try your software at all.
Every install-path question is a moment where the visitor weighs
"how much do I want to try this?" against "how much friction will
this be?" If the answers don't tilt the right way, you lose them.
You never know you lost them, because they don't open an issue
saying "I was going to install this but I wasn't sure how."

So v0.6.1 fixes that. There are five install paths now, documented
on the README, with a single matrix that names the trade-off of
each in one phrase. You don't have to read the install-paths
walkthrough to pick one. You just look at the matrix and pick.

The five are: pip, the default for people who already have a venv
opened. pipx, for people who want the CLI on PATH globally without
polluting any one environment. uv, for the Astral-tooling crowd who
correctly point out that uv is just faster. Docker, for the
"absolutely no Python on the host" crowd, the CI pipelines, the
air-gapped servers, the people whose corporate IT policy means
installing Python is a months-long ticket. And source, for
contributors and people who want to read the code while they use
it.

All five resolve to the same package. The `neuralmind` CLI behaves
identically. The MCP server registers the same tools. The graph
view renders the same canvas. There's exactly one wheel on PyPI;
the matrix is just five fronts onto it.

The headline visual for v0.6.1 is two terminals, side by side. The
left one is `pipx install neuralmind` followed by `neuralmind --help`.
The right one is `docker run ghcr.io/dfrostar/neuralmind neuralmind --help`.
The help output is identical. That's the whole pitch. Same package,
whatever your stack.

There's a Dockerfile in the repo root now, multi-stage, slim
runtime, non-root user. Build it locally if you want; the auto-publish
to GHCR is a Phase 3 / v0.7.x thing because we want the build
pipeline to be hardened before we commit to "one-line `docker pull`
works forever." The Dockerfile itself is already production-grade
and the docs walk through how to run it against a host project
directory.

The `pyproject.toml` keywords got a long overdue refresh — graph-view,
hebbian-learning, code-visualization, force-directed-graph,
neuralmind-serve. PyPI search ranking is fuzzy magic but the
existing v0.5-era keyword list was missing every word we now lead
with in product copy. Half the v0.6.1 install path improvements are
about discoverability before installation: if you can't find the
package, it doesn't matter how easily it installs.

The thing v0.6.1 isn't, deliberately, is a feature release. The
brain isn't smarter than it was in v0.6.0. The graph view doesn't
render any node it couldn't render last week. The synapse layer
behaves the same. If you're already running NeuralMind 0.6.0 and
your install path is fine, the upgrade is approximately zero work
and approximately zero impact. That's a feature, not a problem.
Small patches that change one thing well are the operations the
release-please cycle is designed for.

What v0.6.1 sets up is the v0.7 release after it. v0.7 is the
"Always-On" release: systemd templates, launchd plists, a `/healthz`
endpoint, Aider MCP integration, the screencast where you see the
canvas pulsing as you save files for forty seconds straight because
the watcher daemon never sleeps. That release is for ops people and
SREs. It makes no sense to ship it before "installs anywhere"
exists — you can't tell people to `systemctl enable neuralmind-watch`
if their answer to "how do I install it" is still "well, that depends."

So this is the order. v0.6.0: brain becomes visible. v0.6.1: brain
becomes reachable. v0.7: brain becomes persistent. v0.7.x: brain
becomes auditable. Each release makes the next one credible. v0.6.1
is the second beat in that arc and it deserves to land as its own
small thing — not buried under feature creep, not deferred until
the v0.7 train.

If you've installed NeuralMind already and you're wondering whether
this affects you: probably not directly. The reason to care is that
the next person you tell about NeuralMind doesn't have to ask you
how to install it. They click the README link, see the matrix, pick
the one that matches their tooling, and they're in.

That's the whole point.
