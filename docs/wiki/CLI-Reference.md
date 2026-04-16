# CLI Reference

Complete command-line interface documentation for NeuralMind.

## Table of Contents

- [Overview](#overview)
- [Global Options](#global-options)
- [Commands](#commands)
  - [build](#build)
  - [query](#query)
  - [wakeup](#wakeup)
  - [search](#search)
  - [benchmark](#benchmark)
  - [stats](#stats)
- [Exit Codes](#exit-codes)
- [Environment Variables](#environment-variables)
- [Examples](#examples)

---

## Overview

NeuralMind provides a command-line interface for building neural indexes, querying codebases with natural language, and managing knowledge graphs.

```bash
neuralmind [OPTIONS] COMMAND [ARGS]
```

### Getting Help

```bash
# General help
neuralmind --help

# Command-specific help
neuralmind build --help
neuralmind query --help
```

---

## Global Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |
| `--version` | Show version number |

---

## Commands

### build

Build or rebuild the neural index from a knowledge graph.

```bash
neuralmind build <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root containing `graphify-out/graph.json` |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--force` | False | Force re-embedding of all nodes, even if unchanged |
| `--db-path` | Auto | Custom path for ChromaDB storage |

#### Output

Displays build statistics including:
- Number of nodes processed
- Number of nodes embedded (new/changed)
- Number of nodes skipped (unchanged)
- Number of communities indexed
- Build time elapsed

#### Examples

```bash
# Basic build
neuralmind build /path/to/project

# Force complete rebuild
neuralmind build /path/to/project --force

# Custom database location
neuralmind build /path/to/project --db-path /custom/path/db
```

#### Prerequisites

Before running `build`, ensure:
1. Graphify has been run on the project: `graphify update /path/to/project`
2. The file `graphify-out/graph.json` exists in the project directory

---

### query

Query the codebase with natural language and get optimized context.

```bash
neuralmind query <project_path> "<question>" [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |
| `question` | Yes | Natural language question about the codebase |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | False | Output results as JSON |
| `--verbose` | False | Include detailed layer breakdown |

#### Output

Returns:
- Optimized context text for AI consumption
- Token count and breakdown by layer
- Reduction ratio compared to full codebase
- Communities/modules loaded

#### Examples

```bash
# Basic query
neuralmind query /path/to/project "How does authentication work?"

# Query with JSON output
neuralmind query /path/to/project "What are the main API endpoints?" --json

# Verbose output with layer details
neuralmind query /path/to/project "Explain the database models" --verbose
```

#### Sample Output

```
=== Query: How does authentication work? ===

[Context]
# Project: MyApp
MyApp is a web application with JWT-based authentication...

[Authentication Module]
The auth module handles user login, token generation, and validation...

[Relevant Code]
- auth/jwt_handler.py: JWT token generation and validation
- auth/middleware.py: Authentication middleware for routes
- models/user.py: User model with password hashing

---
Tokens: 847 | Reduction: 59.0x | Layers: L0, L1, L2, L3 | Communities: [5, 12]
```

---

### wakeup

Get minimal wake-up context for starting a new conversation.

```bash
neuralmind wakeup <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | False | Output results as JSON |
| `--export` | None | Export context to file path |

#### Output

Returns L0 (Identity) + L1 (Summary) context, typically ~600 tokens, suitable for:
- Starting new AI conversations
- Providing project context to coding assistants
- Initial system prompts

#### Examples

```bash
# Get wake-up context
neuralmind wakeup /path/to/project

# Export to file
neuralmind wakeup /path/to/project --export context.md

# JSON format
neuralmind wakeup /path/to/project --json
```

#### Sample Output

```
=== Wake-up Context ===

# Project: MyApp

MyApp is a full-stack web application for task management built with React and Node.js.

## Architecture Overview

### Core Components
- **Frontend**: React 18 with TypeScript, Tailwind CSS
- **Backend**: Node.js/Express REST API
- **Database**: PostgreSQL with Prisma ORM
- **Auth**: JWT-based authentication

### Main Modules
1. User Management (users/) - Registration, profiles, settings
2. Task Engine (tasks/) - CRUD operations, scheduling, notifications
3. API Layer (api/) - REST endpoints, middleware, validation

---
Tokens: 412 | Layers: L0, L1
```

---

### search

Perform direct semantic search across codebase entities.

```bash
neuralmind search <project_path> "<query>" [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |
| `query` | Yes | Semantic search query |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--limit` | 10 | Maximum number of results |
| `--type` | All | Filter by node type (function, class, file, etc.) |
| `--community` | All | Filter by community ID |
| `--json` | False | Output results as JSON |

#### Output

Returns matching code entities with:
- Entity name and type
- Similarity score (0-1)
- File path
- Brief description
- Community membership

#### Examples

```bash
# Basic search
neuralmind search /path/to/project "authentication"

# Limited results
neuralmind search /path/to/project "database connection" --limit 5

# Filter by type
neuralmind search /path/to/project "validate" --type function

# Filter by community
neuralmind search /path/to/project "user" --community 5

# JSON output
neuralmind search /path/to/project "API endpoint" --json
```

#### Sample Output

```
=== Search: authentication ===

1. authenticate_user (function) - Score: 0.92
   File: auth/handlers.py
   Validates user credentials and returns JWT token
   Community: 5 (Authentication)

2. AuthMiddleware (class) - Score: 0.87
   File: auth/middleware.py
   Express middleware for JWT validation
   Community: 5 (Authentication)

3. hash_password (function) - Score: 0.81
   File: utils/crypto.py
   Securely hashes passwords using bcrypt
   Community: 5 (Authentication)

---
Results: 3 | Query time: 45ms
```

---

### benchmark

Run performance benchmark with sample queries.

```bash
neuralmind benchmark <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--queries` | Default set | Custom queries (comma-separated) |
| `--json` | False | Output results as JSON |

#### Output

Comprehensive benchmark report including:
- Token counts for each query type
- Reduction ratios
- Query latencies
- Comparison with full codebase size

#### Examples

```bash
# Run default benchmark
neuralmind benchmark /path/to/project

# Custom queries
neuralmind benchmark /path/to/project --queries "How does auth work?,What are the API routes?"

# JSON output
neuralmind benchmark /path/to/project --json
```

#### Sample Output

```
=== NeuralMind Benchmark ===

Project: MyApp
Total Nodes: 241
Communities: 93
Estimated Full Codebase: 50,000 tokens

| Query Type | Tokens | Reduction | Latency |
|------------|--------|-----------|----------|
| Wake-up context | 341 | 146.6x | 45ms |
| How does authentication work? | 739 | 67.7x | 187ms |
| What are the main API endpoints? | 748 | 66.8x | 192ms |
| Explain the database models | 812 | 61.6x | 201ms |
|------------|--------|-----------|----------|
| **Average** | **660** | **85.7x** | **156ms** |

---
Benchmark completed in 625ms
```

---

### stats

Show statistics about the neural index.

```bash
neuralmind stats <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | False | Output as JSON |
| `--verbose` | False | Include detailed breakdowns |

#### Output

Displays:
- Node counts by type
- Community statistics
- Embedding information
- Index storage size
- Last build timestamp

#### Examples

```bash
# Basic stats
neuralmind stats /path/to/project

# Verbose output
neuralmind stats /path/to/project --verbose

# JSON format
neuralmind stats /path/to/project --json
```

#### Sample Output

```
=== NeuralMind Statistics ===

Project: MyApp
Graph Path: /path/to/project/graphify-out/graph.json
DB Path: /path/to/project/graphify-out/neuralmind_db

## Index Summary
- Total Nodes: 241
- Total Edges: 203
- Communities: 93
- Embedding Dimensions: 384

## Node Types
- Functions: 142 (58.9%)
- Classes: 45 (18.7%)
- Files: 38 (15.8%)
- Database Models: 16 (6.6%)

## Storage
- Index Size: 12.4 MB
- Cache Size: 2.1 MB

## Build Info
- Last Build: 2024-01-15 14:30:22
- Build Duration: 8.3s
- Embedding Model: all-MiniLM-L6-v2
```

---

## Exit Codes

| Code | Meaning |
|------|----------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | graph.json not found |
| 4 | Index not built (run `build` first) |
| 5 | Database error |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEURALMIND_DB_PATH` | Auto | Default database path |
| `NEURALMIND_LOG_LEVEL` | INFO | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `CHROMADB_HOST` | None | Remote ChromaDB host (for distributed setups) |
| `CHROMADB_PORT` | None | Remote ChromaDB port |

---

## Examples

### Complete Workflow

```bash
# 1. Generate knowledge graph
graphify update ~/projects/myapp

# 2. Build neural index
neuralmind build ~/projects/myapp

# 3. View statistics
neuralmind stats ~/projects/myapp

# 4. Get wake-up context for new conversation
neuralmind wakeup ~/projects/myapp > context.md

# 5. Query specific functionality
neuralmind query ~/projects/myapp "How does the payment system work?"

# 6. Search for specific entities
neuralmind search ~/projects/myapp "PaymentController" --limit 5

# 7. Run benchmark
neuralmind benchmark ~/projects/myapp
```

### Scripting Integration

```bash
#!/bin/bash
# update_and_query.sh - Update index and run queries

PROJECT="$1"
QUERY="$2"

# Rebuild if graph changed
if [ graphify-out/graph.json -nt graphify-out/neuralmind_db ]; then
    echo "Graph updated, rebuilding index..."
    neuralmind build "$PROJECT"
fi

# Run query
neuralmind query "$PROJECT" "$QUERY" --json
```

### Piping to AI Tools

```bash
# Get context and pipe to clipboard (macOS)
neuralmind wakeup ~/projects/myapp | pbcopy

# Get context and pipe to clipboard (Linux)
neuralmind wakeup ~/projects/myapp | xclip -selection clipboard

# Save context to file for AI assistant
neuralmind query ~/projects/myapp "Explain the auth system" > auth_context.md
```

---

## See Also

- [API Reference](API-Reference.md) - Python API documentation
- [Architecture](Architecture.md) - System design details
- [Integration Guide](Integration-Guide.md) - MCP and tool integrations
