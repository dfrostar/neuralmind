# NeuralMind v4.10.1 — No turbovec store on a ChromaDB project

**Type:** Patch release | **Theme:** Two turbovec checks that ran on every backend

`neuralmind build` and `neuralmind doctor` each check whether the turbovec
index was quarantined, which happens when the installed turbovec can't read
it. Both checks opened the turbovec store to do it, whatever backend the
project uses, and opening it creates the file. So on a project with ChromaDB
pinned, every build left an empty `.neuralmind/neuralmind_turbovec/store.sqlite`
next to the real index in `.neuralmind/neuralmind_db/`, and `doctor` called
that empty store "Index version compatible". Both checks now run only when
the project's backend is turbovec.

---

## What changed

### CLI

- **`neuralmind build` skips the turbovec check on other backends.** When
  `neuralmind-backend.yaml` sets `backend: graph`, `chroma`, `chromadb` or
  `in_memory`, the build no longer creates
  `.neuralmind/neuralmind_turbovec/store.sqlite`. If the project has never
  used turbovec, the `neuralmind_turbovec/` directory an earlier build left
  behind holds no vectors, and you can delete it.
- **`neuralmind doctor` says the check doesn't apply.** On those backends the
  *Turbovec compatibility* line reads
  `not applicable: the chroma backend keeps no turbovec index` (naming the
  configured backend), with status `ok`, instead of reporting an index that
  doesn't exist as compatible.
- **Turbovec projects are checked as before.** With no backend configured,
  or with `backend: turbovec`, `turboquant` or `auto`, a quarantined
  `index.tvim.stale` still makes `build` print its warning before embedding
  and makes `doctor` fail the check.

Both checks resolve the backend the same way `neuralmind build` does: the
`backend:` in `neuralmind-backend.yaml`, where `auto`, an empty value or no
file all mean turbovec.

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | No change | Same |
| **Cursor / Cline / Claude Desktop** (MCP) | No MCP tool changed | Same |
| **Generic MCP client** | No MCP tool changed | Same |
| **Agents that run the CLI** (Hermes skill, scripts) | On a ChromaDB or in-memory project, `doctor --json` reported `"Turbovec compatibility"` as `ok` with `"Index version compatible"`, and `build` created an empty turbovec store | The same check is `ok` with `"not applicable: the <backend> backend keeps no turbovec index"`, and `build` creates no turbovec store |

An agent that gates on `doctor --json`'s `status` sees no difference: the
check was `ok` before and is `ok` now. Only its `detail` text changed.

## Environment variables

None added or changed.

## Upgrade notes

None. No stored data changes shape, and no command takes new arguments.

## Related

- [CLI reference: doctor](../wiki/CLI-Reference.md#doctor-v0120)
- [v4.10.0 release notes](RELEASE_NOTES_v4.10.0.md)
