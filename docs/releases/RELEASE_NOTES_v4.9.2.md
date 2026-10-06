# NeuralMind v4.9.2 — `--` works again in the decisions and memory subcommands

**Type:** Patch release | **Theme:** A v4.9.1 regression in argument parsing

[v4.9.1](RELEASE_NOTES_v4.9.1.md) let six `decisions` and `memory`
subcommands take the project path after their options by parsing them
intermixed. On Python 3.10 and 3.11, on 3.12 before 3.12.8, and on 3.13.0,
intermixed parsing can ignore `--`, so v4.9.1 broke `--` there. This release
fixes that and keeps the path after options.

---

## What changed

### CLI

- **`--` ends the options again.** In v4.9.1, on the Python versions above,
  `decisions query -- -q .` failed with `unrecognized arguments: -q`, and
  `decisions query -- --json .` turned on `--json` and searched for ".".
  Everything after `--` is a positional again, as in v4.9.0. The six
  subcommands (`decisions amend`, `invalidate`, `query` and `restore`, and
  `memory review-approve` and `review-reject`) still take the project path
  after their options, now with or without `--`: `decisions restore <id>
  --commit SHA -- -proj` takes `-proj` as the path. Instead of parsing
  intermixed, NeuralMind applies the rule Python 3.12.7 and 3.13.1 added to
  argparse, on the versions without it, so every supported Python parses
  these lines the same way.
- **A path after a list option needs `--`.** A list option such as `--files`,
  `--rejected`, `--evidence` or `--tags` takes every value up to the next
  option. So `decisions amend <id> --evidence proof.md <path>` reads the path
  as more evidence and runs on the current directory. It always has.
  `decisions record --help` and `amend --help` now say to put `--` before the
  path: `--evidence proof.md -- <path>`.

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | No change | Same |
| **Cursor / Cline / Claude Desktop** (MCP) | No MCP tool changed | Same |
| **Generic MCP client** | No MCP tool changed | Same |
| **Agents that run the CLI** (Hermes skill, scripts) | With v4.9.1 on Python 3.10, 3.11, 3.12 before 3.12.8 or 3.13.0, `--` could fail to end the options of the six subcommands | `--` ends the options, and the path can follow the options with or without it |

## Environment variables

None added or changed.

## Upgrade notes

None. No stored data changes shape, and no command takes new arguments.

## Related

- [CLI reference: decisions](../wiki/CLI-Reference.md#decisions-v410)
- [v4.9.1 release notes](RELEASE_NOTES_v4.9.1.md) ·
  [v4.9.0 release notes](RELEASE_NOTES_v4.9.0.md)
