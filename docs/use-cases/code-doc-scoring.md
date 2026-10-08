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

## Tests and examples are not the code *(v4.11.0+)*

Index a repository from its root and two more kinds of node compete for the
four results: tests and example scripts. Both are code, so the table above
used to give them the code's ×3.0, and a test, which repeats the names of the
code it tests, also got the identifier boost (up to ×10). On
[Click](https://github.com/pallets/click), "which files in this repo handle
parsing command-line options?" came back as an example script, a test and a
doc heading, and `core.py` never made the four.

v4.11.0 scores the project's own code, its tests and examples, and its docs
separately (by layout: `tests/`, `examples/`, `test_*.py`, `*_test.go`,
`*.test.ts` and the like):

| Intent | The project's code | Tests and examples | Docs |
|--------|---------------------|--------------------|------|
| `code` | × 3.0 (docstrings × 0.5) | × 0.5, then × ⅓ | × 0.5, then × ⅓ |
| `docs` | × 0.7 (docstrings × 2.0) | × 0.7, then × ⅓ | × 2.0 |
| `hybrid` | × 1.0 | × ⅓ | × 1.0 |

The ⅓ for tests and examples drops when the question names them ("how do I
test …", "an example of …"). And before any of that is applied, the project's
code is owed two of the four results (one for a `docs` question) when the
search found it at ranks 5–10: the weakest test, example or doc results give
their slots to it. The project's own code is scored exactly as before, so a
repository with no tests, examples or docs in its index ranks as it always did.
`NEURALMIND_L3_ROLES=0` turns this off. Measured in the
[v4.11.0 release notes](../releases/RELEASE_NOTES_v4.11.0.md#measured-roles-on-vs-off).

```bash
neuralmind query . "which files handle parsing command-line options?" --trace
# →   [L3/roles] 2 slot(s) from tests/examples/docs to the project's code
```

## Results

- Code-framed queries: >80% code nodes in top-4 results
- Doc-framed queries: >60% doc nodes in top-4 results
- Hybrid queries: balanced results from both types
