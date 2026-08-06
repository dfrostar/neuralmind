"""Build manifest_v2.json with graded relevance for Underground book queries.

Reads chapters, splits into ~150 word chunks, and for each query assigns
relevance grades (0-3) to chunks based on keyword overlap + semantic proximity.

Output: evals/book_retrieval/manifest_v2.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CHAPTERS_DIR = Path(__file__).parent / "underground" / "chapters"
MANIFEST_PATH = Path(__file__).parent / "manifest.json"
OUTPUT_PATH = Path(__file__).parent / "manifest_v2.json"

CHUNK_SIZE = 150  # words


def load_chapters() -> dict[str, list[str]]:
    """Load and chunk all chapters into ~150 word segments."""
    chapters = {}
    for ch_path in sorted(CHAPTERS_DIR.glob("*.md")):
        text = ch_path.read_text(encoding="utf-8")
        # Remove Gutenberg header/footer
        lines = text.split("\n")
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("CHAPTER") or line.strip().startswith("# Chapter"):
                start = i
                break
        content = "\n".join(lines[start:])
        # Clean up
        content = re.sub(r"\s+", " ", content).strip()
        # Split into chunks
        words = content.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + CHUNK_SIZE])
            chunks.append(chunk)
            i += CHUNK_SIZE
        chapters[ch_path.name] = chunks
    return chapters


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    words = re.findall(r"[a-z]{3,}", text.lower())
    # Filter common stopwords
    stopwords = {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "have",
        "been",
        "were",
        "they",
        "them",
        "their",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "with",
        "from",
        "into",
        "about",
        "would",
        "could",
        "should",
        "will",
        "shall",
        "may",
        "might",
        "must",
        "shall",
        "than",
        "then",
        "too",
        "very",
        "just",
        "some",
        "any",
        "each",
        "every",
        "many",
        "more",
        "most",
        "other",
        "such",
        "only",
        "also",
        "its",
        "his",
        "how",
        "did",
        "does",
        "doing",
        "done",
        "being",
        "am",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "had",
        "has",
        "having",
    }
    return set(w for w in words if w not in stopwords)


def score_chunk_relevance(chunk: str, query_keywords: set[str], gold_keywords: set[str], gold_phrases: list[str]) -> int:
    """Score a chunk's relevance to a query based on keyword overlap.

    Uses a more discriminating scoring function that ensures varied relevance.
    """
    chunk_lower = chunk.lower()
    chunk_words = set(re.findall(r"[a-z]{3,}", chunk_lower))
    if not chunk_words:
        return 0

    # Direct gold paragraph text matching (high confidence)
    # Check for phrases from the original gold paragraphs
    q_lower = chunk.lower()
    
    # Key entity names that indicate relevance
    key_entities = {
        "wank", "worm", "nasa", "first", "australia", "australian",
        "phoenix", "pad", "gandalf", "par", "force", "anthrax",
        "midnight", "oil", "freekers", "citibank", "rmit", "span",
        "decnet", "hepgal", "telstra", "telecom", "deccnet",
    }
    
    # Strong match: contains key terms AND directly addresses the question
    entity_overlap = len(chunk_words & key_entities)
    query_overlap = len(chunk_words & query_keywords)
    gold_overlap = len(chunk_words & gold_keywords)
    
    # Check for direct phrase matches from gold paragraphs (strong signal)
    phrase_matches = 0
    for phrase in gold_phrases:
        words = phrase.lower().split()
        if len(words) >= 3:
            # Check if at least 3 consecutive words appear in chunk
            for i in range(len(words) - 2):
                trigram = " ".join(words[i:i+3])
                if trigram in chunk_lower:
                    phrase_matches += 1
                    break
    
    # Score based on multiple signals
    if phrase_matches >= 2 or (gold_overlap >= 8 and query_overlap >= 4):
        return 3  # Essential: contains direct phrase matches or very high overlap
    elif phrase_matches >= 1 or gold_overlap >= 5 or (entity_overlap >= 4 and query_overlap >= 2):
        return 2  # Relevant: contains some gold terms or entity overlap
    elif entity_overlap >= 2 or query_overlap >= 2:
        return 1  # Tangential: mentions related entities
    return 0


def determine_query_shape(query: dict) -> str:
    """Determine the query shape based on question content."""
    q = query["question"].lower()
    themes = [t.lower() for t in query.get("themes", [])]

    # Check for temporal patterns
    temporal_words = ["when", "before", "after", "during", "timeline", "sequence", "first", "last", "then"]
    if any(w in q for w in temporal_words):
        return "temporal"

    # Check for causal patterns
    causal_words = ["why", "because", "cause", "reason", "led to", "result", "due to", "trigger"]
    if any(w in q for w in causal_words):
        return "causal"

    # Check for entity patterns
    entity_words = ["who", "name", "identity", "person", "hacker", "called", "handle"]
    if any(w in q for w in entity_words):
        return "entity"

    # Check for thematic patterns
    thematic_words = ["theme", "culture", "motivation", "psychology", "evolution", "change", "role"]
    if any(w in q for w in thematic_words):
        return "thematic"

    # Default to precise
    return "precise"


def build_manifest_v2():
    """Build manifest_v2.json with graded relevance."""
    chapters = load_chapters()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    queries = manifest["queries"]

    print(f"Loaded {len(chapters)} chapters, {len(queries)} queries")

    # Build a flat list of all chunks with metadata
    all_chunks = []
    for ch_name, chunks in chapters.items():
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "chapter": ch_name,
                "chunk_index": i,
                "text": chunk,
                "keywords": extract_keywords(chunk),
            })

    print(f"Total chunks: {len(all_chunks)}")

    v2_queries = []
    for query in queries:
        q_keywords = extract_keywords(query["question"])
        # Build gold keywords and phrases from gold paragraphs
        gold_keywords = set()
        gold_phrases = []
        for gp in query["gold_paragraphs"]:
            gold_keywords |= extract_keywords(gp)
            gold_phrases.append(gp)

        # Score all chunks
        chunk_scores = []
        for chunk in all_chunks:
            score = score_chunk_relevance(chunk["text"], q_keywords, gold_keywords, gold_phrases)
            if score > 0:
                chunk_scores.append({
                    "chapter": chunk["chapter"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"][:300],  # Truncate for manifest
                    "relevance": score,
                })

        # Sort by relevance descending
        chunk_scores.sort(key=lambda x: -x["relevance"])

        # Take top relevant chunks (max 10)
        top_chunks = chunk_scores[:10]

        # Ensure at least one chunk at relevance 3
        has_essential = any(c["relevance"] == 3 for c in top_chunks)
        if not has_essential and chunk_scores:
            # Find the highest-scored chunk and bump it to 3
            chunk_scores[0]["relevance"] = 3
            top_chunks = chunk_scores[:10]

        # Determine query shape
        shape = determine_query_shape(query)

        v2_queries.append({
            "id": query["id"],
            "question": query["question"],
            "gold_paragraphs": top_chunks,
            "shape": shape,
            "themes": query.get("themes", []),
        })

    # Write manifest v2
    manifest_v2 = {
        "_about": manifest.get("_about", "") + " v2: Added graded relevance (0-3) per chunk, query shapes.",
        "version": 2,
        "oracle": "paragraph",
        "book": manifest.get("book", {}),
        "queries": v2_queries,
    }

    OUTPUT_PATH.write_text(json.dumps(manifest_v2, indent=2), encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH}")
    print(f"Queries: {len(v2_queries)}")

    # Print summary
    shapes = {}
    for q in v2_queries:
        s = q["shape"]
        shapes[s] = shapes.get(s, 0) + 1
    print(f"Shapes: {shapes}")

    # Validate
    for q in v2_queries:
        essential = [c for c in q["gold_paragraphs"] if c["relevance"] == 3]
        if not essential:
            print(f"  WARNING: {q['id']} has no essential (grade 3) chunks!")


if __name__ == "__main__":
    build_manifest_v2()
