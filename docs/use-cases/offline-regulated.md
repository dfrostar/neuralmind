# Use Case: Offline / Regulated Work

## What you're solving for

You work in a regulated industry (healthcare, finance, defense, legal), on an air-gapped machine, or under a policy that forbids sending source code to third-party services. You still want AI-assisted code understanding — without the code leaving the building.

## Why NeuralMind fits

- **No API calls.** Indexing, embeddings, retrieval — all local.
- **No cloud account required.** No sign-up, no telemetry, no outbound network.
- **No code uploaded anywhere.** ChromaDB runs in-process.
- **Pairs with local LLMs.** Use with Ollama, llama.cpp, vLLM for an end-to-end local stack.

## Fully local stack

```bash
pip install neuralmind graphifyy
graphify update .
neuralmind build .              # local embeddings, local vector store
```

Pair with a local model:

```bash
# Example: Ollama + NeuralMind
ollama pull llama3.1:70b
CONTEXT=$(neuralmind query . "how does auth work?")
echo "$CONTEXT" | ollama run llama3.1:70b "Explain the auth flow"
```

Nothing here touches the public internet.

## Compliance-friendly properties

| Property | NeuralMind |
|---|---|
| Source code transmitted externally | Never |
| Telemetry | None |
| SaaS dependency | None |
| Account / login | None |
| Network required for install | Only to fetch the Python package — mirror it internally if needed |
| License | MIT (auditable) |
| Data at rest | `graphify-out/` and `.neuralmind/` inside your project |
| Data in transit | N/A (no outbound calls) |

## Air-gapped install

1. On a connected machine:
   ```bash
   pip download neuralmind graphifyy -d ./offline-bundle
   ```
2. Copy `./offline-bundle/` to the air-gapped machine.
3. Install:
   ```bash
   pip install --no-index --find-links ./offline-bundle neuralmind graphifyy
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
- Learned patterns (only after `neuralmind learn`): `.neuralmind/learned_patterns.json`

Delete any of these at any time — nothing persists outside your project.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
