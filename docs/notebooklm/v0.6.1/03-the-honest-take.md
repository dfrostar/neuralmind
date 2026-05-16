# The honest take on NeuralMind v0.6.1

*Mixed developer-experience and skeptic's-view source for the
NotebookLM video. Day-in-the-life walkthrough plus the things to
push back on.*

---

Here's how a v0.6.1 install actually goes, told straight, on a
machine that already has Python and Docker installed.

You land on the README from a link in someone's LinkedIn post.
You scroll to the Quick Start section and see five install paths in
a table. You skip the table and look at which command starts with
the install tool you already use. You're a pipx person, so you copy
`pipx install neuralmind && pipx inject neuralmind graphifyy`. You
paste, you press enter, it takes about twenty seconds total, and
you have `neuralmind` on PATH from any directory. You run
`neuralmind --help`, you see the subcommand list, you go to a
project directory, you run `graphify update . && neuralmind build .`,
and you have an index. You run `neuralmind serve .` and a browser
opens to a graph view. Total time from clicking the LinkedIn link
to seeing the graph: maybe four minutes. Most of it was the
`graphify update` step on a real codebase.

That's the experience the v0.6.1 release is designed to produce. If
you're an experienced developer with a clean Python install, that
flow works. The release-cycle bet is that this flow is enough
better than the v0.6.0 flow — which was "you have one option, hope
you like pip" — that the install-completion rate goes up
measurably. We won't have data for a few weeks. PyPI download stats
will give us one signal; GitHub stars correlated with the release
date will give us another; neither is conclusive on its own.

Now the honest pushback.

The first thing to push back on is the framing. "Install five ways"
sounds, on its face, like a meaningful product improvement. It
isn't. It's PR work. The package itself is unchanged. If you read
the v0.6.1 release notes hoping for a smarter synapse layer or a
better graph view, you'll come away disappointed. The argument for
shipping it as its own version isn't that there's new product
value; it's that the v0.6.0 install story was a real conversion
leak and fixing it as its own beat makes both the v0.6.0 launch
moment and the v0.7 launch moment land cleaner. If you don't buy
that argument, v0.6.1 looks like a marketing release with a version
number. That's a fair criticism. You should weigh it.

The second is the Dockerfile. We shipped the Dockerfile but not
the auto-publish to a registry. The README's `docker run
ghcr.io/dfrostar/neuralmind` command works only after you've
manually built and pushed that image — which the maintainer hasn't
done as of v0.6.1. Until the GHCR auto-publish lands in v0.7.x,
"run it in Docker" means "build the image yourself first." That's
documented honestly, but it does mean the Docker line in the matrix
is more aspirational than the other four. We considered hiding the
Docker row until the auto-publish was live; we decided documenting
the path now and explicitly noting the build-locally requirement
was more transparent than waiting. Reasonable people can disagree.

The third is uv. We name uv in the matrix and the install-paths
page. We don't ship a `uv.lock`, we don't pin our dependencies
specifically for uv's resolver, and we don't test against uv in CI.
"uv pip install neuralmind" works because uv is intentionally a
drop-in for pip; we're not doing anything special to support it,
and we're not exercising any uv-specific paths. If something breaks
specifically in a uv environment that doesn't break in pip, we'll
fix it, but we don't have explicit test coverage for it. Worth
knowing if you're going to bet your team's tooling on it.

The fourth is pipx versus pip. The matrix presents them as
co-equal, but they're not the same thing. Pipx isolates the package
in its own venv and only exposes the entry point scripts. That means
if you also want to `import neuralmind` from Python code — for
example, to build something that wraps the synapse layer — pipx
won't let you do that. The README mentions this in the install-paths
walkthrough but it's a footnote there; the matrix doesn't
distinguish. If you're a library author rather than a CLI user, pip
in a project venv is still the right answer.

The fifth is what didn't change. The graph view is still single-user
and single-host. The MCP server still requires a `project_path`
argument from every client (we have an issue to make that
inferrable from cwd, but it's not in v0.6.1). The audit log still
writes to local SQLite, not to a remote backend. The benchmark
suite still ships with the 500-line fixture and produces the same
five-point-something-x reduction it produced before. None of that
is broken; none of it is improved. If those were the things you
were waiting for, v0.6.1 isn't your release.

And the sixth: the install-paths page makes a sales pitch ("`pipx`
for always on PATH") that is, in fairness, what we'd say to any
specific user asking. But "anything works" is also a fair answer
for most projects. The matrix is for the people who have a
preference; if you don't, just run `pip install neuralmind
graphifyy` in whatever environment you already have open and
you're done.

When is v0.6.1 actually worth installing over v0.6.0? When you're
on a machine where `pip install` was failing for some environmental
reason and one of the other paths fixes it. When you want the CLI
on global PATH and didn't realize pipx was an option. When you've
been waiting to put NeuralMind in your CI image and didn't want to
write the Dockerfile yourself. Otherwise: upgrading is fine,
upgrading is approximately zero work, and there's no urgency.

The thing the v0.6.1 release is genuinely good for is being able to
send a colleague the README link and not having to explain how to
install Python tools. That's the small, real, measurable thing it
buys. If your team has been blocked at the install step, this fixes
it. If your team hasn't, you can wait for v0.7 and the always-on
story.

The brain in v0.6.1 is the same brain you had a week ago. There
are just more doors into the room.
