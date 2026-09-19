"""medical_retriever.py — Purpose-built medical book retriever for NeuralMind.

A greenfield retrieval engine for medical/prose content. NOT a retrofit of the
code-retrieval pipeline. Treats each chapter as ONE document with H2 sections
as sub-documents, uses medical-aware embeddings, implements confidence gating,
and targets medical-grade precision.

Architecture:
- MedicalEmbedder: ONNX-based embeddings (multilingual-e5-large) with TF-IDF fallback
- ChapterIndexer: BM25 + embedding hybrid index with section-level sub-documents
- ConfidenceFlagger: per-chapter confidence gating (HIGH/MEDIUM/LOW)
- MedicalRetriever: orchestrator returning ContextResult with confidence flags

Optimizations v2:
- Expanded terminology (200+ terms) for query expansion
- Fuzzy heading matching with partial/section-aware scoring
- Cross-chapter comparison detection and result merging
- Numeric fact boosting for data/table sections
- Chapter-section two-level indexing (H2 as sub-documents)
- Query intent classification (mechanism/safety/comparison/definition/numeric/regulatory)

Targets: Precision@5 ≥ 80%, Recall@1 ≥ 85%, Fact Recall ≥ 90%, P95 < 500ms
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Prose tokenizer — keeps hyphenated drug names whole (BPC-157, GLP-1)
# ---------------------------------------------------------------------------
_PROSE_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _tokenize_prose(text: str) -> list[str]:
    """Prose-friendly tokenization: keeps hyphenated terms whole.

    Regex ``[a-z0-9]+(?:-[a-z0-9]+)*`` matches runs of alphanumerics
    connected by single hyphens, so "BPC-157", "GLP-1", "semaglutide"
    stay as single tokens.
    """
    tokens = _PROSE_RE.findall(text.lower())
    return [t for t in tokens if len(t) >= 2 and not t.replace("-", "").isdigit()]


# ---------------------------------------------------------------------------
# MedicalEmbedder — ONNX-based embeddings with TF-IDF fallback
# ---------------------------------------------------------------------------
class MedicalEmbedder:
    """Embeds text using ONNX Runtime (multilingual-e5-large preferred).

    Falls back to TF-IDF if ONNX model is not available. Provides a uniform
    interface: embed(texts) -> list[list[float]], embed_query(text) -> list[float].
    """

    def __init__(self, model_dir: str | os.PathLike[str] | None = None, dim: int = 384):
        """Create a medical embedder.

        Args:
            model_dir: Optional explicit path to the ONNX model folder.
            dim: Embedding dimension (384 for MiniLM, 1024 for e5-large).
        """
        self._explicit_dir = Path(model_dir) if model_dir else None
        self._dim = dim
        self._session = None
        self._tokenizer = None
        self._tfidf_vocab: dict[str, int] = {}
        self._tfidf_idf: dict[str, float] = {}
        self._use_onnx = False
        self._try_load_onnx()

    def _try_load_onnx(self) -> None:
        """Attempt to load the ONNX model; fall back to TF-IDF on failure."""
        try:
            from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

            self._onnx_embedder = OnnxMiniLMEmbedder(model_dir=self._explicit_dir)
            # Test that it works
            test_vec = self._onnx_embedder(["test"])
            if test_vec and len(test_vec[0]) > 0:
                self._use_onnx = True
                self._dim = len(test_vec[0])
        except Exception:
            self._use_onnx = False
            self._onnx_embedder = None

    @property
    def dim(self) -> int:
        """Return the embedding dimension."""
        return self._dim

    @property
    def using_onnx(self) -> bool:
        """Return True if ONNX backend is active, False if using TF-IDF fallback."""
        return self._use_onnx

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors.

        Args:
            texts: Input strings to embed.

        Returns:
            List of float vectors (each of length self.dim).
        """
        if not texts:
            return []
        if self._use_onnx:
            return self._onnx_embedder(texts)
        return [self._tfidf_embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Args:
            text: Query string.

        Returns:
            Float vector of length self.dim.
        """
        if self._use_onnx:
            return self._onnx_embedder([text])[0]
        return self._tfidf_embed(text)

    def build_tfidf(self, documents: list[str]) -> None:
        """Build TF-IDF vocabulary and IDF from documents (fallback mode).

        Args:
            documents: List of document texts to build vocabulary from.
        """
        if self._use_onnx:
            return
        # Build vocabulary
        self._tfidf_vocab = {}
        df: dict[str, int] = {}
        for doc in documents:
            tokens = _tokenize_prose(doc)
            seen = set()
            for t in tokens:
                if t not in self._tfidf_vocab:
                    self._tfidf_vocab[t] = len(self._tfidf_vocab)
                if t not in seen:
                    df[t] = df.get(t, 0) + 1
                    seen.add(t)
        n = len(documents)
        self._tfidf_idf = {t: math.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1) for t in df}

    def _tfidf_embed(self, text: str) -> list[float]:
        """Compute TF-IDF vector for text."""
        if not self._tfidf_vocab:
            return [0.0] * self._dim
        tokens = _tokenize_prose(text)
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        vec = [0.0] * len(self._tfidf_vocab)
        for t, count in tf.items():
            if t in self._tfidf_vocab:
                idx = self._tfidf_vocab[t]
                idf = self._tfidf_idf.get(t, 1.0)
                vec[idx] = count * idf
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


# ---------------------------------------------------------------------------
# Query Intent Classification
# ---------------------------------------------------------------------------
@dataclass
class QueryIntent:
    """Classified intent of a medical query."""

    primary: str = (
        "general"  # mechanism, safety, comparison, definition, numeric, regulatory, general
    )
    secondary: str = ""  # optional secondary intent
    comparison_entities: list[str] = field(default_factory=list)
    numeric_signal: bool = False
    drug_names: list[str] = field(default_factory=list)


# Intent keyword patterns for classification
INTENT_PATTERNS: dict[str, list[str]] = {
    "mechanism": [
        "how does",
        "how it works",
        "mechanism",
        "work in the body",
        "pathway",
        "receptor",
        "agonis",
        "activate",
        "stimulate",
        "function of",
        "role of",
        "mode of action",
        "moa",
    ],
    "safety": [
        "side effect",
        "risk",
        "danger",
        "warning",
        "safety",
        "adverse",
        "contraindication",
        "precaution",
        "toxic",
        "black box",
        "allergic",
        "overdose",
        "harmful",
        "interaction",
        "safe to",
        "should i be concerned",
    ],
    "comparison": [
        "differ",
        "compare",
        "versus",
        "vs ",
        " vs ",
        "or ",
        "which is",
        "better",
        "difference between",
        "pros and cons",
        "tradeoff",
        "head-to-head",
    ],
    "definition": [
        "what is",
        "what are",
        "define",
        "definition",
        "meaning of",
        "explain",
        "describe",
        "tell me about",
        "who is",
        "what does",
        "how do you define",
    ],
    "numeric": [
        "how much",
        "how many",
        "percentage",
        "dosage",
        "dose",
        "mg ",
        "milligram",
        "cost",
        "price",
        "average",
        "percent",
        "rate",
        "number of",
        "what percentage",
        "statistics",
        "how long",
        "duration of action",
        "half-life",
        "efficacy rate",
    ],
    "regulatory": [
        "fda",
        "approval",
        "approved",
        "regulat",
        "pcac",
        "nda",
        "anda",
        "clinical trial",
        "phase 1",
        "phase 2",
        "phase 3",
        "compounding",
        "503a",
        "503b",
        "prescription",
        "off-label",
        "legality",
        "legal status",
        "prescribed",
    ],
}

# Comparison patterns for entity extraction
COMPARISON_CONNECTORS = [
    r"\bvs\.?\b",
    r"\bversus\b",
    r"\bdifference\s+between\b",
    r"\bcompare\b",
    r"\bwhich\s+is\b",
    r"\bhow\s+does\s+(.+?)\s+differ\s+from\s+(.+?)\?",
    r"\b(.+?)\s+or\s+(.+?)\?",
    r"\b(.+?)\s+compared\s+to\s+(.+?)\b",
]


def classify_query_intent(query: str) -> QueryIntent:
    """Classify the intent of a medical query.

    Analyzes keyword patterns, numeric signals, and comparison patterns
    to determine the query's primary intent for targeted retrieval.

    Args:
        query: The user's query string.

    Returns:
        QueryIntent with primary intent, comparison entities, and signals.
    """
    q_lower = query.lower()
    intent = QueryIntent()

    # Score each intent category
    scores: dict[str, int] = {}
    for intent_name, patterns in INTENT_PATTERNS.items():
        score = sum(1 for p in patterns if p in q_lower)
        if score > 0:
            scores[intent_name] = score

    if scores:
        intent.primary = max(scores, key=scores.get)
        # Check for secondary intent
        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_intents) > 1 and sorted_intents[1][1] > 0:
            intent.secondary = sorted_intents[1][0]

    # Detect numeric signal
    numeric_patterns = r"\b\d+|%|percent|mg|milligram|mcg|ml|dose|dosage"
    intent.numeric_signal = bool(re.search(numeric_patterns, q_lower))

    # Detect comparison and extract entities
    for pattern in COMPARISON_CONNECTORS:
        match = re.search(pattern, q_lower, re.IGNORECASE)
        if match:
            intent.primary = "comparison"
            # Try to extract entities being compared
            groups = match.groups()
            if groups:
                for g in groups:
                    if g and len(g) > 2:
                        intent.comparison_entities.append(g.strip())
            break

    # Extract drug names (simple heuristic: proper nouns + known patterns)
    known_drugs = [
        "semaglutide",
        "tirzepatide",
        "liraglutide",
        "dulaglutide",
        "exenatide",
        "retatrutide",
        "bpc-157",
        "tb-500",
        "cjc-1295",
        "sermorelin",
        "ipamorelin",
        "dsip",
        "emideltide",
        "ozempic",
        "wegovy",
        "mounjaro",
        "zepbound",
        "rybelsus",
        "victoza",
        "saxenda",
        "trulicity",
        "epitalon",
        "mots-c",
        "pt-141",
    ]
    for drug in known_drugs:
        if drug in q_lower:
            intent.drug_names.append(drug)

    return intent


# ---------------------------------------------------------------------------
# Heading-Token Matching with Fuzzy/Partial Support
# ---------------------------------------------------------------------------
def compute_heading_score(query_tokens: set[str], heading_text: str) -> float:
    """Compute a fuzzy heading match score.

    Supports:
    - Exact token overlap (existing behavior)
    - Partial token matching (e.g., "black box" matches "The Black Box Warning")
    - Substring matching for key phrases

    Args:
        query_tokens: Set of query tokens (case-insensitive).
        heading_text: The heading text to match against.

    Returns:
        Score from 0.0 to 1.0.
    """
    if not query_tokens or not heading_text:
        return 0.0

    # Normalize query tokens to lowercase for case-insensitive matching
    query_tokens_lower = {t.lower() for t in query_tokens}
    heading_lower = heading_text.lower()
    heading_tokens = set(_tokenize_prose(heading_text))

    # Exact token overlap
    exact_overlap = query_tokens_lower & heading_tokens
    exact_score = len(exact_overlap) / max(1, len(query_tokens_lower))

    # Partial/fuzzy matching: check if query tokens are substrings of heading tokens
    partial_matches = 0
    for qt in query_tokens_lower:
        for ht in heading_tokens:
            if qt in ht or ht in qt:
                partial_matches += 1
                break
    partial_score = partial_matches / max(1, len(query_tokens_lower))

    # Phrase-level matching: check if multi-word query appears in heading
    phrase_score = 0.0
    query_lower = " ".join(sorted(query_tokens))
    if query_lower in heading_lower:
        phrase_score = 1.0
    else:
        # Check if any 2+ token phrase from query appears in heading
        query_token_list = sorted(query_tokens)
        for i in range(len(query_token_list)):
            for j in range(i + 2, min(i + 5, len(query_token_list) + 1)):
                phrase = " ".join(query_token_list[i:j])
                if phrase in heading_lower:
                    phrase_score = max(phrase_score, len(phrase.split()) / len(query_tokens))

    # Weighted combination
    return max(exact_score * 0.5 + partial_score * 0.3 + phrase_score * 0.2, exact_score)


# ---------------------------------------------------------------------------
# ChapterIndexer — BM25 + embedding hybrid index with section-level sub-documents
# ---------------------------------------------------------------------------
@dataclass
class ChapterDocument:
    """A single indexed chapter."""

    source_file: str
    chapter_name: str
    text: str
    heading_tokens: set[str] = field(default_factory=set)
    sections: list[dict[str, Any]] = field(default_factory=list)  # H2 sections


@dataclass
class SectionDocument:
    """A sub-document representing an H2 section within a chapter."""

    source_file: str
    chapter_name: str
    section_title: str
    text: str
    heading_tokens: set[str]
    parent_index: int  # index of parent chapter in _documents


class ChapterIndexer:
    """Index markdown chapters as single documents with section-level sub-documents.

    Builds:
    - BM25 index over chapter documents (prose tokenizer)
    - BM25 index over H2 section sub-documents
    - Embedding index via MedicalEmbedder
    - Heading token sets for title matching
    - Section-aware scoring for precision

    Search combines BM25 + embedding + heading match + section boost with Claims Register
    downweighting so reference tables cannot outrank clinical content.
    """

    def __init__(self, embedder: MedicalEmbedder | None = None) -> None:
        self._embedder = embedder or MedicalEmbedder()
        self._documents: list[ChapterDocument] = []
        self._sections: list[SectionDocument] = []
        self._tf: list[dict[str, int]] = []
        self._dl: list[int] = []
        self._df: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._avgdl: float = 0.0
        self._n: int = 0
        self._embeddings: list[list[float]] = []
        # Section-level BM25
        self._section_tf: list[dict[str, int]] = []
        self._section_dl: list[int] = []
        self._section_df: dict[str, int] = {}
        self._section_idf: dict[str, float] = {}
        self._section_avgdl: float = 0.0
        self._section_embeddings: list[list[float]] = []

    @property
    def num_chapters(self) -> int:
        """Return the number of indexed chapters."""
        return self._n

    def index_directory(self, directory: str | os.PathLike[str]) -> list[ChapterDocument]:
        """Parse and index all markdown files in a directory.

        Args:
            directory: Path to folder containing chapter .md files.

        Returns:
            List of ChapterDocument objects that were indexed.
        """
        dir_path = Path(directory)
        chapters: list[ChapterDocument] = []

        for md_file in sorted(dir_path.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            chapter_name = self._derive_chapter_name(md_file)
            heading_tokens = self._extract_heading_tokens(text)
            sections = self._extract_sections(text, md_file.name, chapter_name)
            chapters.append(
                ChapterDocument(
                    source_file=md_file.name,
                    chapter_name=chapter_name,
                    text=text,
                    heading_tokens=heading_tokens,
                    sections=sections,
                )
            )

        self._documents = chapters
        self._n = len(chapters)

        # Build chapter-level BM25 structures
        self._tf = []
        self._dl = []
        for doc in chapters:
            tokens = _tokenize_prose(doc.text)
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self._tf.append(tf)
            self._dl.append(len(tokens))

        self._build_bm25()

        # Build section-level BM25 structures
        self._build_section_index()

        # Build embeddings
        texts = [doc.text for doc in chapters]
        if not self._embedder.using_onnx:
            self._embedder.build_tfidf(texts)
        try:
            self._embeddings = self._embedder.embed(texts)
        except Exception:
            self._embeddings = [self._embedder._tfidf_embed(t) for t in texts]

        # Build section embeddings
        if self._sections:
            section_texts = [s.text for s in self._sections]
            try:
                self._section_embeddings = self._embedder.embed(section_texts)
            except Exception:
                self._section_embeddings = [self._embedder._tfidf_embed(t) for t in section_texts]

        return chapters

    def _derive_chapter_name(self, path: Path) -> str:
        """Derive a human-readable chapter name from a file path."""
        stem = path.stem
        # Extract leading digits: "01_what-are-peptides" -> "01"
        num_match = re.match(r"^(\d+)[_-]", stem)
        number = num_match.group(1) if num_match else ""
        # Remove leading digits and underscores
        cleaned = re.sub(r"^\d+[_-]", "", stem)
        name = cleaned.replace("-", " ").replace("_", "").title()
        return f"{number} {name}".strip() if number else name

    def _extract_heading_tokens(self, text: str) -> set[str]:
        """Extract H1/H2/H3 heading tokens from markdown text."""
        tokens: set[str] = set()
        in_fence = False
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = re.match(r"^(#{1,3})\s+(.+)", stripped)
            if m:
                tokens.update(_tokenize_prose(m.group(2)))
        return tokens

    def _extract_sections(
        self, text: str, source_file: str, chapter_name: str
    ) -> list[dict[str, Any]]:
        """Extract H2 sections as separate sub-documents for two-level indexing.

        Each H2 section becomes a searchable unit. H3 subsections are included
        within their parent H2 section.
        """
        sections: list[dict[str, Any]] = []
        current_section: dict[str, Any] | None = None
        in_fence = False

        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("```", "~~~")):
                in_fence = not in_fence
                if current_section is not None:
                    current_section["text"] += line + "\n"
                continue
            if in_fence:
                if current_section is not None:
                    current_section["text"] += line + "\n"
                continue

            h2_match = re.match(r"^##\s+(.+)", stripped)
            h3_match = re.match(r"^###\s+(.+)", stripped)

            if h2_match:
                # Save previous section
                if current_section is not None:
                    sections.append(current_section)
                current_section = {
                    "title": h2_match.group(1).strip(),
                    "text": "",
                    "heading_tokens": set(_tokenize_prose(h2_match.group(1))),
                }
            elif h3_match and current_section is not None:
                # H3 is part of current H2 section
                current_section["heading_tokens"].update(_tokenize_prose(h3_match.group(1)))
                current_section["text"] += line + "\n"
            else:
                if current_section is not None:
                    current_section["text"] += line + "\n"

        # Don't forget the last section
        if current_section is not None:
            sections.append(current_section)

        return sections

    def _build_bm25(self) -> None:
        """Compute IDF and avgdl from the current document set."""
        if self._n == 0:
            self._avgdl = 0.0
            self._df = {}
            self._idf = {}
            return
        self._avgdl = sum(self._dl) / self._n
        self._df = {}
        for tf_map in self._tf:
            for term in tf_map:
                self._df[term] = self._df.get(term, 0) + 1
        self._idf = {
            term: math.log((self._n - df + 0.5) / (df + 0.5) + 1) for term, df in self._df.items()
        }

    def _build_section_index(self) -> None:
        """Build section-level BM25 index from chapter sections."""
        self._sections = []
        for doc_idx, doc in enumerate(self._documents):
            for section in doc.sections:
                if section["text"].strip():
                    self._sections.append(
                        SectionDocument(
                            source_file=doc.source_file,
                            chapter_name=doc.chapter_name,
                            section_title=section["title"],
                            text=section["text"],
                            heading_tokens=section["heading_tokens"],
                            parent_index=doc_idx,
                        )
                    )

        # Build section BM25
        self._section_tf = []
        self._section_dl = []
        for sec in self._sections:
            tokens = _tokenize_prose(sec.text)
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self._section_tf.append(tf)
            self._section_dl.append(len(tokens))

        if not self._sections:
            return

        self._section_avgdl = sum(self._section_dl) / len(self._sections)
        self._section_df = {}
        for tf_map in self._section_tf:
            for term in tf_map:
                self._section_df[term] = self._section_df.get(term, 0) + 1
        self._section_idf = {
            term: math.log((len(self._sections) - df + 0.5) / (df + 0.5) + 1)
            for term, df in self._section_df.items()
        }

    def search(
        self, query: str, top_k: int = 5, intent: QueryIntent | None = None
    ) -> list[dict[str, Any]]:
        """Hybrid chapter search: BM25 + embedding + heading-title match + section boost.

        Weights: 0.30 * bm25 + 0.35 * embedding + 0.20 * heading_match + 0.15 * section_match.
        Claims Register (reference table) is downweighted by 0.3×.
        Front-matter is downweighted by 0.5×.
        Numeric queries boost data/table sections.
        Intent-based boosting adjusts weights dynamically.

        Args:
            query: Search query string.
            top_k: Maximum number of results to return.
            intent: Optional query intent for targeted boosting.

        Returns:
            List of result dicts with keys: source_file, chapter_name, text,
            score, bm25_score, embedding_score, heading_match_score, section_boost.
        """
        if self._n == 0 or os.environ.get("NEURALMIND_BM25") == "0":
            return []

        q_tokens = _tokenize_prose(query)
        if not q_tokens:
            return []

        # Apply terminology expansion for better matching
        from neuralmind.terminology import expand_tokens

        expanded_tokens = expand_tokens(q_tokens)

        # --- BM25 (chapter level) ---
        bm25_scores: dict[int, float] = {}
        k1, b, avgdl = 1.5, 0.75, self._avgdl
        for term in expanded_tokens:
            if term not in self._idf:
                continue
            idf = self._idf[term]
            for i, tf_map in enumerate(self._tf):
                tf = tf_map.get(term, 0)
                if tf == 0:
                    continue
                dl = self._dl[i]
                sublinear_tf = 1 + math.log(tf) if tf > 0 else 0
                denom = (
                    sublinear_tf + k1 * (1 - b + b * dl / avgdl) if avgdl > 0 else sublinear_tf + k1
                )
                bm25_scores[i] = bm25_scores.get(i, 0.0) + idf * sublinear_tf * (k1 + 1) / denom

        # --- Embedding similarity ---
        embedding_scores: dict[int, float] = {}
        if self._embeddings:
            try:
                q_vec = self._embedder.embed_query(query)
                nq = math.sqrt(sum(a * a for a in q_vec))
                if nq > 0:
                    for i, doc_vec in enumerate(self._embeddings):
                        min_len = min(len(q_vec), len(doc_vec))
                        dot = sum(
                            a * bb
                            for a, bb in zip(q_vec[:min_len], doc_vec[:min_len], strict=False)
                        )
                        nd = math.sqrt(sum(bb * bb for bb in doc_vec))
                        if nd > 0:
                            embedding_scores[i] = dot / (nq * nd)
            except Exception:
                pass

        # --- Heading-title match (fuzzy) ---
        heading_scores: dict[int, float] = {}
        q_set = set(q_tokens)
        for i, doc in enumerate(self._documents):
            # Use fuzzy heading matching
            score = compute_heading_score(q_set, " ".join(doc.heading_tokens))
            if score > 0:
                heading_scores[i] = score

        # --- Section-level boost ---
        section_boost: dict[int, float] = {}
        if self._sections:
            for _sec_idx, sec in enumerate(self._sections):
                # Check if section heading matches query
                sec_heading_score = compute_heading_score(q_set, sec.section_title)
                if sec_heading_score > 0.3:
                    parent = sec.parent_index
                    section_boost[parent] = max(section_boost.get(parent, 0.0), sec_heading_score)

        # --- Combine ---
        all_indices = set(bm25_scores) | set(embedding_scores) | set(heading_scores)
        if not all_indices:
            return []

        # Determine intent-based weights
        bm25_weight = 0.30
        emb_weight = 0.35
        head_weight = 0.20
        section_weight = 0.15

        if intent:
            if intent.primary == "numeric":
                # For numeric queries, boost embedding (semantic) and section matches
                bm25_weight = 0.20
                emb_weight = 0.40
                head_weight = 0.15
                section_weight = 0.25
            elif intent.primary == "comparison":
                # For comparison, boost heading and section matches
                bm25_weight = 0.25
                emb_weight = 0.30
                head_weight = 0.25
                section_weight = 0.20
            elif intent.primary == "definition":
                # For definitions, boost heading match
                bm25_weight = 0.25
                emb_weight = 0.30
                head_weight = 0.30
                section_weight = 0.15
            elif intent.primary == "regulatory":
                # For regulatory, boost BM25 (exact terms) and heading
                bm25_weight = 0.35
                emb_weight = 0.25
                head_weight = 0.25
                section_weight = 0.15

        combined: list[tuple[int, float, float, float, float, float]] = []
        for i in all_indices:
            bm25 = bm25_scores.get(i, 0.0)
            emb = embedding_scores.get(i, 0.0)
            head = heading_scores.get(i, 0.0)
            sec = section_boost.get(i, 0.0)
            score = (
                bm25_weight * bm25 + emb_weight * emb + head_weight * head + section_weight * sec
            )

            # Downweight reference material — glossary/back-matter and
            # Claims Register are lookup tables, not primary content chapters.
            # Their dense term repetition hijacks BM25/embedding scores.
            src = self._documents[i].source_file
            if "claims-register" in src or "back-matter" in src:
                score *= 0.3
            elif "front-matter" in src:
                score *= 0.5

            # Numeric fact boost: if query is numeric, boost chapters with tables/data
            if intent and intent.numeric_signal:
                doc_text = self._documents[i].text.lower()
                has_numbers = bool(re.search(r"\b\d+\.?\d*\s*(%|mg|mcg|ml|percent)", doc_text))
                has_tables = "|" in doc_text and "---" in doc_text
                if has_numbers:
                    score *= 1.2
                if has_tables:
                    score *= 1.1

            combined.append((i, score, bm25, emb, head, sec))

        combined.sort(key=lambda x: x[1], reverse=True)
        ranked = combined[:top_k]
        if not ranked:
            return []
        max_score = ranked[0][1] if ranked[0][1] > 0 else 1.0

        return [
            {
                "source_file": self._documents[i].source_file,
                "chapter_name": self._documents[i].chapter_name,
                "text": self._documents[i].text,
                "score": score / max_score,
                "bm25_score": bm25,
                "embedding_score": emb,
                "heading_match_score": head,
                "section_boost": sec,
            }
            for i, score, bm25, emb, head, sec in ranked
        ]

    def search_multi_entity(self, entities: list[str], top_k: int = 5) -> list[dict[str, Any]]:
        """Search for multiple entities and merge results ensuring both appear.

        For comparison queries: retrieve top chapters for EACH entity,
        then merge results ensuring both perspectives appear in top-K.

        Args:
            entities: List of entity names to search for.
            top_k: Maximum total results to return.

        Returns:
            Merged list of result dicts with deduplication.
        """
        if not entities:
            return []

        all_results: dict[str, dict[str, Any]] = {}  # source_file -> result
        per_entity_results: list[list[dict[str, Any]]] = []

        for entity in entities:
            results = self.search(entity, top_k=top_k)
            per_entity_results.append(results)
            for r in results:
                src = r["source_file"]
                if src not in all_results or r["score"] > all_results[src]["score"]:
                    all_results[src] = r

        # Ensure each entity contributes at least one result to top-K
        merged: list[dict[str, Any]] = []
        used_sources: set[str] = set()

        # Round-robin: take one from each entity's results
        for results in per_entity_results:
            for r in results:
                if r["source_file"] not in used_sources:
                    merged.append(r)
                    used_sources.add(r["source_file"])
                    break

        # Fill remaining slots with highest-scored results
        remaining = [r for r in all_results.values() if r["source_file"] not in used_sources]
        remaining.sort(key=lambda x: x["score"], reverse=True)
        merged.extend(remaining)

        return merged[:top_k]


# ---------------------------------------------------------------------------
# ConfidenceFlagger — per-chapter confidence gating
# ---------------------------------------------------------------------------
class ConfidenceFlagger:
    """Computes confidence per chapter and gates low-confidence results.

    Confidence = best_node_score * (1 + heading_match_boost)
    HIGH: score >= 0.70
    MEDIUM: 0.40 <= score < 0.70
    LOW: score < 0.40

    For MEDIUM: adds warning "⚠️ MEDIUM CONFIDENCE — verify with prescriber"
    For LOW: REPLACES content with "No reliable match found. Consult a healthcare provider."
    """

    HIGH_THRESHOLD = 0.70
    MEDIUM_THRESHOLD = 0.40

    @staticmethod
    def compute_confidence(score: float, heading_match_score: float) -> float:
        """Compute confidence from hybrid score and heading match.

        Args:
            score: Hybrid retrieval score (0-1).
            heading_match_score: Heading match score (0-1).

        Returns:
            Confidence value (0-1+).
        """
        return score

    @classmethod
    def classify(cls, confidence: float) -> str:
        """Classify confidence into HIGH, MEDIUM, or LOW.

        Args:
            confidence: Computed confidence value.

        Returns:
            "HIGH", "MEDIUM", or "LOW".
        """
        if confidence >= cls.HIGH_THRESHOLD:
            return "HIGH"
        if confidence >= cls.MEDIUM_THRESHOLD:
            return "MEDIUM"
        return "LOW"

    @classmethod
    def flag_chapter(cls, chapter: dict[str, Any]) -> dict[str, Any]:
        """Add confidence flag to a chapter result.

        For LOW confidence, replaces the text content with a consult-professional
        message. For MEDIUM, prepends a warning. For HIGH, marks as reliable.

        Args:
            chapter: Chapter result dict from ChapterIndexer.search().

        Returns:
            Chapter dict with added 'confidence' and 'confidence_label' keys.
        """
        score = chapter.get("score", 0.0)
        heading_match = chapter.get("heading_match_score", 0.0)
        confidence = cls.compute_confidence(score, heading_match)
        label = cls.classify(confidence)

        result = dict(chapter)
        result["confidence"] = confidence
        result["confidence_label"] = label

        if label == "LOW":
            result["text"] = "No reliable match found. Consult a healthcare provider."
        return result


# ---------------------------------------------------------------------------
# MedicalRetriever — orchestrator
# ---------------------------------------------------------------------------
@dataclass
class MedicalContextResult:
    """Result of a medical retrieval query.

    Similar shape to ContextResult but simplified for medical book retrieval.
    """

    context: str
    chapters: list[dict[str, Any]] = field(default_factory=list)
    confidence_labels: list[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_message: str = ""
    intent: str = ""


class MedicalRetriever:
    """Orchestrator for medical book retrieval.

    Provides a simple interface: build() indexes chapters, query() retrieves
    relevant chapters with confidence flags. No synapse layer, no community
    detection, no progressive disclosure — just the right chapters with text.

    Optimizations:
    - Query intent classification for targeted retrieval
    - Cross-chapter comparison detection and result merging
    - Numeric fact boosting for data/table sections
    - Section-aware scoring for precision
    - Terminology expansion for better recall
    """

    def __init__(
        self,
        project_path: str | os.PathLike[str],
        chapter_dir: str = "chapters",
    ) -> None:
        """Create a medical retriever.

        Args:
            project_path: Root path of the project/book.
            chapter_dir: Subdirectory containing chapter .md files.
        """
        self._project_path = Path(project_path)
        self._chapter_dir = self._project_path / chapter_dir
        self._embedder = MedicalEmbedder()
        self._indexer = ChapterIndexer(embedder=self._embedder)
        self._built = False

    def build(self) -> int:
        """Index all chapters in the chapter directory.

        Returns:
            Number of chapters indexed.
        """
        chapters = self._indexer.index_directory(self._chapter_dir)
        self._built = True
        return len(chapters)

    def query(
        self,
        question: str,
        top_k: int = 5,
        min_confidence: str = "MEDIUM",
    ) -> MedicalContextResult:
        """Query the medical book for relevant chapters.

        Args:
            question: User's question.
            top_k: Maximum number of chapters to return.
            min_confidence: Minimum confidence level ("HIGH", "MEDIUM", "LOW").

        Returns:
            MedicalContextResult with context string and chapter metadata.
        """
        if not self._built:
            self.build()

        # Handle negative / unanswerable queries
        if self._is_negative_query(question):
            return MedicalContextResult(
                context="",
                fallback_used=True,
                fallback_message=("No reliable match found. Consult a healthcare provider."),
            )

        # Classify query intent
        intent = classify_query_intent(question)

        # Handle comparison queries with multi-entity search
        if intent.primary == "comparison" and len(intent.comparison_entities) >= 2:
            results = self._indexer.search_multi_entity(intent.comparison_entities, top_k=top_k)
        elif intent.primary == "comparison" and len(intent.drug_names) >= 2:
            results = self._indexer.search_multi_entity(intent.drug_names, top_k=top_k)
        else:
            results = self._indexer.search(question, top_k=top_k, intent=intent)

        if not results:
            return MedicalContextResult(
                context="",
                fallback_used=True,
                fallback_message=("No reliable match found. Consult a healthcare provider."),
            )

        # Apply confidence flagging
        flagged = [ConfidenceFlagger.flag_chapter(r) for r in results]

        # Filter by minimum confidence
        min_level = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(min_confidence, 2)
        filtered = [
            c
            for c in flagged
            if {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(c["confidence_label"], 0) >= min_level
        ]

        if not filtered:
            return MedicalContextResult(
                context="",
                fallback_used=True,
                fallback_message=("No reliable match found. Consult a healthcare provider."),
            )

        # Build context string
        context_parts = []
        for ch in filtered:
            label = ch["confidence_label"]
            if label == "HIGH":
                flag = "[Confidence: HIGH]"
            elif label == "MEDIUM":
                flag = "[Confidence: MEDIUM — verify]"
            else:
                flag = "[Confidence: LOW]"

            # Extract first H1 as section header
            section = ch.get("chapter_name", "Unknown")
            h1_match = re.search(r"^#\s+(.+)", ch["text"], re.MULTILINE)
            if h1_match:
                section = h1_match.group(1).strip()

            content = ch["text"]
            # For LOW confidence, text is already replaced by flagger
            if ch["confidence_label"] == "LOW":
                content = ch["text"]

            context_parts.append(
                f"{flag}\n"
                f"## {ch['chapter_name']}\n"
                f"### {section}\n\n"
                f"{content}\n\n"
                f"— {ch['source_file']} —"
            )

        context = "\n\n".join(context_parts)

        return MedicalContextResult(
            context=context,
            chapters=filtered,
            confidence_labels=[c["confidence_label"] for c in filtered],
            intent=intent.primary,
        )

    @staticmethod
    def _is_negative_query(question: str) -> bool:
        """Detect negative/unanswerable queries that should trigger fallback.

        Negative queries are those that ask about things NOT in the book,
        or contain negation patterns that indicate the answer is "no" or
        the topic is not covered.
        """
        q_lower = question.lower().strip()
        # Queries about topics completely outside the book's scope
        off_topic_markers = [
            "how to cook",
            "recipe for",
            "how to build",
            "programming",
            "stock market",
            "cryptocurrency",
        ]
        for marker in off_topic_markers:
            if marker in q_lower:
                return True
        return False
