"""retrieval_enhancement.py — three adversarial fixes for shallow retrieval.

Fixes three failure modes identified by QA:

1. **Intent misclassification** — "how does X implement Y" was classified as
   `docs` intent (because "how does" is a doc keyword), causing the system to
   boost docstrings over implementation code. Now: queries matching the pattern
   "how does <noun> implement/perform/do <noun>" are classified as `code`
   intent, surfacing the actual algorithm.

2. **Missing code-signal boost** — For implementation queries, extract
   function/class/variable identifiers from the query (e.g., "Hebbian",
   "reinforce", "decay", "spread") and boost results from files whose source
   code contains those identifiers. This bridges the vocabulary gap between
   natural language queries and code tokens.

3. **No synapse-seeded expansion** — Before vector search, check if any
   query term matches a known synapse node. If so, spread activation through
   the synapse graph to find co-implemented neighbors and include them in
   the candidate set. This surfaces implementation files that vector search
   misses because they share few words with the query.

Pure, stdlib-only, fail-open.

Version:
    3.9.0
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from .synapses import (
    DEFAULT_NAMESPACE,
    SynapseStore,
    _canonical,
)

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# 1. Intent classification fix
# --------------------------------------------------------------------------- #

# Words that indicate an implementation/how-it-works query
_IMPLEMENTATION_VERBS = frozenset({
    "implement", "perform", "execute", "handle", "process", "work",
    "function", "operate", "behave", "act", "compute", "calculate",
    "achieve", "accomplish", "deploy", "apply", "employ", "use",
    "utilize", "leverage", "harness", "wield", "exercise",
    "instantiate", "actualize", "realize", "manifest", "embody",
    "express", "translate", "convert", "transform", "turn", "change",
    "morph", "evolve", "develop", "grow", "build", "construct",
    "make", "form", "fashion", "shape", "mold",
})

# Common stopwords to ignore
_STOPWORDS = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "may", "might",
    "shall", "can", "to", "of", "in", "for", "on", "with", "at",
    "by", "from", "as", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all",
    "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "because", "but", "and", "or", "if", "while",
    "about", "what", "which", "who", "whom", "whose", "whom", "am",
    "it", "its", "he", "she", "they", "them", "we", "us", "me", "him",
    "her", "my", "your", "show", "tell", "give", "get", "make",
    "take", "come", "go", "see", "know", "think", "say", "look",
    "want", "let", "put", "keep", "turn", "move", "try", "use",
    "work", "call", "ask", "seem", "feel", "leave", "start", "run",
    "part", "long", "great", "small", "large", "high", "low", "old",
    "new", "young", "big", "good", "bad", "well", "also", "back",
    "even", "still", "way", "thing", "man", "woman", "child", "world",
    "life", "hand", "day", "week", "month", "year", "time", "end",
    "point", "home", "water", "room", "mother", "area", "money",
    "story", "fact", "right", "left", "power", "city", "team", "state",
    "place", "case", "side", "head", "house", "service", "friend",
    "father", "line", "tree", "car", "name", "word", "letter", "number",
    "set", "group", "kind", "type", "form", "class", "issue", "side",
    "kind", "head", "house", "service", "friend", "father", "power",
    "hour", "game", "end", "member", "law", "car", "city", "community",
    "name", "president", "team", "minute", "idea", "body", "information",
    "back", "parent", "face", "level", "office", "door", "health",
    "person", "art", "war", "history", "party", "result", "change",
    "morning", "reason", "research", "girl", "guy", "moment", "air",
    "teacher", "force", "education", "does", "perform", "implement",
    "handle", "process", "function", "operate", "behave",
})


def classify_intent(query: str, existing_code_keywords: list[str], existing_doc_keywords: list[str]) -> str:
    """Enhanced intent classification that distinguishes implementation queries.

    Returns 'code', 'docs', or 'hybrid'.
    """
    query_lower = query.lower().strip()

    # Check for "how does X implement/perform/do Y" pattern
    # This pattern strongly signals a code-intent query
    words = query_lower.split()
    for i, word in enumerate(words):
        if word in ("does", "do", "did", "is", "are", "was", "were"):
            # Look ahead for an implementation verb
            remaining = words[i+1:]
            # Check if any implementation verb appears in the next 5 words
            for j, next_word in enumerate(remaining[:5]):
                clean_word = next_word.strip("?,.").lower()
                if clean_word in _IMPLEMENTATION_VERBS:
                    return "code"

    # Check for "how does X work/works" pattern
    if re.search(r'how\s+(?:does\s+)?(?:\w+\s+){1,4}works?', query_lower):
        return "code"
    
    # Check for "show me how X works" pattern
    if re.search(r'show\s+me\s+how\s+(?:\w+\s+){1,4}works?', query_lower):
        return "code"

    # Check for "what is X" or "which X" patterns (docs intent)
    if re.match(r'^(?:what|which|who|whom|whose|where|when|why)\s+(?:is|are|was|were)\s+', query_lower):
        return "docs"

    # Fall back to keyword scoring
    code_score = 0
    doc_score = 0

    for kw in existing_code_keywords:
        if kw in query_lower:
            code_score += 1

    for kw in existing_doc_keywords:
        if kw in query_lower:
            doc_score += 1

    threshold = float(os.environ.get("NEURALMIND_INTENT_THRESHOLD", "0.6"))

    if code_score > doc_score * (1 + threshold):
        return "code"
    if doc_score > code_score * (1 + threshold):
        return "docs"
    return "hybrid"


# --------------------------------------------------------------------------- #
# 2. Code-signal boost
# --------------------------------------------------------------------------- #

# Pattern to extract potential identifiers from a query
_CAMEL_CASE_PATTERN = re.compile(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b')
_SNAKE_CASE_PATTERN = re.compile(r'\b([a-z]+(?:_[a-z]+)+)\b')
_WORD_PATTERN = re.compile(r'\b([a-zA-Z][a-zA-Z]{2,})\b')


def extract_code_identifiers(query: str) -> list[str]:
    """Extract potential code identifiers from a natural language query.

    For example:
        "How does the synapse layer implement Hebbian learning?"
        → ["synapse", "layer", "Hebbian", "learning", "synapse_layer"]
    """
    identifiers = []
    seen = set()

    # First, look for CamelCase identifiers
    for m in _CAMEL_CASE_PATTERN.finditer(query):
        term = m.group(1)
        if term.lower() not in _STOPWORDS and term not in seen:
            identifiers.append(term)
            seen.add(term)

    # Then, look for snake_case identifiers
    for m in _SNAKE_CASE_PATTERN.finditer(query):
        term = m.group(1)
        if term not in _STOPWORDS and term not in seen:
            identifiers.append(term)
            seen.add(term)
            # Also add individual parts
            parts = term.split('_')
            for part in parts:
                if len(part) >= 3 and part not in _STOPWORDS and part not in seen:
                    identifiers.append(part)
                    seen.add(part)

    # Then, extract individual words that could be identifiers
    for m in _WORD_PATTERN.finditer(query):
        word = m.group(1)
        if word.lower() not in _STOPWORDS and word not in seen:
            identifiers.append(word)
            seen.add(word)

    # Also extract compound phrases
    for m in re.finditer(r'\b([a-z]{3,})\s+([a-z]{3,})\b', query, re.IGNORECASE):
        w1, w2 = m.group(1), m.group(2)
        for w in [w1, w2]:
            if w.lower() not in _STOPWORDS and w not in seen:
                identifiers.append(w)
                seen.add(w)

    return identifiers


def compute_code_signal_score(result: dict, identifiers: list[str]) -> float:
    """Compute a boost score for a result based on code-signal identifiers.

    Returns a multiplier (1.0 = no boost, >1.0 = boost).
    Uses additive boost for strong matches to overcome large vector score gaps.
    """
    if not identifiers:
        return 1.0

    meta = result.get("metadata", {})
    source_file = meta.get("source_file", "")
    label = meta.get("label", "")
    document = result.get("document", "")
    file_type = meta.get("file_type", "")

    # Only boost code files
    is_doc = file_type in ("rationale", "document") or source_file.endswith(
        (".md", ".markdown", ".txt", ".rst", ".org")
    )
    if is_doc:
        return 0.3  # Strongly penalize docs for code-signal queries

    # Check how many identifiers appear in the source file name
    file_name = source_file.lower().replace("/", "_").replace(".", "_")
    file_matches = sum(
        1 for ident in identifiers
        if ident.lower() in file_name or file_name in ident.lower()
    )

    # Check how many identifiers appear in the label
    label_lower = label.lower()
    label_matches = sum(
        1 for ident in identifiers
        if ident.lower() in label_lower or label_lower in ident.lower()
    )

    # Check how many identifiers appear in the document content
    doc_lower = document.lower()
    doc_matches = sum(
        1 for ident in identifiers
        if ident.lower() in doc_lower
    )

    # Weight matches: file name > label > document content
    total_score = (file_matches * 3.0) + (label_matches * 2.0) + (doc_matches * 0.5)

    if total_score > 0:
        # Use additive boost for strong matches to overcome vector score gaps
        # Base multiplier 1.0 + additive boost (capped at 10x)
        return min(10.0, 1.0 + total_score * 1.5)

    return 1.0


def apply_code_signal_boost(results: list[dict], identifiers: list[str]) -> list[dict]:
    """Apply code-signal boost to results.

    Mutates results in place. Returns the re-ranked list.
    """
    if not identifiers or not results:
        return results

    for result in results:
        boost = compute_code_signal_score(result, identifiers)
        result["score"] = result.get("score", 0.0) * boost
        if boost > 1.0:
            result["_code_signal_boost"] = boost

    results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
    return results


# --------------------------------------------------------------------------- #
# 3. Synapse-seeded expansion
# --------------------------------------------------------------------------- #

def extract_potential_node_ids(query: str) -> list[str]:
    """Extract potential node IDs from a query.

    For example:
        "How does the synapse layer implement Hebbian learning?"
        → ["synapse", "layer", "Hebbian", "learning"]
    """
    return extract_code_identifiers(query)


def synapse_seeded_expansion(
    store: SynapseStore | None,
    query: str,
    existing_results: list[dict],
    max_expansions: int = 5,
    now: float | None = None,
) -> list[dict]:
    """Expand results using synapse graph spreading.

    For each potential node ID extracted from the query, check if it matches
    a known synapse node. If so, spread activation to find co-implemented
    neighbors and add them to the result set.

    Returns the expanded result list.
    """
    if store is None:
        return existing_results

    ts = now if now is not None else time.time()
    identifiers = extract_potential_node_ids(query)

    if not identifiers:
        return existing_results

    # Find matching synapse nodes
    seed_nodes: list[tuple[str, float]] = []
    try:
        with store._connect() as conn:
            for ident in identifiers:
                # Check if this identifier matches any synapse node
                cur = conn.execute(
                    """SELECT DISTINCT node_a FROM synapses
                       WHERE node_a LIKE ? OR node_b LIKE ?
                       LIMIT 5""",
                    (f"%{ident}%", f"%{ident}%"),
                )
                for row in cur.fetchall():
                    if row[0] not in [s[0] for s in seed_nodes]:
                        seed_nodes.append((row[0], 1.0))

                cur = conn.execute(
                    """SELECT DISTINCT node_b FROM synapses
                       WHERE node_a LIKE ? OR node_b LIKE ?
                       LIMIT 5""",
                    (f"%{ident}%", f"%{ident}%"),
                )
                for row in cur.fetchall():
                    if row[0] not in [s[0] for s in seed_nodes]:
                        seed_nodes.append((row[0], 1.0))

    except Exception:
        log.debug("synapse-seeded expansion query failed", exc_info=True)
        return existing_results

    if not seed_nodes:
        return existing_results

    # Spread activation from matched nodes
    try:
        neighbors = store.spread(seed_nodes, depth=2, top_k=max_expansions * 2)
    except Exception:
        log.debug("synapse-seeded spread failed", exc_info=True)
        return existing_results

    if not neighbors:
        return existing_results

    # Get existing IDs to avoid duplicates
    existing_ids = {r.get("id") for r in existing_results}

    # Add neighbor results (simplified - just add IDs as placeholders)
    new_results = []
    for node_id, energy in neighbors:
        if node_id not in existing_ids and len(new_results) < max_expansions:
            # Get actual node data from embedder if available
            node_data = {
                "id": node_id,
                "score": energy * 0.5,  # Lower base score for expanded results
                "metadata": {
                    "source_file": node_id.split(":")[0] if ":" in node_id else "unknown",
                    "label": node_id,
                    "file_type": "code",
                },
                "document": f"Synapse-expanded from: {query}",
                "_synapse_seeded": True,
                "_synapse_seed_energy": energy,
            }
            
            # Try to get actual document content from embedder
            try:
                embedder = getattr(store, '_embedder', None)
                if embedder is not None:
                    nodes = embedder.get_nodes_by_ids([node_id])
                    if nodes:
                        node_data["document"] = nodes[0].get("document", node_data["document"])
                        node_data["metadata"] = nodes[0].get("metadata", node_data["metadata"])
            except Exception:
                pass
            
            new_results.append(node_data)

    return existing_results + new_results


def dependency_graph_expansion(
    structural_index: Any,
    query: str,
    existing_results: list[dict],
    identifiers: list[str],
    max_expansions: int = 3,
    depth: int = 2,
) -> list[dict]:
    """Expand results using dependency graph traversal.

    For each identifier, find its callers/callees/imports in the structural
    graph and add them to the result set. This surfaces code that is
    structurally related to the query, even if it's not semantically similar.

    Returns the expanded result list.
    """
    if structural_index is None or not identifiers:
        return existing_results

    existing_ids = {r.get("id") for r in existing_results}
    new_results = []

    try:
        for ident in identifiers:
            # Try to find this identifier in the structural graph
            neighbors = structural_index.neighbors(ident)
            if not neighbors:
                continue

            for view, neighbor_ids in neighbors.items():
                for nid in neighbor_ids[:max_expansions]:
                    if nid in existing_ids:
                        continue

                    new_results.append({
                        "id": nid,
                        "score": 0.8,  # High score for structural matches
                        "metadata": {
                            "source_file": nid.split(":")[0] if ":" in nid else "unknown",
                            "label": nid,
                            "file_type": "code",
                        },
                        "document": f"Structural neighbor ({view}) of: {ident}",
                        "_structural_expansion": True,
                        "_structural_relation": view,
                    })
                    existing_ids.add(nid)

                    if len(new_results) >= max_expansions:
                        break

                if len(new_results) >= max_expansions:
                    break

            if len(new_results) >= max_expansions:
                break

    except Exception:
        log.debug("dependency graph expansion failed", exc_info=True)

    return existing_results + new_results


# --------------------------------------------------------------------------- #
# Unified enhancement pipeline
# --------------------------------------------------------------------------- #

def enhance_retrieval(
    store: SynapseStore | None,
    query: str,
    results: list[dict],
    intent: str,
    code_keywords: list[str],
    doc_keywords: list[str],
    embedder: Any = None,
    now: float | None = None,
) -> list[dict]:
    """Apply all three retrieval enhancements.

    Order of operations:
    1. Re-classify intent with enhanced patterns
    2. Apply code-signal boost for code-intent queries
    3. Apply synapse-seeded expansion
    4. Two-pass retrieval: if code-intent, search source files directly
    5. Re-apply intent boost with corrected intent
    """
    if not results:
        return results

    # 1. Re-classify intent
    corrected_intent = classify_intent(query, code_keywords, doc_keywords)

    # 2. Extract code identifiers
    identifiers = extract_code_identifiers(query)

    # 3. Apply code-signal boost for code-intent queries
    if corrected_intent == "code" and identifiers:
        results = apply_code_signal_boost(results, identifiers)

    # 4. Apply synapse-seeded expansion
    if store is not None and identifiers:
        results = synapse_seeded_expansion(store, query, results, now=now)

    # 5. Two-pass retrieval: for code-intent queries, search source files directly
    if corrected_intent == "code" and identifiers and embedder is not None:
        try:
            from .retrieval_enhancement import _search_source_files, _extract_code_snippet
            source_results = _search_source_files(embedder, identifiers, top_k=5)
            if source_results:
                # For source file matches, extract code snippets
                for sr in source_results:
                    snippet = _extract_code_snippet(embedder, sr.get("id", ""), identifiers)
                    if snippet:
                        sr["document"] = snippet  # Replace generic document with code snippet

                # Merge source file results, avoiding duplicates
                existing_ids = {r.get("id") for r in results}
                for sr in source_results:
                    if sr.get("id") not in existing_ids:
                        results.append(sr)
                        existing_ids.add(sr.get("id"))
        except Exception:
            pass  # Fail open

    # 6. Dependency graph expansion: traverse callers/callees/imports
    if corrected_intent == "code" and identifiers:
        try:
            from .retrieval_enhancement import dependency_graph_expansion
            structural_index = getattr(store, '_structural_index', None)
            if structural_index is None:
                # Try to get from embedder
                structural_index = getattr(embedder, '_structural_index', None)
            if structural_index is not None:
                results = dependency_graph_expansion(
                    structural_index, query, results, identifiers, max_expansions=3
                )
        except Exception:
            pass  # Fail open

    # 7. Apply intent boost with corrected intent
    if corrected_intent != "hybrid":
        results = _apply_intent_boost_with_intent(results, corrected_intent)

    return results


def _search_source_files(embedder: Any, identifiers: list[str], top_k: int = 5) -> list[dict]:
    """Search source files directly for code identifiers.

    This is the second pass of two-pass retrieval. Instead of relying on
    vector search (which favors docstrings), we search the actual source
    file content for identifiers extracted from the query.
    """
    if not identifiers or embedder is None:
        return []

    results = []
    seen_ids = set()

    try:
        # Get all nodes from the embedder
        all_nodes = getattr(embedder, 'get_all_nodes', lambda: [])()
        if not all_nodes:
            return []

        for node in all_nodes:
            node_id = node.get("id", "")
            if node_id in seen_ids:
                continue

            metadata = node.get("metadata", {})
            source_file = metadata.get("source_file", "")
            file_type = metadata.get("file_type", "")

            # Skip doc files
            is_doc = file_type in ("rationale", "document") or source_file.endswith(
                (".md", ".markdown", ".txt", ".rst", ".org")
            )
            if is_doc:
                continue

            # Check if any identifier appears in the source file, node ID, or label
            file_lower = source_file.lower().replace("/", "_").replace(".", "_")
            id_lower = node_id.lower()
            label = metadata.get("label", "").lower()
            document = node.get("document", "").lower()

            # Skip marketing/site nodes for implementation queries
            is_site = ("site_src" in id_lower or "site/" in source_file.lower() or 
                      "publications" in id_lower)
            
            # Priorize implementation nodes (neuralmind/ prefix)
            is_impl = "neuralmind_" in id_lower or "neuralmind/" in source_file.lower()

            score = 0.0
            for ident in identifiers:
                ident_lower = ident.lower()
                # File name match (strongest signal)
                if ident_lower in file_lower:
                    score += 3.0
                # Node ID match (strong signal - contains function/class names)
                if ident_lower in id_lower:
                    score += 2.5
                # Label match
                if ident_lower in label:
                    score += 2.0
                # Document content match
                if ident_lower in document:
                    score += 0.5

            if score > 0:
                # Penalize site nodes, boost implementation nodes
                if is_site:
                    score *= 0.2  # Heavy penalty for marketing pages
                elif is_impl:
                    score *= 1.5  # Boost for implementation files
                
                # Additional boost for function definitions (not just constants)
                if '__fn' in id_lower or '__cls' in id_lower:
                    score *= 1.3
                
                node["score"] = min(2.0, score * 0.3)  # Cap at 2.0
                node["_source_file_match"] = True
                results.append(node)
                seen_ids.add(node_id)

        # Sort by score and return top_k
        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        return results[:top_k]

    except Exception:
        return []


def _extract_code_snippet(embedder: Any, node_id: str, identifiers: list[str], max_lines: int = 20) -> str:
    """Extract a code snippet from a source file, centered on the best-matching identifier.

    This replaces the generic document snippet with actual source code read from disk.
    """
    if embedder is None or not node_id:
        return ""

    import os

    try:
        nodes = embedder.get_nodes_by_ids([node_id])
        if not nodes:
            return ""

        node = nodes[0]
        metadata = node.get("metadata", {})
        source_file = metadata.get("source_file", "")
        document = node.get("document", "")
        
        # Extract line number from document (format: "Location: L561")
        line_num = None
        for line in document.split('\n'):
            if 'Location: L' in line:
                try:
                    # Extract number after 'L'
                    parts = line.split('Location: L')
                    if len(parts) > 1:
                        line_num = int(parts[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
                break
        
        if not source_file or not line_num:
            return document  # Fall back to original document

        # Read the actual source file from disk
        # Try relative to project path first, then absolute
        project_path = getattr(embedder, 'project_path', None)
        if project_path:
            file_path = os.path.join(str(project_path), source_file)
            if not os.path.exists(file_path):
                file_path = source_file  # Try as absolute
        else:
            file_path = source_file

        if not os.path.exists(file_path):
            return document  # Fall back

        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        # Center the snippet on the line number
        start = max(0, line_num - 1 - max_lines // 2)
        end = min(len(lines), start + max_lines)
        snippet_lines = lines[start:end]

        # Add line numbers
        line_num_start = start + 1
        numbered = [f"{line_num_start + i}: {line.rstrip()}" for i, line in enumerate(snippet_lines)]

        if start > 0:
            numbered.insert(0, "...")
        if end < len(lines):
            numbered.append("...")

        return '\n'.join(numbered)

    except Exception:
        return ""


def _apply_intent_boost_with_intent(results: list[dict], intent: str) -> list[dict]:
    """Apply type-aware boost based on query intent (standalone version)."""
    if intent == "hybrid":
        return results

    code_boost = float(os.environ.get("NEURALMIND_CODE_BOOST", "3.0"))
    doc_boost = float(os.environ.get("NEURALMIND_DOC_BOOST", "2.0"))

    for result in results:
        meta = result.get("metadata", {})
        file_type = meta.get("file_type", "")
        source_file = meta.get("source_file", "")

        is_doc = file_type in ("rationale", "document") or source_file.endswith(
            (".md", ".markdown", ".txt", ".rst", ".org")
        )
        is_code = not is_doc and (file_type == "code" or bool(source_file))

        if intent == "code":
            if is_code:
                result["score"] = result.get("score", 0) * code_boost
                result["_intent_boost"] = code_boost
            else:
                result["score"] = result.get("score", 0) * 0.5
                result["_intent_boost"] = 0.5
        elif intent == "docs":
            if is_doc:
                result["score"] = result.get("score", 0) * doc_boost
                result["_intent_boost"] = doc_boost
            else:
                result["score"] = result.get("score", 0) * 0.7
                result["_intent_boost"] = 0.7

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results
