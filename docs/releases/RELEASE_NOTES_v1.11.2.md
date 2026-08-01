# Release Notes — NeuralMind v1.11.2

**Release date:** 2026-08-02
**Type:** Patch (bug fixes from adversarial QA)
**Tests:** 17/17 document ingestion tests green

---

## What's Fixed

### Data Loss Bug
Same-named files in different directories (e.g. `specs/a/README.md` and `docs/b/README.md`) previously collided on the same node ID — one would silently overwrite the other. Now uses hashed parent path to disambiguate.

### Silent Retrieval Gap
BM25 keyword search was using code-style labels (`Entity: Gap Analysis`) instead of document text — so keyword queries for document content returned no results. Now uses `content_text` for document nodes.

### Latent Crash
Empty communities (edge case) crashed L2 context formatter with `UnboundLocalError`. Fixed by moving snippet display inside the loop.

### Security Hardening
Binary rejection (ELF/PE magic bytes) now applies regardless of `--type` flag — `--type pdf` can no longer bypass the binary guard. Root walk for project detection now caps at filesystem root.

### First-Query Sync
Ingested documents now appear immediately in first query (previously required a rebuild to show in BM25).

---

## Known Limitations

- PDF parsing requires `pdfplumber` (optional dependency)
- Audio/video ingestion out of scope
- `neuralmind learn` requires a build first (`neuralmind build .`)
- Large documents (>1MB) are chunked; very large chunk counts may impact query latency

---

## Upgrade

```bash
pip install --upgrade neuralmind
```

**Backward compatible:** Yes. Existing code graphs unchanged.
