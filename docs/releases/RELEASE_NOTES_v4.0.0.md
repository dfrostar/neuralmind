# Release Notes — NeuralMind v4.0.0

**Release Date:** 2026-09-16  
**License:** MIT  
**Compare:** [v3.13.0 → v4.0.0](https://github.com/dfrostar/neuralmind/compare/v3.13.0...v4.0.0)

---

## What's New

### Lean-Context-Inspired Memory Modules (v3.13.0 → v4.0.0)

Five new modules built from lean-ctx patterns:

| Module | Purpose | Status |
|--------|---------|--------|
| **context_budget** | Fixed token budget with L3→L2→L1→L0 progressive trimming | ✅ Shipped |
| **session_summaries** | Periodic semantically-recallable digests of agent sessions | ✅ Shipped |
| **graph_traversal** | Learned co-access edges that strengthen with use | ✅ Shipped |
| **read_dedup** | Content-hash dedup + LRU cache eliminates redundant reads | ✅ Shipped |
| **cognition_loop** | Background knowledge consolidation: reinforce, decay, promote, prune | ✅ Shipped |

### Medical Retriever Integration

`NeuralMind.query()` now routes prose/book projects to a specialized BM25 + terminology-expansion retriever. Enables peptide-book, clinical-manuscript, and long-form prose indexing alongside code.

### Compliance Hardening

- Stopped parsing version strings and SVG paths as SOC 2 controls ([#453](https://github.com/dfrostar/neuralmind/issues/453))
- Annotation engine stability for CMMC/NIST/SOX/HIPAA marker scanning

### Site + Marketing

- Proof section on homepage (honest benchmark, every miss published)
- "Measure Your Own" page: `neuralmind benchmark .` on your own repo
- llms.txt (correctly returns 404 — Google doesn't use it)
- robots.txt allows all AI crawlers

---

## Benchmarks (Reproducible)

| Metric | Value | Command |
|--------|-------|---------|
| Gold-file recall | **93.75%** mean / 79–100% per repo | `python -m evals.public.run` |
| Token reduction vs pasting | **45–257×** | Same |
| Requests backend | **45.7×** fewer tokens | Same |
| Click backend | **107.7×** fewer tokens | Same |

**Benchmark is reproducible:**
```bash
pip install neuralmind && python -m evals.public.run
```

Every miss is published. No cherry-picking.

---

## Upgrade Notes

**No breaking changes.** Existing NeuralMind users:
```bash
pip install --upgrade neuralmind
neuralmind wakeup .   # picks up new modules automatically
```

Memory layer (decision storage + commit-level invalidation) is **not** in this release — it's the next build target per the Memory Layer spec.

---

## Assets

- `neuralmind-4.0.0-py3-none-any.whl`
- `neuralmind-4.0.0.tar.gz`
- SBOM: `neuralmind-v4.0.0.sbom.json`

---

**Full Changelog**: [CHANGELOG.md](https://github.com/dfrostar/neuralmind/blob/main/CHANGELOG.md)
