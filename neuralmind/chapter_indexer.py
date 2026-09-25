"""Chapter-level indexer for prose/book retrieval.

Treats each markdown chapter as a single searchable document
with H2 sections as sub-documents for precision retrieval.

Indexing strategy:
- One BM25 document per chapter (full text as value).
- H1 used as chapter title; H2/H3 grouped as section
  headings and indexed for title matching.
- TF-IDF fallback vectors when no embedder is supplied.
- Section-level sub-documents for two-level retrieval.
- Search combines BM25, title, and vector scores with
  Claims Register down-weighting so medical reference
  tables cannot outrank clinical content chapters.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any

# Prose-friendly tokenizer (same as medical_retriever.py)
_PROSE_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _tokenize_prose(text: str) -> list[str]:
    tokens = _PROSE_RE.findall(text.lower())
    return [t for t in tokens if len(t) >= 2 and not t.replace("-", "").isdigit()]


class ChapterIndexer:
    """Index markdown chapters as single documents with section-level sub-documents."""

    def __init__(self, embedder: Any = None) -> None:
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict[str, Any]] = []
        self._tf: list[dict[str, int]] = []
        self._dl: list[int] = []
        self._df: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._avgdl: float = 0.0
        self._n: int = 0
        self._embedder = embedder
        self._embeddings: list[list[float]] = []
        self._chapter_names: dict[str, str] = {}
        self._heading_tokens: list[set[str]] = []
        # Section-level structures
        self._section_data: list[dict[str, Any]] = []
        self._section_tf: list[dict[str, int]] = []
        self._section_dl: list[int] = []
        self._section_df: dict[str, int] = {}
        self._section_idf: dict[str, float] = {}
        self._section_avgdl: float = 0.0
        self._section_embeddings: list[list[float]] = []

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_directory(self, directory: str) -> list[dict[str, Any]]:
        dir_path = Path(directory)
        chapters: list[dict[str, Any]] = []

        for md_file in sorted(dir_path.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            chapter_name = md_file.stem.replace("-", " ").replace("_", " ").title()
            headings = self._extract_headings(text)
            heading_tokens: set[str] = set()
            for _, h_text in headings:
                heading_tokens.update(_tokenize_prose(h_text))

            chapters.append(
                {
                    "source_file": md_file.name,
                    "chapter_name": chapter_name,
                    "text": text,
                    "heading_tokens": heading_tokens,
                }
            )

        self._ids = [c["source_file"] for c in chapters]
        self._texts = [c["text"] for c in chapters]
        self._metadatas = [
            {"source_file": c["source_file"], "chapter_name": c["chapter_name"]} for c in chapters
        ]
        self._chapter_names = {c["source_file"]: c["chapter_name"] for c in chapters}
        self._heading_tokens = [c["heading_tokens"] for c in chapters]

        for text in self._texts:
            tokens = _tokenize_prose(text)
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self._tf.append(tf)
            self._dl.append(len(tokens))

        self._n = len(self._ids)

        # Build IDF first (needed for both ONNX and TF-IDF fallback)
        self._build()

        # Build section-level index
        self._build_section_index()

        if self._embedder is not None:
            try:
                self._embeddings = self._embedder.embed(self._texts)
            except Exception:
                self._embeddings = []
        if not self._embeddings and self._n > 0:
            # TF-IDF fallback vectors when ONNX is unavailable or failed
            vocab = sorted(self._idf.keys())
            for tf_map in self._tf:
                self._embeddings.append([tf_map.get(t, 0) * self._idf[t] for t in vocab])

        # Build section embeddings
        if self._section_data:
            section_texts = [s["text"] for s in self._section_data]
            try:
                self._section_embeddings = self._embedder.embed(section_texts)
            except Exception:
                self._section_embeddings = []

        return chapters

    def _extract_headings(self, text: str) -> list[tuple[int, str]]:
        """Extract markdown headings as (level, text) tuples."""
        headings: list[tuple[int, str]] = []
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
                headings.append((len(m.group(1)), m.group(2).strip()))
        return headings

    def _build(self) -> None:
        if self._n == 0:
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
        """Build section-level sub-document index for precision retrieval."""
        self._section_data = []
        for idx, (text, source_file, chapter_name) in enumerate(
            zip(
                self._texts,
                self._ids,
                [self._metadatas[i]["chapter_name"] for i in range(self._n)],
                strict=True,
            )
        ):
            sections = self._extract_sections(text, source_file, chapter_name, idx)
            self._section_data.extend(sections)

        # Build section BM25
        for sec in self._section_data:
            tokens = _tokenize_prose(sec["text"])
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self._section_tf.append(tf)
            self._section_dl.append(len(tokens))

        if not self._section_data:
            return

        self._section_avgdl = sum(self._section_dl) / len(self._section_data)
        self._section_df = {}
        for tf_map in self._section_tf:
            for term in tf_map:
                self._section_df[term] = self._section_df.get(term, 0) + 1
        self._section_idf = {
            term: math.log((len(self._section_data) - df + 0.5) / (df + 0.5) + 1)
            for term, df in self._section_df.items()
        }

    def _extract_sections(
        self, text: str, source_file: str, chapter_name: str, chapter_idx: int
    ) -> list[dict[str, Any]]:
        """Extract H2 sections as sub-documents for two-level indexing."""
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
                    "source_file": source_file,
                    "chapter_name": chapter_name,
                    "chapter_index": chapter_idx,
                }
            elif h3_match and current_section is not None:
                current_section["heading_tokens"].update(_tokenize_prose(h3_match.group(1)))
                current_section["text"] += line + "\n"
            else:
                if current_section is not None:
                    current_section["text"] += line + "\n"

        if current_section is not None:
            sections.append(current_section)

        return sections

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Hybrid chapter search: BM25 + vector + heading-title match + section boost.

        Weights tuned for small indexes (N ≈ 10-20) where BM25
        score clustering is severe and heading matches carry
        disproportionately high signal for definition/safety queries.
        """
        if self._n == 0 or os.environ.get("NEURALMIND_BM25") == "0":
            return []

        q_tokens = _tokenize_prose(query)
        if not q_tokens:
            return []

        # --- BM25 ---
        bm25_scores: dict[int, float] = {}
        k1, b, avgdl = 1.5, 0.75, self._avgdl
        for term in q_tokens:
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

        # --- Vector similarity (TF-IDF cosine fallback) ---
        vec_scores: dict[int, float] = {}
        if self._embedder is not None and self._embeddings:
            try:
                q_vec = self._embedder.embed([query])[0]
                for i, doc_vec in enumerate(self._embeddings):
                    dot = sum(a * bb for a, bb in zip(q_vec, doc_vec, strict=True))
                    nq = math.sqrt(sum(a * a for a in q_vec))
                    nd = math.sqrt(sum(bb * bb for bb in doc_vec))
                    if nq > 0 and nd > 0:
                        vec_scores[i] = dot / (nq * nd)
            except Exception:
                pass
        elif self._n > 0 and self._idf:
            # TF-IDF cosine against the same vocabulary
            q_tf: dict[str, int] = {}
            for t in q_tokens:
                q_tf[t] = q_tf.get(t, 0) + 1
            vocab = sorted(self._idf.keys())
            q_vec = [q_tf.get(t, 0) * self._idf[t] for t in vocab]
            nq = math.sqrt(sum(a * a for a in q_vec))
            if nq > 0:
                for i, doc_vec in enumerate(self._embeddings):
                    dot = sum(a * bb for a, bb in zip(q_vec, doc_vec, strict=True))
                    nd = math.sqrt(sum(bb * bb for bb in doc_vec))
                    if nd > 0:
                        vec_scores[i] = dot / (nq * nd)

        # --- Heading-title match ---
        # H2/H3 headings often contain the exact phrase a user
        # queries ("Black Box Warning", "Oral Peptide Delivery").
        title_scores: dict[int, float] = {}
        q_set = set(q_tokens)
        for i, headings in enumerate(self._heading_tokens):
            overlap = q_set & headings
            if overlap:
                title_scores[i] = min(1.0, len(overlap) / max(1, len(q_set)))

        # --- Section-level boost ---
        section_boost: dict[int, float] = {}
        if self._section_data:
            for sec in self._section_data:
                sec_overlap = q_set & sec.get("heading_tokens", set())
                if sec_overlap:
                    parent = sec["chapter_index"]
                    score = min(1.0, len(sec_overlap) / max(1, len(q_set)))
                    section_boost[parent] = max(section_boost.get(parent, 0.0), score)

        # --- Combine ---
        # Weights favor heading match and vector over raw BM25 on
        # small indexes where BM25 scores cluster tightly.
        # Claims Register is clinically critical to down-weight;
        # it is a reference table, not a content chapter, and its
        # high term density otherwise hijacks exact-term hits.
        combined: list[tuple[int, float]] = []
        all_indices = set(bm25_scores) | set(vec_scores) | set(title_scores)

        claims_penalty = 0.4

        for i in all_indices:
            bm25 = bm25_scores.get(i, 0.0)
            vec = vec_scores.get(i, 0.0)
            title = title_scores.get(i, 0.0)
            sec_boost = section_boost.get(i, 0.0)

            score = 0.30 * bm25 + 0.30 * vec + 0.25 * title + 0.15 * sec_boost
            if "claims-register" in self._ids[i]:
                score *= claims_penalty

            combined.append((i, score))

        if not combined:
            return []

        combined.sort(key=lambda x: x[1], reverse=True)
        ranked = combined[:top_k]
        max_score = ranked[0][1] if ranked else 1.0

        return [
            {
                "id": self._ids[i],
                "source_file": self._metadatas[i]["source_file"],
                "chapter_name": self._metadatas[i]["chapter_name"],
                "text": self._texts[i],
                "score": score / max_score,
                "_bm25_raw": bm25_scores.get(i, 0.0),
                "_vec_score": vec_scores.get(i, 0.0),
                "_title_score": title_scores.get(i, 0.0),
            }
            for i, score in ranked
        ]
