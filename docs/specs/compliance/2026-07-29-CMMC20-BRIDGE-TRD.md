# CMMC 2.0 Query Routing Bridge — NeuralMind ↔ Local LLM Integration
## Technical Requirements Document (TRD)

**Date:** 2026-07-29
**Module:** `neuralmind/cmmc20_bridge.py`
**Parent spec:** `docs/specs/compliance/2026-07-29-CMMC20-BRIDGE-BRD.md`
**Status:** Draft
**Commit:** pending

---

## 1. Scope

Add a query routing bridge (`cmmc20_bridge.py`) that connects NeuralMind's code graph to a local Ollama LLM (qwen2.5:3b) for CMMC 2.0 compliance Q&A, with cloud fallback (DeepSeek V4 Pro) for complex queries.

### In Scope

- `CMMC20Bridge` class with `retrieve()`, `route()`, `analyze()`, `export_gap()` methods
- NeuralMind graph integration: `embedder.search()`, `compliance_matcher.find_compliance_annotations()`, CMMC content node retrieval
- Local LLM integration: Ollama API calls with context window management (32K tokens)
- Cloud routing: DeepSeek V4 Pro fallback for multi-practice or multi-codebase queries
- 5 prompt templates: practice lookup, code-compliance gap, compliance checklist, evidence generation, POA&M
- Config-driven routing: `NEURALMIND_CMMC_ROUTER = "local" | "cloud" | "hybrid"` (default: hybrid)
- Evidence export: feeds into NeuralMind's existing `export.py` pipeline (CSV gap report)
- CLI command: `neuralmind cmmc query "..."` and `neuralmind cmmc gap --practice AC.L2-3.1.1`

### Out of Scope

- Fine-tuned model training (see BRD §5.2)
- Real-time file watcher integration
- API server / auth layer
- Jira/ServiceNow connectors
- Multi-framework (SOX, NIST, HIPAA) routing — single-framework CMMC only in v1

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        CMMC20 BRIDGE ARCHITECTURE                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────┐     ┌─────────────────────────────────────┐             │
│  │ User Query │────▶│         CMMC20Bridge                │             │
│  └────────────┘     │                                     │             │
│                     │  ┌─────────┐  ┌───────┐  ┌───────┐  │             │
│                     │  │retrieve │─▶│ route │─▶│analyze│  │             │
│                     │  └────┬────┘  └───┬───┘  └───┬───┘  │             │
│                     │       │           │           │      │             │
│                     └───────┼───────────┼───────────┼──────┘             │
│                             │           │           │                    │
│  ┌──────────────────────────┼───────────┼───────────┼──────────────┐    │
│  │  NeuralMind (existing)   │           │           │              │    │
│  │                          ▼           │           │              │    │
│  │  ┌────────────────┐  ┌─────────┐    │           │              │    │
│  │  │ embedder.search│  │compliance│    │           │              │    │
│  │  │ (code nodes)   │  │_matcher │    │           │              │    │
│  │  └────────────────┘  └─────────┘    │           │              │    │
│  │  ┌──────────────────────────────────┘           │              │    │
│  │  │ CMMC content nodes (from ingest-cmmc)        │              │    │
│  │  └──────────────────────────────────────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│                                ┌───┐───┐                                │
│                                │ ROUTE  │                                │
│                                └───┬────┘                                │
│                          ┌──────────┴──────────┐                       │
│                          ▼                      ▼                       │
│  ┌─────────────────────────┐    ┌──────────────────────────┐            │
│  │  LOCAL (Ollama)         │    │  CLOUD (DeepSeek V4 Pro) │            │
│  │  qwen2.5:3b-instruct   │    │  api.deepseek.com/v1     │            │
│  │  localhost:11434        │    │  API key from config     │            │
│  │  ~3B params             │    │  ~236B params (MoE)      │            │
│  │  Context: 32K tokens    │    │  Context: 128K tokens    │            │
│  │  Latency: ~2-8s/token   │    │  Latency: ~0.5-3s/req   │            │
│  │  Cost: $0               │    │  Cost: ~$0.03/query      │            │
│  └─────────────────────────┘    └──────────────────────────┘            │
│                                       │                                │
│  ┌────────────────────────────────────┘                                │
│  ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  export_gap() → CSV evidence report (feeds export.py)        │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Data Flow

```
1. Parse user query → extract practice IDs + domain hints + file refs
2. NeuralMind.embedder.search(query, n=10) → relevant code nodes
3. compliance_matcher.find_compliance_annotations() on retrieved code
4. Query CMMC content nodes for matching practice details (by node_id "cmc:PRACTICE_ID")
5. Route decision based on query complexity (single vs multi practice, single vs multi file)
6. Build structured prompt from retrieved context
7. Call LLM (local or cloud depending on route)
8. Parse LLM response → structured answer + evidence references
9. Optionally feed into export pipeline
```

---

## 3. Module: `cmmc20_bridge.py`

### 3.1 Class: `CMMC20Bridge`

```python
class CMMC20Bridge:
    """Query routing bridge between NeuralMind and local/cloud LLM for CMMC Q&A."""

    def __init__(
        self,
        mind: NeuralMind,
        *,
        router: str = "hybrid",       # "local" | "cloud" | "hybrid"
        local_model: str = "qwen2.5:3b-instruct-q4_K_M",
        local_endpoint: str = "http://localhost:11434/api/generate",
        cloud_model: str = "deepseek-chat",
        cloud_endpoint: str = "https://api.deepseek.com/v1/chat/completions",
        cloud_api_key: str | None = None,
        max_local_tokens: int = 8192,  # max generate tokens locally
        context_window: int = 8192,    # max prompt tokens before truncation
    ):
        ...
```

### 3.2 Method: `retrieve()`

```python
def retrieve(
    self,
    query: str,
    *,
    n_code_nodes: int = 10,
) -> dict:
    """Retrieve relevant context from NeuralMind for the given query.

    Returns:
        {
            "code_nodes": [...],          # embedder.search() results
            "compliance_annotations": [...],  # annotations found in retrieved code
            "cmmc_practices": [...],      # matching CMMC content nodes
            "query_parse": {
                "practice_ids": [...],    # extracted from query or empty
                "domains": [...],
                "file_refs": [...],
                "complexity": "single_practice" | "multi_practice" | "cross_domain"
            }
        }
    """
```

**Implementation notes:**
- Calls `self.mind.embedder.search(query, n=n_code_nodes)` for code nodes
- Calls `compliance_matcher.find_compliance_annotations()` on each retrieved code node's source
- Queries the embedder for CMMC content nodes by matching extracted practice IDs against content node metadata
- Parses the query for known CMMC practice IDs (regex: `([A-Z]{2,3}\.L[12]-\d+(?:\.\d+)+)`)
- Parses for known domains: `AC`, `IA`, `SC`, `CA`, `PE`, `AT`, `AU`, `IR`, `MA`, `MP`, `PS`, `RA`, `SA`, `SI`

### 3.3 Method: `route()`

```python
def route(
    self,
    retrieve_result: dict,
) -> dict:
    """Decide where to send the query based on complexity analysis.

    Returns:
        {
            "target": "local" | "cloud",
            "rationale": str,
            "estimated_tokens": int,
            "prompt_builder": Callable,  # function reference to build the right prompt
        }
    """
```

**Decision logic:**
```
def _classify_complexity(retrieve_result):
    practice_ids = retrieve_result["query_parse"]["practice_ids"]
    code_nodes = retrieve_result["code_nodes"]
    file_refs = retrieve_result["query_parse"]["file_refs"]

    # LOCAL conditions:
    # - 0-1 practice IDs referenced
    # - <=5 code nodes returned
    # - <=3 unique files
    # - No cross-domain request
    # - Estimated prompt tokens <= 6000 (leaves 2000+ tokens for generation)

    # CLOUD conditions:
    # - 2+ practice IDs referenced
    # - 5+ code nodes returned
    # - 3+ unique files
    # - Cross-domain (e.g. "AC + IA" or "all practices")
    # - Estimated prompt tokens > 6000
    # - POA&M or evidence checklist generation requested
```

### 3.4 Method: `analyze()`

```python
def analyze(
    self,
    query: str,
    *,
    prompt_template: str = "code_gap",
    export_results: bool = False,
) -> dict:
    """Full pipeline: retrieve → route → generate → return structured answer.

    Returns:
        {
            "query": str,
            "practice_ids": [...],
            "code_nodes_used": [...],
            "route": "local" | "cloud",
            "answer": str,
            "source_ids": [...],          # practice IDs cited
            "confidence": "high" | "medium" | "low",
            "has_gaps": bool,
            "gap_details": [...],         # list of {practice_id, code_node, gap_description}
            "latency_ms": int,
            "token_count": int,
            "export_path": str | None,
        }
    """
```

**Implementation:**
```python
def analyze(self, query, *, prompt_template="code_gap", export_results=False):
    t0 = time.time()

    # Step 1: Retrieve
    context = self.retrieve(query)

    # Step 2: Route
    route_result = self.route(context)

    # Step 3: Build prompt
    prompt = self._build_prompt(
        prompt_template,
        context=context,
        query=query,
    )

    # Step 4: Call LLM
    if route_result["target"] == "local":
        answer = self._call_local_llm(prompt)
    else:
        answer = self._call_cloud_llm(prompt)

    # Step 5: Parse and structure
    result = self._parse_answer(answer, context)
    result["latency_ms"] = int((time.time() - t0) * 1000)

    # Step 6: Optional export
    if export_results:
        result["export_path"] = self.export_gap(result)

    return result
```

### 3.5 Method: `export_gap()`

```python
def export_gap(
    self,
    analysis_result: dict,
    *,
    output_path: str | None = None,
) -> str:
    """Export gap analysis results as CSV evidence report.

    Feeds into NeuralMind's existing export.py pipeline. Returns the path
    to the generated CSV file.

    The CSV schema extends the existing export format:
        practice_id, code_node_id, source_file, gap_description,
        confidence, query_timestamp
    """
```

**Implementation notes:**
- Calls into `neuralmind.export.export_csv(mind, path, controls=True)` for the base compliance mapping
- Appends a new section with LLM-generated gap descriptions
- Uses the same `compliance_synapse_key()` convention for cross-referencing

---

## 4. NeuralMind Integration

### 4.1 Graph Queries Used

| Integration Point | How the Bridge Calls It | Purpose |
|------------------|------------------------|---------|
| `mind.embedder.search(query, n=10)` | Direct method call | Finds code nodes relevant to the query |
| `mind.embedder.get_nodes_by_ids(node_ids)` | Direct method call | Fetches full node details for selected results |
| `compliance_matcher.find_compliance_annotations(text)` | Import + call | Detects CMMC annotations in code snippets |
| `mind.embedder.collection.get(ids=[...])` | Direct collection access | Retrieves CMMC practice content nodes by ID |
| `compliance_matcher.compliance_synapse_key(...)` | Import + call | Maps code nodes to compliance controls |
| `export.export_csv(mind, path, controls=True)` | Import + call | Feeds gap results into existing export pipeline |

### 4.2 Graph Assumptions

The bridge assumes NeuralMind has been built and CMMC practices ingested:

```python
mind = NeuralMind(project_path)
mind.build()                           # index code graph
mind.ingest_cmmc(registry_path)        # load 110 practices as content nodes
```

The bridge will raise `CMMCBridgeError` with an actionable message if the graph is not built or practices are not ingested.

---

## 5. Local LLM Integration

### 5.1 Ollama API

```python
def _call_local_llm(self, prompt: str) -> str:
    """Call Ollama API for local inference. Handles context window management."""
    resp = requests.post(
        self.local_endpoint,
        json={
            "model": self.local_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_ctx": self.context_window,
                "num_predict": self.max_local_tokens,
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")
```

### 5.2 Context Window Management

The qwen2.5:3b model has a 32K context window, but we target `context_window=8192` (default) for latency predictability:

```python
def _truncate_prompt(self, prompt: str, max_tokens: int = 8000) -> str:
    """Truncate prompt to fit within the target context window.

    Truncation strategy:
    1. Estimate tokens (~4 chars/token for English + code)
    2. If over limit, truncate code snippets first (oldest/lowest score), then practice details
    3. Never truncate the query itself or the instruction section
    4. Append a truncation warning: "[... code context truncated ...]"
    """
```

### 5.3 Error Handling

```python
class OllamaConnectionError(CMMCBridgeError):
    """Raised when the local Ollama instance is unreachable.

    Message: 'Ollama not running at http://localhost:11434. Start with: ollama serve'
    """

class OllamaModelNotFound(CMMCBridgeError):
    """Raised when the model is not available in Ollama.

    Message: 'Model qwen2.5:3b-instruct-q4_K_M not found. Pull with: ollama pull qwen2.5:3b-instruct-q4_K_M'
    """
```

On local LLM failure, the bridge **falls back to cloud** automatically when `router="hybrid"`.

---

## 6. Cloud Routing (DeepSeek V4 Pro)

### 6.1 API Integration

```python
def _call_cloud_llm(self, prompt: str) -> str:
    """Call DeepSeek V4 Pro API for complex queries."""
    resp = requests.post(
        self.cloud_endpoint,
        headers={
            "Authorization": f"Bearer {self.cloud_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": self.cloud_model,
            "messages": [
                {"role": "system", "content": CMMC_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
```

### 6.2 Cloud-Only Features

When routed to cloud, the bridge unlocks:
- **Multi-practice synthesis**: Compare 5+ practices across 10+ code files
- **POA&M generation**: Structured remediation plan with priority scoring
- **Cross-domain analysis**: "How do AC, IA, and SC practices interact in our auth code?"
- **Report-quality output**: Longer, structured markdown suitable for assessor review

---

## 7. Prompt Templates

### 7.1 CMMC System Prompt

```python
CMMC_SYSTEM_PROMPT = """You are a CMMC 2.0 compliance assessment assistant. You analyze code against CMMC Level 2 practices.

Rules:
1. Use ONLY the practice context and code context provided below.
2. Reference specific practice IDs (e.g., AC.L2-3.1.1) in every answer.
3. Cite specific code files and line references where available.
4. Distinguish between "satisfied", "partially satisfied", and "not satisfied".
5. If there is insufficient information, say so — do not guess.
6. Be concise for local queries, comprehensive for cloud queries.
"""
```

### 7.2 Template: Practice Lookup (BRIEF)

**Used when:** User asks "What is AC.L2-3.1.1?"

```
{CMMC_SYSTEM_PROMPT}

## CMMC Practice Context
{practice_text}

## Question
{query}

## Answer
Provide the practice ID, title, description, and implementation guidance in 3-5 sentences.
```

### 7.3 Template: Code-Compliance Gap (STANDARD)

**Used when:** User asks "Does auth.py meet AC.L2-3.1.1?"

```
{CMMC_SYSTEM_PROMPT}

## CMMC Practice Context
{practice_text}

## Code Context
{code_snippets}

## Compliance Annotations Found in Code
{annotations}

## Question
{query}

## Analysis
1. Does the code address the practice requirements? (Yes/Partially/No)
2. What specific code elements support or violate the practice?
3. What evidence would an assessor look for?
4. What remediation steps are needed?
```

### 7.4 Template: Compliance Checklist (STANDARD)

**Used when:** User asks "What evidence do we need for AC.L2-3.1.1?"

```
{CMMC_SYSTEM_PROMPT}

## CMMC Practice Context
{practice_text}

## Question
{query}

## Evidence Checklist
Generate a numbered checklist of evidence items an assessor would request for this practice.
For each item, indicate whether the code context supports it (Present / Missing / Partial).
```

### 7.5 Template: Evidence Generation (STANDARD)

**Used when:** User asks "Generate evidence statements for our auth code against AC.L2-3.1.1"

```
{CMMC_SYSTEM_PROMPT}

## CMMC Practice Context
{practice_text}

## Code Context
{code_snippets}

## Compliance Annotations Found in Code
{annotations}

## Question
{query}

## Evidence Statements
Generate specific evidence statements in this format:

| Evidence ID | Practice | Statement | Code Reference | Status |
|------------|----------|-----------|---------------|--------|
```

### 7.6 Template: POA&M Generation (VERBOSE — cloud only)

**Used when:** User requests a plan of actions and milestones

```
{CMMC_SYSTEM_PROMPT}

## CMMC Practice Context
{practice_text}

## Code Context
{code_snippets}

## Question
{query}

## Plan of Actions and Milestones (POA&M)

| # | Practice ID | Gap Description | Code Location | Recommended Action | Priority | Estimated Effort |
|---|------------|----------------|---------------|-------------------|----------|-----------------|

Include:
- Each identified gap with specific file/line references
- A priority score (Critical/High/Medium/Low) based on CMMC assessment weight
- Estimated remediation effort (hours or story points)
- Dependencies between remediation items
```

---

## 8. Configuration

### 8.1 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEURALMIND_CMMC_ROUTER` | `"hybrid"` | Routing mode: `local`, `cloud`, or `hybrid` |
| `NEURALMIND_CMMC_LOCAL_MODEL` | `"qwen2.5:3b-instruct-q4_K_M"` | Ollama model name |
| `NEURALMIND_CMMC_LOCAL_ENDPOINT` | `"http://localhost:11434/api/generate"` | Ollama endpoint |
| `NEURALMIND_CMMC_CLOUD_MODEL` | `"deepseek-chat"` | Cloud model name |
| `NEURALMIND_CMMC_CLOUD_ENDPOINT` | `"https://api.deepseek.com/v1/chat/completions"` | Cloud API endpoint |
| `NEURALMIND_CMMC_CLOUD_API_KEY` | `None` | DeepSeek API key |
| `NEURALMIND_CMMC_CONTEXT_WINDOW` | `8192` | Local LLM context window tokens |
| `NEURALMIND_CMMC_MAX_LOCAL_TOKENS` | `8192` | Max generate tokens for local |
| `NEURALMIND_CMMC_REGISTRY_PATH` | `"/home/dtfrost5/cmmc_practices_registry.json"` | CMMC practice registry |
| `NEURALMIND_CMMC_LOCAL_ONLY_FALLBACK` | `"cloud"` | Fallback target on local failure |

### 8.2 CLI Integration

```python
# In neuralmind/cli.py

# Query command
parser = subparsers.add_parser("cmmc", help="CMMC compliance query and gap analysis")
sub = parser.add_subparsers(dest="cmmc_command")

query_p = sub.add_parser("query", help="Ask a CMMC compliance question")
query_p.add_argument("query", nargs="+", help="Natural language query")
query_p.add_argument("--router", choices=["local", "cloud", "hybrid"], default=None)
query_p.add_argument("--template", choices=["lookup", "code_gap", "checklist", "evidence", "poam"],
                     default="code_gap")

gap_p = sub.add_parser("gap", help="Run gap analysis for a specific practice")
gap_p.add_argument("--practice", required=True, help="CMMC practice ID (e.g. AC.L2-3.1.1)")
gap_p.add_argument("--export", action="store_true", help="Export results as CSV")

# In neuralmind build-in hook: check for CMMC index on `neuralmind build`
```

### 8.3 Config File Extension

Add to NeuralMind's existing `neuralmind.toml` or `.neuralmind/config.toml`:

```toml
[cmmc_bridge]
router = "hybrid"
local_model = "qwen2.5:3b-instruct-q4_K_M"
local_endpoint = "http://localhost:11434/api/generate"
cloud_model = "deepseek-chat"
cloud_endpoint = "https://api.deepseek.com/v1/chat/completions"
# cloud_api_key = ...     # from env var preferred for security
context_window = 8192
max_local_tokens = 8192
```

---

## 9. Prompt Templates Reference

### 9.1 Template Enum

```python
class PromptTemplate(str, enum.Enum):
    PRACTICE_LOOKUP = "lookup"        # Brief: what is this practice
    CODE_GAP = "code_gap"             # Standard: code vs practice analysis
    COMPLIANCE_CHECKLIST = "checklist"  # Standard: evidence items needed
    EVIDENCE_GENERATION = "evidence"  # Standard: generate evidence statements
    POAM = "poam"                     # Verbose: plan of actions and milestones (cloud only)
```

### 9.2 Template Mapping

| Template | Depth | Token Budget | Route Preference | Context Elements |
|----------|-------|-------------|-----------------|-----------------|
| `lookup` | Brief | ~500 gen | local | Practice text only |
| `code_gap` | Standard | ~1500 gen | local | Practice + code + annotations |
| `checklist` | Standard | ~1000 gen | local | Practice text only |
| `evidence` | Standard | ~2000 gen | local | Practice + code + annotations |
| `poam` | Verbose | ~4000 gen | cloud | Practice(s) + code + annotations |

---

## 10. Test Strategy

### 10.1 Unit Tests

```
tests/test_cmmc20_bridge.py
```

| Test | What It Validates |
|------|-----------------|
| `test_retrieve_extracts_practice_ids` | Query parsing extracts `AC.L2-3.1.1` from natural language |
| `test_retrieve_calls_embedder_search` | `retrieve()` delegates to `mind.embedder.search()` |
| `test_retrieve_calls_compliance_matcher` | Annotations are scanned from retrieved code nodes |
| `test_route_single_practice_is_local` | 0-1 practices → local |
| `test_route_multi_practice_is_cloud` | 2+ practices → cloud |
| `test_route_poam_is_cloud` | POA&M template → cloud |
| `test_route_prompt_too_large_is_cloud` | >6000 est. tokens → cloud |
| `test_analyze_full_pipeline` | End-to-end with mock LLM |
| `test_export_gap_creates_csv` | `export_gap()` writes CSV to disk |
| `test_context_truncation` | Truncation kicks in at threshold |
| `test_ollama_unreachable_falls_back` | Local failure → cloud fallback |
| `test_ollama_unreachable_local_only_errors` | Local-only mode raises on failure |
| `test_config_from_env_vars` | All env vars read correctly |
| `test_config_from_file` | Config file overrides defaults |
| `test_prompt_builder_lookup_template` | Practice lookup prompt structure |
| `test_prompt_builder_code_gap_template` | Code gap prompt structure |
| `test_prompt_builder_poam_template` | POA&M prompt structure |

### 10.2 Fixture Design

```python
@pytest.fixture
def mock_mind():
    """Provide a mock NeuralMind with seeded code nodes + CMMC content nodes."""
    mind = MagicMock(spec=NeuralMind)

    # Seed code nodes
    code_nodes = [
        {"id": "auth_login", "label": "login_handler", "source_file": "auth/login.py",
         "metadata": {"file_type": "function"}},
        {"id": "auth_mfa", "label": "mfa_verify", "source_file": "auth/mfa.py",
         "metadata": {"file_type": "function"}},
    ]
    mind.embedder.search.return_value = code_nodes

    # Seed CMMC content nodes
    cmmc_nodes = [
        {"id": "cmc:AC.L2-3.1.1", "label": "AC.L2-3.1.1: Authorized Access Control",
         "file_type": "cmmc_practice",
         "content_text": "...", "metadata": {"practice_id": "AC.L2-3.1.1"}},
    ]
    mind.embedder.collection.get.return_value = {"ids": ["cmc:AC.L2-3.1.1"],
                                                  "documents": ["..."],
                                                  "metadatas": [{"practice_id": "AC.L2-3.1.1"}]}

    return mind

@pytest.fixture
def bridge(mock_mind):
    """Provide a CMMC20Bridge configured for testing (local-only, no cloud)."""
    return CMMC20Bridge(mock_mind, router="local")

@pytest.fixture
def bridge_hybrid(mock_mind):
    """Provide a CMMC20Bridge with hybrid routing."""
    return CMMC20Bridge(mock_mind, router="hybrid",
                        cloud_api_key="test-key")
```

### 10.3 Integration Test

```
tests/test_cmmc20_bridge_integration.py
```

| Test | What It Validates |
|------|-----------------|
| `test_integration_real_ollama` | Queries real Ollama (requires: ollama running) |
| `test_integration_real_neuralmind` | Queries a real NeuralMind build on a test project |
| `test_integration_full_pipeline` | Real NeuralMind + real Ollama on sample project with CMMC annotations |

The integration tests are marked `@pytest.mark.skipif(...)` when dependencies (Ollama, NeuralMind graph) are unavailable.

---

## 11. Error Handling & Edge Cases

| Scenario | Behavior | Error Message |
|----------|----------|---------------|
| NeuralMind not built | Raise `CMMCBridgeError` | "NeuralMind graph not built. Run `neuralmind build` first." |
| CMMC practices not ingested | Raise `CMMCBridgeError` | "CMMC practices not found in graph. Run `neuralmind ingest-cmmc` first." |
| No code nodes match query | Return answer with "no relevant code found" | — |
| No practices match query | Fall back to `cmmc_rag_v2.py`-style semantic search | — |
| Local LLM unreachable, hybrid mode | Auto-fallback to cloud | Log warning, route to cloud |
| Local LLM unreachable, local-only mode | Raise `OllamaConnectionError` | "Ollama not running..." |
| Cloud API unreachable, hybrid mode | Return local-only answer if possible, else error | Log warning |
| Context window exceeded | Truncate code snippets (oldest/lowest score first) | Append truncation notice to prompt |
| Empty query | Raise `ValueError` | "Query cannot be empty" |
| Invalid practice ID format | Attempt semantic search via embedder | — |

---

## 12. Performance Budget

| Component | Allocation | Notes |
|-----------|-----------|-------|
| `retrieve()` | <500ms | ChromaDB query + annotation scanning |
| `route()` | <50ms | Hash-map lookup, no I/O |
| Local LLM inference | 2-8s | qwen2.5:3b on 16GB RAM, quantized |
| Cloud LLM inference | 1-3s | DeepSeek API latency |
| `export_gap()` | <200ms | CSV write only |
| `analyze()` total (local) | <10s | P95 target |
| `analyze()` total (cloud) | <15s | P95 target |

Memory: bridge itself adds <50MB overhead. Local LLM model consumes ~2.5GB (q4 quantized 3B).

---

## 13. Future Work

### 13.1 v1.1 — Fine-Tuned Model Integration

```python
# Future: After cmmc-expert-v3 is trained
local_model = "cmmc-expert-v3"  # replace qwen2.5:3b
```

When the local model is fine-tuned:
- Move from zero-shot to few-shot prompting
- Reduce `temperature` to 0.1
- Reduce context window from 8K to 4K (model has practice knowledge embedded)
- Re-evaluate routing thresholds — more queries can stay local

### 13.2 v1.2 — Multi-Framework Support

```python
# Extend to SOX, NIST, HIPAA, ISO 27001
retrieve_result = self.retrieve(query, framework="NIST")
```

All frameworks already supported by `compliance_matcher.py`. The bridge adds framework selection.

### 13.3 v1.3 — Streaming & Server Mode

```python
# FastAPI wrapper for webhook integration
@app.post("/cmmc/analyze")
async def analyze(payload: CMMCQuery):
    return await bridge.analyze_async(payload.query, stream=True)
```

### 13.4 v2.0 — Continuous Gap Monitoring

Cron-driven daily bridge runs:
```python
# cron: 0 6 * * 1
bridge = CMMC20Bridge(mind)
results = bridge.analyze("Check all AC practices against current code")
bridge.export_gap(results, output_path="weekly_gap_report.csv")
```

---

## 14. Dependencies

### 14.1 Runtime Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `neuralmind` | >=2.0 | Code graph, embedder, compliance_matcher, export |
| `requests` | >=2.31 | Ollama + DeepSeek API calls |
| `chromadb` | (via neuralmind) | Embedded vector store for practice content nodes |

### 14.2 Optional Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `ollama` (system) | >=0.1 | Local LLM inference server |

### 14.3 No New External Dependencies

The bridge uses only `requests` (already a transitive dependency of NeuralMind via chromadb) and stdlib. Zero new PyPI packages.

---

## 15. Open Technical Questions

| # | Question | Resolution |
|---|----------|-----------|
| T1 | Should `retrieve()` also query the synapse store for compliance-linked nodes? | **Yes** — call `mind.synapses.connected(compliance_synapse_key(...))` for additional nodes not returned by vector search. |
| T2 | Should the prompt include full code snippets or summarized descriptions? | **Summarized descriptions** for >20-line functions, full snippet for <20 lines. Controlled by `_truncate_prompt()`. |
| T3 | Should the bridge cache LLM responses for identical queries? | **Deferred to v1.1** — caching introduces staleness risk against a live codebase. |
| T4 | What is the actual char-to-token ratio for CMMC practice text + code? | **~3.5 chars/token** for mixed English + Python (empirical — needs benchmarking). |
