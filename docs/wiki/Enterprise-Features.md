# Enterprise Features Guide

Complete guide to NeuralMind's enterprise-ready capabilities for large-scale, regulated deployments.

## Table of Contents

1. [NIST AI RMF Audit Trail](#nist-ai-rmf-audit-trail)
2. [Pluggable Embedding Backends](#pluggable-embedding-backends)
3. [MCP Server Security](#mcp-server-security)
4. [Custom Embedding Models](#custom-embedding-models)
5. [Hybrid Context Strategy](#hybrid-context-strategy)
6. [Compliance & Governance](#compliance--governance)
7. [Deployment Patterns](#deployment-patterns)

---

## NIST AI RMF Audit Trail

### Overview

Every query is logged with complete provenance for NIST AI RMF compliance:
- GOVERN: Who called what, with full transparency
- MAP: What code was retrieved, evidence of decisions
- MEASURE: Token metrics and efficiency gains
- MANAGE: Reproducibility scores, git state snapshots

### Features

**Automatic Logging**
- Audit entries created automatically on every query
- Stored in `.neuralmind/audit/queries.jsonl` (immutable JSONL format)
- No performance impact (logging is non-blocking)

**Evidence Tracking**
- Code entities retrieved with relevance scores
- File paths and line numbers
- Semantic relationships used

**Model Metadata**
- Embedding model version
- Backend used (ChromaDB, PostgreSQL, etc.)
- Vector dimensions and configuration

**Code State Snapshots**
- Git commit SHA (reproducibility)
- Git branch (context)
- Timestamp

**Confidence Metrics**
- Overall confidence (0.0-1.0)
- Evidence quality score
- Deterministic decision flag

### Usage

```bash
# View recent audit entries
neuralmind audit-list .
# Output:
#   Audit entries for my-project:
#   Total: 147
#   1. 2026-04-21T14:30:00Z
#      Query: How does auth work?
#      Evidence: 3 items
#      Reduction: 59.0x

# Generate NIST AI RMF report
neuralmind audit-report . --format json --output
# Generates: .neuralmind/audit/reports/nist_rmf_report_20260421_*.json

# Export for external auditors
neuralmind audit-export . --format markdown
# Generates: .neuralmind/audit/reports/nist_rmf_report_20260421_*.md
```

### Report Structure

**Audit Entry Format**
```json
{
  "audit_id": "550e8400-e29b-41d4-a716-446655440000",
  "query_text": "How does authentication work?",
  "timestamp": "2026-04-21T14:30:00Z",
  "project_path": "/home/user/myproject",
  "user_id": "alice@company.com",
  
  "evidence": [
    {
      "entity_id": "authenticate_user",
      "entity_type": "function",
      "entity_name": "authenticate_user",
      "file_path": "auth/handlers.py",
      "community_id": 5,
      "relevance_score": 0.92,
      "evidence_type": "EXTRACTED",
      "line_number": 42
    }
  ],
  "evidence_count": 3,
  "evidence_type_breakdown": {"EXTRACTED": 3},
  
  "tokens_used": 847,
  "tokens_baseline": 50000,
  "reduction_ratio": 59.0,
  "layer_breakdown": {"L0": 150, "L1": 600, "L2": 97},
  
  "model_metadata": {
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_backend": "chromadb",
    "embedding_dimensions": 384
  },
  
  "code_state": {
    "git_commit": "a1b2c3d4...",
    "git_branch": "main",
    "timestamp": "2026-04-21T14:30:00Z"
  },
  
  "reproducibility_score": 0.95,
  "confidence_metrics": {
    "overall": 0.95,
    "evidence_quality": 0.95,
    "deterministic": 1.0
  }
}
```

---

## Pluggable Embedding Backends

### Overview

Choose your embedding storage backend based on your infrastructure:

| Backend | Best For | Scale | Server | Cost |
|---------|----------|-------|--------|------|
| **ChromaDB** | Development, small teams | Up to 10M vectors | No | Free |
| **PostgreSQL pgvector** | Enterprise, existing DB infrastructure | 100M+ vectors | Yes (your existing DB) | Low |
| **LanceDB** | Offline, edge, air-gapped | Up to 50M vectors | No | Free |

### ChromaDB (Default)

**Configuration**
```toml
[embeddings]
backend = "chromadb"

[backends.chromadb]
db_path = "graphify-out/neuralmind_db/"
```

**When to use:**
- Development and testing
- Small teams with single-machine deployments
- Air-gapped environments with local-only requirements

**Advantages:**
- Zero setup
- Instant startup
- Great for development

### PostgreSQL pgvector

**Configuration**
```toml
[embeddings]
backend = "postgres"

[backends.postgres]
connection_string = "postgresql://user:pass@db.company.com/neuralmind"
table_name = "code_embeddings"
vector_dimensions = 384
```

**When to use:**
- Enterprise deployments with existing PostgreSQL
- Large codebases (100M+ vectors)
- Need for backup/replication
- Regulatory requirements for database consolidation

**Advantages:**
- Scales to 100M+ vectors
- ACID compliance
- Replicates with database backups
- Full SQL querying possible
- No vendor lock-in (pgvector is OSS)

**Setup**
```bash
# Create PostgreSQL database
createdb neuralmind

# Enable pgvector extension (as superuser)
psql -d neuralmind -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Update neuralmind.toml with connection details
```

### LanceDB

**Configuration**
```toml
[embeddings]
backend = "lancedb"

[backends.lancedb]
db_path = ".neuralmind/embeddings.lance"
```

**When to use:**
- Offline deployments
- Air-gapped networks
- Edge/mobile deployments
- Environments without external services

**Advantages:**
- No server required (embedded)
- Blazing fast Rust implementation
- Minimal footprint
- Great for CI/CD and automation

### Switching Backends

Migrate between backends with zero downtime:

```bash
# Check current backend
neuralmind backend-check .
# Output:
#   Backend: GraphEmbedder
#   Status: ✓ Healthy
#   Statistics: total_nodes: 2847, communities: 42

# List available backends
neuralmind backend-list
# Output:
#   Available embedding backends:
#   • chromadb
#   • lancedb
#   • postgres

# Switch backends (automatic re-indexing)
neuralmind backend-switch postgres \
  --connection-string "postgresql://localhost/neuralmind"
# Automatic: re-embeds graph, stores in PostgreSQL, updates config
```

---

## MCP Server Security

### Overview

For teams running NeuralMind as a centralized MCP server:
- Control who can call what (RBAC)
- Prevent abuse (rate limiting)
- Track usage (audit logging)
- Detect anomalies (suspicious patterns)

### Role-Based Access Control

**Roles and Permissions**

| Role | `query` | `wakeup` | `search` | `build` | `stats` |
|------|---------|---------|---------|--------|--------|
| **Viewer** | ✓ | ✓ | ✓ | ✗ | ✓ |
| **Developer** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Admin** | ✓ | ✓ | ✓ | ✓ | ✓ |

**Implementation**
```python
from neuralmind.mcp_security import (
    MCPSecurityMiddleware, Role, RolePermissionMap
)

# Check permissions
print(RolePermissionMap.get_permissions(Role.DEVELOPER))
# Output: {Permission.QUERY_READ, Permission.QUERY_WRITE}

# Wrap tools with role-based security
middleware = MCPSecurityMiddleware(
    project_path=".",
    user_id="alice@company.com",
    role=Role.DEVELOPER
)

secure_query = middleware.wrap_tool("neuralmind_query", tool_query)
```

### Rate Limiting

**Configuration**
```python
from neuralmind.mcp_security import RateLimit

rate_limit = RateLimit(
    calls_per_minute=100,      # Max 100 calls/minute
    calls_per_hour=5000,       # Max 5000 calls/hour
    max_token_budget_per_day=1_000_000  # Max 1M tokens/day
)

middleware = MCPSecurityMiddleware(
    project_path=".",
    user_id="alice@company.com",
    role=Role.DEVELOPER,
    rate_limit_config=rate_limit
)
```

**Behavior**
- Tracks calls per user
- Resets daily at UTC midnight
- Returns `RateLimitError` when exceeded
- Logged to audit trail with reason

### Audit Logging

**MCP Audit Trail**
```bash
# View MCP tool call history
cat .neuralmind/audit/mcp/tool_calls.jsonl | jq '.[] | {timestamp, user_id, tool_name, result_status}'

# Export for SIEM
cat .neuralmind/audit/mcp/tool_calls.jsonl | jq '[.[] | select(.result_status != "success")]'
```

**Audit Entry Format**
```json
{
  "timestamp": "2026-04-21T14:30:00Z",
  "user_id": "alice@company.com",
  "role": "developer",
  "tool_name": "neuralmind_query",
  "project_path": "/shared/myproject",
  "parameters": {
    "question": "How does auth work?"
  },
  "result_tokens": 847,
  "result_status": "success"
}
```

### Anomaly Detection

Detects suspicious patterns:
- Too many calls in short window
- Repeated same tool in succession
- Many consecutive queries without delay

```python
from neuralmind.mcp_security import AnomalyDetector

detector = AnomalyDetector(window_minutes=60)

# Track calls
detector.record_call("alice@company.com", "neuralmind_query")

# Check for anomalies
anomalies = detector.detect_anomalies("alice@company.com")
for anomaly in anomalies:
    print(f"⚠️ {anomaly}")
    # Output: "High call volume: 150 calls in 60 minutes"
```

---

## Custom Embedding Models

### Overview

Use domain-specific or fine-tuned embedding models for better semantic understanding:

**Use cases:**
- Domain-specific code (medical, financial, legal)
- Fine-tuned on your organization's codebase
- Regulatory: use models trained on approved data
- Cost optimization: smaller models for less critical projects

### Available Model Types

**SentenceTransformers (Default)**
```python
from neuralmind.embedding_models import EmbeddingModelFactory

# Default (fast, lightweight)
model = EmbeddingModelFactory.create(
    model_type="sentence-transformers",
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    options={"device": "cpu"}
)

# Better accuracy
model = EmbeddingModelFactory.create(
    model_type="sentence-transformers",
    model_name="sentence-transformers/all-mpnet-base-v2",
    options={"device": "cuda", "batch_size": 64}
)

# Code-specific
model = EmbeddingModelFactory.create(
    model_type="sentence-transformers",
    model_name="sentence-transformers/CodeBERTa",
    options={"device": "cuda"}
)
```

**Ollama (Local-Only)**
```python
model = EmbeddingModelFactory.create(
    model_type="ollama",
    model_name="nomic-embed-text",
    endpoint="http://ollama.company.com:11434"
)
```

**Configuration in TOML**
```toml
[embeddings.model]
type = "sentence-transformers"
name = "sentence-transformers/all-mpnet-base-v2"
dimensions = 768

[embeddings.model.options]
device = "cuda"
batch_size = 64
```

---

## Hybrid Context Strategy

### Overview

Intelligently balance speed, cost, and accuracy:
- **Fast retrieval** (~3s): NeuralMind optimized context
- **Long-context** (~60s): Full codebase
- **Hybrid**: Smart combination based on confidence

### Strategy Selection

```python
from neuralmind.hybrid_context import (
    HybridContextSelector, HybridContextConfig
)

config = HybridContextConfig(
    strategy="hybrid",
    auto_switch_enabled=True,
    auto_switch_threshold=0.75,
    max_retrieval_tokens=1500,
    max_long_context_tokens=50000
)

selector = HybridContextSelector(config)

# Evaluate retrieval quality
metrics = selector.evaluate_retrieval_result(context_result)
print(f"Confidence: {metrics.confidence:.0%}")  # 0-1

# Should we load more context?
if selector.should_augment_context(metrics):
    print("Low confidence - augmenting with more context...")
    context, meta = selector.build_hybrid_context(
        context_result, full_codebase
    )

# Get cost analysis
estimate = selector.estimate_query_cost(847, 50000)
print(f"Savings: {estimate.savings_percent:.0f}%")
```

### Cost Analysis

Show stakeholders the value:

```python
from neuralmind.hybrid_context import estimate_query_cost, print_cost_analysis

# Typical query at GPT-4o pricing (April 2026)
estimate = estimate_query_cost(
    retrieval_tokens=847,
    full_context_tokens=50000,
    input_price_per_mtok=0.003,  # $0.003/1M tokens
    output_tokens=500,
    output_price_per_mtok=0.006   # $0.006/1M tokens
)

print_cost_analysis(estimate)
# Output:
#   ========================================
#   CONTEXT STRATEGY COST ANALYSIS
#   ========================================
#   
#   NeuralMind Retrieval:
#     Cost: $0.000039
#     Time: ~3s
#   
#   Full Long-Context:
#     Cost: $0.000232
#     Time: ~60s
#   
#   Savings with Retrieval: 83%
#   Recommended: retrieval
#   ========================================
```

---

## Compliance & Governance

### Frameworks Supported

NeuralMind is compatible with:
- ✅ **NIST AI RMF**: Native audit trail for all 4 phases
- ✅ **GDPR**: Local processing, no external APIs
- ✅ **HIPAA**: On-premise capable, data under your control
- ✅ **SOC 2 Type II**: Audit trail + security controls
- ✅ **ISO 27001**: Comprehensive security logging
- ✅ **FedRAMP**: Air-gap ready, on-premise deployment

### Audit Trail Structure

```
.neuralmind/
├── audit/
│   ├── queries.jsonl              # Query history (immutable)
│   ├── mcp/
│   │   └── tool_calls.jsonl       # MCP tool calls (if applicable)
│   └── reports/
│       ├── nist_rmf_report_*.json # NIST compliance reports
│       └── nist_rmf_report_*.md   # Auditor-friendly markdown
└── config.toml                    # Configuration (versioned)
```

### For Auditors

**What to provide:**
```bash
# Export complete audit trail
tar czf neuralmind_audit_export.tar.gz .neuralmind/audit/

# Or just reports
neuralmind audit-export . --format json
# Share: .neuralmind/audit/reports/*.json
```

**Report includes:**
- Complete list of queries with metadata
- Evidence of every code retrieval decision
- Model versions and backend information
- Reproducibility proof (git commits)
- Compliance alignment checklist

---

## Deployment Patterns

### Single-Machine (Development)

```bash
# Simple: use defaults
pip install neuralmind graphify
neuralmind build .
neuralmind query . "How does X work?"
```

### Team with Central PostgreSQL

```toml
# neuralmind.toml (committed to git)
[embeddings]
backend = "postgres"

[backends.postgres]
connection_string = "$DB_URL"  # Set via environment variable
table_name = "code_embeddings"
```

```bash
# All developers pull same config
git pull
neuralmind backend-check .  # Verifies connection
neuralmind query . "How does X work?"  # Audit logged automatically
```

### Centralized MCP Server

```python
# server.py
from neuralmind.mcp_server import Server
from neuralmind.mcp_security import MCPSecurityMiddleware, Role

server = Server()
middleware_viewer = MCPSecurityMiddleware(
    project_path="/shared/project",
    user_id="external-ai",
    role=Role.VIEWER
)

# Register tools with security
for tool_name, tool_func in tools.items():
    server.register_tool(
        middleware_viewer.wrap_tool(tool_name, tool_func)
    )

server.run()
```

### Air-Gapped (FedRAMP/Classified)

```toml
[embeddings]
backend = "lancedb"

[embeddings.model]
type = "ollama"
endpoint = "http://local-ollama:11434"
```

```bash
# Pre-build on connected machine
neuralmind build .

# Copy .neuralmind to air-gapped environment
# Everything works offline:
neuralmind query . "..."
neuralmind audit-report . --format json
```

---

## Getting Started

1. **Enable audit trail:**
   ```bash
   neuralmind audit-report . --format json --output
   ```

2. **Choose your backend:**
   ```bash
   neuralmind backend-list
   neuralmind backend-check .
   ```

3. **Configure security (if MCP server):**
   ```python
   from neuralmind.mcp_security import MCPSecurityMiddleware, Role
   ```

4. **Review compliance:**
   - Check `SECURITY.md` for details
   - Export audit reports for your auditors
   - Share with your compliance team

5. **Optimize for your use case:**
   - Adjust embedding model for your domain
   - Configure rate limits for your team
   - Set backend strategy (retrieval vs hybrid)

---

## Support

For questions about enterprise features:
- Review [SECURITY.md](../../SECURITY.md) for detailed policies
- See [Integration Guide](Integration-Guide.md) for developer setup
- Check [Troubleshooting](Troubleshooting.md) for common issues
