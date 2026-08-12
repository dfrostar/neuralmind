# Code/Document Scoring

NeuralMind v3.1.4+ automatically detects query intent and boosts relevant results.

## The Problem

By default, documents (READMEs, changelogs, wikis) dominate search results — even for code-framed queries like "Show me the auth.py implementation." This happens because:

- Document nodes have more text → denser embeddings → higher cosine similarity
- Documents appear in more communities → more paths for spreading activation
- No query intent detection → all nodes scored equally

## The Solution

NeuralMind now auto-detects query intent and applies type-aware boosting:

| Intent | Code Nodes | Doc Nodes |
|--------|------------|-----------|
| `code` | × 3.0 | × 0.5 |
| `docs` | × 0.7 | × 2.0 |
| `auto` (code detected) | × 3.0 | × 0.5 |
| `auto` (docs detected) | × 0.7 | × 2.0 |
| `auto` (hybrid) | × 1.0 | × 1.0 |

## Usage

```bash
# Auto-detect intent (default)
neuralmind query . "implement authentication middleware"

# Explicit code filter
neuralmind query . "Show me the auth.py implementation" --type code

# Explicit docs filter
neuralmind query . "Explain the architecture" --type docs
```

## Configuring Boost Factors

```bash
# Increase code boost (default: 3.0)
NEURALMIND_CODE_BOOST=5.0 neuralmind query . "auth.py" --type code

# Increase doc boost (default: 2.0)
NEURALMIND_DOC_BOOST=4.0 neuralmind query . "architecture" --type docs

# Adjust intent threshold (default: 0.6)
NEURALMIND_INTENT_THRESHOLD=0.8 neuralmind query . "auth"
```

Lower threshold = more sensitive detection. Higher threshold = more queries classified as hybrid.

## How It Works

1. **Keyword matching** — queries containing file paths (`.py`, `.ts`), code keywords (`def`, `class`, `implement`), or function names get code intent
2. **Doc indicators** — queries with `explain`, `what is`, `how does`, `documentation` get docs intent
3. **File path detection** — regex matches like `src/auth/handler.py` strongly signal code intent
4. **Scoring** — code and doc scores are computed, threshold applied for final classification

## Results

- Code-framed queries: >80% code nodes in top-4 results
- Doc-framed queries: >60% doc nodes in top-4 results
- Hybrid queries: balanced results from both types
