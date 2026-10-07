# NeuralMind v4.10.0 — Hermes can install the NeuralMind plugin itself, and the plugin says why when it can't work

**Type:** Minor release | **Theme:** Hermes-Agent plugin, ready for Hermes's own installer

v4.9.0 gave Hermes-Agent [NeuralMind's context in every turn](RELEASE_NOTES_v4.9.0.md)
through a plugin, installed with `neuralmind install-hermes-plugin`. Three things
stood between that plugin and a Hermes user finding and installing it the
Hermes way:

- **Only NeuralMind's command could install it.** Its manifest was generated
  at install, so a clone of its directory wasn't a plugin Hermes could load.
- **It went quiet when it couldn't work.** Without a NeuralMind it could run,
  or with one too old to give the recap, turns simply got no context, or no
  recap, and nothing said why.
- **Uninstalling, then installing again, left it off.** `--uninstall`
  disabled the plugin before removing it, which left it on Hermes's
  `plugins.disabled` list, and the next install respected that.

v4.10.0 fixes all three.

## Hermes can install it

The plugin's directory, `neuralmind/hermes_plugin/`, now carries its own
`plugin.yaml` and a [README](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/hermes_plugin/README.md),
so Hermes's own installer can install it from a clone of this repository:

```bash
pip install -U neuralmind                       # the plugin runs NeuralMind; it doesn't bundle it
neuralmind build /path/to/project
hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable
```

- **Hermes owns the code.** `hermes plugins update neuralmind` updates it.
- **It runs the `neuralmind` command on Hermes's PATH.** It looks only in
  absolute PATH entries, never the working directory, so a repository you work
  in can't supply its own `neuralmind`. Where Hermes's PATH doesn't include it
  (a gateway run as a service, Hermes Desktop), also run
  `neuralmind install-hermes-plugin`: on a plugin Hermes installed, it writes
  only the interpreter and the project to the plugin's `config.json`, and
  leaves the code alone. If Hermes's install records
  (`plugins/.install-metadata.json`) can't be read, it leaves the code alone
  too, and says so.
- **The manifest declares `requires_hermes: ">=0.21.5"`**, the version it's
  tested with, so an older Hermes skips it.
- **The README lists what the plugin does on your machine**: the subprocess it
  runs, what it reads and writes in the project's `.neuralmind/`, what it
  copies into Claude Code's memory directory, its network use, and what
  reaches your model provider.
- **Hermes's catalog check passes.** `hermes plugins validate` on the
  directory passes every check, the install security scan included.

`neuralmind install-hermes-plugin` works as before and stays the simplest way
in: it copies the plugin, records the Python interpreter that has NeuralMind,
and enables it.

## It says why when it can't work

When the plugin can't start NeuralMind, finds one older than 4.9, or a call
times out, it logs one warning per Hermes process, naming the fix:

```bash
hermes logs --level WARNING | grep -i neuralmind
# WARNING hermes_plugins.neuralmind: NeuralMind plugin: /home/you/.local/bin/neuralmind is
#   NeuralMind 4.3.5, too old for this plugin: turns get no session recap. Install NeuralMind
#   4.9 or later so the `neuralmind` command is on Hermes's PATH, or run
#   `neuralmind install-hermes-plugin` to point the plugin at it.
```

An older NeuralMind still answers, so before this the only sign was a missing
recap. The version check runs once per Hermes process, in the background, off
the turn's path. As before, nothing breaks the turn: it goes ahead without
NeuralMind's context.

## Fixed: a reinstall after an uninstall stays on

`neuralmind install-hermes-plugin --uninstall` now runs Hermes's own
`hermes plugins remove neuralmind`, which removes the directory and every entry
naming the plugin in that home's `config.yaml`, so installing it again later
turns it back on. A fresh install also enables the plugin whatever an earlier
one left on the disabled list; only a re-run over an existing install respects
a `hermes plugins disable neuralmind` you ran. Hermes won't remove a symlinked
`plugins/neuralmind`, so for one the command still disables the plugin and
removes the link, never what it points to. If `hermes plugins remove` fails,
even after it has already deleted the directory, the command disables the
plugin instead and says Hermes's config may still name it.

The install's last line also stopped saying "Each Hermes turn now gets
NeuralMind's related files…" when the plugin wasn't enabled (left disabled,
`--no-enable`, Hermes not set up yet, or `hermes` not on PATH). It now reads
"Once it's enabled, each Hermes turn gets …" in those cases.

## Also in this release

Two fixes found while fixing [v4.9.1](RELEASE_NOTES_v4.9.1.md). Neither loses data.

- **`validate` stops flagging prose chapters as stale.** In a project whose
  queries go through the prose path (a `chapters/` directory, built with a
  graph rather than as a book), each query records the chapters it retrieved
  in the synapse store by file name, such as `ch01.md`. That's never a graph
  node id, so `neuralmind validate` reported every chapter synapse as stale.
  A chapter name now counts as known when the index still holds
  `chapters/<name>`. A chapter you deleted is still reported, and so is any
  other name that doesn't resolve.
- **The daemon sleep pass no longer treats ephemeral edges as long-term.**
  `DaemonSleep.promote_ltp_edges` nudges long-term edges back up after decay.
  It picked them by activation count and weight alone, so it also boosted
  edges in the `ephemeral` namespace, which decay never protects. It now uses
  the same long-term rule as decay, `status` and `SYNAPSE_MEMORY.md`: at least
  five activations, a weight of at least 0.20, and not ephemeral. Nothing in
  the CLI, hooks, daemon or MCP tools runs the sleep pass yet; this fixes the
  `neuralmind.sleep` API for code that calls it.

## What the agent sees

Nothing new in a turn: the same recap and recall v4.9.0 added, appended to the
user message. What changes is that more installs actually deliver it, and when
one doesn't, Hermes's log says why. Tested against Hermes v0.21.5 (a
0.21.5+5355 main-branch build) in live `hermes chat` sessions: the first-turn
recap, recall, edits made with `patch` and `write_file`, a resumed session
(recall only), a subagent (skipped), a directory that hasn't been built
(nothing), both ways of installing, and uninstalling. What the context changes
in Hermes's answers still isn't measured.

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Hermes-Agent** | It can install the plugin itself (`hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin`), and update it with `hermes plugins update neuralmind`. When the plugin can't run NeuralMind, finds an old one, or times out, Hermes's log says so. Uninstalling and installing again leaves it enabled. |
| **Claude Code** | Nothing. |
| **Cursor / Cline / generic MCP clients** | Nothing. |
| **Other agents with a shell** | Nothing. |

## Use cases

- **Existing:** [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md).
  The install step gains the Hermes-native route, and the limits section says
  where to look when turns get no context.
- **Potential:** a Hermes user who manages everything through
  `hermes plugins` can now add NeuralMind the same way as any other plugin,
  and keep it updated with the rest. Listing it in Hermes's curated plugin
  catalog, so `hermes plugins install neuralmind` finds it by name, is the
  next step; it takes a pull request to Hermes pinned to this release.

## Settings

No new settings. `NEURALMIND_PROJECT` and `NEURALMIND_HERMES_TIMEOUT` work as
in v4.9.0, and a timeout is now logged.

## Upgrading

`pip install -U neuralmind`, then re-run `neuralmind install-hermes-plugin`:
the plugin it installed is a copy, and a re-run keeps an earlier pin and leaves
a plugin you disabled disabled. A plugin Hermes installed is updated with
`hermes plugins update neuralmind` instead.

## Related

- Plugin README: [neuralmind/hermes_plugin/README.md](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/hermes_plugin/README.md)
- Use case: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md)
- Integration guide: [Hermes-Agent](../wiki/Integration-Guide.md#hermes-agent)
- CLI reference: [`install-hermes-plugin`](../wiki/CLI-Reference.md#install-hermes-plugin-v490)
- Previous release: [v4.9.1](RELEASE_NOTES_v4.9.1.md) · [v4.9.0](RELEASE_NOTES_v4.9.0.md)
