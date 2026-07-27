# Data Deletion Procedure

**Date:** 2026-07-27
**Version:** 1.0
**SOC 2 Control:** P3.1

---

## 1. Purpose

Define how to completely delete all NeuralMind data from a project.

## 2. Scope

All NeuralMind data in a project:
- `.neuralmind/` (synapse store, audit logs, caches, IR)
- `graphify-out/` (vector index, graph)
- `.neuralmind-team-memory.json` (committed team memory)
- `.neuralmind/hooks/` (installed git hooks)

## 3. Deletion Procedure

### 3.1 Complete Deletion

```bash
# Remove all NeuralMind data from current project
rm -rf .neuralmind/
rm -rf graphify-out/
rm -f .neuralmind-team-memory.json
```

### 3.2 Selective Deletion

```bash
# Remove only synapse store (keep index)
rm -f .neuralmind/synapses.db

# Remove only audit logs
rm -f .neuralmind/audit_events.jsonl

# Remove only team memory bundle
rm -f .neuralmind-team-memory.json

# Remove only hooks
rm -rf .neuralmind/hooks/
```

### 3.3 Verification

After deletion:
```bash
# Should return nothing
ls -la .neuralmind/ 2>/dev/null
ls -la graphify-out/ 2>/dev/null
ls -la .neuralmind-team-memory.json 2>/dev/null
```

## 4. Recovery

NeuralMind data can be rebuilt:
- Index: `neuralmind build .`
- Synapses: re-learn from usage (no backup needed)
- Team memory: re-import from teammate's clone

## 5. Audit Trail

Deletion events are NOT logged (the act of deletion removes the log). This is acceptable because:
- Deletion is user-initiated
- No external party is affected
- Git history preserves code (not data)

---

*This procedure is reviewed annually. Last reviewed: 2026-07-27.*
