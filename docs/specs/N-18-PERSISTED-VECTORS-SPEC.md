# N-18 Persisted Vectors — Embedder-Free Index Recovery from 1M Documents Up

**Status:** PROPOSED (decision record + spec), revision 1
**Date:** 2026-10-08
**Baseline:** v4.11.0 (`main` @ `ed66521`). Every `file:line` below was checked against that commit.
**Decision owner:** NeuralMind maintainers.
**Depends on:** [`N-17-RETRIEVAL-RESILIENCE-SPEC.md`](N-17-RETRIEVAL-RESILIENCE-SPEC.md): its R6.3 chunked recovery writer, its R3.1 index-health states, and its scale tiers T0–T3 (§6.1).
**Supersedes:** N-17 R7 and AC20, which were split out of N-17 into this document. N-17 keeps both IDs as pointers here.

> **Scope note.** This spec decides **whether and how NeuralMind persists embedding vectors** so a lost or incompatible vector index can be rebuilt without re-running the embedder. It does not change retrieval ranking (N-15) or the turbovec format (upstream).

### Conventions

The same conventions as N-17 apply:
- **RFC 2119 / 8174 key words.** These carry their normative meaning in §5 only, and only in uppercase.
- **Stable IDs.** IDs are prefixed `N18-`, so they cannot collide with N-17's.
- **Evidence grades.** Every figure is tagged **measured**, **derived** or **projected**, as N-17 defines them. Measurements here were taken on a 4-vCPU / 15 GB Linux container, Python 3.13, turbovec 1.1.2, `bit_width=4`, 384-dim vectors. The scripts are in Appendix A.

This document is shaped as an architecture decision record (context → drivers → options → decision → consequences → confirmation), followed by the normative requirements and acceptance criteria that implement the decision.

---

## 1. Context and problem statement

NeuralMind's SQLite store (`store.<scope>.sqlite`) keeps each node's `document` text (`turbovec_backend.py:167-186`) but not its vector. The only copy of the vectors is the quantized turbovec index (`index.<scope>.tvim`). When that index becomes unusable (a turbovec version bump, corruption, a partial write), every recovery path rebuilds it by **re-running the embedder** over the whole store (`_rebuild_index_from_store`, `turbovec_backend.py:465-523`; N-17 §2).

The cost of that grows with corpus size (N-17 §2.2–§2.3):

| Tier | Documents | Re-embed recovery at 27 docs/s *(derived)* | Rebuild from stored float16 vectors |
|---|---:|---:|---:|
| T1 | 100k | ≈ 1 h | — |
| T2 | 1M | ≈ 10 h | **6.1 s** *(measured, warm page cache)* |
| T3 | 10M | ≈ 4.3 days | ≈ 1–2.5 min *(projected: 10× the 1M figure, up to the 148 s full-index build N-17 measured)* |

N-17 R6 makes the slow path *safe*: off the read path, checkpointed, resumable, locked and visible. It cannot make it *fast*. Above 1M documents, re-embedding is not a viable recovery, so an index that a routine `pip install -U turbovec` invalidates costs the user a day or more of CPU time.

The quantized index cannot rescue itself. Its 4-bit codes are lossy and are exactly the artefact that became unreadable, so the full-precision vectors have to be kept somewhere else.

## 2. Decision drivers

| # | Driver |
|---|---|
| D1 | **Recovery time at T2/T3:** recovery should take minutes, not hours or days. |
| D2 | **Retrieval quality:** results must not get worse (§N18-R4). |
| D3 | **Disk cost:** an extra 0.5–1.5 KB per row has to be justified, and users need a way to opt out. |
| D4 | **Crash consistency:** a vector must never be attached to the wrong row, and an interrupted write must not poison the store. |
| D5 | **Embedder changes:** vectors from one model must never be mixed with another model's (`NEURALMIND_ONNX_MODEL_DIR` lets a user swap the model; `onnx_embedder.py:18`). |
| D6 | **Per-query cost:** the store scans N-17 R3.3 relies on must not get slower. |
| D7 | **Privacy surface:** nothing new may leave `.neuralmind/` (team-memory bundles, `neuralmind memory publish`). |

## 3. Considered options

| Option | Recovery at 1M | Disk at 1M / 10M | Quality | Notes |
|---|---|---|---|---|
| **A.** Status quo + N-17 R6 (re-embed, made safe) | ≈ 10 h *(derived)* | 0 | unchanged | Fails D1. This is today's behaviour, with N-17's known gap. |
| **B.** float32 vectors in a new BLOB column of `nodes` | seconds | 1.5 GB / 15 GB | identical | Doubles the SQLite pages that every full scan (N-17 R3.3, `doctor --deep`) reads, so it fails D6. Simple and transactional with the row (D4). |
| **C.** float16 vectors in a BLOB column of `nodes` | seconds | 0.77 GB / 7.7 GB | top-10 overlap 0.992 vs float32 *(measured, synthetic)* | Half of B's cost but the same D6 problem. Transactional (D4). |
| **D.** float16 vectors in an append-only, memory-mapped sidecar file (`vectors.<scope>.f16`), addressed by row offset | **6.1 s** *(measured)* | 0.77 GB / 7.7 GB | as C | Keeps SQLite pages small (D6). Recovery reads sequentially. Needs its own consistency protocol (N18-R3). |
| **E.** Keep a backup copy of the previous `.tvim` | — | ≈ 0.2 GB / 2 GB | unchanged | Does not help: a version-incompatible backup is just as unreadable, and quantized codes cannot be re-imported. Rejected. |
| **F.** Parallelise the embedder only | ≈ 2.5–3 h on 4 cores *(derived, assumes linear scaling)* | 0 | unchanged | Divides the hours but cannot reach minutes (D1). Worth doing on its own; out of scope here (N-17 R6.7). |

## 4. Decision outcome

**Proposed: Option D**, float16 vectors in an append-only memory-mapped sidecar. Two conditions:

1. **Gate on recall.** If the real-embedding recall check (N18-AC4) shows that float16 lowers retrieval quality, switch the sidecar's dtype to float32. The cost is doubled disk (1.5 GB per million documents); the design is otherwise unchanged.
2. **Fallback to C.** If the sidecar's consistency protocol (N18-R3) proves too costly to make crash-safe on Windows file semantics, fall back to Option C and accept the D6 cost. Mitigate that cost by moving the per-query count to N-17's `vectorizable_rows` counter, which already avoids the scan.

Rationale: D is the only option that meets D1 and D6 together, and it is the cheapest storage that meets D2 on the evidence so far. C is the same idea with a simpler consistency story, which is why it is the named fallback.

### 4.1 Consequences

**Positive**
- Recovery from any `unloadable` state at T2/T3 takes seconds to minutes, with zero embedder calls (N18-AC1, AC2).
- turbovec upgrades stop being expensive events, so the version-mismatch path in N-17 R5 becomes routine.
- Changing turbovec's `bit_width`, or any other index parameter, becomes a cheap rebuild instead of a re-embed.

**Negative**
- Extra disk: 768 B per row. That is 0.77 GB at 1M and 7.7 GB at 10M, on top of the ≈1 GB / 10 GB store.
- A second file to keep consistent with SQLite (N18-R3).
- A legacy store has no vectors. Its first recovery after upgrading still re-embeds once, while it back-fills the sidecar (N18-R5).

**Neutral**
- Query results are unchanged by construction. Search never reads the sidecar; only index (re)builds do.

### 4.2 Confirmation

The decision is confirmed when all of the following pass at T2 and T3: N18-AC1 (zero embedder calls), N18-AC2 (time budget), N18-AC4 (recall gate) and N18-AC6 (crash-consistency fuzz). Until then the status stays PROPOSED.

---

## 5. Requirements

**N18-R1 — Embedder-free recovery.** When a persisted vector exists for every row, recovery from the `unloadable` and `inconsistent` states (N-17 R3.1) MUST rebuild the index from persisted vectors and MUST NOT call the embedder. Rows without a valid persisted vector MUST be re-embedded through N-17 R6 (diff, checkpointed, locked) and back-filled.

**N18-R2 — Write at embed time.** Every vector produced by `embed_nodes`, `embed_content` or recovery MUST be persisted in the same chunk that adds it to the index. A second embedding pass is never needed. Removing a row (`delete_nodes`) MUST mark its vector slot dead. Compaction MAY reclaim dead slots during a rebuild.

**N18-R3 — Crash consistency.** The sidecar and the store MUST never disagree silently:
- The sidecar header MUST record the format version, dtype, dimension, and the embedder identity (N18-R6).
- Each row's sidecar offset MUST be written to SQLite only **after** the vector bytes are flushed (`fsync` or platform equivalent). A crash therefore leaves at worst an orphaned tail in the sidecar, never a row pointing at missing bytes.
- On open, any offset beyond the sidecar's valid length, and any header mismatch, MUST be treated as "no persisted vector" for the affected rows. Those rows are re-embedded through N18-R1, not trusted.

**N18-R4 — No quality regression.** Retrieval quality on the `neuralmind benchmark --quality` suites MUST NOT drop when the index is built from float16 vectors rather than float32 vectors (N18-AC4). Healthy-index `query` output MUST stay byte-identical to the same build without N-18 (N-17 §6 regression guard).

**N18-R5 — Legacy stores.** A store written before N-18 MUST keep working with no migration step. Its first index rebuild back-fills the sidecar. `doctor` MUST report `vectors: not persisted (next recovery re-embeds N documents, ≈<estimate>)` until the back-fill completes, so an operator at T2/T3 can schedule the one-time cost.

**N18-R6 — Embedder identity.** Persisted vectors MUST be keyed by the embedder that produced them: the model name plus the SHA-256 of `model.onnx` for the default embedder, or an injected embedder's declared identity. A mismatch with the active embedder MUST invalidate the whole sidecar for recovery purposes, and `doctor` MUST say so. Mixing vectors from different models in one index is never allowed.

**N18-R7 — Opt-out and visibility.** Persistence SHOULD be on by default. `NEURALMIND_PERSIST_VECTORS=0` MUST disable it and fall back to N-17 behaviour. The new env var ships with its docs surfaces per `CLAUDE.md`'s shipping checklist. `doctor` and `stats` MUST report the sidecar's size and the fraction of rows with valid vectors.

**N18-R8 — Stays local.** The sidecar MUST live under `.neuralmind/` beside the store. It MUST be excluded from `neuralmind memory publish` and any team-memory bundle, and MUST be covered by the same ignore rules as the store.

## 6. Acceptance criteria

| ID | Criterion | Grade of evidence it produces |
|---|---|---|
| N18-AC1 | At T2 and T3, recovery from `unloadable` with a complete sidecar makes **zero** embedder calls. *(Formerly N-17 AC20, first half.)* | measured |
| N18-AC2 | At T2 and T3, that recovery completes within 2× the tier's sidecar-rebuild baseline in `bench/scale/results.json`. *(Formerly N-17 AC20, second half.)* | measured |
| N18-AC3 | A store with vectors for 90% of rows re-embeds exactly the missing 10% and back-fills them (N18-R1, R5). | measured |
| N18-AC4 | On every `neuralmind benchmark --quality` suite, MRR and Recall@5 for an index built from float16 vectors are ≥ the float32-built values, within the suite's published run-to-run spread. If this fails, the sidecar dtype becomes float32 (§4). | measured |
| N18-AC5 | Changing the active embedder (a different `model.onnx`) invalidates the sidecar. The next recovery re-embeds, and `doctor` names the mismatch (N18-R6). | measured |
| N18-AC6 | Crash fuzz: kill the writer at random points across ≥ 1,000 runs. Every reopen yields either a correct vector or "no persisted vector" for each row, never a wrong vector (N18-R3). Runs on Linux, macOS and Windows CI. | measured |
| N18-AC7 | With `NEURALMIND_PERSIST_VECTORS=0`, no sidecar is created, and behaviour matches N-17 exactly (N18-R7). | measured |
| N18-AC8 | `neuralmind memory publish` output contains no sidecar bytes or paths (N18-R8). | measured |
| N18-AC9 | Healthy-index `query` output is byte-identical with and without N-18 (N18-R4). | measured |

### 6.1 Traceability

| Requirement | Drivers | Verified by |
|---|---|---|
| N18-R1 | D1 | AC1, AC2, AC3 |
| N18-R2 | D1, D4 | AC3, AC6 |
| N18-R3 | D4 | AC6 |
| N18-R4 | D2 | AC4, AC9 |
| N18-R5 | D1, D3 | AC3 |
| N18-R6 | D5 | AC5 |
| N18-R7 | D3 | AC7 |
| N18-R8 | D7 | AC8 |

## 7. Test and measurement plan

- **Tiers.** Reuse N-17 §6.1: T0/T1 on every PR with a fake embedder, T2 nightly, T3 weekly and before each release. Sidecar size, rebuild time and peak RSS are added to `bench/scale/results.json`.
- **Recall gate (AC4).** Use the real ONNX embedder on the existing `benchmark --quality` suites, which are small enough to embed in CI. The synthetic result in §3 (top-10 overlap 0.992; recall@10 0.835 vs 0.837) only motivates the default. It does not satisfy AC4.
- **Crash fuzz (AC6).** Use a subprocess writer killed with `SIGKILL` (or `TerminateProcess` on Windows) at random byte offsets, followed by the N18-R3 open-time validation.
- **Cold-cache rebuild.** The 6.1 s figure in §1 was taken with a warm page cache. T2/T3 MUST also record a cold-cache rebuild (drop caches, or use a fresh runner) so AC2's baseline is not flattered.

## 8. Delivery

| PR | Contents | Requirements |
|---|---|---|
| 1 | Sidecar format + writer + open-time validation, behind `NEURALMIND_PERSIST_VECTORS` (default **off**) | N18-R2, R3, R6, R8; AC5, AC6, AC8 |
| 2 | Embedder-free recovery path + back-fill + `doctor`/`stats` reporting | N18-R1, R5, R7; AC1–AC3, AC7 |
| 3 | Recall gate; then flip the default to **on** and ship the docs surfaces | N18-R4; AC4, AC9 |

Every PR depends on N-17 PR 3 (chunked recovery writer) and N-17 PR 6 (tier workflows). The default stays off until PR 3's recall gate passes.

## 9. Open questions

| # | Question | Resolves by |
|---|---|---|
| Q1 | Does float16 hold recall on real embeddings, not just synthetic ones? | N18-AC4 |
| Q2 | Is a memory-mapped append-only file crash-safe enough on Windows (no `fsync` equivalent on mapped views without `FlushFileBuffers`)? If not, choose fallback C. | N18-AC6 on Windows CI |
| Q3 | What is the cold-cache rebuild time at 10M on the T3 runner? This replaces the projected row in §1. | first T3 run |
| Q4 | Should `bit_width` changes (2-bit for smaller indexes) become a supported user setting once rebuilds are cheap? | separate proposal |

## 10. Revision history

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-10-08 | Split out of N-17 (its R7 and AC20). Written as a decision record with options A–F. Proposed D (float16 sidecar) on measured 1M rebuild and synthetic recall figures. |

---

## Appendix A — reproducing §1 and §3

```python
import os, sys, time, numpy as np, turbovec
d, out, n, C = 384, sys.argv[1], int(sys.argv[2]), 100_000
p, rng = os.path.join(out, "vec.f16"), np.random.default_rng(1)
mm = np.lib.format.open_memmap(p, mode="w+", dtype=np.float16, shape=(n, d))
for s in range(0, n, C):                                   # write the sidecar in chunks
    x = rng.standard_normal((C, d)).astype(np.float32)
    mm[s:s + C] = (x / np.linalg.norm(x, axis=1, keepdims=True)).astype(np.float16)
mm.flush(); del mm
t = time.perf_counter()                                    # rebuild the index from it
mm, idx = np.load(p, mmap_mode="r"), turbovec.IdMapIndex(dim=d, bit_width=4)
for s in range(0, n, C):
    idx.add_with_ids(np.ascontiguousarray(mm[s:s + C], dtype=np.float32),
                     np.arange(s + 1, s + C + 1, dtype=np.uint64))
idx.prepare()
print(f"rebuild from f16 sidecar: {time.perf_counter() - t:.1f}s, "
      f"size={os.path.getsize(p) / 1e6:.0f}MB")
```

Recall comparison: build two 4-bit indexes over the same 100k unit vectors, one from float32 and one from float16-rounded copies. Run 200 noisy queries and compare each index's top-10 with the other's and with exact cosine top-10.
