# Use Case: Offline / Regulated Work

## What you're solving for

You work in a regulated industry (healthcare, finance, defense, legal), on an air-gapped machine, or under a policy that forbids sending source code to third-party services. You still want AI-assisted code understanding — without the code leaving the building.

## Why NeuralMind fits

- **No API calls by default.** Indexing, embeddings, retrieval — all
  local. The one exception is opt-in and documented below.
- **No cloud account required.** No sign-up, no telemetry, no outbound
  network in the default configuration.
- **No code uploaded anywhere by the default path.** ChromaDB runs
  in-process. The one opt-in LLM path (below) is a narrower but real
  exception — read it before assuming "never."
- **Pairs with local LLMs.** Use with Ollama, llama.cpp, vLLM for an end-to-end local stack.

**The one opt-in exception — read the fine print.** Setting both
`NEURALMIND_LLM_SEED=1` and `ANTHROPIC_API_KEY` reads whatever bytes exist
at two fixed paths — `README.md` and `docs/architecture.md` relative to
the project root — and sends up to the first 8,000 characters (combined)
to Anthropic's API to seed synapse edges. **This is a path-based read, not
a content classifier:** the code does not verify the file is prose before
sending it. In the overwhelmingly common case these are ordinary
documentation files, but a `README.md` that embeds real code snippets,
API keys in example blocks, or internal architecture detail — or a
`README.md`/`docs/architecture.md` that is itself a symlink to something
else — would have that content sent unfiltered. If your policy prohibits
any client file reaching a third party regardless of its usual contents,
don't opt in, and audit what's actually at those two paths before you do.
Both env vars are unset by default; leave them unset and this path never
runs at all. Fail-open: any error returns `0` and never blocks indexing.
Full disclosure, code-cited:
[`docs/compliance/THIRD_PARTY_LLM_DISCLOSURE.md`](../compliance/THIRD_PARTY_LLM_DISCLOSURE.md).

## Fully local stack

```bash
pip install neuralmind
neuralmind build .              # local embeddings, local vector store
```

Pair with a local model:

```bash
# Example: Ollama + NeuralMind
ollama pull llama3.1:70b
CONTEXT=$(neuralmind query . "how does auth work?")
echo "$CONTEXT" | ollama run llama3.1:70b "Explain the auth flow"
```

Nothing here touches the public internet under the default configuration
(`NEURALMIND_LLM_SEED` unset, which it is unless you set it).

## Compliance-friendly properties

| Property | NeuralMind |
|---|---|
| Source code transmitted externally | Never, under the default configuration (both env vars unset) |
| Contents of `README.md`/`docs/architecture.md` transmitted externally | Only if you opt in with `NEURALMIND_LLM_SEED=1` + `ANTHROPIC_API_KEY` (both unset by default) — unfiltered, path-based, not verified to be prose-only; see [disclosure](../compliance/THIRD_PARTY_LLM_DISCLOSURE.md) before opting in |
| Telemetry | None |
| SaaS dependency | None |
| Account / login | None |
| Network required for install | Only to fetch the Python package — mirror it internally if needed |
| License | MIT (auditable) |
| Data at rest | `graphify-out/` and `.neuralmind/` inside your project |
| Data in transit | N/A under default configuration (no outbound calls) |

## Air-gapped install

1. On a connected machine:
   ```bash
   pip download neuralmind -d ./offline-bundle
   ```
2. Copy `./offline-bundle/` to the air-gapped machine.
3. Install:
   ```bash
   pip install --no-index --find-links ./offline-bundle neuralmind
   ```

ChromaDB pulls its embedding model on first use — download it in advance or point `HF_HOME` at a pre-populated directory.

## Turning off query memory (if your policy forbids local logs)

```bash
export NEURALMIND_MEMORY=0
export NEURALMIND_LEARNING=0
```

Or decline the TTY consent prompt the first time `neuralmind query` runs. No events are logged.

## Audit trail

Every action is a local file operation — easy to log via existing endpoint monitoring:

- Knowledge graph: `graphify-out/graph.json`
- Vector store: `graphify-out/neuralmind_db/`
- Query events (only if opted in): `.neuralmind/memory/query_events.jsonl`
- Learned synapse memory: `.neuralmind/synapses.db` (the Hebbian graph the synapse layer learns automatically from usage)

Delete any of these at any time — nothing persists outside your project.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
