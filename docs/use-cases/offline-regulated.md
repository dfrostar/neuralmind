# Running NeuralMind in Regulated Industries

For teams in healthcare, finance, defense, legal, or any environment where
code cannot leave the building. This document pairs with
[COMPLIANCE-SUMMARY.md](../COMPLIANCE-SUMMARY.md) — that document is the
one-pager for auditors; this one expands on operational considerations for
regulated deployments.

---

## Why local-first matters

NeuralMind never transmits code, embeddings, or queries outside the host
machine. Implications by vertical:

- **Defense / classified** — air-gapped deployment is a documented posture,
  not a workaround (see [`use-cases/air-gapped.md`](air-gapped.md)).
- **Healthcare (HIPAA)** — no external entity receives PHI-referencing data;
  the operator remains the sole data controller.
- **Finance (SOX/PCI)** — audit trail is local and append-only; no
  third-party processor to audit or notify on breach.

Code containing comments with PII (commit hashes in comments, emails in
headers) stays local. NeuralMind does not act as a data processor under
GDPR — there is no external entity to which data is transferred.

## Deployment patterns

All four postures documented in [COMPLIANCE-SUMMARY.md](../COMPLIANCE-SUMMARY.md)
apply. Typical regulated deployment:

```bash
# On a connected machine
pip download neuralmind -d ./offline-bundle
# Transfer to air-gapped machine
pip install --no-index --find-links ./offline-bundle neuralmind
neuralmind build .              # local embeddings, local vector store
```

Pair with local LLMs (Ollama, llama.cpp, vLLM) for an end-to-end stack
that never touches a hybrid or public cloud.

## Data residency & GDPR

- **Lawful basis** — operator-controlled.
- **Data minimisation** — retrieval returns ~800 tokens of context per
  query, not the full codebase.
- **Storage limitation** — synapse store decays unused edges (configurable
  via `NEURALMIND_SYNAPSE_DECAY_HALF_LIFE`).
- **Right to erasure** — `rm -rf .neuralmind/` is a complete erasure path.
- **Breach notification** — no external surface area, no third-party
  processor to notify.

Full mapping: [COMPLIANCE-SUMMARY.md](../COMPLIANCE-SUMMARY.md).

## Audit trail — capabilities and limitations

| Capability | OSS (MIT) | Commercial |
|---|---|---|
| Local audit log (`.neuralmind/audit_events.jsonl`) | ✅ shipped | ✅ shipped |
| Query provenance (trace to code nodes) | ✅ shipped | ✅ shipped |
| Centralized log shipping | ❌ not available | ✅ roadmap (commercial module) |
| Admin console log viewer | ❌ roadmap | ✅ roadmap |

OSS ships local JSONL only. If your compliance regime requires centralized
log aggregation (typical for SOC 2 Type II), that capability is a
commercial module, not yet shipped.

## Known gaps for regulated use

| Gap | Status |
|---|---|
| SOC 2 certification | Architecture supports certification; not certified today. See [COMPLIANCE-SUMMARY.md](../COMPLIANCE-SUMMARY.md). |
| Admin console (RBAC, audit viewer) | Roadmap commercial module, not shipped. |
| Air-gap validation (`tcpdump` proof) | On the validation checklist since v0.9.0; not yet executed on isolated hardware. |
| Formal HIPAA BAA | Available under commercial engagement only. |

---

**Evaluating NeuralMind for a regulated environment?** We offer a free
AI-spend assessment — we benchmark NeuralMind against one of your repos and
report your actual token-reduction ratio, then advise honestly on fit
(including when *not* to deploy). See [ASSESSMENT.md](../ASSESSMENT.md) for
details and how to book.
