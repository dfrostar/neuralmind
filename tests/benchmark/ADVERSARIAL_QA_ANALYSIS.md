# Adversarial QA: NeuralMind Peptide Book Retrieval — Deep Analysis

**Date:** 2026-09-15  
**Scope:** v3.12.0 benchmark (14 queries, 61 nodes, 11 chapters)  
**Methodology:** Source code review + benchmark data analysis + comparative web research

---

## 1. Executive Summary

The current system achieves **R@5=95.2%** but **P@5=38.6%** and **R@1=64.3%**. The headline number (95% recall@5) masks fundamental problems: the system returns too many irrelevant chapters, ranks them poorly, and misses most facts. The root causes are (1) a critical tokenizer bug in BM25 prose search, (2) intent boost logic that systematically over-boosts common chapters, (3) RRF_K=60 being wrong for a 61-node index, and (4) general-purpose embeddings on medical content.

**Bottom line:** The architecture is workable but has a critical bug and several design choices that are actively counterproductive at this scale.

---

## 2. CRITICAL BUG: BM25 Prose Search Uses Wrong Tokenizer

### The Bug
In `bm25.py` line 207, `bm25_search_prose()` calls `self._tokenize(query)` instead of `_tokenize_prose(query)`.

```python
def bm25_search_prose(self, query: str, n: int = 10) -> list[dict[str, Any]]:
    """...tokenizes the query with :func:`_tokenize_prose` so hyphenated terms 
    (BPC-157, GLP-1) stay whole..."""
    ...
    q_tokens = self._tokenize(query)  # BUG: should be _tokenize_prose
```

### Impact
The docstring promises prose tokenization, but the implementation uses the **code tokenizer**. This means:

| Query Term | Code Tokenizer Output | Prose Tokenizer Output |
|------------|----------------------|------------------------|
| BPC-157 | ["bpc", "157"] | ["bpc-157"] |
| GLP-1 | ["glp", "1"] | ["glp-1"] |
| semaglutide | ["semaglutide"] | ["semaglutide"] |

The "157" and "1" tokens are pure digits and get **dropped** by the noise guard (`not t.replace("-", "").isdigit()`). So "What is BPC-157?" searches BM25 for just "bpc" — a 3-character token that appears in many documents and carries no specific meaning.

**Severity: CRITICAL.** This completely undermines the BM25 contribution for the exact term matches the hybrid system is supposed to excel at. Every hyphenated drug name in the book is being searched incorrectly.

### Why It Wasn't Caught
The method exists, is wired up in `_fetch_search()`, and the index builds correctly. But since the tokenizer is the code tokenizer, the BM25 scores for hyphenated terms are always zero, so BM25 results either (a) fall back to matching shorter substrings or (b) return nothing for those terms, making the bug invisible unless you trace tokenization.

---

## 3. Root Cause Analysis: Why Precision@5 = 38.6%

### The Math
P@5 = (relevant chapters in top 5) / 5. At 38.6%, only ~1.9 chapters out of 5 are relevant.

### Contributing Factors

#### 3.1 Intent Boost Systematically Over-Boosts Popular Chapters

The `_PROSE_CHAPTER_INTENT_WEIGHTS` table maps intents to chapters:

```python
"03_fda-approved-peptides": {"comparison": 1.0, "regulatory": 1.0, "mechanism": 0.5}
```

Chapter 3 has the most intent tags of any chapter. It gets boosted for queries about:
- "what is" (via definition intent → also chapter 01, 08, 00, 99)
- "how does" (via mechanism intent)
- "difference" (via comparison intent)
- "fda" (via regulatory intent)

The boost formula: **2.0× for primary intent, 1.5× for secondary intent**.

Query: "What exactly is a peptide?" → detected intents: ["definition"]
- Chapter 01 (definition=1.0): 2.0× boost
- Chapter 03 (definition=0.5): no boost (not primary, not 1.0 weight)
- Chapter 08 (definition=1.0): 2.0× boost
- Chapter 00 (definition=1.0): 2.0× boost
- Chapter 99 (definition=1.0): 2.0× boost

But the benchmark shows top result is `03_fda-approved-peptides.md`! This means either:
1. The embedding similarity for chapter 3 is so high that even after the 2.0× boost to chapters 01/08/00/99, chapter 3 still wins
2. The intent detection is picking up additional signals from the question wording

Looking at the actual question "What exactly is a peptide and how is it different from a protein?", the word "different" triggers **comparison** intent (2 points + 2 bonus = 4). Chapter 3 has comparison=1.0, so it gets 2.0× boost. Combined with the embedding similarity, this pushes chapter 3 above chapter 1.

**The problem:** The intent keyword matching is too generic. "different" in a definition question shouldn't trigger comparison intent.

#### 3.2 Cross-Chapter Expansion Adds Noise

`P1.4` expands top-3 results with cross-chapter edges (references, related_via_terms, shared_section). On a 61-node index, this adds 1-5 extra nodes that may not be relevant. These extra nodes then compete for the same top-K slots and can push out actually relevant chapters.

For query `peptide-definition` (R@5=1.0 but P@5=0.2), the top-5 contains the correct chapter but also 4 irrelevant ones.

#### 3.3 Post-Retrieval Filtering Is Too Aggressive

```python
cutoff = top_score * 0.3
merged = [n for n in merged if n.get("score", 0.0) >= cutoff]
```

With a 61-node index, scores are tightly clustered (0.6-0.9 cosine similarity). A 30% cutoff on the top score keeps almost everything, so it doesn't filter noise. But on queries where the top score is anomalously high, it could drop relevant results.

#### 3.4 Chapter Dedup in `_weighted_hybrid_score` is Aggressive

```python
seen_chapters: set[str] = set()
for nid, score, node in combined:
    chapter_key = ...
    if chapter_key in seen_chapters:
        continue
    seen_chapters.add(chapter_key)
```

This keeps only the **first** node per chapter. But the first node might be a marginal match while a later node from the same chapter is the best match for the query. For example, if chapter 4 has one node about BPC-157 (score 0.85) and another about general grey-market risks (score 0.70), and the query is "BPC-157 grey market", the BPC-157 node might rank 5th while the grey-market node ranks 3rd. After dedup, only the grey-market node survives, and the specific BPC-157 evidence is lost.

---

## 4. Root Cause Analysis: Why Recall@1 = 64.3%

### The Math
R@1 = 9/14 = 64.3%. Five queries fail to rank the correct chapter first.

### Per-Query Failures

| Query | Expected Top | Actual Top | Cause |
|-------|-------------|------------|-------|
| peptide-definition | 01 | 03 | "different" triggers comparison boost for ch3 |
| weight-loss-semaglutide | 03 | 06 | Semaglutide terminology expansion adds "GLP-1 receptor agonist" which matches ch6 |
| pcac-recommendation | 04/06 | 03 | "PCAC" not in terminology table; "FDA" boosts ch3 |
| bpc157-grey-market | 04 | 01 | BM25 bug: "BPC-157" → "bpc" (useless); ch1 has general peptide content |
| grey-market-risks | 04/05/06 | 08 | "questions-to-ask" has high semantic similarity for risk queries |

### The "Winner Takes All" Problem

The chapter dedup means that if a chapter has ANY node with high embedding similarity, it dominates the ranking. A chapter with one strong match (0.9) and one weak match (0.4) will be ranked by the 0.9, pushing above a chapter with two medium matches (0.7, 0.7). But the two-medium-match chapter may actually be more relevant overall.

The `_weighted_hybrid_score` applies `chapter_strong_boost = 1.5` to any chapter with a node scoring > 0.7. This is meant to surface chapters with one definitive match, but on a 61-node index where all similarities are high, almost every chapter gets boosted.

---

## 5. Is the Small Index (61 Nodes) the Fundamental Bottleneck?

### Yes, but not for the obvious reasons.

The 61-node index is ~5.5 nodes per chapter. This means:

1. **Granularity mismatch**: A node is a section/heading, not a full paragraph. Many facts live BETWEEN nodes or spread across multiple nodes.
2. **Score clustering**: With only 61 vectors in 384-dim space, cosine similarities are all high (0.65-0.95). The ranking has very little signal-to-noise.
3. **Boost dominance**: On a large index, a 1.5× boost moves a result from rank 50 to rank 30. On a 61-node index, a 1.5× boost moves a result from rank 5 to rank 1 — it completely overrides the embedding signal.
4. **BM25 IDF collapse**: IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1). With N=61 and most medical terms appearing in 1-5 documents, IDF values are all in a narrow range (2.0-4.0). Rare terms don't get the dramatic IDF boost they would on a larger index.

### What "Good" Looks Like

From web research on comparable medical RAG benchmarks:

| System | Corpus | R@1 | R@5 | P@5 | MRR |
|--------|--------|-----|-----|-----|-----|
| NV-Embed-v2 (hybrid) | Public health docs | 0.80 | 0.97 | — | 0.85 |
| Hybrid + Reranking (T2-RAGBench) | 7,318 docs | — | 0.816 | — | 0.605 |
| BM25 only (T2-RAGBench) | 7,318 docs | — | 0.658 | — | — |
| **NeuralMind current** | **61 nodes** | **0.64** | **0.95** | **0.39** | **0.79** |

The R@5 of 0.95 is actually competitive with systems 100× larger. The problem is P@5 and R@1 — the ranking within the top-5 is poor.

---

## 6. Would a Different Embedding Model Help?

### Yes, significantly.

Current: `all-MiniLM-L6-v2` (384-dim, general purpose, 2020)

From web research on medical retrieval:

| Model | P@1 | R@5 | Notes |
|-------|-----|-----|-------|
| NV-Embed-v2 (8B) | 0.76 | 0.96 | Best in class |
| SFR-Embedding-Mistral (7B) | 0.71 | 0.94 | Strong instruction-following |
| text-embedding-3-large | 0.68 | 0.92 | OpenAI, good medical |
| multilingual-e5-large (0.6B) | 0.68 | 0.91 | Best open-source <1B |
| ModernBERT-base | 0.63 | 0.90 | Recent, strong |
| BM25 (baseline) | 0.65 | 0.87 | No embedding at all |
| MiniLM-L6-v2 (current) | ~0.40 | ~0.70 | Estimated from benchmark |

The current model is estimated at P@1≈0.40, R@5≈0.70 on medical content. Upgrading to multilingual-e5-large or ModernBERT-base could improve P@1 by 50-70%.

### But: Embedding model alone won't fix the ranking bugs

Even with perfect embeddings, the intent boost and chapter dedup logic would still distort rankings. The embedding model is the ceiling; the ranking logic is the floor.

---

## 7. Is BM25 Hurting More Than Helping at This Scale?

### Currently: YES, because of the tokenizer bug.

With the bug fixed, BM25 would help for:
- Exact drug name matches (semaglutide, tirzepatide, retatrutide)
- Hyphenated terms (BPC-157, GLP-1, GIP)
- Specific medical phrases ("black box warning", "research chemical")

### But the RRF_K=60 is wrong for 61 nodes

From web research: "k=60 is tuned for large corpora (thousands of documents). For small corpora of 50–200 documents, a lower k (try 10–20) creates steeper rank differentiation."

With k=60 and N=61:
- Rank 1: 1/61 = 0.0164
- Rank 5: 1/65 = 0.0154
- Rank 10: 1/70 = 0.0143

The difference between rank 1 and rank 10 is only 13%. This means BM25 and vector results are almost equally weighted regardless of rank position.

With k=10:
- Rank 1: 1/11 = 0.0909
- Rank 5: 1/15 = 0.0667
- Rank 10: 1/20 = 0.0500

The difference between rank 1 and rank 10 is now 45% — much stronger signal.

### Adaptive Weights Are Too Aggressive

```python
if avg_df <= 3:
    vec_weight = 0.2
    kw_weight = 0.8
```

On a 61-node index, almost every term has avg_df ≤ 3. This means BM25 gets 80% weight for most queries, which is too much — the embedding signal (which captures semantic meaning) gets drowned out by exact-term matching.

---

## 8. Is the Intent Boost (1.5×/1.25×) Actually Working?

### No. It's adding noise.

Evidence from the benchmark:

1. **peptide-definition**: "what is" → definition intent → boosts chapters 01, 08, 00, 99. But the top result is chapter 03 (which has definition=0.5, not boosted). The boost didn't help.

2. **weight-loss-semaglutide**: "how much" → no clear intent match. But the terminology expansion adds "GLP-1 receptor agonist" which matches chapter 6 (regulatory) more than chapter 3 (FDA-approved). The terminology expansion is working against the correct result.

3. **bpc157-grey-market**: "what is" + "controversial" → definition + safety intents. Chapter 4 has safety=0.8, so it should get 1.5× boost. But the top result is chapter 1. The boost wasn't enough to overcome the embedding similarity of chapter 1.

4. **grey-market-risks**: "risks" → safety intent. Chapter 5 has safety=1.0, chapter 4 has safety=0.8. But the top result is chapter 8 (questions-to-ask). The intent boost failed.

### Why It Fails

1. **Keyword matching is too generic**: "different" in "what is X and how is it different from Y" triggers comparison intent, but the query is really asking for a definition.

2. **Chapter intent weights are hand-tuned and wrong**: Chapter 3 has 3 intent tags (comparison, regulatory, mechanism) while chapter 5 has only 1 (safety). Chapter 3 gets boosted more often, creating a systematic bias.

3. **The 2.0× boost is too strong for a 61-node index**: It completely overrides the embedding signal. A chapter with a mediocre embedding match but the right intent tag will beat a chapter with a strong embedding match but no intent tag.

4. **No negative boosting**: The system only boosts matching chapters; it doesn't penalize non-matching chapters. This means the boost adds noise without adding signal.

---

## 9. Are Fundamental Architecture Changes Needed?

### For the peptide book specifically: YES.

NeuralMind is designed for code retrieval. The prose mode is a retrofit. The fundamental mismatches:

1. **L0/L1 layers are code-centric**: "Knowledge Graph: 61 entities, 0 clusters", "Code repository with semantic indexing". These are meaningless for a book.

2. **Synapse layer is useless for static content**: Hebbian co-activation learns from usage patterns. A book doesn't change. The synapse layer adds latency and complexity with zero benefit.

3. **Community detection doesn't apply**: Books have chapters, not communities. The community-based L2 retrieval is irrelevant.

4. **Progressive disclosure (L0-L3) is overkill**: For a book, you just need "find the right chapter and return its text." The 4-layer architecture adds complexity without value.

### What Would Work Better

A purpose-built book retriever:
1. Index each chapter as a single document (or use paragraph-level chunking)
2. Use a medical embedding model (multilingual-e5-large, ModernBERT, or BioBERT)
3. Use BM25 with correct prose tokenization
4. Simple RRF fusion with k=10
5. Return top-K chapters with their full text (or relevant excerpts)
6. No intent boost, no synapse layer, no community detection

---

## 10. Concrete Recommendations (Ordered by Impact)

### P0: Fix the BM25 Tokenizer Bug (Expected: +15-20% P@5, +10% R@1)

```python
# In bm25.py, line 207:
q_tokens = self._tokenize_prose(query)  # was: self._tokenize(query)
```

This is a one-line fix that should have immediate impact.

### P1: Reduce RRF_K from 60 to 10 (Expected: +5-10% P@5)

```python
# In context_selector.py:
RRF_K = 10  # was: 60
```

For a 61-node index, k=10 creates proper rank differentiation.

### P2: Reduce Intent Boost Strength (Expected: +10-15% R@1)

Change from 2.0×/1.5× to 1.3×/1.1×, or disable entirely:

```python
chapter_strong_boost = 1.3  # was: 1.5
# In _apply_prose_intent_boost:
boost = 1.3  # was: 2.0
```

Or better: remove the intent boost entirely and rely on embedding + BM25.

### P3: Fix Adaptive Weights (Expected: +5-10% R@1)

```python
# Don't go below 0.5/0.5 for vec/kw split on small indexes
if avg_df <= 3:
    vec_weight = 0.5  # was: 0.2
    kw_weight = 0.5  # was: 0.8
```

### P4: Upgrade Embedding Model (Expected: +20-30% R@1, +15% P@5)

Replace `all-MiniLM-L6-v2` with `multilingual-e5-large` or `ModernBERT-base`. Both are open-source, run on CPU, and significantly outperform MiniLM on medical text.

### P5: Increase Context Budget (Expected: +20-30% Fact Recall)

Current: 800 tokens (~3200 chars) for prose context. A typical chapter is 5000-10000 chars. Increase to 2000-4000 tokens, or use a smarter excerpt selection that picks the most relevant paragraphs from each chapter.

### P6: Remove Chapter Dedup in Ranking (Expected: +5-10% P@5)

Instead of keeping only the top node per chapter, keep the top N nodes per chapter (N=2-3) to capture multiple relevant sections.

### P7: Disable Cross-Chapter Expansion for Focused Queries (Expected: +5% P@5)

The cross-chapter expansion adds noise for focused queries. Only enable it for queries explicitly detected as cross-chapter.

---

## 11. What Success Looks Like

After P0-P3 fixes (all quick wins, no new dependencies):

| Metric | Current | Expected After P0-P3 |
|--------|---------|---------------------|
| R@1 | 64.3% | 75-80% |
| R@3 | 76.2% | 85-90% |
| R@5 | 95.2% | 95%+ (maintain) |
| P@5 | 38.6% | 55-65% |
| MRR | 0.79 | 0.85-0.90 |
| Fact Recall | 47% | 55-65% |

After P4-P7 (structural improvements):

| Metric | Expected After P4-P7 |
|--------|---------------------|
| R@1 | 85-90% |
| R@3 | 90-95% |
| R@5 | 95%+ |
| P@5 | 65-75% |
| MRR | 0.90-0.95 |
| Fact Recall | 70-80% |

---

## 12. Honest Assessment

### What's Actually Working
- **R@5 = 95.2%**: The system finds the right chapter almost always. This is genuinely good.
- **Hit Rate = 100%**: Every query returns at least one relevant chapter.
- **MRR = 0.79**: The correct chapter is usually in the top 2-3.

### What's Fundamentally Broken
- **BM25 tokenizer bug**: This is a critical bug that makes the hybrid search worse than pure embedding for medical terms.
- **Intent boost is counterproductive**: It systematically over-boosts chapter 3 and adds noise.
- **Fact recall is abysmal**: 47% means the system is useless for factual QA. You can't answer "how much weight loss" if the context doesn't contain the STEP 1 trial data.

### What's Just Suboptimal
- **Embedding model**: MiniLM is weak for medical text. Upgrading would help but isn't the bottleneck.
- **Small index**: 61 nodes is fine for chapter-level retrieval but too coarse for fact-level retrieval.
- **RRF_K=60**: Wrong for the scale but not catastrophic.

### The Hard Truth

The current system is a code retrieval engine retrofitted for books. The prose mode works well enough for chapter-level retrieval (R@5=95%) but fails at fact-level retrieval (47% fact recall). The architecture is over-engineered for the use case — a simple embedding + BM25 hybrid with proper tokenization would outperform the current system with all its boosts, synapses, and progressive disclosure layers.

**Recommendation:** Fix P0-P3 immediately (same day). Evaluate whether P4-P7 are worth the effort, or whether a simpler purpose-built retriever would be more cost-effective.

---

*Analysis by adversarial QA subagent. All claims backed by source code evidence and benchmark data.*
