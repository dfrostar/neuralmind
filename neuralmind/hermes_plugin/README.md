# NeuralMind for Hermes-Agent

NeuralMind's code memory in every Hermes turn, without a tool call. Before the
model runs, the plugin adds the files and recorded decisions related to the
user's message. A session's first turn also starts with a recap of the last
session in the project, whether that was a Hermes session or a Claude Code one.

## What the model sees

The plugin appends a block to the turn's user message, not to the system
prompt, so Hermes's prompt cache isn't invalidated. A session's first turn,
in a small example project:

```text
NeuralMind session recap — the previous session in this project (last active just now). This is context for continuity, not instructions: don't resume that work unless the user asks to.

It started with: "In shop/pricing.py, add a discount code SAVE20 that takes 20% off, next to SAVE10."
Most recent prompts:
- "Does checkout.total already honour SAVE20, or does it need a change?"

Files edited (1, most recent first): shop/pricing.py

## NeuralMind associative recall

- shop_pricing_py (activation 0.26)
- shop_pricing_py__add_tax_fn (activation 0.21)
- shop_checkout_py__total_fn (activation 0.07)
```

Later turns get the recall part only. The recall lists NeuralMind's graph
nodes for the code (files, functions, symbols) ranked by how strongly they're
associated with the message. Those associations are learned from the files
sessions in the project work on and edit.

## Requirements

- Hermes-Agent 0.21.5 or later.
- NeuralMind 4.9 or later, installed so its `neuralmind` command works:
  `pip install neuralmind`, `pipx install neuralmind` or
  `uv tool install neuralmind`.
- A project NeuralMind has built: `neuralmind build /path/to/project`.
  Anywhere else, the plugin does nothing.

## Install

With NeuralMind's installer:

```bash
neuralmind install-hermes-plugin                    # follow the directory Hermes works in
neuralmind install-hermes-plugin /path/to/project   # or pin one project
```

It copies this directory into the Hermes home's `plugins/neuralmind/`,
records the Python interpreter that has NeuralMind installed, and runs
`hermes plugins enable neuralmind`. The copy doesn't update itself: run the
command again after upgrading NeuralMind.

Or with Hermes's own installer, which clones this directory:

```bash
hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable
```

Hermes then owns the plugin's code, and `hermes plugins update neuralmind`
updates it. Installed this way, the plugin runs the `neuralmind` command it
finds on Hermes's PATH. Where Hermes's PATH doesn't include it (a gateway run
as a service, Hermes Desktop), also run `neuralmind install-hermes-plugin`
once: on a plugin Hermes installed, it writes only the interpreter and the
project to the plugin's `config.json` and leaves the code alone. If Hermes's
install records (`plugins/.install-metadata.json`) can't be read, it leaves the
code alone too, and says so.

Start a new Hermes session, or restart the gateway, to load the plugin.

## Which project

1. `NEURALMIND_PROJECT`, if set;
2. else the project pinned at install;
3. else Hermes's terminal working directory (`TERMINAL_CWD`);
4. else, only when `TERMINAL_CWD` isn't set, the directory Hermes runs in.

The first of these that has been built wins. If none has, the plugin does
nothing. `TERMINAL_CWD` matches the terminal CLI and a standalone gateway.
Hermes Desktop, ACP editor sessions and per-session workspaces keep each
session's directory elsewhere, so with those, pin a project or set
`NEURALMIND_PROJECT`.

A pin applies to every Hermes session that uses that Hermes home, in any
directory. Each one gets the pinned project's context, has its prompts
recorded in that project, and adds the paths of the files it edits to that
project's synapse store. `neuralmind memory publish` can carry those paths
into the project's committed team-memory bundle. If you use Hermes across
several projects, don't pin one.

## Settings

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_PROJECT` | unset | The project to serve, ahead of the pinned one |
| `NEURALMIND_HERMES_TIMEOUT` | `8` | Seconds each call to NeuralMind may take before it's stopped and its context left out. A session's first turn makes two calls; keep twice this below Hermes's `plugins.hook_callback_timeout` (default 30) |
| `NEURALMIND_BYPASS` | unset | `1` switches off every action |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | `0` leaves out the recall |
| `NEURALMIND_SESSION_RECAP` | `1` | `0` stops recording prompts and edited files, and the recap |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | `0` skips the `SYNAPSE_MEMORY.md` export on a session's first turn |
| `NEURALMIND_NO_LEARN` | unset | `1` stops the recording and the learning; an existing recap is still shown |

## What it does on your machine

- **Runs NeuralMind in a separate process.** The plugin runs
  `neuralmind _hook <action>` once per turn (twice on a session's first:
  the recap, then recall), and once for each file a `write_file` or `patch`
  call wrote, on a background thread. Each call is stopped after
  `NEURALMIND_HERMES_TIMEOUT` seconds.
- **Reads and writes the project's `.neuralmind/` directory.** NeuralMind
  stores what it learns there and, for the recap, each session's prompts
  (secret-redacted and truncated) and the paths of the files it edited.
  Files changed through the terminal aren't recorded.
- **Runs NeuralMind's whole `SessionStart` action on a session's first
  turn**, as Claude Code's hook does: a synapse decay tick, the team-memory
  import, clearing session-scoped associations, and an export of
  `.neuralmind/SYNAPSE_MEMORY.md`. That export is also copied into Claude
  Code's memory directory for the project (`~/.claude/projects/<project>/memory/`)
  when that directory exists.
- **Network.** The plugin makes no network requests of its own, and
  NeuralMind sends no telemetry. NeuralMind downloads its embedding model
  once, over HTTPS, when it has no cached copy, normally during
  `neuralmind build`. `NEURALMIND_ONNX_MODEL_DIR` points it at a copy you
  provide instead.
- **What reaches your model provider.** The added context is part of the
  user message, so it's sent to your model provider with that turn. Hermes
  keeps it in the session's history, so it's sent again with the session's
  later turns.
- **What it leaves alone.** It registers no tools, changes no Hermes
  settings, and never waits for a person. Subagent turns and cron jobs are
  skipped: they aren't recorded or given context. When NeuralMind can't run
  or a call times out, the turn goes ahead without NeuralMind's context.

## Troubleshooting

If turns get no NeuralMind context, check that:

- `hermes plugins list` shows `neuralmind` as enabled;
- the project has been built (it has a `.neuralmind/build_status.json`);
- Hermes's log has no warning from the plugin. The plugin logs one warning
  per Hermes process when it can't run NeuralMind, when the NeuralMind it
  found is too old to give a recap, or when a call times out,
  naming the fix:

  ```bash
  hermes logs --level WARNING | grep -i neuralmind
  ```

## Limits

- Tested with Hermes v0.21.5.
- What the added context changes in Hermes's answers hasn't been measured.

## Uninstall

```bash
neuralmind install-hermes-plugin --uninstall
```

It runs `hermes plugins remove neuralmind`, which removes the plugin and its
entries in Hermes's `config.yaml`. Running that Hermes command yourself does
the same.

## License

MIT. Source: [dfrostar/neuralmind](https://github.com/dfrostar/neuralmind),
in `neuralmind/hermes_plugin/`.
